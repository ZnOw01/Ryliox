# ==============================================================================
# Ryliox Makefile
# Common commands for development, testing, building, and deployment
# ==============================================================================

.PHONY: help install dev test lint format build deploy clean

# Default target
.DEFAULT_GOAL := help

# ==============================================================================
# Help
# ==============================================================================
help: ## Show this help message
	@echo "Ryliox Development Commands"
	@echo "==========================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ==============================================================================
# Development
# ==============================================================================
install: ## Install Python dependencies
	pip install --upgrade pip
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-mock pytest-cov black ruff mypy

dev: ## Start development server with hot reload
	python -m launcher

dev-docker: ## Start development server in Docker with hot reload
	docker-compose up -d

dev-logs: ## View development logs
	docker-compose logs -f ryliox

# ==============================================================================
# Testing
# ==============================================================================
test: ## Run all tests
	pytest -v

test-unit: ## Run unit tests only
	pytest -v -m unit

test-integration: ## Run integration tests only
	pytest -v -m integration

test-e2e: ## Run end-to-end tests
	pytest -v -m e2e

test-coverage: ## Run tests with coverage report
	pytest -v --cov=core --cov=plugins --cov=web --cov=utils --cov-report=html --cov-report=term-missing

test-coverage-xml: ## Run tests and generate XML coverage report
	pytest -v --cov=core --cov=plugins --cov=web --cov=utils --cov-report=xml

# ==============================================================================
# Code Quality
# ==============================================================================
lint: ## Run all linters
	ruff check .
	black --check .
	mypy --ignore-missing-imports core/ plugins/ web/ utils/ config.py launcher.py

format: ## Format code with ruff and black
	ruff format .
	black .

format-check: ## Check code formatting without modifying
	ruff format --check .
	black --check .

fix: ## Fix auto-fixable linting issues
	ruff check --fix .

# ==============================================================================
# Security
# ==============================================================================
security-scan: ## Run security scans (Bandit, Safety)
	bandit -r core/ plugins/ web/ utils/ -ll
	safety check

docker-scan: ## Scan Docker image with Trivy
	@docker build -t ryliox:scan -f Dockerfile.prod .
	trivy image ryliox:scan

# ==============================================================================
# Building
# ==============================================================================
build: ## Build Docker image for local use
	docker build -t ryliox:latest .

build-prod: ## Build optimized production Docker image
	docker build -t ryliox:prod -f Dockerfile.prod --target runtime .

build-dev: ## Build development Docker image
	docker build -t ryliox:dev -f Dockerfile.prod --target development .

build-test: ## Build testing Docker image
	docker build -t ryliox:test -f Dockerfile.prod --target tester .

build-multiarch: ## Build multi-arch Docker images (amd64, arm64)
	docker buildx create --name multiarch-builder --use || true
	docker buildx build --platform linux/amd64,linux/arm64 -t ryliox:latest --push .

frontend-build: ## Build frontend only
	cd frontend && npm ci && npm run build

# ==============================================================================
# Running
# ==============================================================================
run: ## Run the application locally
	python -m launcher

run-docker: ## Run Docker container locally
	docker run -d --name ryliox -p 8000:8000 -v $(PWD)/data:/app/data -v $(PWD)/output:/app/output ryliox:latest

run-prod: ## Run production Docker container
	docker-compose -f docker-compose.prod.yml up -d

stop: ## Stop all containers
	docker-compose down
	docker-compose -f docker-compose.prod.yml down

stop-prod: ## Stop production containers
	docker-compose -f docker-compose.prod.yml down

restart: ## Restart containers
	docker-compose restart

# ==============================================================================
# Deployment
# ==============================================================================
deploy-prod: ## Deploy to production (requires proper SSH setup)
	./scripts/deploy-production.sh

backup: ## Backup data and output directories
	./scripts/backup.sh

restore: ## Restore from backup
	./scripts/restore.sh

# ==============================================================================
# Docker Compose Operations
# ==============================================================================
dev-up: ## Start development environment
	docker-compose up -d

dev-down: ## Stop development environment
	docker-compose down

dev-rebuild: ## Rebuild and restart development environment
	docker-compose down
	docker-compose up --build -d

prod-up: ## Start production environment
	docker-compose -f docker-compose.prod.yml up -d

prod-down: ## Stop production environment
	docker-compose -f docker-compose.prod.yml down

prod-logs: ## View production logs
	docker-compose -f docker-compose.prod.yml logs -f ryliox

# ==============================================================================
# Maintenance
# ==============================================================================
clean: ## Clean up build artifacts and cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name "*.pyd" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache .ruff_cache 2>/dev/null || true

docker-clean: ## Clean up Docker images, containers, and volumes
	docker-compose down -v
	docker-compose -f docker-compose.prod.yml down -v
	docker system prune -f
	docker volume prune -f

logs: ## View application logs
	docker-compose logs -f

logs-prod: ## View production logs
	docker-compose -f docker-compose.prod.yml logs -f

status: ## Show container status
	docker-compose ps
	docker-compose -f docker-compose.prod.yml ps

# ==============================================================================
# Git Operations
# ==============================================================================
git-status: ## Show git status
	git status

git-pull: ## Pull latest changes
	git pull origin main

git-push: ## Push changes to origin
	git push origin main

# ==============================================================================
# Health Checks
# ==============================================================================
health: ## Check application health
	@curl -s http://localhost:8000/api/health | python -m json.tool || echo "Health check failed"

health-prod: ## Check production health
	@curl -s https://ryliox.example.com/api/health | python -m json.tool || echo "Health check failed"

# ==============================================================================
# Information
# ==============================================================================
info: ## Show project information
	@echo "Ryliox Project"
	@echo "=============="
	@echo "Python version: $(shell python --version)"
	@echo "Docker version: $(shell docker --version)"
	@echo "Docker Compose version: $(shell docker-compose --version)"
	@echo ""
	@echo "Available environments:"
	@echo "  - Development: localhost:8000"
	@echo "  - Production: https://ryliox.example.com"

version: ## Show version information
	@echo "Ryliox $(shell grep -E '^version' pyproject.toml | head -1 | sed 's/version = //' | tr -d '"')"
