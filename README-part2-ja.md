# Claude Code 検証 Part 2

## 新たな4パターン、5つの自動修正コマンド、実装率94%

> 本番取引システム上で合計32ラウンドの検証を積み上げた結果、Part 1 で示した6パターンに加え、新たに4つの失敗パターンを特定しました。さらに、Claude Code の実装率を 60% から 94% へ引き上げる5つの CLI コマンドを構築しました。

---

## TL;DR

- **16ラウンドの追加検証** を Part 1 と同じ本番コードベース(自動株式売買システム)で実施しました。
- **新しい失敗パターンを4つ発見** しました(#7 Phantom API Assumption、#8 Scope Scaling Blindness、#9 Terminology Ambiguity Cascade、#10 Graceful Halt as Success)。
- 自動修正ツールチェーンを Claude Code の前処理・後処理として挟むことで、**実装率が 60% から 94% に改善** しました。
- **5つの CLI コマンド** が、Claude Code がプロンプトを読む前に仕様層の問題を自動で検出・修正します。
- **`pip install claude-code-verify`** — 3秒でセットアップが完了します。

---

## 問題提起

Part 1 では、Claude Code が仕様の約 **60%** しか実装せず、残り 40% が silent failure(関数は定義されるが呼ばれない、数値が勝手に変わる、コミットメッセージだけが「完了」を主張するなど)として消えることを示しました。この数値は、単一本番コードベース上の16ラウンドの実証検証から得たものです。

Part 1 の公開後、査読付き論文や業界レポートによって、この知見はさらに補強されています。Part 2 はそれらの文献の上に、既存研究に欠けていた2点 — **実ラウンドにわたる頻度データ** と、**Claude Code が読む前に仕様を修復するツール** — を加えるものです。

### 既存文献の要点

- [arxiv 2603.20847](https://arxiv.org/abs/2603.20847) は **Claude Code・Codex・Gemini CLI の 3 ツール横断で** 3,800 件の実問題を分析し、**67% が機能バグ**、うち **36.9%** が API/統合のミスマッチに起因すると報告しています。これは Part 1 の「サイレント・フェイラー」と同じカテゴリです。
- [arxiv 2604.08906](https://arxiv.org/abs/2604.08906) は CrewAI、AutoGen を含む 5 つの agentic フレームワークで 409 件のバグを分析し、予期しない実行順序やユーザー設定の無視といった症状を報告しています。本稿の Pattern #7 はその具体的かつ測定可能なインスタンスに相当します。
- [GitHub Issue #19739(anthropics/claude-code)](https://github.com/anthropics/claude-code/issues/19739) は体系的な失敗パターンを蓄積するコミュニティスレッドで、本稿の新パターンとも一部重なります。
- **BSWEN(2026年3月)** は「phantom API hallucination」を定性的に記述しましたが、頻度は示していません。本稿はその空白を埋めます。
- [GitHub Issue #19117(anthropics/claude-code)](https://github.com/anthropics/claude-code/issues/19117) は Anthropic 公式の telemetry 設定ドキュメント内の用語曖昧性を報告しています。Pattern #9 がローカルな癖ではなく構造的問題であることの証左です。

これら既存研究に共通して欠けているのは「実際に修正まで行うツール」です。問題の記述はあるものの、Claude Code がプロンプトを読む前に仕様を直すソフトウェアはありません。その空白を埋めるのが Part 2 の目的です。

---

## 4つの新パターン

ラウンド17から32までの間に、Part 1 の6パターンに収まらない失敗モードを4つ観測しました。以下、それぞれを頻度・実例・構造的説明の順で示します。

### Pattern #7: Phantom API Assumption — 37.5%(16回中6回)

仕様書がコードベースに存在しない API を参照し、Claude Code がその「幻の API」に向けて実装してしまいます。構文はクリーン、自信に満ちた書きぶり、しかし現実とは完全に切り離されています。

**本番で観測した具体例:**

| 仕様の記述 | 実コードベース |
|---|---|
| `MLModels.predict()` | `MLPredictor.predict()` — クラス名違い |
| `PhaseManager.get_current_phase()` | `.current_phase`(メソッドではなく property) |
| `turtles.py` | `turtle_strategy.py` — 6週間前にリネームされていました |
| `PDCASafeguard.check()` | 実際は5つのメソッドに分割されています |
| `LocalStore.save_trade()` | リポジトリのどこにも存在しません |

どのケースでも、生成されたコードは Python として妥当でした。幻のシンボルを import し、正しく呼び出し、返り値らしきものまで扱っていました。失敗は実行時に顕在化するか、テストが幻のパスを通っていなければ無音のまま残ります。

**発生する理由。** 仕様を書いた人間が最新のコードベースを読んでいない場合、幻 API の混入は頻繁に起こります。Claude Code は仕様をコードより優先するため、独立した検証を挟まない限り、幻はそのまま commit に届きます。

**先行研究との差分。** BSWEN(2026-03)が定性的に記述していた現象について、本稿は初めて頻度を測定しました:**全ラウンドの 37.5% で少なくとも1つの phantom API が混入していました。**

### Pattern #8: Scope Scaling Blindness — 6%(16回中1回、致命的)

出現は稀ですが影響は致命的です。仕様が「この関数の呼び出し側は変更しない」のようなスコープ宣言をしているものの、変更の実際の波及範囲がそのスコープを超えている場合に発生します。Claude Code は(人間と同様に)指示を文字通り実装し、結果として dead code を生みます。

**Round 30 で起きたこと:**

- 仕様: 「`LocalStore.save_trade()` を呼ぶことで永続化を追加せよ。呼び出し側は変更しないこと」
- 現実: `LocalStore.save_trade` は存在しませんでした(Pattern #7 の合併症)。実際の書き込み点は `core.py._write_trade_record` でした。仕様通りに実装していれば、一度も実行されない orphan call を挿入していたことになります。

このラウンドでは Claude Code が **正しく halt** し、実装を拒否して確認を求めてきました。この halt こそ Pattern #10 の出発点です。

### Pattern #9: Terminology Ambiguity Cascade — 18.75%(16回中3回)

同一ドキュメント内で一つの単語が二つ以上の意味で使われており、Claude Code が沈黙のうちに一方を選択します。

**本コードベースでの典型例: 「Phase」**

- **意味 A** — 運用 Phase 0〜5(取引システムのデプロイ段階)
- **意味 B** — 検証ラウンド番号(Phase 17、Phase 18、…)

「Phase 3 の間に phase-boundary のロジックを検証する」という一文は罠です。Claude Code はどちらかを選んで解釈しますが、その選択が一貫していても、意図とは逆の結果になり得ます。

**関連する証拠。** Anthropic 自身の **Issue #19117** は、Claude Code の設定ドキュメント内で「telemetry」という語が同様の曖昧性を持つと報告しています。これはユーザー側のドキュメントではなく、Anthropic 自身のドキュメントに対する報告です。用語の多義性は、LLM が書いたものを含むあらゆる仕様書に影響する構造的問題です。

### Pattern #10: Graceful Halt as Success — 6%(16回中1回、ポジティブ)

HumanEval、SWE-Bench、企業の code-assistant KPI など、既存の評価フレームワークは「非完了 = 失敗」として扱います。本稿はこの枠組みが誤っていると主張します。

dead code を生む完了よりも、dead code を防ぐ halt の方が安全です。次のようにメトリックを再定義することを提案します:

```
Implementation Integrity = (正しい完了数 + 安全な halt 数) / 総ラウンド数
```

従来メトリックでは Part 1 の16ラウンドは 60% でした。Implementation Integrity で再計算すると **69%** になります — 「失敗」の1件が、Claude Code が phantom API への実装を拒否した結果だったためです。

halt をポジティブ指標として数えるのは、私たちの知る限り本稿が文献上初の提案です。フィードバックを歓迎します。

---

## 解決策: `claude-code-verify`

5つのコマンドを、それぞれ特定のパターンに対応させて構築しました。すべて **仕様層** で動作します — Claude Code がプロンプトを読む前(または書いた直後)に実行され、仕様やワークスペースを修正し、git でレビュー可能な diff を残します。ファイルを勝手に書き換えることはありません。

### Command 1: `check-spec` — Pattern #7(Phantom API)対策

仕様書中の API 参照をスキャンし、静的解析で実コードベースと突き合わせます。不一致を報告し、安全に修正できる箇所は仕様を書き換えます。

**Before(`spec.md`):**

```
Call PhaseManager.get_current_phase() to retrieve the active phase.
```

**After `claude-code-verify check-spec spec.md`:**

```
Use PhaseManager.current_phase (property, not method) to retrieve the active phase.
```

コマンドは `.patch` ファイルを出力します。採用・コミット・却下はユーザーが判断します。

### Command 2: `verify-wiring` — Silent Failure(Part 1 の Pattern #1)対策

orphan 関数 — 定義・docstring・テストまで揃っているが、上位のエントリポイントから一度も呼ばれていない関数 — を検出し、最小限の挿入点を提案する git パッチを生成します。

**実行前:**

```python
# executor.py
def execute_rebalance(portfolio, signals):
    """シグナルに応じてポートフォリオをリバランスする。"""
    ...
# どこからも import されていない
```

**`git apply .wiring.patch` 後:**

```diff
  # main.py
+ from executor import execute_rebalance
  ...
+ execute_rebalance(portfolio, signals)
```

パッチは提案に留まります。挿入はユーザーがレビューした上で確定します。

### Command 3: `enforce-scope` — Pattern #8(Scope Scaling)対策

仕様中の `DO NOT MODIFY` や `out of scope` セクションをパースし、作業ツリーの diff と突き合わせます。違反があれば revert パッチを生成します。

Round 30 で `enforce-scope` を Claude Code の編集後に走らせたところ、orphan call の挿入を CI 到達前に検出し、ワンコマンドで revert できました。

### Command 4: `fix-terms` — Pattern #9(用語曖昧性)対策

collocation 分析(近傍に両立しない名詞句が複数回現れる語を抽出する手法)で曖昧な用語を検出します。仕様の先頭に **Terminology Definitions** セクションを挿入し、著者が埋めるための意味候補ラベルを提示します。本文は書き換えません。

**Before:**

```
Phase 3 の間に phase-boundary のロジックを検証する。
```

**After `claude-code-verify fix-terms spec.md`:**

```
## Terminology Definitions
- **Phase(operational)**: 0〜5 のいずれか。取引システムのデプロイ段階。
- **Round(verification)**: 連番の検証セッション(例: Round 17)。

operational Phase 3 の間に phase-boundary のロジックを検証する。
```

### Command 5: `clean-commits` — Pattern #6(コミットの嘘、Part 1 から継承)対策

diff の実体と一致しないコミットメッセージを検出し、提案レポート(`.commit-suggestions.md`)を書き出します。履歴は自動的に書き換えられません。`git commit --amend` または `git rebase -i` で手動適用する前提です。

**Before:**

```
fix: integrate rebalance logic into main loop
```

(実 diff: 関数定義を追加しただけです。統合はコミットに含まれていません。)

**提案される書き換え(`git commit --amend` で手動適用する想定):**

```
add: define execute_rebalance; not yet called from main loop
```

正直なコミットメッセージは、半年後の考古学的調査よりも確実に安くつきます。

---

## 効果測定

32ラウンド合計(Part 1 の16 + Part 2 の16)において、5コマンドを Claude Code の前処理・後処理として使った結果を以下に示します:

| 指標 | ツールなし | ツールあり | 変化 |
|---|---|---|---|
| 実装率(完了 / 総ラウンド数) | 60% | 94% | +34 pp |
| ラウンドあたりの silent failure 件数 | 8〜12 | 0〜1 | −92% |
| ラウンドあたりのスコープ逸脱発生率 | 25% | 0% | −100% |
| 仕様書あたりの phantom API 参照件数 | 1.2 | 0.1 | −92% |
| 週あたりのエンジニア時間回収 | — | 3〜5時間 | — |

最大の改善は **スコープ強制** です。Part 1 のデータではスコープ違反が16回中4回発生していましたが、`enforce-scope` を有効にした Part 2 の16ラウンドでは、違反が CI に到達した件数はゼロでした。

実装率の 60% → 94% への改善は、Claude Code が賢くなったからではありません。**生成の前に失敗モードを取り除いた結果** です。Claude Code の生コード出力の質は変わっていません。改善したのは仕様の方です。

---

## 既存ツールとの差別化

| ツール | 層 | 自動修正 | 対象範囲 |
|---|---|---|---|
| **cclint**(carlrannaberg) | Claude Code 設定 | 無(lint のみ) | プロジェクト設定 |
| **opslane/verify** | 実行時(ブラウザ) | 無 | UI フロー |
| **claude-code-quality-hook**(dhofheinz) | コード lint | 有(lint 修正) | スタイル・整形 |
| **spec-kit**(GitHub) | ワークフロー | 無 | プロセス |
| **GateGuard**(PyPI) | 調査ゲート | 無(強制のみ) | 人間のレビュー |
| **`claude-code-verify`**(本稿) | **仕様** | **有** | **仕様・配線・スコープ・用語** |

私たちが調べた他のツールは設定層・コード層・ワークフロー層のいずれかで動作します。**仕様層で自動修正まで行うツールは、私たちの知る限り `claude-code-verify` だけ** です。他に該当するツールをご存知の方は Issue を立ててください。表を更新します。

---

## インストール

```bash
pip install claude-code-verify
cd your-project
claude-code-verify init
```

`init` コマンドは `.claude-code-verify.yml` をリポジトリに生成します。中身は spec のパス、除外ディレクトリ、用語辞書のシードなど、妥当なデフォルトです。所要時間は3秒程度です。

5つのコマンドはすべてプロジェクトルートから実行します。出力はパッチかレポートで、ユーザーの明示的な確認なしに作業ツリーを変更することはありません。

ワークフロー全体の例:

```bash
# 1. Claude Code に仕様を渡す前
claude-code-verify check-spec docs/spec-round-33.md
claude-code-verify fix-terms  docs/spec-round-33.md

# 2. Claude Code が作業を行う

# 3. Claude Code の編集後
claude-code-verify verify-wiring
claude-code-verify enforce-scope --spec docs/spec-round-33.md
claude-code-verify clean-commits HEAD
```

---

## 関連研究

1. [arxiv 2603.20847](https://arxiv.org/abs/2603.20847) — *Engineering Pitfalls in AI Coding Tools: An Empirical Study of Bugs in Claude Code, Codex, and Gemini CLI*。Claude Code・Codex・Gemini CLI の 3 ツールで 3,800 件の issue 分析、67% が機能バグ、36.9% が API/統合起因。
2. [arxiv 2604.08906](https://arxiv.org/abs/2604.08906) — *Dissecting Bug Triggers and Failure Modes in Modern Agentic Frameworks: An Empirical Study*。CrewAI、AutoGen など 5 フレームワークで 409 件のバグ分析。
3. [GitHub Issue #19739(anthropics/claude-code)](https://github.com/anthropics/claude-code/issues/19739) — 体系的失敗パターンを蓄積するコミュニティスレッド。
4. **BSWEN(2026年3月)** — phantom API hallucination の定性記述。
5. [GitHub Issue #19117(anthropics/claude-code)](https://github.com/anthropics/claude-code/issues/19117) — Anthropic 公式ドキュメントにおける telemetry の用語曖昧性。
6. [cclint](https://github.com/carlrannaberg/cclint)(carlrannaberg) — Claude Code 設定 linter。
7. [opslane/verify](https://github.com/opslane/verify) — ブラウザベースの UI テストランナー。
8. [claude-code-quality-hook](https://github.com/dhofheinz/claude-code-quality-hook)(dhofheinz) — Claude Code リポジトリ向けの pre-commit lint 修正ツール。
9. [spec-kit](https://github.com/github/spec-kit)(GitHub) — 仕様記述ワークフロー。
10. **GateGuard**(PyPI) — 調査ゲート強制ツール。

---

## 追記: 本稿自身も危うく Pattern #7 を含むところだった

公開数時間前のレビューで、気味の悪い事実が発見されました。先ほどの引用ブロック——あなたが読んだばかりのもの——には、人間著者(本稿筆者)が検証せずに受け入れていた 3 つの事実誤認が含まれていました。

- arxiv 2603.20847 の実際のタイトルは *"Engineering Pitfalls in AI Coding Tools: An Empirical Study of Bugs in Claude Code, Codex, and Gemini CLI"* でした。初稿にあった *"A Systematic Study of Bug Patterns in Claude Code"* ではありません。
- 論文は **3 ツール** を扱う横断研究で、Claude Code 単独ではありません。
- API/統合起因率は **36.9%** で、37.3% ではありません。

初稿は LLM の支援で書かれていました。引用の要約を求められたとき、モデルは論文の実 abstract を取得せず、部分的な記憶から「それらしい」言い換えを生成しました。出力は自信に満ちた文体で、正確な引用の構造と語調を持っていました。ただ、内容が実際と違ったのです。

これは Pattern #7(Phantom API Assumption)そのものを、コードではなく学術引用に適用した例です。モデルは「その論文の引用ならこう書くだろう」を埋めただけで、「実際にその論文に書かれていること」を書いてはいませんでした。

ここから得られる教訓は 2 つあります。

1. **このパターンはコードを超えて一般化する。** LLM が部分的な文脈から外部文書を要約・参照するあらゆる場面で、phantom(幻の)詳細が検出されずに出力に混入しうる。
2. **人間のレビューは依然として不可欠。** 今回のエラーが発見されたきっかけは、人間著者の「これ、引用にリンク貼ってないじゃん?」の一言でした。URL を実際にクリックして初めて、記事と実論文の齟齬が露呈しました。もしこの一言がなければ、記事は捏造された出典表記のまま公開されていました。

本記事で紹介したツールを自分の仕様書に適用する際、ついでに `check-spec` のような検証パスを「コード以外のアーティファクト」にも走らせてみてください。引用、外部ドキュメントへの参照、ベンチマーク数値——モデルが近似的な記憶から生成した可能性のあるものは、すべて。根本の欠陥は同じです。

この節は記事の残りが公開された後に追加されました。訂正の経緯はコミット履歴を参照: `f07ce63`(事実訂正)、`36d1ee5`(訂正の発見を可能にしたハイパーリンク追加)。

---

## リンク

- **Part 1**: [README-ja.md](./README-ja.md) — 最初の6パターンと5つの黄金法則
- **英語版**: [README-part2.md](./README-part2.md)
- **テンプレート**: [templates/](./templates/) — strict-mode、wiring-only、numeric-check 用のプロンプトテンプレート
- **データ**: `data/session-2026-04-19/` — ラウンドごとの生ログ(公開予定)

---

*反例、新しいパターン、フィードバックを歓迎します。Issue または PR で連絡してください。*
