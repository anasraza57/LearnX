SHELL = /bin/bash

.ONESHELL:
venv:
	python3.10 -m venv venv && \
    source venv/bin/activate && \
    python3.10 -m pip install --upgrade pip setuptools wheel && \
    python3.10 -m pip install -e ".[dev]" && \
    pre-commit install && \
    pre-commit autoupdate

# Run model comparison (GPT-3.5-Turbo vs GPT-4o-Mini)
compare-models:
	source .venv/bin/activate && python examples/run_model_comparison.py

# Quick model comparison with smaller sample
compare-models-quick:
	source .venv/bin/activate && python -c "from src.evaluation.model_comparison import ModelComparison; c = ModelComparison(); c.run_comparison_experiment(num_students=10)"

# Run full evaluation suite
evaluate-all:
	source .venv/bin/activate && python -m src.evaluation.evaluate_system

# Run tests
test:
	source .venv/bin/activate && pytest tests/ -v

# Run with coverage
test-coverage:
	source .venv/bin/activate && pytest tests/ --cov=src --cov-report=html --cov-report=term