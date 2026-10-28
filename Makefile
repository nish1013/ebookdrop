.PHONY: install test test-api test-web lint api-types sandbox-image metrics

install:
	cd api && uv sync
	cd web && npm ci && npx playwright install chromium

test: test-api test-web

test-api:
	cd api && uv run pytest -q

test-web: sandbox-image
	cd web && npx playwright test

lint: api-types
	cd api && uv run ruff check . && uv run ruff format --check . && uv run mypy
	cd web && npx eslint . && npx tsc -b
	git diff --exit-code -- api/openapi.json web/src/api/schema.d.ts

api-types:
	cd api && uv run python scripts/openapi.py > openapi.json
	cd web && npm run -s api-types

sandbox-image:
	docker build -q -t ebookdrop-sandbox -f api/sandbox/Dockerfile api

metrics:
	cd api && uv run python scripts/metrics.py
