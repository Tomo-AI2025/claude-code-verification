# Numeric Check — Parameter Value Verification Template

> Use this when your code contains **threshold values, monetary amounts, percentages, retry counts, or any numeric constants** that are safety-critical or business-critical.
>
> Pattern #2 — **Numeric Alteration** — happens in 25% of LLM-generated changes. The LLM silently rewrites `$1,000` as `$10,000`, or `5.0%` as `10.0%`, or `retries=3` as `retries=10`.

**Detection rate for Numeric Alterations:** ~95% when followed.

---

## Why This Pattern Is Dangerous

LLMs treat numbers as "soft" tokens — they often substitute "reasonable looking" values when the original feels arbitrary. A single zero added or removed can:

- Turn a $1,000 position limit into a $10,000 one (10× capital risk)
- Turn a 5% stop-loss into a 50% one (catastrophic loss)
- Turn a 3-retry network call into a 30-retry retry storm
- Turn a 5-second timeout into a 5,000-second hang

Code review with eyes-only catches maybe half. **Grep is the only reliable defense.**

---

## How to Use

1. Before the LLM touches the file: list every numeric constant you care about. Save it.
2. After the change: run **every applicable check** below.
3. Compare each value against your "before" list.
4. Any drift → re-prompt with the exact value and re-verify.

---

## The Numeric Inventory (build this BEFORE any LLM change)

```
File: <FILE>
Constants snapshot taken at: <DATE_TIME>

| Constant Name        | Expected Value | Unit         | Why this value |
|----------------------|----------------|--------------|----------------|
| STOP_LOSS_PCT        | 5.0            | percent      | Risk policy    |
| MAX_POSITION_USD     | 1000           | dollars      | Per-trade cap  |
| RETRY_COUNT          | 3              | attempts     | Avoid storm    |
| API_TIMEOUT_SEC      | 5              | seconds      | UX limit       |
| MIN_LIQUIDITY_USD    | 50000          | dollars      | Slippage floor |
| WHALE_THRESHOLD_USD  | 1000           | dollars      | Signal cutoff  |
| ...                  | ...            | ...          | ...            |
```

Paste this table into your PR description — reviewers can compare it against the diff.

---

## The 12 Numeric Checks

### N1. Named constant exact-match
```bash
grep -n "<CONSTANT_NAME>\s*=" <FILE>
```
**Expected:** Exact value from your inventory.

### N2. Magnitude check (catch 10× and 0.1× drift)
```bash
grep -nE "<CONSTANT_NAME>\s*=\s*[0-9]+" <FILE>
```
Compare digit count: `1000` = 4 digits, `10000` = 5 digits, `100` = 3 digits.

### N3. Decimal placement (5.0 vs 0.05 vs 50.0)
```bash
grep -nE "<CONSTANT_NAME>\s*=\s*[0-9]+\.?[0-9]*" <FILE>
```
Check for accidental percentage / decimal swap.

### N4. Currency drift — common amounts
```bash
grep -nE "100\b|1000\b|1_000\b|10000\b|10_000\b|100000\b|100_000\b" <FILE>
```
Visually scan for unexpected zeros.

### N5. Percentage representation consistency
```bash
grep -nE "0\.[0-9]+|[0-9]+\.[0-9]+%|[0-9]+\s*%" <FILE>
```
Did `5.0` (meaning 5%) become `0.05` (meaning 5% in decimal form) somewhere?

### N6. Time unit consistency (seconds vs ms vs minutes)
```bash
grep -nE "timeout|interval|delay|sleep|wait" <FILE>
```
Check the value matches the expected unit. `timeout=5` could mean 5 seconds or 5 ms.

### N7. Retry / attempt counts
```bash
grep -nE "retry|retries|max_tries|attempts|max_attempts" <FILE>
```
Single-digit values usually correct; double-digit retries often indicate drift.

### N8. Pagination / batch sizes
```bash
grep -nE "page_size|batch_size|chunk|limit\s*=" <FILE>
```

### N9. Threshold comparisons
```bash
grep -nE ">\s*[0-9]|<\s*[0-9]|>=\s*[0-9]|<=\s*[0-9]" <FILE>
```
Verify each threshold matches inventory.

### N10. Range bounds (min/max)
```bash
grep -nE "MIN_|MAX_|min=|max=" <FILE>
```

### N11. Index / offset values
```bash
grep -nE "\[0\]|\[-1\]|offset\s*=" <FILE>
```
Off-by-one drift is invisible until production.

### N12. Magic numbers (untracked constants)
```bash
grep -nE "[^a-zA-Z_0-9][0-9]{2,}" <FILE> | grep -v "^\s*#"
```
Look for hard-coded numbers that should be named constants. New magic numbers = silent policy changes.

---

## Cross-File Consistency Checks

When the same value appears in multiple files, drift in one file is a silent break.

### X1. Same constant across modules
```bash
grep -rn "<CONSTANT_NAME>" src/ --include="*.py"
```
**Expected:** Either one definition + many imports, OR identical literal values everywhere.

### X2. Config vs code agreement
```bash
grep -n "<CONSTANT_NAME>" config/ src/
```
Config file value MUST equal the code's default fallback.

### X3. Test fixtures match production constants
```bash
grep -rn "<CONSTANT_NAME>" tests/
```
Tests using outdated values produce false confidence.

---

## Worked Example — Whale Tracker Threshold

**Inventory (before LLM edit):**
```
WHALE_THRESHOLD_USD = 1000  (the "$1k whale" signal)
```

**After LLM edit, run:**
```bash
grep -n "WHALE_THRESHOLD" src/trading/whale_tracker.py
# → 12: WHALE_THRESHOLD_USD = 10000  ❌ DRIFT — 10×

grep -rn "WHALE_THRESHOLD" src/ --include="*.py"
# → src/trading/whale_tracker.py:12: 10000
# → src/analysis/scoring.py:88:      1000   ❌ INCONSISTENT
```

**Fix prompt:**
```
In src/trading/whale_tracker.py line 12, the constant WHALE_THRESHOLD_USD
must be exactly 1000 (one thousand US dollars), not 10000.

Do NOT change any other code. Only restore this single value.
After the change, also verify src/analysis/scoring.py line 88 still reads 1000.
```

**Re-verify:**
```bash
grep -rn "WHALE_THRESHOLD\|1000" src/trading/whale_tracker.py src/analysis/scoring.py
# → both files show 1000 ✅
```

---

## Tally

| Drift detected? | Action |
|---|---|
| **No drift on any check** | ✅ Numeric integrity verified. Proceed. |
| **1-2 drifted values** | Re-prompt for those exact values, re-run only those checks. |
| **3+ drifted values** | Reject the change wholesale. Re-issue with the inventory table embedded in the prompt: "These constants MUST remain at the listed values. Verify with grep after editing." |

---

## When to Use This Template

✅ Use for:
- Trading / financial code (positions, stops, limits)
- Rate limiting / retry logic
- Timeouts / SLAs
- Safety thresholds (drawdowns, kill-switches)
- Feature flag percentages / rollouts
- Pricing / billing math

❌ Skip for:
- Pure UI / styling code
- Comments and documentation only
- Test scaffolding without real assertions

For code that is both numeric- AND wiring-heavy (e.g., a kill-switch with thresholds), run **`numeric-check.md` first**, then `wiring-only.md`, then `strict-mode.md` as final gate.
