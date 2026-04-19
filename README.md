# Claude Code Blind Spots — What Nobody Tells You About AI Code Generation

> **Claude Code implements only ~60% of your specifications on average.** The other 40% silently fails — functions are defined but never called, numeric parameters get altered, and commit messages claim completion while code remains incomplete.

This repository documents **16 empirical verification rounds** on a real production codebase (automated stock trading system), revealing **6 systematic failure patterns** and **5 golden rules** for achieving 100% implementation fidelity with Claude Code.

## 📖 Continue Reading

- **[Part 2: 4 More Patterns + 5 Auto-Fix Commands](README-part2.md)** — Our follow-up with 16 more verification rounds, 4 new failure patterns, and a CLI toolkit (`claude-code-verify`) that raises implementation rate from 60% to 94%.
- Japanese version: [README-ja.md](README-ja.md)

## Why This Matters

Every developer using Claude Code, Cursor, Copilot, or any LLM-based coding agent faces the same invisible problem: **the code looks complete, but critical wiring is missing.**

We call this the **"Silent Failure"** — a function exists in the file, it has proper docstrings, it even has unit tests. But no other module ever calls it. The function sits there, doing nothing, while you believe your system is fully functional.

**This is not a Claude Code bug.** It's a structural limitation of how LLMs generate code, and it affects every AI coding tool.

## The 6 Failure Patterns (with frequency data)

| # | Pattern | Frequency | Danger Level | Analogy |
|---|---|---|---|---|
| 1 | **Silent Failure** — Function defined but never called from other modules | 69% (11/16 rounds) | ★★★★★ | Doorbell installed but not wired to the button |
| 2 | **Numeric Alteration** — Parameter values silently changed ($1,000→$10,000) | 25% (4/16) | ★★★★☆ | Recipe says "1 tsp salt" but the cook adds 10 |
| 3 | **Tail Ignoring** — Instructions at the end of prompts get skipped | 19% (3/16) | ★★★☆☆ | Shopping list: only the top 3 items get bought |
| 4 | **Missing Prerequisites** — Code references files that don't exist (RSA keys) | 13% (2/16) | ★★★★★ | Lock installed but no key was ever made |
| 5 | **Config-Only** — Settings defined but no execution code uses them | 50% (8/16) | ★★★☆☆ | Restaurant menu exists but no chef in the kitchen |
| 6 | **Commit Message Lies** — Git commit says "integrated" but integration was lost | 6% (1/16) | ★★★★☆ | Diary says "did homework" but the notebook is blank |

## The 5 Golden Rules

### Rule 1: Separate "Definition" and "Wiring" into different commands
```
# BAD — wiring will be skipped
"Add calculate_net_profit() method to cost_manager.py"

# GOOD — two separate commands
Command 1: "Add calculate_net_profit() method to cost_manager.py"
Command 2: "In executor.py, call cost_manager.calculate_net_profit() after every sell order fills"
```

### Rule 2: Specify call sites with filename, function name, and timing
```
# BAD — too vague
"Integrate with scoring.py"

# GOOD — exact location specified
"In src/analysis/scoring.py, inside score_stock() at line 120,
add: score += whale_tracker.calculate_score()"
```

### Rule 3: Always do "Pair Verification" (grep for definition + grep for call site)
```bash
# Check DEFINITION exists
grep -n "def evaluate" src/trading/kill_switch.py
# → 152: def evaluate(self, current_capital)  ✅

# Check CALL SITE exists
grep -rn "evaluate" src/ --include="*.py" | grep -v "def evaluate"
# → executor.py:277: self._kill_switch.evaluate(current_capital)  ✅

# If call site = 0 hits → SILENT FAILURE — the function exists but does nothing
```

