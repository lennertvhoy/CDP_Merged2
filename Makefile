.PHONY: help install dev test lint format type-check coverage docker-up docker-down clean pre-commit-install az-login tf-init tf-plan tf-apply tf-destroy tf-output tf-tracardi-init tf-tracardi-plan tf-tracardi-apply tf-tracardi-output aoai-print containerapp-update-print eval-suite

PYTHON := uv run python
PYTEST := uv run pytest
RUFF   := uv run ruff
MYPY   := uv run mypy
AZURE_CONFIG_DIR ?= $(PWD)/.azure-config
TFVARS ?= infra/terraform/terraform.tfvars
TF_TRACARDI_VARS ?= infra/tracardi/terraform.tfvars
SUB_PREFIX ?= ed

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies (production + dev)
	uv sync --locked

dev: ## Run the application in development mode
	CHAINLIT_DEBUG=true uv run chainlit run src/app.py --watch

test: ## Run unit tests (no external services required)
	$(PYTEST) tests/ -m "not integration and not e2e" -v

test-all: ## Run all tests including integration (requires running services)
	$(PYTEST) tests/ -v

eval-suite: ## Run deterministic retrieval/grounding eval suite and gate on thresholds
	$(PYTHON) -m tests.integration.test_retrieval_grounding_eval_harness \
		--artifact tests/integration/snapshots/eval_suite/eval_summary.json

lint: ## Run ruff linter
	$(RUFF) check src/ tests/

format: ## Format code with ruff formatter
	$(RUFF) format src/ tests/
	$(RUFF) check --fix src/ tests/

type-check: ## Run mypy type checking
	$(MYPY) src/

coverage: ## Run tests with coverage report
	$(PYTEST) tests/ -m "not integration and not e2e" \
		--cov=src \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-fail-under=60

pre-commit-install: ## Install pre-commit hooks
	uv run pre-commit install

pre-commit-run: ## Run pre-commit on all files
	uv run pre-commit run --all-files

docker-up: ## Start the full local stack (PostgreSQL, Tracardi, chatbot)
	docker compose up -d --build

docker-down: ## Stop all infrastructure services
	docker compose down

docker-logs: ## Tail docker compose logs
	docker compose logs -f

az-login: ## Login to Azure and select subscription prefix (default: ed)
	AZURE_CONFIG_DIR=$(AZURE_CONFIG_DIR) ./scripts/azure/az_login.sh $(SUB_PREFIX)

tf-init: ## Initialize Terraform in infra/terraform
	AZURE_CONFIG_DIR=$(AZURE_CONFIG_DIR) ./scripts/azure/tf.sh init

tf-plan: ## Terraform plan (set TFVARS=... if needed)
	AZURE_CONFIG_DIR=$(AZURE_CONFIG_DIR) ./scripts/azure/tf.sh plan -var-file=$(TFVARS)

tf-apply: ## Terraform apply (set TFVARS=... if needed)
	AZURE_CONFIG_DIR=$(AZURE_CONFIG_DIR) ./scripts/azure/tf.sh apply -var-file=$(TFVARS)

tf-destroy: ## Terraform destroy (set TFVARS=... if needed)
	AZURE_CONFIG_DIR=$(AZURE_CONFIG_DIR) ./scripts/azure/tf.sh destroy -var-file=$(TFVARS)

tf-output: ## Terraform outputs for deployed Azure stack
	AZURE_CONFIG_DIR=$(AZURE_CONFIG_DIR) ./scripts/azure/tf.sh output

tf-tracardi-init: ## Initialize Terraform in infra/tracardi
	AZURE_CONFIG_DIR=$(AZURE_CONFIG_DIR) ./infra/tracardi/scripts/tf.sh init

tf-tracardi-plan: ## Terraform plan for Tracardi stack (set TF_TRACARDI_VARS=... if needed)
	AZURE_CONFIG_DIR=$(AZURE_CONFIG_DIR) ./infra/tracardi/scripts/tf.sh plan -var-file=$(TF_TRACARDI_VARS)

tf-tracardi-apply: ## Terraform apply for Tracardi stack (set TF_TRACARDI_VARS=... if needed)
	AZURE_CONFIG_DIR=$(AZURE_CONFIG_DIR) ./infra/tracardi/scripts/tf.sh apply -var-file=$(TF_TRACARDI_VARS)

tf-tracardi-output: ## Terraform outputs for Tracardi stack
	AZURE_CONFIG_DIR=$(AZURE_CONFIG_DIR) ./infra/tracardi/scripts/tf.sh output

aoai-print: ## Print Azure OpenAI create/deploy/show commands for this stack
	AZURE_CONFIG_DIR=$(AZURE_CONFIG_DIR) ./infra/tracardi/scripts/azure_openai.sh print

containerapp-update-print: ## Print Container App env update commands for Tracardi/Azure OpenAI integration
	AZURE_CONFIG_DIR=$(AZURE_CONFIG_DIR) ./infra/tracardi/scripts/update_containerapp.sh print

clean: ## Remove __pycache__, .pytest_cache, htmlcov, .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov .coverage .mypy_cache .ruff_cache
