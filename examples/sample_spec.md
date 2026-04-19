# Sample Spec (for check-spec demonstration)

Use `MLPredictor.predict()` to get a trading signal.

Do NOT use `MLModels.predict()` — the class does not exist in our codebase.

Read `PhaseManager.current_phase` to determine the active operational phase.

Do NOT call `PhaseManager.get_current_phase()` — current_phase is a property, not a method.

The following code block references should be ignored:

```python
from ignored import IgnoredClass
IgnoredClass.ignored_method()
```

End of spec.