### Rule 4: Use scenario thought experiments to prevent abstraction
```
Scenario: Drawdown reaches -20%
1. portfolio.get_total_capital() returns 80% of peak  ← Does this get called?
2. monitor_loop calls evaluate()                       ← Is this wired?
3. _on_dd_20pct dispatches                             ← Does this branch exist?
4. All positions market-sold                           ← Does executor actually run?
5. sys.exit(1)                                         ← Does process actually stop?

Each "←" question must be verified with grep. One broken link = system doesn't work.
```

### Rule 5: Assume numeric parameters WILL be altered — always grep to verify
```bash
grep -n "STOP_LOSS_PCT" src/trading/safety_net.py
# Verify it's still 5.0, not 10.0

grep -n "1000\|1_000" src/trading/whale_tracker.py
# Verify it's still $1,000, not $10,000
```

## Implementation Rate Across 16 Verification Rounds

| Round | Target | Initial Rate | After Fix |
|---|---|---|---|
| 1 | scoring.py integration | 57% | — |
| 2 | whale_tracker.py | 22% | — |
| 3 | pair_trading.py | 38% | — |
| 4 | turtle_strategy.py | 80% | — |
| 5 | trading modules | 90% | — |
| 6 | RSA encryption | 50% | 95% |
| 7 | RSA fix verification | 95% | — |
| 8 | safety_net + executor | 77% | — |
| 9 | 3-layer defense | 44% | — |
| 10 | cost/calendar/fallback | 47% | 94.5% |
| 11 | wiring fix | 94.5% | 100% ✅ |
| 12 | kill_switch | 35% | 100% ✅ |
| 13-14 | kill_switch verification | 95%→100% | — |
| 15 | position_sizer | 86% | — |
| 16 | position_sizer fix | 100% | ✅ |

**Average initial implementation rate: ~60%**
**After verification + fix loop: 100%**

## Verification Templates (Copy-Paste Ready)

This repo includes ready-to-use verification templates:

- **`templates/standard-check.md`** — Basic 10-item verification for any module
- **`templates/strict-mode.md`** — 45-60 item verification for safety-critical code
- **`templates/wiring-only.md`** — Focused on call-site verification after silent failure detection
- **`templates/numeric-check.md`** — Parameter value verification

## How This Differs from Existing Work

| Approach | Focus | Our Contribution |
|---|---|---|
| [Issue #29795](https://github.com/anthropics/claude-code/issues/29795) (68 failures, 5-layer QA) | Hook-based physical blocking | **grep-based post-hoc verification** |
| [opslane/verify](https://github.com/opslane/verify) | Playwright UI verification | **Code-level structural verification** |
| [DEV.to CLAUDE.md patterns](https://dev.to/ajbuilds/your-claudemd-is-probably-broken-5-silent-failure-patterns-and-how-to-fix-them-1abn) | CLAUDE.md configuration issues | **Implementation completeness measurement** |
| Anthropic Best Practices | General workflow guidance | **Quantified failure rates + systematic taxonomy** |

**Our unique contributions:**
1. First **quantified implementation rates** across 16 verification rounds (22%-100%)
2. First **taxonomy of 6 failure patterns** with empirical frequency data
3. First **"pair verification" methodology** (definition grep + call-site grep)
4. First **"spec-first update" rule** (update CLAUDE.md before changing code)
5. First **scenario-based thought experiment** framework for LLM code verification

## Project Context

These findings were discovered while building an automated stock trading system using:
- Claude Code Max ($100/month)
- Polymarket prediction data → 7-layer scoring → moomoo securities auto-execution
- 480+ line Python codebase across 15+ modules

The verification methodology is **tool-agnostic** — it applies equally to Cursor, Copilot, Windsurf, or any LLM coding agent.

## License

MIT

## Contributing

If you've discovered additional failure patterns or have quantified implementation rates with other LLM coding tools, please open an issue or PR. We're particularly interested in:
- Failure pattern data from Cursor, Copilot, or Windsurf
- Verification methods for languages other than Python
- Automated pair-verification tooling

## Author

[@Tomo-AI2025](https://github.com/Tomo-AI2025)

---

*If this saved you from a silent failure in production, consider giving it a ⭐*
