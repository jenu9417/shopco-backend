# Frontend Integration Guide

For the developer building the Next.js storefront (and, later, the admin UI).

## 1. Basics

| Thing | Value |
|---|---|
| Base URL (local) | `http://localhost:8000/api/v1` |
| Interactive docs | `http://localhost:8000/docs` |
| OpenAPI spec | `http://localhost:8000/openapi.json` |
| Content type | JSON (`Content-Type: application/json`) |
| IDs | UUID strings |
| Timestamps | ISO-8601 UTC |
| **Money** | **Integer paise** + `currency` (`"INR"`). `129900` = ₹1,299.00. Never use floats. |

Format money in the UI:

```ts
export const formatINR = (paise: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(paise / 100);
```

API surfaces:

- `/api/v1/auth/*` - shared by storefront and admin
- `/api/v1/store/*` - public storefront (no auth needed for catalog)
- `/api/v1/admin/*` - staff/admin only (needs a staff/admin access token)

## 2. Generate a typed client (recommended)

The OpenAPI spec is the contract. Generate types so request/response shapes never drift:

```bash
npm i -D openapi-typescript && npm i openapi-fetch
npx openapi-typescript http://localhost:8000/openapi.json -o src/lib/api/schema.d.ts
```

```ts
import createClient from "openapi-fetch";
import type { paths } from "./schema";

export const api = createClient<paths>({ baseUrl: process.env.NEXT_PUBLIC_API_URL, credentials: "include" });

const { data, error } = await api.GET("/api/v1/store/products", {
  params: { query: { sort: "newest", page_size: 8 } },
});
```

Alternatives: `orval` (React Query hooks), `@hey-api/openapi-ts`. Operation ids are stable and readable
(e.g. `store_catalog_list_products`, `auth_login`). Re-run generation when the backend changes.

## 3. Authentication

Two tokens:

- **Access token** (JWT, 15 min): returned in the JSON body. Send as `Authorization: Bearer <token>`.
  Keep it **in memory** (a variable / React state / context), not in localStorage.
- **Refresh token** (30 days): set by the server as an **httpOnly cookie** - JS can't read it.
  It is only sent to `/api/v1/auth/*`. It **rotates on every refresh**.

Flow:

1. `POST /auth/register` or `POST /auth/login` → `{access_token, expires_in, user}` + sets the cookie.
2. Call the API with `Authorization: Bearer <access_token>`.
3. When any call returns **401 with `error.code == "token_expired"`** → `POST /auth/refresh` (no body;
   the browser sends the cookie) → new access token → retry the original request once.
4. If refresh returns 401 → the session is over → send the user to login.
5. On app load, call `POST /auth/refresh` once to restore the session (access token is lost on page reload).
6. `POST /auth/logout` revokes the refresh token and clears the cookie.

**Cookies require `credentials: "include"`** on every fetch to the API (CORS is already configured for that).

> **Refresh must be single-flight.** The server detects refresh-token *reuse* (theft signal) and revokes
> the whole session. If two tabs/requests refresh at the same moment with the same cookie, one looks like
> a replay. Use one shared in-flight promise per tab (example below).

### Minimal client with auto-refresh

```ts
// lib/api.ts
const BASE = process.env.NEXT_PUBLIC_API_URL + "/api/v1";
let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;

export const setAccessToken = (t: string | null) => (accessToken = t);

async function refresh(): Promise<boolean> {
  refreshing ??= fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "include" })
    .then(async (r) => {
      if (!r.ok) { accessToken = null; return false; }
      accessToken = (await r.json()).access_token;
      return true;
    })
    .finally(() => { refreshing = null; });
  return refreshing;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init.headers,
    },
  });
  if (res.status === 401 && retry) {
    const err = await res.clone().json().catch(() => null);
    if (err?.error?.code === "token_expired" && (await refresh())) return apiFetch<T>(path, init, false);
  }
  if (!res.ok) throw await ApiError.from(res);
  return res.status === 204 ? (undefined as T) : res.json();
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown, public requestId?: string) {
    super(message);
  }
  static async from(res: Response) {
    const body = await res.json().catch(() => null);
    const e = body?.error;
    return new ApiError(res.status, e?.code ?? "unknown", e?.message ?? res.statusText, e?.details, e?.request_id);
  }
}
```

