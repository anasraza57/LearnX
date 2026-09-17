SHELL = /bin/bash
PYTHON = .venv/bin/python
MODEL ?= gpt-5.4-mini
ARGS ?=

.ONESHELL:
# Python 3.11 environment from the frozen lock file (arm64 on Apple silicon)
venv:
	python3.11 -m venv .venv && \
    .venv/bin/python -m pip install --upgrade pip setuptools wheel && \
    .venv/bin/python -m pip install -r requirements.lock.txt && \
    .venv/bin/python -c "import platform; print('venv architecture:', platform.machine())"

# ---- Scenario-based evaluation harness ----

# Verify the committed scenario set is reproducible
scenarios:
	$(PYTHON) -m src.experiment.scenarios --check

# Fetch, label and index the fixed corpus (fetch runs once per corpus version)
corpus-fetch:
	$(PYTHON) -m src.experiment.corpus fetch
corpus-label:
	$(PYTHON) -m src.experiment.corpus label
corpus-index:
	$(PYTHON) -m src.experiment.corpus index

# E1 ablation on the reference model
e1:
	$(PYTHON) -m src.experiment.runner --experiment e1 --model $(MODEL) --conditions A1 A2 A3 A4 A5 $(ARGS)

# Three-run determinism probe (D27)
probe:
	$(PYTHON) -m src.experiment.runner --experiment probe --model $(MODEL) --conditions A1 --scenarios S01 --repeats 3 $(ARGS)

# ---- Retired: these draw results from assumed distributions instead of running
# the system, so they cannot be used as evaluation results.
compare-models compare-models-quick evaluate-all:
	@echo "'$@' samples results from assumed distributions rather than running the system. Disabled; use the harness targets above."; exit 1

# Run tests
test:
	$(PYTHON) -m pytest tests/ -v

# Run with coverage
test-coverage:
	$(PYTHON) -m pytest tests/ --cov=src --cov-report=html --cov-report=term
