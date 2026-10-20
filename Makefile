PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
PIP := $(BIN)/python -m pip
PYTEST_ARGS ?=

.PHONY: setup test lint doctor clean

setup:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

test:
	@test -x $(BIN)/python || { echo "error: run 'make setup' first" >&2; exit 1; }
	$(BIN)/python -m pytest $(PYTEST_ARGS)

lint:
	@test -x $(BIN)/ruff || { echo "error: run 'make setup' first" >&2; exit 1; }
	$(BIN)/ruff check .
	@if command -v shellcheck >/dev/null 2>&1; then \
		find . -path './.venv' -prune -o -type f \( -name '*.sh' -o -name 'pre-push' \) -print0 \
			| xargs -0 -r shellcheck -s bash; \
	else \
		echo "shellcheck not installed; skipping"; \
	fi
	@if command -v yamllint >/dev/null 2>&1; then \
		yamllint .github/workflows/*.yml; \
	else \
		echo "yamllint not installed; skipping"; \
	fi

doctor:
	$(PYTHON) plan/agentctl.py doctor

clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache build dist *.egg-info
