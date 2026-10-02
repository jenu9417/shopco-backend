.PHONY: up down logs migration migrate seed test lint openapi

up:            ## start db + api
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api

migration:     ## make migration m="add something"
	docker compose exec api alembic revision --autogenerate -m "$(m)"

migrate:       ## apply migrations
	docker compose exec api alembic upgrade head

seed:          ## admin user + demo catalog (idempotent)
	docker compose exec api python -m scripts.seed

test:          ## run tests locally (needs requirements-dev.txt)
	pytest -q

lint:
	ruff check . && ruff format --check .

openapi:       ## export docs/openapi.json for the frontend dev
	python -m scripts.export_openapi
