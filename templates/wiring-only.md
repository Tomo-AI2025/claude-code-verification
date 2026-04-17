# Wiring-Only — Call-Site Verification Template

> Use this **after detecting a Silent Failure** (Pattern #1, frequency 69%).
> When `grep "def <FUNCTION>"` returns a hit but `grep "<FUNCTION>(" --exclude="def"` returns nothing, the function exists in isolation. This template fixes that.

**Detection rate for Silent Failures:** ~100% when followed.

---

## The Silent Failure Symptom

```bash
# DEFINITION exists ✅
grep -n "def calculate_net_profit" src/trading/cost_manager.py
# → 84: def calculate_net_profit(self, gross_profit: float) -> float:

# CALL SITE missing ❌
grep -rn "calculate_net_profit" src/ --include="*.py" | grep -v "def calculate_net_profit"
# → (no output)

# = Silent Failure. The function does nothing in production.
```

---

## The Fix Workflow (5 Steps)

### Step 1 — Identify the expected caller(s)

Ask yourself: **"Who SHOULD call this function?"** Be specific — name the file, the function, and the timing.

| Function | Should be called by | At what moment |
|---|---|---|
| `calculate_net_profit` | `executor.py :: on_sell_filled` | After every sell order fills |
| `evaluate` (kill_switch) | `monitor.py :: monitor_loop` | Every tick / iteration |
| `score_stock` (whale) | `scoring.py :: score_stock` | Inside the main scoring composition |

Write your row here:

```
Function:        <FUNCTION>
Expected caller: <CALLER_FILE> :: <CALLER_FUNCTION>
At moment:       <WHEN>
```

---

### Step 2 — Re-prompt with Golden Rule #2 (exact location)

Use this prompt template **verbatim**:

```
In <CALLER_FILE>, inside <CALLER_FUNCTION>() at line <APPROX_LINE>,
add a call to: <FUNCTION>(<ARGS>)

The call must:
1. Be placed AFTER <PRECEDING_OPERATION>
2. Store the return value in a variable named <RETURN_VAR>
3. Use <RETURN_VAR> in the subsequent <DOWNSTREAM_OPERATION>

Do NOT modify the definition in <DEFINITION_FILE> — only add the call site.
```

This separates "definition" from "wiring" (Golden Rule #1) and prevents the LLM from drifting.

---

### Step 3 — Verify the wire was actually added

Run **all 7 checks**. A single ❌ means the wire is still missing.

#### W1. Call site appears in the expected file
```bash
grep -n "<FUNCTION>" <CALLER_FILE>
```
**Expected:** 1+ hit (excluding `def`).

#### W2. Call site is in the expected function
```bash
grep -B5 "<FUNCTION>(" <CALLER_FILE> | grep "def <CALLER_FUNCTION>"
```
**Expected:** Match — the call sits inside the right function.

#### W3. Import statement present
```bash
grep -n "from <MODULE>\|import <MODULE>" <CALLER_FILE>
```
**Expected:** 1+ hit.

#### W4. Class instance available (if OOP)
```bash
grep -n "self\.<INSTANCE_NAME>\|<CLASS>(" <CALLER_FILE>
```
**Expected:** Instance exists in scope at the call site.

#### W5. Return value consumed (not discarded)
```bash
grep -n "= .*<FUNCTION>(" <CALLER_FILE>
```
**Expected:** 1+ hit showing assignment, OR explicit reason for void call.

#### W6. Call is reachable (not behind unreachable branch)
```bash
grep -B10 "<FUNCTION>(" <CALLER_FILE>
```
Manually check: no unconditional `return` above it, no `if False:` wrapper.

#### W7. The full chain works end-to-end
```bash
grep -rn "<FUNCTION>" src/ --include="*.py"
```
**Expected:** Definition (1) + caller(s) (1+) = 2+ total hits.

---

### Step 4 — Walk the scenario mentally (Golden Rule #4)

State out loud the end-to-end scenario:

> *"When `<TRIGGERING_EVENT>` happens, `<CALLER_FUNCTION>` runs.
> Inside it, `<FUNCTION>` is called with `<ARGS>`.
> The result `<RETURN_VAR>` is then used by `<DOWNSTREAM>`.
> Final visible effect: `<OUTCOME>`."*

For each "is called" / "is used" link, run a `grep` to verify. **Each unverified link is a potential second silent failure.**

---

### Step 5 — Update CLAUDE.md (or your spec file) FIRST next time

The "spec-first update" rule prevents recurrence:

```markdown
## <MODULE>
- `<FUNCTION>` is defined in `<DEFINITION_FILE>:<LINE>`
- It MUST be called from `<CALLER_FILE>::<CALLER_FUNCTION>` after `<TRIGGER>`
- Its return value MUST be consumed by `<DOWNSTREAM>`
```

Then ask the LLM to "match the implementation to CLAUDE.md."

---

## Worked Example — `evaluate()` from kill_switch.py

**Symptom:**
```bash
grep -n "def evaluate" src/trading/kill_switch.py
# → 152: def evaluate(self, current_capital): ✅

grep -rn "evaluate" src/ --include="*.py" | grep -v "def evaluate"
# → (empty) ❌  Silent Failure
```

**Fix prompt (Step 2):**
```
In src/trading/executor.py, inside monitor_loop() at line ~270,
add a call to: self._kill_switch.evaluate(current_capital)

The call must:
1. Be placed AFTER current_capital = portfolio.get_total_capital()
2. If it returns True, immediately call self._emergency_shutdown()
3. Use within the existing while True loop, not outside it

Do NOT modify kill_switch.py — only add the call site in executor.py.
```

**Verification (Step 3):**
```bash
grep -n "evaluate" src/trading/executor.py
# → 277: if self._kill_switch.evaluate(current_capital): ✅
# → 278:     self._emergency_shutdown() ✅

grep -rn "evaluate" src/ --include="*.py" | grep -v "def evaluate" | wc -l
# → 1+  ✅
```

---

## When to Use This Template

✅ Use when:
- `standard-check.md` Check 2 returned 0 hits
- A previously working function suddenly stopped firing in production
- Commit message says "integrated X" but you can't find the integration
- Refactoring deleted the call site but kept the definition (Pattern #6)

❌ Don't use for:
- Brand new feature implementations (use `standard-check.md` first)
- Numeric drift problems (use `numeric-check.md`)
