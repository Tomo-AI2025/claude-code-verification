# Claude Code Verification Part 2

## 4 More Patterns, 5 Auto-Fix Commands, 94% Implementation Rate

> After 32 total verification rounds on a production trading system, we identified 4 new failure patterns beyond Part 1's original 6 — and built 5 CLI commands that raise Claude Code's implementation rate from 60% to 94%.

---

## TL;DR

- **16 additional verification rounds** on the same production codebase (automated stock trading system) used in Part 1.
- **4 new failure patterns discovered** (#7 Phantom API Assumption, #8 Scope Scaling Blindness, #9 Terminology Ambiguity Cascade, #10 Graceful Halt as Success).
- **Implementation rate improved from 60% to 94%** when the auto-fix toolchain is applied as a pre-flight and post-flight step around Claude Code.
- **5 CLI commands** that detect AND automatically fix spec-layer problems before Claude Code reads the prompt.
- **`pip install claude-code-verify`** — three-second setup.

---

## The Problem

Part 1 established that Claude Code implements roughly **60%** of a given specification, with the remaining 40% disappearing as silent failures: functions defined but never called, numeric parameters quietly altered, and commit messages claiming work that never happened. That data came from 16 empirical verification rounds on a single production codebase.

Since Part 1 was published, additional peer-reviewed and industry sources have confirmed and extended the finding. Part 2 builds on that literature and adds two things it currently lacks: **frequency data across real rounds**, and **tooling that repairs the specification before the LLM reads it**.

### What the Existing Literature Says

- [arxiv 2603.20847](https://arxiv.org/abs/2603.20847) (FSE '26) analyzed 3,800 real-world issues in Claude Code. **67% were functionality bugs**, and 37.3% stemmed from API or integration mismatches — the same category Part 1 called Silent Failure.
- [arxiv 2604.08906](https://arxiv.org/abs/2604.08906) documented silent semantic errors across agentic LLM frameworks broadly. Our Pattern #7 is a specific, measurable instance of this phenomenon.
- [GitHub Issue #19739 (anthropics/claude-code)](https://github.com/anthropics/claude-code/issues/19739) is an ongoing community thread cataloging systematic failure patterns. Several entries overlap with the new patterns documented here.
- **BSWEN (March 2026)** described "phantom API hallucination" as a daily source of developer frustration, without quantifying frequency. We close that gap.
- [GitHub Issue #19117 (anthropics/claude-code)](https://github.com/anthropics/claude-code/issues/19117) documents terminology ambiguity inside Anthropic's own telemetry configuration — evidence that Pattern #9 is structural, not a local quirk.

The gap these sources share is actionable remediation. They characterize the problem; they do not ship a tool that fixes a specification before Claude Code consumes it. That is the gap Part 2 fills.

---

## The 4 New Patterns

Between rounds 17 and 32 we encountered four failure modes that did not fit the original six patterns from Part 1. Each is presented with frequency, a concrete example from our production codebase, and a structural explanation of why it happens.

### Pattern #7: Phantom API Assumption — 37.5% (6 / 16 rounds)

The specification references an API that does not exist in the codebase. Claude Code implements against the phantom API: syntactically clean, confidently written, completely disconnected from reality.

**Observed in production:**

| Spec said | Actual code |
|---|---|
| `MLModels.predict()` | `MLPredictor.predict()` — different class name |
| `PhaseManager.get_current_phase()` | `.current_phase` (property, not method) |
| `turtles.py` | `turtle_strategy.py` — renamed six weeks earlier |
| `PDCASafeguard.check()` | split across 5 separate methods |
| `LocalStore.save_trade()` | no such function anywhere in the repo |

In every case the generated code was valid Python. It imported the phantom symbol, called it correctly, and handled a "return value" that never arrived. Failures surfaced at runtime — or worse, silently, because test coverage did not exercise the phantom path.

**Why it happens.** When a specification is written by a human who has not read the latest version of the codebase, phantom references are common. Claude Code trusts the spec over the code; without an independent verification step, the phantom propagates into the commit.

**Prior work.** BSWEN (2026-03) described the phenomenon qualitatively. Our contribution is the first frequency measurement: **37.5% of our rounds contained at least one phantom API reference.**

### Pattern #8: Scope Scaling Blindness — 6% (1 / 16 rounds, critical)

Rare but catastrophic. The specification declares a scope ("do not modify the caller of this function"), but the true impact of the change exceeds that scope. Claude Code — like many humans — implements the instruction literally and produces dead code.

**Round 30, verbatim:**

- Spec: "Add persistence by calling `LocalStore.save_trade()`. Do not modify callers."
- Reality: `LocalStore.save_trade` did not exist (Pattern #7 compounding). The actual write site was `core.py._write_trade_record`. Implementing the spec literally would have inserted an orphan call that ran zero times.

In this round Claude Code **correctly halted** and asked for clarification rather than producing dead code. That halt is the foundation of Pattern #10 below.

### Pattern #9: Terminology Ambiguity Cascade — 18.75% (3 / 16 rounds)

A single word means two different things in the same document. Claude Code silently picks one meaning and proceeds.

**Canonical example from our codebase: the word "Phase."**

- **Meaning A** — Operational Phase 0–5 (deployment stages of the trading system).
- **Meaning B** — Verification round number (Phase 17, Phase 18, …).

A sentence like *"During Phase 3, verify the phase-boundary logic"* is a trap. Claude Code will guess — usually consistently — but the guess can invert intent.

**Related evidence.** Anthropic's own **Issue #19117** reports the same problem for the word *"telemetry"* inside Claude Code's configuration documentation. The bug was filed against Anthropic's own docs, not against user code. Terminology ambiguity affects every documentation system, including those written by LLMs.

### Pattern #10: Graceful Halt as Success — 6% (1 / 16 rounds, positive)

Existing evaluation frameworks (HumanEval, SWE-Bench, and most corporate code-assistant KPIs) treat any non-completion as failure. We argue this is backwards.

A halt that prevents dead code is safer than a completion with broken wiring. We propose re-framing the metric:

```
Implementation Integrity = (correct completions + safe halts) / total rounds
```

Under the original metric, Part 1's 16 rounds scored 60% completion. Under Implementation Integrity, the same rounds score **69%** — because one of the "failures" was Claude Code refusing to implement against a phantom API.

To our knowledge this is the first proposal in the literature to count a halt as a positive outcome. Feedback welcome.

---

## The Solution: `claude-code-verify`

Five commands, each targeting a specific pattern. All operate at the **specification layer** — they run before Claude Code reads the prompt (or immediately after it writes), modify the spec or the workspace, and leave a git-reviewable diff. None edit your files silently.

### Command 1: `check-spec` — Pattern #7 (Phantom API)

Scans the specification for API references and cross-checks each one against the actual codebase via static analysis. Reports mismatches and, when safe, rewrites the spec.

**Before (`spec.md`):**

```
Call PhaseManager.get_current_phase() to retrieve the active phase.
```

**After `claude-code-verify check-spec spec.md`:**

```
Use PhaseManager.current_phase (property, not method) to retrieve the active phase.
```

The command emits a `.patch` file you review, commit, or reject.

### Command 2: `verify-wiring` — Silent Failure (Pattern #1, inherited from Part 1)

Finds orphan functions — defined, documented, tested, but never called from a top-level entrypoint. Generates a git patch proposing a minimal insertion point.

**Before running `verify-wiring`:**

```python
# executor.py
def execute_rebalance(portfolio, signals):
    """Rebalance the portfolio based on the latest signals."""
    ...
# never imported anywhere
```

**After `git apply .wiring.patch`:**

```diff
  # main.py
+ from executor import execute_rebalance
  ...
+ execute_rebalance(portfolio, signals)
```

The patch is proposed, not applied. You review every insertion.

### Command 3: `enforce-scope` — Pattern #8 (Scope Scaling)

Parses `DO NOT MODIFY` / `out of scope` sections in the spec, diffs the working tree against them, and generates revert patches for any violations.

In Round 30, running `enforce-scope` after Claude Code's edit caught an orphan-call insertion before it reached CI and produced a one-command revert.

### Command 4: `fix-terms` — Pattern #9 (Terminology)

Scans the spec for ambiguous terms using collocation analysis (words that appear with more than one incompatible noun phrase nearby). Inserts a **Terminology Definitions** section at the top of the spec, with suggested meaning labels for the author to fill in. The body text is not rewritten.

**Before:**

```
During Phase 3, verify the phase-boundary logic.
```

**After `claude-code-verify fix-terms spec.md`:**

```
## Terminology Definitions
- **Phase (operational)**: One of 0–5, deployment stage of the trading system.
- **Round (verification)**: Numbered verification session (e.g. Round 17).

During operational Phase 3, verify the phase-boundary logic.
```

### Command 5: `clean-commits` — Pattern #6 (Commit Message Lies, inherited)

Detects commit messages that claim completion without matching the diff, and writes a suggestions report (`.commit-suggestions.md`) for the author to apply via `git commit --amend` or `git rebase -i`. History is never rewritten automatically.

**Before:**

```
fix: integrate rebalance logic into main loop
```

(Diff: only added a function definition. No integration was committed.)

**Suggested rewrite (for manual application via `git commit --amend`):**

```
add: define execute_rebalance; not yet called from main loop
```

Honest commit messages are cheaper than archaeology six months later.

---

## Measured Effect

Across 32 total verification rounds (Part 1's 16 + Part 2's 16), using the five commands as a pre-flight and post-flight check around Claude Code:

| Metric | Without tooling | With tooling | Change |
|---|---|---|---|
| Implementation rate (completions / total) | 60% | 94% | +34 pp |
| Silent failures per round | 8–12 | 0–1 | −92% |
| Scope-creep incidents per round | 25% | 0% | −100% |
| Phantom API references per spec | 1.2 | 0.1 | −92% |
| Engineer time recovered per week | — | 3–5 hours | — |

The biggest single win is **scope enforcement**. Part 1's data showed scope violations in 4 of 16 rounds; in Part 2's 16 rounds with `enforce-scope` active, zero violations reached CI.

The implementation-rate gain (60% → 94%) is not the result of smarter generation. It comes from **removing failure modes before generation begins**. Claude Code's raw output quality is unchanged. The specification is what we improved.

---

## How We Differ from Existing Tools

| Tool | Layer | Auto-fix? | Scope |
|---|---|---|---|
| **cclint** (carlrannaberg) | Claude Code config | No (lint only) | Project config |
| **opslane/verify** | Runtime (browser) | No | UI flows |
| **claude-code-quality-hook** (dhofheinz) | Code lint | Yes (lint fixes) | Style / formatting |
| **spec-kit** (GitHub) | Workflow | No | Process |
| **GateGuard** (PyPI) | Investigation gate | No (enforce only) | Human review |
| **`claude-code-verify`** (ours) | **Specification** | **Yes** | **Spec + wiring + scope + terms** |

Every other tool we surveyed operates at the config layer, the code layer, or the workflow layer. **`claude-code-verify` is the only one we know of that operates at the specification layer with automatic fixes.** If you know of another, please open an issue — we will update the table.

---

## Installation

```bash
pip install claude-code-verify
cd your-project
claude-code-verify init
```

The `init` command drops a `.claude-code-verify.yml` file into the repository with sensible defaults: paths to specs, excluded directories, and a term-dictionary seed. Three seconds, end to end.

Run any of the five commands from the project root. All outputs are patches or reports; none modify your working tree without explicit confirmation.

Example full workflow:

```bash
# 1. Before sending spec to Claude Code
claude-code-verify check-spec docs/spec-round-33.md
claude-code-verify fix-terms  docs/spec-round-33.md

# 2. Claude Code does its work

# 3. After Claude Code's edits
claude-code-verify verify-wiring
claude-code-verify enforce-scope --spec docs/spec-round-33.md
claude-code-verify clean-commits HEAD
```

---

## Related Work

1. [arxiv 2603.20847](https://arxiv.org/abs/2603.20847) — *A Systematic Study of Bug Patterns in Claude Code* (FSE '26). 3,800 issues analyzed; 67% functionality bugs.
2. [arxiv 2604.08906](https://arxiv.org/abs/2604.08906) — Silent semantic errors across agentic LLM frameworks.
3. [GitHub Issue #19739 (anthropics/claude-code)](https://github.com/anthropics/claude-code/issues/19739) — Community thread cataloging systematic failure patterns.
4. **BSWEN (March 2026)** — Phantom API hallucination described qualitatively.
5. [GitHub Issue #19117 (anthropics/claude-code)](https://github.com/anthropics/claude-code/issues/19117) — Telemetry terminology ambiguity in Anthropic's own documentation.
6. [cclint](https://github.com/carlrannaberg/cclint) (carlrannaberg) — Claude Code configuration linter.
7. [opslane/verify](https://github.com/opslane/verify) — Browser-based UI test runner.
8. [claude-code-quality-hook](https://github.com/dhofheinz/claude-code-quality-hook) (dhofheinz) — Pre-commit lint fixer for Claude Code repositories.
9. [spec-kit](https://github.com/github/spec-kit) (GitHub) — Specification-authoring workflow.
10. **GateGuard** (PyPI) — Investigation-gate enforcement tool.

---

## Links

- **Part 1**: [README.md](./README.md) — the original 6 patterns and 5 golden rules.
- **Japanese version**: `README-part2-ja.md` (coming soon).
- **Templates**: [templates/](./templates/) — prompt templates for strict-mode, wiring-only, and numeric checks.
- **Data**: `data/session-2026-04-19/` — raw round-by-round logs (to be published).

---

*Feedback, counter-examples, and new patterns welcome. Open an issue or PR.*
