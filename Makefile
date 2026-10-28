# Common tasks. Works with GNU make on macOS, Linux and Windows (Git Bash / PowerShell with make).
ifeq ($(OS),Windows_NT)
  VENV_BIN := backend/.venv/Scripts
  SYSTEM_PYTHON ?= python
else
  VENV_BIN := backend/.venv/bin
  SYSTEM_PYTHON ?= python3
endif
PY := $(VENV_BIN)/python
IMAGE ?= portfolio-risk-backend
GIT_SHA ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
PORT ?= 7860

.PHONY: setup test lint run-backend run-frontend docker-build docker-run

setup: ## Create the backend venv, install backend and frontend dependencies
	$(SYSTEM_PYTHON) -m venv backend/.venv
	$(PY) -m pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

test: ## Backend tests with coverage, then frontend tests
	cd backend && ../$(PY) -m pytest -q --cov=app
	cd frontend && npm run test

lint: ## ruff (check and format check), then ESLint and Prettier
	cd backend && ../$(PY) -m ruff check .
	cd backend && ../$(PY) -m ruff format --check .
	cd frontend && npm run lint

run-backend: ## API on http://localhost:8000 with reload
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --port 8000

run-frontend: ## Vite dev server on http://localhost:5173
	cd frontend && npm run dev

docker-build: ## Build the backend image
	docker build -t $(IMAGE) backend

docker-run: ## Run the image on http://localhost:7860 (reads .env for keys if it exists)
	docker run --rm -p $(PORT):7860 $(if $(wildcard .env),--env-file .env) \
		-e ALLOWED_ORIGINS=http://localhost:5173 -e GIT_SHA=$(GIT_SHA) $(IMAGE)
