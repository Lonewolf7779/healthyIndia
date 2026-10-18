.PHONY: help install lint format test dev-api dev-web build clean

help:
	@echo "healthyIndia Monorepo Commands:"
	@echo "  make install   Install dependencies for backend and frontend"
	@echo "  make lint      Run code linters (ruff, eslint, type-check)"
	@echo "  make format    Format code (ruff)"
	@echo "  make test      Run all backend and frontend tests"
	@echo "  make dev-api   Start FastAPI backend development server"
	@echo "  make dev-web   Start Next.js frontend development server"
	@echo "  make build     Build production bundles"

install:
	cd services/api && uv sync
	cd apps/web && pnpm install

lint:
	cd services/api && uv run ruff check .
	cd apps/web && pnpm run type-check

format:
	cd services/api && uv run ruff format .

test:
	cd services/api && uv run python -m pytest -v
	cd apps/web && pnpm run test

dev-api:
	cd services/api && uv run python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-web:
	cd apps/web && pnpm run dev

build:
	cd apps/web && pnpm run build

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
