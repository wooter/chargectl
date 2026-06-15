# HOM-8: Reproducible `tests/test_modulation.py` Execution Path

Date: 2026-05-11
Issue: HOM-8

## Canonical Local Path (Python 3.11 venv)

```bash
python3.11 -m venv .venv311
.venv311/bin/python -m pip install --upgrade pip
.venv311/bin/python -m pip install -e ".[dev]"
.venv311/bin/python -m pytest tests/test_modulation.py -q
```

Equivalent `make` targets:

```bash
make dev-install
make test-modulation
```

## CI Mapping

- Workflow: `.github/workflows/test-modulation.yml`
- CI step command: `make ci-test-modulation`
- CI target executes:
  - `python -m pip install --upgrade pip`
  - `python -m pip install -e ".[dev]"`
  - `python -m pytest tests/test_modulation.py -q`

This keeps local and CI execution paths aligned on the same test entrypoint.

## Pass/Fail Evidence (Executed in this heartbeat)

Direct venv invocation:

```text
Python 3.11.15
pip 26.1.1 from /Users/wouterhermans/Developer/chargectl/.venv311/lib/python3.11/site-packages/pip (python 3.11)
.........................                                                [100%]
25 passed in 0.01s
```

Canonical make path:

```text
make dev-install
...
make test-modulation
.........................                                                [100%]
25 passed in 0.01s
```

## Reproduction Criteria

Another engineer can clone the repo, run the canonical local path above on a machine with Python 3.11, and execute `tests/test_modulation.py` without ad-hoc host fixes.
