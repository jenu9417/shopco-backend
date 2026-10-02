# Architecture & Conventions

## Principles

- **Modular monolith.** One deployable, strict module boundaries. Split into services later only if needed.
- **Layering per module:** `router → service → repository → models` (+ `schemas` for the API contract).
  - *Router*: HTTP only (parse, call service, shape response).
  - *Service*: business rules, transactions (`commit()` lives here), raises `AppError` subclasses.
  - *Repository*: queries only, no business rules.
- **Modules talk through services or (soon) events, never each other's tables.** Cross-module imports are
  limited to a module's public surface (e.g. `app.modules.auth.deps`).
- **Contract first.** Pydantic schemas = OpenAPI = generated frontend client. Never return ORM objects directly.

## Conventions

| Topic | Rule |
|---|---|
| Money | integer minor units (paise) + `currency` |
| IDs | UUID v4 |
| Time | timezone-aware UTC (`DateTime(timezone=True)`) |
| Errors | raise `AppError` subclasses with a stable `code`; never `HTTPException` in services |
| Sessions | one `AsyncSession` per request (`DbSession`); services call `commit()` explicitly |
| Soft delete | products are archived, not deleted (orders must keep referencing them) |
| Slugs | auto-generated, unique (`-2`, `-3` suffix); explicit slug conflicts return 409 |
| Naming | tags `store-*` / `admin-*`; operation id = `{tag}_{function}` |

## Security model

- Passwords: Argon2id; timing-equalised login; generic `invalid_credentials`.
- Access JWT (15 min, in memory on the client) + opaque refresh token (30 d, httpOnly cookie,
  stored **hashed**, rotated on use, family revoked on reuse).
- RBAC via dependencies: `CurrentUser`, `StaffUser`, `AdminUser`, or `require_roles(...)`.
- Rate limiting on auth endpoints (in-memory; swap to Redis for multi-instance).
- Security headers, strict CORS allow-list, request ids, no stack traces in responses.
- Startup guards: weak secret / insecure cookies are rejected in staging/production.

## Adding a module (example: `cart`)

1. `app/modules/cart/{models,schemas,repository,service,router}.py`
2. Register models in `app/db/models.py`; router in `app/api/v1.py`
3. `make migration m="add cart"` → review the generated file → `make migrate`
4. Tests in `tests/test_cart.py`; document endpoints in `docs/API_REFERENCE.md`

## Roadmap (suggested order)

1. **Inventory**: stock per location, reservations with expiry (replaces `stock_quantity` on variants)
2. **Cart**: guest carts (cart id), merge on login, server-side totals
3. **Checkout + Razorpay**: idempotency keys, Razorpay order creation, signature verification, **webhook as
   source of truth** (dedupe by event id), reconciliation job for stuck `pending_payment` orders, COD option
4. **Orders**: state machine (`pending_payment → paid → processing → shipped → delivered`, plus
   cancel/return/refund branches), events on every transition
5. **Pricing & tax**: promo codes, GST (CGST/SGST vs IGST by state), GST invoices (sequential numbers, PDF)
6. **Shipping**: pincode serviceability, rates, AWB tracking (provider abstraction: Shiprocket/Delhivery)
7. **Notifications**: email/SMS/WhatsApp via background worker (ARQ/Celery + Redis)
8. **Customers**: addresses (PIN/state validation), wishlist; phone-OTP login
9. **Reviews & search**: ratings (feeds `rating_avg`), Postgres FTS → Meilisearch/OpenSearch
10. **Hardening**: Redis rate limiting/cache, structured logging + OpenTelemetry + Sentry, image uploads via
    presigned URLs, audit log for admin actions, backups, load tests

## Known limitations of this scaffold

- Stock is a simple integer on the variant (no reservations yet), so it must not be used for real checkout yet.
- Category filter matches the exact category (does not include descendants yet).
- Title search is `ILIKE`; fine for thousands of products, replace with FTS/Meilisearch beyond that.
- Rate limiter is per-process memory.
- Email verification, password reset and phone-OTP login are not implemented yet.
