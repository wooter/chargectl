PYTHON ?= python3.11
VENV_DIR ?= .venv311
VENV_PYTHON := $(VENV_DIR)/bin/python

.PHONY: venv dev-install test-modulation ci-test-modulation

venv:
	$(PYTHON) -m venv $(VENV_DIR)

dev-install: venv
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e ".[dev]"

test-modulation:
	$(VENV_PYTHON) -m pytest tests/test_modulation.py -q

ci-test-modulation:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"
	$(PYTHON) -m pytest tests/test_modulation.py -q
