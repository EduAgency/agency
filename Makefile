# Nasuru — one entry point for every routine command.
#
# Python packages are managed with uv; Node with npm. Nothing here needs a
# manually activated virtualenv — every backend target goes through .venv
# directly, so `make test` works from a cold shell.
#
#   make            list every target
#   make setup      install both stacks and start the infrastructure
#   make verify     everything CI runs
#
# Windows note: the venv puts binaries in Scripts/, POSIX puts them in bin/.
# The detection below keeps a single Makefile working on both.

SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND  := backend
FRONTEND := frontend
VENV     := $(BACKEND)/.venv

ifeq ($(OS),Windows_NT)
	PY := $(VENV)/Scripts/python.exe
else
	PY := $(VENV)/bin/python
endif

# Every backend command runs from backend/ with that venv's interpreter.
MANAGE := cd $(BACKEND) && ../$(PY) manage.py
PYTEST := cd $(BACKEND) && ../$(PY) -m pytest

.PHONY: help
help: ## Show this list
	@echo "Nasuru — available commands"
	@echo
	@grep -hE '^[a-zA-Z0-9_.-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

.PHONY: setup
setup: infra install migrate ## Full first-run setup: infra, dependencies, migrations
	@echo "Ready. 'make dev' starts both servers."

.PHONY: install
install: install-backend install-frontend ## Install both stacks

.PHONY: install-backend
install-backend: ## Create the venv and install Python dependencies with uv
	@test -d $(VENV) || uv venv --python 3.13 $(VENV)
	uv pip install --python $(PY) -r $(BACKEND)/requirements.txt

.PHONY: install-frontend
install-frontend: ## Install Node dependencies
	cd $(FRONTEND) && npm install

.PHONY: env
env: ## Write backend/.env with freshly generated keys (never overwrites)
	@if [ -f $(BACKEND)/.env ]; then \
		echo "backend/.env already exists — leaving it alone."; \
	else \
		cp $(BACKEND)/.env.example $(BACKEND)/.env && \
		echo "Created backend/.env. Fill in DJANGO_SECRET_KEY and FIELD_ENCRYPTION_KEY:"; \
		echo "  make keys"; \
	fi

.PHONY: keys
keys: ## Print a fresh DJANGO_SECRET_KEY and FIELD_ENCRYPTION_KEY
	@$(PY) -c "import secrets; print('DJANGO_SECRET_KEY=' + secrets.token_urlsafe(50))"
	@$(PY) -c "from cryptography.fernet import Fernet; print('FIELD_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

.PHONY: infra
infra: ## Start Postgres and Redis
	docker compose up -d db redis

.PHONY: infra-down
infra-down: ## Stop the containers, keeping the data
	docker compose stop db redis

.PHONY: infra-reset
infra-reset: ## Destroy the containers AND their data, then start fresh
	docker compose down -v
	docker compose up -d db redis

# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

.PHONY: dev
dev: ## Reminder of the processes a full local stack needs
	@echo "Run these in separate terminals:"
	@echo "  make dev-backend     Django on :8010"
	@echo "  make dev-frontend    Next.js on :3000"
	@echo "  make worker          Celery worker (webhooks, notifications)"
	@echo "  make beat            Celery beat (reconciliation, nudges)"

.PHONY: dev-backend
dev-backend: ## Django development server on :8010
	$(MANAGE) runserver 8010

.PHONY: dev-frontend
dev-frontend: ## Next.js development server on :3000
	cd $(FRONTEND) && npm run dev

.PHONY: worker
worker: ## Celery worker — webhook processing and notifications
	cd $(BACKEND) && ../$(PY) -m celery -A config worker --loglevel=info

.PHONY: beat
beat: ## Celery beat — nightly reconciliation and nudges
	cd $(BACKEND) && ../$(PY) -m celery -A config beat --loglevel=info

.PHONY: migrate
migrate: ## Apply database migrations
	$(MANAGE) migrate

.PHONY: migrations
migrations: ## Generate migrations for model changes
	$(MANAGE) makemigrations

.PHONY: seed
seed: ## Load the demo dataset, including a clickable student
	$(MANAGE) seed_demo --with-student

.PHONY: superuser
superuser: ## Create an admin account
	$(MANAGE) createsuperuser

.PHONY: shell
shell: ## Django shell
	$(MANAGE) shell

# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

.PHONY: verify
verify: check-backend check-frontend ## Everything CI runs
	@echo
	@echo "All checks passed."

.PHONY: check-backend
check-backend: lint-backend test-backend ## Backend lint and tests

.PHONY: check-frontend
check-frontend: contrast launch-check lint-frontend types test-frontend ## Frontend checks, minus e2e

.PHONY: test
test: test-backend test-frontend ## Unit tests, both stacks

.PHONY: test-backend
test-backend: ## pytest — needs Postgres, so run `make infra` first
	$(PYTEST)

.PHONY: test-frontend
test-frontend: ## Vitest unit tests
	cd $(FRONTEND) && npm run test

.PHONY: e2e
e2e: ## Playwright + axe across public, student and staff routes
	cd $(FRONTEND) && npx playwright test

.PHONY: e2e-install
e2e-install: ## Download the browsers Playwright needs
	cd $(FRONTEND) && npx playwright install chromium

.PHONY: lint
lint: lint-backend lint-frontend ## Lint both stacks

.PHONY: lint-backend
lint-backend: ## ruff
	cd $(BACKEND) && ../$(PY) -m ruff check .

.PHONY: lint-frontend
lint-frontend: ## eslint, including jsx-a11y at error level
	cd $(FRONTEND) && npm run lint

.PHONY: types
types: ## TypeScript, no emit
	cd $(FRONTEND) && npx tsc --noEmit

.PHONY: format
format: ## Apply ruff and prettier
	cd $(BACKEND) && ../$(PY) -m ruff check --fix .
	cd $(FRONTEND) && npm run format

.PHONY: contrast
contrast: ## Verify every design token pair against its WCAG threshold
	cd $(FRONTEND) && npm run check:contrast

.PHONY: launch-check
launch-check: ## Report policy clauses still awaiting a decision
	cd $(FRONTEND) && npm run check:launch

.PHONY: launch-gate
launch-gate: ## Same, but FAILS if any remain — run before deploying
	cd $(FRONTEND) && node scripts/check-launch-ready.mjs --strict

.PHONY: build
build: ## Production build of the frontend
	cd $(FRONTEND) && npm run build

.PHONY: clean
clean: ## Remove build output and test artefacts
	rm -rf $(FRONTEND)/.next $(FRONTEND)/test-results $(FRONTEND)/playwright-report
	find $(BACKEND) -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