### Recommended: proxy the API through Next.js (same origin)

This avoids cross-site cookie/CORS headaches in production and makes cookies work in server components.

```js
// next.config.js
module.exports = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.API_INTERNAL_URL}/api/:path*` }];
  },
};
```

Then use `BASE = "/api/v1"` in the browser. The refresh cookie path (`/api/v1/auth`) lines up automatically.

If you do **not** proxy and the API is on a different *site* in production (e.g. `shop.com` vs `api.other.com`),
the backend needs `COOKIE_SAMESITE=none` + `COOKIE_SECURE=true` (HTTPS), and `CORS_ORIGINS` must list your exact origin.
Same-site subdomains (`shop.com` ↔ `api.shop.com`) work with the default `lax`; set `COOKIE_DOMAIN=.shop.com`.

## 4. Errors (uniform)

Every non-2xx response:

```json
{ "error": { "code": "sku_already_exists", "message": "SKU 'TEE-M' already exists",
             "details": null, "request_id": "9c1e…" } }
```

- **Branch on `code`**, never on `message` (message is human text and may change).
- Validation errors (422) have `code: "validation_error"` and `details: [{field, message, type}]` - map `field`
  straight to form inputs (e.g. `"password"`, `"variants.0.price"`).
- Include `request_id` when reporting bugs; it is also in the `X-Request-ID` response header
  (you can send your own `X-Request-ID` to correlate logs).

Common codes:

| HTTP | code | Meaning / what to do |
|---|---|---|
| 401 | `not_authenticated` | No/missing bearer token → login |
| 401 | `token_expired` | Access token expired → refresh, retry once |
| 401 | `invalid_token` | Bad token → login |
| 401 | `invalid_credentials` | Wrong email/password |
| 401 | `refresh_token_missing` / `invalid_refresh_token` / `refresh_token_expired` / `refresh_token_reused` | Session over → login |
| 403 | `insufficient_permissions` | Logged in but not staff/admin |
| 403 | `account_disabled` | Account deactivated |
| 404 | `product_not_found`, `not_found`, … | |
| 409 | `email_already_registered`, `sku_already_exists`, `slug_already_exists`, `product_not_publishable`, `conflict` | |
| 422 | `validation_error`, `invalid_price_range` | Fix input |
| 429 | `rate_limited` | Honour the `Retry-After` header (seconds) |
| 500 | `internal_error` | Show generic error; report `request_id` |

## 5. Lists: pagination, filtering, sorting

Paginated endpoints return:

```json
{ "items": [...], "total": 42, "page": 1, "page_size": 20, "pages": 3 }
```

Query: `?page=1&page_size=20` (page_size max 100).

`GET /store/products` filters (all optional, combine freely):

| Param | Example | Notes |
|---|---|---|
| `q` | `q=tee` | title search |
| `brand` | `brand=zara&brand=gucci` | brand **slug**, repeatable (OR) |
| `category` | `category=t-shirts` | category **slug**, repeatable (OR) |
| `size` | `size=M&size=L` | case-insensitive, matches an active variant |
| `color` | `color=black` | case-insensitive |
| `min_price`, `max_price` | `min_price=100000` | **paise**; compares the product's lowest price |
| `sort` | `sort=newest` | `newest` · `best_selling` · `price_asc` · `price_desc` · `rating` |

Size + colour together must match the **same** variant.

## 6. Homepage → endpoint map (SHOP.CO design)

| UI element | Call |
|---|---|
| Header search box | `GET /store/products?q=<text>&page_size=5` (suggestions) · full results page: same without small page_size |
| "Shop" menu / category links | `GET /store/categories` (flat list; build a tree with `parent_id`) |
| Brand strip (Versace, Zara, Gucci, Prada, Calvin Klein) | `GET /store/brands` (`logo_url` may be null → render the name) |
| Hero stats (200+ brands, 2,000+ products) | `GET /store/stats` → `{products, brands}`. (Happy-customers count is not exposed yet - hard-code/marketing copy until the reviews/orders modules exist.) |
| **New Arrivals** | `GET /store/products?sort=newest&page_size=4` |
| **Top Selling** | `GET /store/products?sort=best_selling&page_size=4` |
| Product card | uses `ProductListItem`: `thumbnail_url`, `title`, `rating_avg`, `price`, `compare_at_price`, `discount_percent` (show "-20%" badge when > 0) |
| "On Sale" page | `GET /store/products?sort=newest` and filter client-side on `discount_percent > 0` for now (a server-side `on_sale` filter is a trivial add - ask) |
| Product page | `GET /store/products/{slug}` → images, variants, `sizes`, `colors`, `description` |
| Size/colour picker | from `variants[]` (each has `size`, `color`, `price`, `in_stock`); pick the variant → send its `id` to the cart (cart module coming) |
| Promo banner ("Sign up and get 20% off") | static for now; discount codes arrive with the pricing module |
| Cart badge, checkout, orders | **not built yet** (next modules) |

Product card fields: `price` is the cheapest active variant's price; show "From ₹x" if variants differ.
Out of stock → `in_stock: false` (disable add-to-cart).

Product images from the seed are placeholders. Real image upload (presigned S3/R2 URLs) is on the roadmap;
until then admins attach image URLs.

## 7. Next.js examples

Server component (SSR/ISR) listing:

```tsx
// app/page.tsx
const API = process.env.API_INTERNAL_URL + "/api/v1";

