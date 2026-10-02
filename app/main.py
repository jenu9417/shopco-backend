from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.api.health import router as health_router
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import ErrorResponse, register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import register_middleware
from app.db.session import engine

OPENAPI_TAGS = [
    {"name": "auth", "description": "Register, login, token refresh, profile. Shared by storefront and admin."},
    {"name": "store-catalog", "description": "Public storefront: products, categories, brands. No auth."},
    {"name": "admin-catalog", "description": "Catalog management. Requires a staff/admin access token."},
    {"name": "system", "description": "Health probes."},
]

API_DESCRIPTION = """
E-commerce backend API.

* **Money** is always integer *paise* (`129900` = ₹1,299.00) with a `currency` field.
* **Errors** always look like `{"error": {"code", "message", "details", "request_id"}}` - branch on `code`.
* **Auth**: send `Authorization: Bearer <access_token>`. The refresh token lives in an httpOnly cookie.
* Full integration guide: `docs/FRONTEND_INTEGRATION.md`.
"""


def _operation_id(route: APIRoute) -> str:
    # Stable, readable ids -> nice generated client method names (e.g. storeCatalogListProducts)
    tag = route.tags[0] if route.tags else "default"
    return f"{str(tag).replace('-', '_')}_{route.name}"


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.debug)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        generate_unique_id_function=_operation_id,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )

    register_exception_handlers(app)
    register_middleware(app)
    # CORS is added last so it is the outermost middleware (error responses get CORS headers too)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,  # required for the httpOnly refresh cookie
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )

    app.include_router(health_router)
    app.include_router(
        api_router,
        prefix=settings.api_prefix,
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
    )
    return app


app = create_app()
