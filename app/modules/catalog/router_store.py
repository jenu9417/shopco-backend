"""Public storefront endpoints (no auth). Prefix: /api/v1/store"""

from fastapi import APIRouter, Depends, Response

from app.core.pagination import Page, PageDep, make_page
from app.db.session import DbSession
from app.modules.catalog.filters import ProductFilters, product_filters
from app.modules.catalog.schemas import (
    BrandOut,
    CategoryOut,
    ProductDetail,
    ProductListItem,
    StoreStats,
)
from app.modules.catalog.service import CatalogService

router = APIRouter(prefix="/store", tags=["store-catalog"])

_CACHE_1_MIN = "public, max-age=60, stale-while-revalidate=120"


@router.get(
    "/products",
    response_model=Page[ProductListItem],
    summary="List/search/filter published products",
    description=(
        "Use `sort=newest` for **New Arrivals** and `sort=best_selling` for **Top Selling**. "
        "Repeat a param for multiple values (`?brand=zara&brand=gucci`). Prices are in paise."
    ),
)
async def list_products(
    db: DbSession,
    params: PageDep,
    filters: ProductFilters = Depends(product_filters),
):
    items, total = await CatalogService(db).list_products(
        filters, offset=params.offset, limit=params.page_size, public=True
    )
    return make_page([ProductListItem.model_validate(p) for p in items], total, params)


@router.get(
    "/products/{slug}",
    response_model=ProductDetail,
    summary="Product detail by slug",
)
async def get_product(slug: str, db: DbSession):
    return await CatalogService(db).get_published_product(slug)


@router.get("/categories", response_model=list[CategoryOut], summary="Active categories (flat)")
async def list_categories(response: Response, db: DbSession):
    response.headers["Cache-Control"] = _CACHE_1_MIN
    return await CatalogService(db).list_categories(active_only=True)


@router.get("/brands", response_model=list[BrandOut], summary="All brands")
async def list_brands(response: Response, db: DbSession):
    response.headers["Cache-Control"] = _CACHE_1_MIN
    return await CatalogService(db).list_brands()


@router.get("/stats", response_model=StoreStats, summary="Counts for homepage hero stats")
async def stats(response: Response, db: DbSession):
    response.headers["Cache-Control"] = _CACHE_1_MIN
    return await CatalogService(db).stats()
