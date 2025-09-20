SHELL := /usr/bin/env bash

VENV := .venv
PY := $(VENV)/Scripts/python.exe
PIP := $(VENV)/Scripts/pip.exe

$(VENV):
	python -m venv $(VENV)
	$(PIP) install --upgrade pip

.PHONY: install
install: $(VENV)
	$(PIP) install -e .[dev]

.PHONY: dev
dev: install
	$(PY) -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port $${PORT:-8080} --reload

.PHONY: test
test: install
	$(VENV)/Scripts/pytest.exe -q

.PHONY: lint
lint: install
	$(VENV)/Scripts/ruff.exe check .

.PHONY: typecheck
typecheck: install
	$(VENV)/Scripts/mypy.exe app
