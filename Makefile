.DEFAULT_GOAL := help
COMPOSE := docker compose
SERVICE  := web

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- Environment -----------------------------------------------------------
.PHONY: init
init: ## Create .env from the template if it does not exist yet
	@test -f .env || (cp .env.example .env && echo "Created .env - edit the secrets before running 'make up'")

# --- Lifecycle -------------------------------------------------------------
.PHONY: build
build: ## Build the images
	$(COMPOSE) build

.PHONY: up
up: ## Start the full stack in the background
	$(COMPOSE) up -d --build
	@echo "API: http://localhost:$${APP_PORT:-8000}"

.PHONY: down
down: ## Stop the stack (volumes are kept)
	$(COMPOSE) down

.PHONY: destroy
destroy: ## Stop the stack AND delete the Postgres/Redis volumes
	$(COMPOSE) down -v --remove-orphans

.PHONY: restart
restart: down up ## Restart everything

.PHONY: prod
prod: ## Run the production configuration locally (no dev override)
	$(COMPOSE) -f docker-compose.yml up -d --build

# --- Observability ---------------------------------------------------------
.PHONY: logs
logs: ## Tail logs from every service
	$(COMPOSE) logs -f

.PHONY: logs-web
logs-web: ## Tail the application logs only
	$(COMPOSE) logs -f $(SERVICE)

.PHONY: ps
ps: ## Show container status
	$(COMPOSE) ps

.PHONY: health
health: ## Hit the readiness probe
	@curl -fsS http://localhost:$${APP_PORT:-8000}/api/v1/health/ready | python3 -m json.tool

# --- Shells ----------------------------------------------------------------
.PHONY: shell
shell: ## Bash shell inside the app container
	$(COMPOSE) exec $(SERVICE) bash

.PHONY: flask-shell
flask-shell: ## Flask REPL with db, models and redis preloaded
	$(COMPOSE) exec $(SERVICE) flask shell

.PHONY: psql
psql: ## psql session on the application database
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-roadtojapan} -d $${POSTGRES_DB:-roadtojapan}

.PHONY: redis-cli
redis-cli: ## redis-cli session
	$(COMPOSE) exec redis redis-cli

# --- Database --------------------------------------------------------------
.PHONY: migrate
migrate: ## Autogenerate a migration: make migrate m="add posts table"
	@test -n "$(m)" || (echo "Usage: make migrate m=\"message\"" && exit 1)
	$(COMPOSE) exec $(SERVICE) flask db migrate -m "$(m)"

.PHONY: upgrade
upgrade: ## Apply all pending migrations
	$(COMPOSE) exec $(SERVICE) flask db upgrade

.PHONY: downgrade
downgrade: ## Roll back one migration
	$(COMPOSE) exec $(SERVICE) flask db downgrade -1

.PHONY: db-history
db-history: ## Show the migration history
	$(COMPOSE) exec $(SERVICE) flask db history

.PHONY: seed
seed: ## Insert the development seed data
	$(COMPOSE) exec $(SERVICE) flask seed

.PHONY: flush-cache
flush-cache: ## Clear the Redis application cache
	$(COMPOSE) exec $(SERVICE) flask flush-cache

# --- Quality ---------------------------------------------------------------
.PHONY: test
test: ## Run the test suite inside the container
	$(COMPOSE) exec $(SERVICE) pytest

.PHONY: test-local
test-local: ## Run the suite in a one-shot container (no running stack needed)
	$(COMPOSE) run --rm -e RUN_MIGRATIONS=0 -e RUN_SEED=0 $(SERVICE) pytest

.PHONY: lint
lint: ## Ruff + mypy
	$(COMPOSE) exec $(SERVICE) ruff check app tests
	$(COMPOSE) exec $(SERVICE) mypy app

.PHONY: format
format: ## Apply black and ruff --fix
	$(COMPOSE) exec $(SERVICE) black app tests
	$(COMPOSE) exec $(SERVICE) ruff check --fix app tests

.PHONY: check
check: lint test ## Lint then test
