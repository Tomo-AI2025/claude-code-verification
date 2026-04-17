# Strict Mode — 45-60 Item Verification Template

> **For safety-critical code only.** Use this when failure means real money lost, data corrupted, or users harmed.
> Examples: kill-switches, payment processing, authentication, encryption, trade execution, medical dosing.

**Average detection rate:** Catches ~99% of all 6 failure patterns when followed completely.
**Time cost:** 20-40 minutes per module. **Worth it.**

---

## How to Use

1. Copy this entire checklist into a working document.
2. Fill in placeholders (`<MODULE>`, `<FUNCTION>`, `<FILE>`, `<VALUE>`, `<CALLER>`).
3. Run **every command**. Mark ✅ or ❌ for each.
4. **Any ❌ blocks completion.** Re-prompt with the specific gap, then re-run the failed checks.
5. Apply the scenario thought experiment (Section H) — walk through the code path mentally.

---

## Section A — Definition Layer (8 checks)

### A1. Function signature exists
```bash
grep -n "def <FUNCTION>" <FILE>
```

### A2. Class signature exists (if applicable)
```bash
grep -n "class <CLASS>" <FILE>
```

### A3. Type hints present on all parameters
```bash
grep -A1 "def <FUNCTION>" <FILE>
```

### A4. Return type annotation present
```bash
grep -n "def <FUNCTION>.*->" <FILE>
```

### A5. Docstring exists
```bash
grep -A2 "def <FUNCTION>" <FILE> | grep '"""'
```

### A6. No `pass`-only body
```bash
grep -A3 "def <FUNCTION>" <FILE>
```

### A7. No `raise NotImplementedError` body
```bash
grep -A5 "def <FUNCTION>" <FILE> | grep "NotImplementedError"
```
**Expected:** 0 hits.

### A8. Function length > 1 line (excluding signature)
```bash
grep -c "    " <FILE>
```

---

## Section B — Wiring / Call-Site Layer (10 checks)

### B1. At least one external caller exists
```bash
grep -rn "<FUNCTION>" src/ --include="*.py" | grep -v "def <FUNCTION>" | grep -v "<FILE>"
```
**Expected:** 1+ hit. **If 0:** Silent Failure confirmed.

### B2. Call site is in expected file
```bash
grep -n "<FUNCTION>" <EXPECTED_CALLER_FILE>
```

### B3. Call site is on the expected line range
```bash
grep -n "<FUNCTION>" <EXPECTED_CALLER_FILE>
```
Check line number falls within the documented range.

### B4. Caller imports the module
```bash
grep -n "from <MODULE>\|import <MODULE>" <CALLER>
```

### B5. Caller instantiates the class (if OOP)
```bash
grep -n "<CLASS>(" <CALLER>
```

### B6. Caller stores instance correctly
```bash
grep -n "self\.<INSTANCE>" <CALLER>
```

### B7. Function arguments match signature
```bash
grep -B1 -A2 "<FUNCTION>(" <CALLER>
```

### B8. Return value is consumed (not discarded)
```bash
grep -n "= .*<FUNCTION>(" <CALLER>
```

### B9. Call sits inside the correct conditional / loop
Manually inspect the surrounding context.

### B10. Call is reachable (no `return` above it that always fires)
Manually trace.

---

## Section C — Numeric Parameters (8 checks)

### C1. Constant value exact match
```bash
grep -n "<CONSTANT_NAME>\s*=" <FILE>
```
Verify exact value (e.g., `STOP_LOSS_PCT = 5.0`, not `10.0`).

### C2. Threshold value exact match
```bash
grep -n "<THRESHOLD>" <FILE>
```

### C3. Currency / monetary values exact
```bash
grep -n "1000\|1_000\|10000\|10_000" <FILE>
```
Verify dollars haven't drifted by 10×.

### C4. Percentages stored consistently (5.0 vs 0.05)
```bash
grep -n "0\.05\|5\.0\|5%" <FILE>
```

### C5. Time intervals exact (seconds vs minutes)
```bash
grep -n "interval\|timeout\|sleep" <FILE>
```

### C6. Array sizes / limits exact
```bash
grep -n "MAX_\|LIMIT_\|SIZE_" <FILE>
```

### C7. Retry counts exact
```bash
grep -n "retry\|attempts\|max_tries" <FILE>
```

### C8. No magic numbers replacing named constants
```bash
grep -nE "[^a-zA-Z_][0-9]{2,}" <FILE>
```

---

## Section D — Configuration Wiring (6 checks)

### D1. Config key defined in config file
```bash
grep -n "<CONFIG_KEY>" config/
```

