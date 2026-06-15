# HOM-9: Clean-Room Reproducibility Check for `chargectl` Test Workflow

Date: 2026-05-11
Issue: HOM-9

## Scope

Validate that the GitHub Actions test workflow command path is reproducible in a clean-room local environment (fresh directory, no inherited repo venv, no `.git` context assumptions).

Workflow under test:

- `.github/workflows/test-modulation.yml`
- CI step command: `make ci-test-modulation`

## Clean-Room Procedure

```bash
REPO=/path/to/chargectl
RUNROOT=$(mktemp -d /tmp/hom9-cleanroom-XXXXXX)
rsync -a --delete --exclude '.git' --exclude '.venv*' --exclude '__pycache__' "$REPO/" "$RUNROOT/repo/"
cd "$RUNROOT/repo"
make ci-test-modulation
```

## Initial Finding

Initial run failed in clean-room with:

```text
make: python: No such file or directory
make: *** [ci-test-modulation] Error 1
```

Root cause: `ci-test-modulation` hardcoded `python`, while the project standard interpreter is configured via `PYTHON ?= python3.11`.

## Fix Applied

Updated `Makefile` target `ci-test-modulation` to use `$(PYTHON)` consistently:

- `python -m ...` -> `$(PYTHON) -m ...`

## Verification After Fix

Re-ran the exact clean-room procedure above without PATH overrides.

Observed result:

```text
python3.11 -m pytest tests/test_modulation.py -q
.........................                                                [100%]
25 passed in 0.01s
```

## Outcome

`make ci-test-modulation` now reproduces in a clean-room environment with Python 3.11 available, matching the workflow interpreter contract.

## Next Action

Keep this target as the single canonical CI entrypoint; if future jobs add commands, require `$(PYTHON)` for interpreter consistency in clean-room runs.
