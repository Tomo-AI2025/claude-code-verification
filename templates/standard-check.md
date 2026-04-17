# Standard Check — 10-Item Verification Template

> Basic verification for any module after Claude Code (or any LLM coding agent) generates or modifies code.
> Use this **after every implementation task** to catch the most common failure patterns.

**Average detection rate:** Catches ~80% of Silent Failures, Numeric Alterations, and Config-Only patterns.

---

## How to Use

1. Copy this checklist into your terminal or notes app.
2. Replace `<MODULE>`, `<FUNCTION>`, `<FILE>`, and `<VALUE>` placeholders with your actuals.
3. Run each grep command and confirm the expected result.
4. **A single ❌ means the implementation is incomplete — do not mark the task done.**

---

## The 10 Checks

### ✅ Check 1 — Definition exists
```bash
grep -n "def <FUNCTION>" <FILE>
```
**Expected:** 1+ hit showing the function signature.
**If 0 hits:** The function was never written. Re-prompt.

---

### ✅ Check 2 — Call site exists (the most important check)
```bash
grep -rn "<FUNCTION>" src/ --include="*.py" | grep -v "def <FUNCTION>"
```
**Expected:** 1+ hit from a *different* file than where the function is defined.
**If 0 hits:** **SILENT FAILURE** — the function exists but nothing calls it. Pattern #1.

---

### ✅ Check 3 — Import statement present in the caller
```bash
grep -n "import <MODULE>\|from <MODULE>" <CALLER_FILE>
```
**Expected:** Import line exists.
**If 0 hits:** Caller cannot reach the function — wiring incomplete.

---

### ✅ Check 4 — Numeric parameters unchanged
```bash
grep -n "<EXPECTED_VALUE>" <FILE>
```
**Expected:** The exact value you specified (e.g., `1000`, `5.0`, `0.05`).
**If altered:** Pattern #2 — Numeric Alteration. Re-prompt with the correct value.

---

### ✅ Check 5 — Config keys are referenced in execution code
```bash
grep -rn "<CONFIG_KEY>" src/ --include="*.py"
```
**Expected:** 2+ hits — one in the config file, one+ in the executor.
**If only 1 hit (config only):** Pattern #5 — Config-Only. Settings exist but no code uses them.

---

### ✅ Check 6 — Required files / prerequisites exist
```bash
ls -la <PATH_TO_REQUIRED_FILE>
```
**Expected:** File present and readable.
**If missing:** Pattern #4 — Missing Prerequisites (e.g., RSA keys, schema files, certs).

---

### ✅ Check 7 — Tail-of-prompt instructions implemented
Re-read your original prompt. Did you list multiple instructions? Verify the **last 1-2 items** specifically — they get skipped 19% of the time (Pattern #3).

```bash
grep -n "<LAST_INSTRUCTION_KEYWORD>" <FILE>
```

---

### ✅ Check 8 — Commit message matches reality
```bash
git log -1 --stat
git diff HEAD~1 -- <FILE>
```
**Expected:** Commit message claims must be backed by visible diff lines.
**If commit says "integrated X" but diff doesn't show the call site:** Pattern #6 — Commit Message Lie.

---

### ✅ Check 9 — No dead branches or unreachable code
```bash
grep -n "TODO\|FIXME\|pass$\|raise NotImplementedError" <FILE>
```
**Expected:** 0 hits in newly added code.
**If hits:** Implementation is a stub, not real code.

---

### ✅ Check 10 — Tests exist AND assert behavior
```bash
grep -rn "<FUNCTION>" tests/ --include="*.py"
```
**Expected:** Test file references the new function with `assert` statements.
**If only `assert True` or no assertions:** Tests are theatrical, not verifying behavior.

---

## Quick Result Tally

| ✅ Passed | ❌ Failed | Verdict |
|---|---|---|
| 10 / 10 | 0 | **Implementation complete.** Safe to merge. |
| 8-9 / 10 | 1-2 | **Re-prompt for the failed items.** Do not merge. |
| ≤ 7 / 10 | 3+ | **Major gaps.** Reject and re-issue the original task with separated definition + wiring commands (Golden Rule #1). |

---

## Related Templates

- For safety-critical code (trading, auth, encryption): use `strict-mode.md`
- After detecting a Silent Failure: use `wiring-only.md`
- For parameter-heavy modules: use `numeric-check.md`