### D2. Config key consumed in execution code
```bash
grep -rn "<CONFIG_KEY>" src/ --include="*.py" | grep -v "config/"
```
**Expected:** 1+ hit outside config dir. **If 0:** Config-Only failure (Pattern #5).

### D3. Default values defined
```bash
grep -n "default\|DEFAULT" <CONFIG_FILE>
```

### D4. Required env vars documented (no actual secrets!)
```bash
grep -n "os\.environ\|getenv" src/ -r
```

### D5. Config validation exists at startup
```bash
grep -rn "validate.*config\|assert.*config" src/
```

### D6. Config changes propagate without restart (or restart documented)
Manual review.

---

## Section E — Prerequisites & External Resources (5 checks)

### E1. Required files exist
```bash
ls -la <PATH_TO_REQUIRED_FILES>
```

### E2. Key files / certs present (do NOT print contents)
```bash
ls -la keys/ certs/ 2>/dev/null
```

### E3. Required directories exist
```bash
ls -d data/ logs/ tmp/ 2>/dev/null
```

### E4. Database tables / schemas exist
```bash
# Run your migration check command
```

### E5. External services reachable (in dry-run mode)
```bash
# Run your health-check script
```

---

## Section F — Error Handling (6 checks)

### F1. Try/except blocks around I/O
```bash
grep -B1 -A5 "try:" <FILE>
```

### F2. Specific exceptions caught (not bare `except:`)
```bash
grep -n "except:" <FILE>
```
**Expected:** 0 bare excepts.

### F3. Errors logged, not silently swallowed
```bash
grep -A3 "except" <FILE> | grep "log\|raise"
```

### F4. Critical paths have rollback
```bash
grep -n "rollback\|revert\|undo" <FILE>
```

### F5. Resource cleanup uses context managers
```bash
grep -n "with .* as " <FILE>
```

### F6. Timeouts set on network calls
```bash
grep -n "timeout=" <FILE>
```

---

## Section G — Tests (6 checks)

### G1. Test file exists
```bash
ls tests/ | grep "<MODULE>"
```

### G2. Test imports the function under test
```bash
grep -n "<FUNCTION>" tests/test_<MODULE>.py
```

### G3. At least one assertion per test
```bash
grep -c "assert " tests/test_<MODULE>.py
```

### G4. No `assert True` placeholders
```bash
grep -n "assert True" tests/
```
**Expected:** 0 hits.

### G5. Edge cases tested (empty, None, max, min)
```bash
grep -n "None\|empty\|MAX\|MIN" tests/test_<MODULE>.py
```

### G6. Test actually runs (not skipped)
```bash
grep -n "@pytest.mark.skip\|@unittest.skip" tests/test_<MODULE>.py
```
**Expected:** 0 hits (or documented reason).

---

## Section H — Scenario Thought Experiment (manual, 5 questions)

Walk through the **end-to-end execution path**. For each step, ask: "Is this wired?"

### H1. Trigger event fires
> *Example: Market drawdown reaches -20%.*
> Does the code that detects this event actually run on a schedule / event loop?
```bash
grep -rn "<TRIGGER>" src/
```

### H2. Detection function returns the right value
> Does `evaluate()` (or equivalent) actually get called by the loop?
```bash
grep -rn "evaluate\|check\|monitor" src/ | grep -v "def "
```

### H3. Dispatched action exists
> When the condition is met, does the dispatch branch (`_on_dd_20pct`, `_on_threshold`, etc.) exist?
```bash
grep -n "_on_\|handle_\|dispatch" <FILE>
```

### H4. Side effect is executed
> Does the action actually call the executor (sell positions, send alert, log entry)?
```bash
grep -rn "<EXECUTOR>" src/
```

### H5. Final state is reached
> Does the process actually exit / lock / persist as designed?
```bash
grep -n "sys.exit\|os._exit\|lockfile" <FILE>
```

**One broken link in this chain = the entire safety-critical feature does nothing.**

---

## Section I — Documentation & Commit Hygiene (4 checks)

### I1. CLAUDE.md (or equivalent) updated to reflect new behavior
```bash
grep -n "<FUNCTION>\|<MODULE>" CLAUDE.md
```

### I2. Commit message matches actual diff
```bash
git log -1 --stat
git diff HEAD~1
```

### I3. No `.env` / secrets in diff
```bash
git diff HEAD~1 | grep -iE "api[_-]?key|password|secret|token"
```
**Expected:** 0 hits. **If hits:** ABORT and rewrite history.

### I4. Changelog entry added (if project uses one)
```bash
grep -n "<FUNCTION>" CHANGELOG.md
```

---

## Final Verdict

| ✅ Passed | ❌ Failed | Verdict |
|---|---|---|
| 45-48 / 48 | 0-1 | **Production ready.** Merge with confidence. |
| 40-44 / 48 | 4-8 | **Conditional pass.** Fix the failures, re-run those specific checks, then merge. |
| 30-39 / 48 | 9-18 | **Major rework.** Re-prompt with separated definition / wiring / config commands. Re-run the entire strict mode after rework. |
| < 30 / 48 | 19+ | **Reject and restart.** The implementation has fundamental gaps. Use scenario-based thought experiment (Golden Rule #4) before re-prompting. |

---

## When to Use Strict Mode

✅ Use for:
- Trading / financial code
- Authentication / authorization
- Encryption / key management
- Medical / health dosing logic
- Anything in `kill_switch.py`, `safety_net.py`, `payment.py`
- Anything that runs unattended on a schedule

❌ Don't use for:
- UI tweaks, copy changes, styling
- Internal dev tools / scripts
- Prototypes / spikes

For non-critical changes, use `standard-check.md` instead.