async function getProducts(sort: string) {
  const res = await fetch(`${API}/store/products?sort=${sort}&page_size=4`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error("Failed to load products");
  return res.json() as Promise<{ items: ProductListItem[]; total: number }>;
}

export default async function Home() {
  const [fresh, top] = await Promise.all([getProducts("newest"), getProducts("best_selling")]);
  /* render <ProductGrid title="New Arrivals" items={fresh.items} /> … */
}
```

Public catalog endpoints need no auth, so they are safe to call from server components and to cache.
Categories/brands/stats also send `Cache-Control: public, max-age=60`.

Login form:

```ts
const r = await apiFetch<AuthResponse>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
setAccessToken(r.access_token);   // keep r.user in your auth context
```

Show field errors from a 422:

```ts
catch (e) {
  if (e instanceof ApiError && e.code === "validation_error")
    (e.details as {field: string; message: string}[]).forEach(d => setError(d.field as any, { message: d.message }));
}
```

## 8. Rules the backend enforces (so the UI can rely on them)

- Password: 8-128 chars with at least one letter and one digit. Emails are lower-cased.
- Phone (optional): digits with optional leading `+`, 10-15 digits.
- Login: 10 attempts/minute/IP, register: 10/hour/IP (`429` + `Retry-After`).
- Only `published` products appear on `/store/*`. A product needs ≥1 active variant to be published.
- Prices are recomputed server-side at checkout (never trust client totals).

## 9. Working before everything is built

- Run the seed (`python -m scripts.seed`) to get 8 demo products across the 5 categories and 5 brands.
- Swagger UI (`/docs`) has an **Authorize** button: log in via `POST /auth/login`, paste the `access_token`.
- Staff/admin endpoints can be exercised with the seeded admin account.

## 10. Change policy

- Additive changes (new fields/endpoints) are non-breaking: ignore unknown fields.
- Breaking changes go under a new prefix (`/api/v2`), `v1` stays until you migrate.
- Regenerate the typed client whenever the backend deploys.
