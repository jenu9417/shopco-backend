# API Reference (v1)

Base: `http://localhost:8000/api/v1`. Authoritative, always-current reference: **`/docs`** (Swagger).
This page is a quick map with copy-paste examples. Prices are integer **paise**.

Legend: 🌐 public · 🔑 any logged-in user · 🛡️ staff/admin

## Auth

| | Method & path | Purpose |
|---|---|---|
| 🌐 | `POST /auth/register` | Create customer account, log in (sets refresh cookie) |
| 🌐 | `POST /auth/login` | Log in (customers, staff, admins) |
| 🌐 | `POST /auth/refresh` | Cookie → new access token (rotates cookie) |
| 🌐 | `POST /auth/logout` | Revoke refresh token, clear cookie (204) |
| 🔑 | `GET /auth/me` | Current user |
| 🔑 | `PATCH /auth/me` | Update `first_name`, `last_name`, `phone` |

```bash
curl -i -X POST localhost:8000/api/v1/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"jane@example.com","password":"Passw0rd!x","first_name":"Jane"}'

# cookie jar (-c save, -b send) mimics the browser
curl -c jar.txt -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"Admin@12345"}'
curl -b jar.txt -c jar.txt -X POST localhost:8000/api/v1/auth/refresh
```

Response (register/login/refresh):

```json
{ "access_token": "eyJ…", "token_type": "bearer", "expires_in": 900,
  "user": { "id": "…", "email": "jane@example.com", "first_name": "Jane", "last_name": null,
            "phone": null, "role": "customer", "created_at": "2026-10-02T10:00:00Z" } }
```

## Storefront catalog (🌐)

| Method & path | Purpose |
|---|---|
| `GET /store/products` | List/search/filter/sort (see filters in the integration guide) |
| `GET /store/products/{slug}` | Product detail |
| `GET /store/categories` | Active categories, flat (`parent_id` for tree) |
| `GET /store/brands` | Brands |
| `GET /store/stats` | `{products, brands}` counts |

```bash
curl 'localhost:8000/api/v1/store/products?sort=best_selling&size=M&min_price=100000&page_size=4'
curl  localhost:8000/api/v1/store/products/skinny-fit-jeans
```

`ProductListItem`:

```json
{ "id": "…", "title": "Skinny Fit Jeans", "slug": "skinny-fit-jeans", "thumbnail_url": "https://…",
  "brand": {"id": "…", "name": "Calvin Klein", "slug": "calvin-klein", "logo_url": null},
  "price": 240000, "compare_at_price": 300000, "discount_percent": 20, "currency": "INR",
  "rating_avg": 3.5, "rating_count": 70, "in_stock": true }
```

`ProductDetail` adds: `description`, `images[]`, `variants[]` (`id, sku, title, size, color, price,
compare_at_price, currency, in_stock`), `categories[]`, `sizes[]`, `colors[]`, `created_at`.

## Admin catalog (🛡️)

| Method & path | Purpose |
|---|---|
| `GET /admin/products?status=draft` | All products incl. drafts/archived (+ same filters/pagination) |
| `POST /admin/products` | Create (nested `variants[]`, `images[]`, `category_ids[]`) |
| `GET/PATCH /admin/products/{id}` | Read / update (`status` draft·published·archived) |
| `DELETE /admin/products/{id}` | Archive (soft delete) |
| `POST /admin/products/{id}/variants` | Add variant |
| `PATCH/DELETE /admin/variants/{id}` | Update / delete variant (incl. `stock_quantity`, `is_active`) |
| `POST /admin/products/{id}/images`, `DELETE /admin/images/{id}` | Manage images (URL based for now) |
| `GET/POST /admin/categories`, `PATCH/DELETE /admin/categories/{id}` | Categories |
| `GET/POST /admin/brands`, `PATCH/DELETE /admin/brands/{id}` | Brands |

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"Admin@12345"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -X POST localhost:8000/api/v1/admin/products -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{
  "title": "Classic Tee", "status": "published",
  "images": [{"url": "https://placehold.co/600x800"}],
  "variants": [
    {"sku": "TEE-M-BLK", "size": "M", "color": "Black", "price": 99900, "compare_at_price": 149900, "stock_quantity": 20},
    {"sku": "TEE-L-BLK", "size": "L", "color": "Black", "price": 99900, "stock_quantity": 10}
  ]}'
```

Admin product view adds: `status`, `hsn_code`, `tax_rate_bps` (GST, 1800 = 18%), `sales_count`,
`updated_at`, and per-variant `stock_quantity`, `is_active`.

## System

`GET /health` (liveness) · `GET /ready` (DB check) - not under `/api/v1`.

## Roles

`customer` (default on register) · `staff` · `admin`. Staff and admin can use `/admin/*` today; admin-only
actions (user management, settings) arrive with later modules. Promote a user to admin via SQL or the seed script.
