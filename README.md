# ShopCo Backend (FastAPI)

Modular, async e-commerce backend: FastAPI + SQLAlchemy 2 (async) + PostgreSQL + Alembic.
Built to plug into a Next.js storefront with a typed API contract, uniform errors and cookie-based sessions.

**Implemented so far:** project foundation, auth (email + password, rotating refresh tokens, roles),
catalog (products, variants, categories, brands, images, search/filter/sort), admin catalog APIs, tests, docs.
**Next modules:** inventory & reservations, cart, checkout + Razorpay, orders, GST invoices, shipping, notifications.

## For the frontend developer: start here

1. [`docs/FRONTEND_INTEGRATION.md`](docs/FRONTEND_INTEGRATION.md) - auth flow, conventions, Next.js snippets, homepage → endpoint map
2. [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) - every endpoint with curl examples
3. Live, try-it-out docs at **http://localhost:8000/docs** (Swagger) and `/redoc`; spec at `/openapi.json`
   (also exportable to `docs/openapi.json` with `make openapi`)

## Quickstart (Docker)

```bash
cp .env.example .env
docker compose up -d --build

# one-time: create the first migration from the models, then apply it
docker compose exec api alembic revision --autogenerate -m "initial schema"
docker compose exec api alembic upgrade head

docker compose exec api python -m scripts.seed     # admin user + demo catalog
```

API: http://localhost:8000 · Docs: http://localhost:8000/docs · Health: `/health`, `/ready`
Seeded admin: `admin@example.com` / `Admin@12345` (override in `.env`; change it anywhere real).

> Commit the generated file in `migrations/versions/`. From then on, every model change =
> `make migration m="what changed"` + `make migrate`.

## Run locally without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
# Postgres running somewhere; set DATABASE_URL in .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Tests & quality

```bash
pytest -q          # uses in-memory SQLite, no Postgres needed
ruff check .       # lint
```

## Layout

```
app/
  core/        config, security (JWT, Argon2), errors, pagination, rate limit, middleware
  db/          Base/mixins, async session, model registry
  modules/     auth/  catalog/  (each: models, schemas, repository, service, router)
  api/         v1 router aggregation, health probes
migrations/    Alembic
scripts/       seed.py, export_openapi.py
tests/         pytest (httpx AsyncClient + SQLite)
docs/          FRONTEND_INTEGRATION.md, API_REFERENCE.md, ARCHITECTURE.md
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for conventions and how to add a module.

## Configuration

All via environment variables (see `.env.example`). Startup refuses to run in staging/production with
the default `JWT_SECRET`, a short secret, or `COOKIE_SECURE=false`.
