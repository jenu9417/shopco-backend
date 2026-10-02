"""Admin endpoints (staff/admin only). Prefix: /api/v1/admin"""

import uuid

from fastapi import APIRouter, Depends, Query

from app.core.pagination import Page, PageDep, make_page
from app.db.session import DbSession
from app.modules.auth.deps import require_roles
from app.modules.auth.models import Role
from app.modules.catalog.filters import ProductFilters, product_filters
from app.modules.catalog.models import ProductStatus
from app.modules.catalog.schemas import (
    AdminProductOut,
    AdminVariantOut,
    BrandCreate,
    BrandOut,
    BrandUpdate,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ImageCreate,
    ImageOut,
    ProductCreate,
    ProductUpdate,
    VariantCreate,
    VariantUpdate,
)
from app.modules.catalog.service import CatalogService

router = APIRouter(
    prefix="/admin",
    tags=["admin-catalog"],
    dependencies=[Depends(require_roles(Role.staff, Role.admin))],
)


# ------------------------------------------------------------------ products
@router.get("/products", response_model=Page[AdminProductOut], summary="List all products")
async def list_products(
    db: DbSession,
    params: PageDep,
    status: ProductStatus | None = Query(None, description="draft | published | archived"),
    filters: ProductFilters = Depends(product_filters),
):
    filters.status = status.value if status else None
    items, total = await CatalogService(db).list_products(
        filters, offset=params.offset, limit=params.page_size, public=False
    )
    return make_page([AdminProductOut.model_validate(p) for p in items], total, params)


@router.post("/products", response_model=AdminProductOut, status_code=201, summary="Create product")
async def create_product(body: ProductCreate, db: DbSession):
    return await CatalogService(db).create_product(body)


@router.get("/products/{product_id}", response_model=AdminProductOut, summary="Get product")
async def get_product(product_id: uuid.UUID, db: DbSession):
    return await CatalogService(db).get_product(product_id)


@router.patch("/products/{product_id}", response_model=AdminProductOut, summary="Update product")
async def update_product(product_id: uuid.UUID, body: ProductUpdate, db: DbSession):
    return await CatalogService(db).update_product(product_id, body)


@router.delete("/products/{product_id}", status_code=204, summary="Archive product (soft delete)")
async def archive_product(product_id: uuid.UUID, db: DbSession):
    await CatalogService(db).archive_product(product_id)


# ------------------------------------------------------------------ variants & images
@router.post(
    "/products/{product_id}/variants",
    response_model=AdminVariantOut,
    status_code=201,
    summary="Add a variant",
)
async def add_variant(product_id: uuid.UUID, body: VariantCreate, db: DbSession):
    return await CatalogService(db).add_variant(product_id, body)


@router.patch("/variants/{variant_id}", response_model=AdminVariantOut, summary="Update a variant")
async def update_variant(variant_id: uuid.UUID, body: VariantUpdate, db: DbSession):
    return await CatalogService(db).update_variant(variant_id, body)


@router.delete("/variants/{variant_id}", status_code=204, summary="Delete a variant")
async def delete_variant(variant_id: uuid.UUID, db: DbSession):
    await CatalogService(db).delete_variant(variant_id)


@router.post(
    "/products/{product_id}/images",
    response_model=ImageOut,
    status_code=201,
    summary="Attach an image by URL",
)
async def add_image(product_id: uuid.UUID, body: ImageCreate, db: DbSession):
    return await CatalogService(db).add_image(product_id, body)


@router.delete("/images/{image_id}", status_code=204, summary="Delete an image")
async def delete_image(image_id: uuid.UUID, db: DbSession):
    await CatalogService(db).delete_image(image_id)


# ------------------------------------------------------------------ categories
@router.get("/categories", response_model=list[CategoryOut], summary="All categories")
async def list_categories(db: DbSession):
    return await CatalogService(db).list_categories(active_only=False)


@router.post("/categories", response_model=CategoryOut, status_code=201, summary="Create category")
async def create_category(body: CategoryCreate, db: DbSession):
    return await CatalogService(db).create_category(body)


@router.patch("/categories/{category_id}", response_model=CategoryOut, summary="Update category")
async def update_category(category_id: uuid.UUID, body: CategoryUpdate, db: DbSession):
    return await CatalogService(db).update_category(category_id, body)


@router.delete("/categories/{category_id}", status_code=204, summary="Delete category")
async def delete_category(category_id: uuid.UUID, db: DbSession):
    await CatalogService(db).delete_category(category_id)


# ------------------------------------------------------------------ brands
@router.get("/brands", response_model=list[BrandOut], summary="All brands")
async def list_brands(db: DbSession):
    return await CatalogService(db).list_brands()


@router.post("/brands", response_model=BrandOut, status_code=201, summary="Create brand")
async def create_brand(body: BrandCreate, db: DbSession):
    return await CatalogService(db).create_brand(body)


@router.patch("/brands/{brand_id}", response_model=BrandOut, summary="Update brand")
async def update_brand(brand_id: uuid.UUID, body: BrandUpdate, db: DbSession):
    return await CatalogService(db).update_brand(brand_id, body)


@router.delete("/brands/{brand_id}", status_code=204, summary="Delete brand")
async def delete_brand(brand_id: uuid.UUID, db: DbSession):
    await CatalogService(db).delete_brand(brand_id)
