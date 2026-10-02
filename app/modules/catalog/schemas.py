import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.catalog.models import ProductStatus

# ---------------------------------------------------------------- shared small types


class BrandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    parent_id: uuid.UUID | None
    description: str | None
    image_url: str | None
    position: int
    is_active: bool


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    url: str
    alt: str | None
    position: int


class VariantOut(BaseModel):
    """Storefront view of a variant. Prices are integer paise (12999 = ₹129.99)."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sku: str
    title: str
    size: str | None
    color: str | None
    price: int
    compare_at_price: int | None
    currency: str
    in_stock: bool


class AdminVariantOut(VariantOut):
    stock_quantity: int
    is_active: bool
    position: int


# ---------------------------------------------------------------- products (read)


class ProductListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    slug: str
    thumbnail_url: str | None
    brand: BrandOut | None
    price: int | None = Field(description="Price of the cheapest active variant, in paise")
    compare_at_price: int | None
    discount_percent: int
    currency: str
    rating_avg: float
    rating_count: int
    in_stock: bool


class ProductDetail(ProductListItem):
    description: str | None
    images: list[ImageOut]
    variants: list[VariantOut]
    categories: list[CategoryOut]
    sizes: list[str]
    colors: list[str]
    created_at: datetime


class AdminProductOut(ProductDetail):
    variants: list[AdminVariantOut]  # type: ignore[assignment]
    status: ProductStatus
    hsn_code: str | None
    tax_rate_bps: int
    sales_count: int
    updated_at: datetime


# ---------------------------------------------------------------- admin write models


class VariantCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    title: str | None = Field(None, max_length=255, description="Defaults to 'size / color'")
    size: str | None = Field(None, max_length=20)
    color: str | None = Field(None, max_length=30)
    price: int = Field(ge=0, description="Paise")
    compare_at_price: int | None = Field(None, ge=0, description="MRP in paise")
    stock_quantity: int = Field(0, ge=0)
    is_active: bool = True

    @model_validator(mode="after")
    def _compare_at_not_below_price(self):
        if self.compare_at_price is not None and self.compare_at_price < self.price:
            raise ValueError("compare_at_price must be >= price")
        return self


class VariantUpdate(BaseModel):
    sku: str | None = Field(None, min_length=1, max_length=64)
    title: str | None = Field(None, max_length=255)
    size: str | None = Field(None, max_length=20)
    color: str | None = Field(None, max_length=30)
    price: int | None = Field(None, ge=0)
    compare_at_price: int | None = Field(None, ge=0)
    stock_quantity: int | None = Field(None, ge=0)
    is_active: bool | None = None


class ImageCreate(BaseModel):
    url: str = Field(max_length=500)
    alt: str | None = Field(None, max_length=255)


class ProductCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=280, description="Auto-generated from title if omitted")
    description: str | None = None
    brand_id: uuid.UUID | None = None
    category_ids: list[uuid.UUID] = []
    status: ProductStatus = ProductStatus.draft
    thumbnail_url: str | None = Field(None, max_length=500)
    hsn_code: str | None = Field(None, max_length=10)
    tax_rate_bps: int = Field(0, ge=0, le=10000)
    images: list[ImageCreate] = []
    variants: list[VariantCreate] = []


class ProductUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=280)
    description: str | None = None
    brand_id: uuid.UUID | None = None
    category_ids: list[uuid.UUID] | None = None
    status: ProductStatus | None = None
    thumbnail_url: str | None = Field(None, max_length=500)
    hsn_code: str | None = Field(None, max_length=10)
    tax_rate_bps: int | None = Field(None, ge=0, le=10000)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(None, max_length=140)
    description: str | None = None
    image_url: str | None = Field(None, max_length=500)
    parent_id: uuid.UUID | None = None
    position: int = 0
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    slug: str | None = Field(None, max_length=140)
    description: str | None = None
    image_url: str | None = Field(None, max_length=500)
    parent_id: uuid.UUID | None = None
    position: int | None = None
    is_active: bool | None = None


class BrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(None, max_length=140)
    logo_url: str | None = Field(None, max_length=500)


class BrandUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    slug: str | None = Field(None, max_length=140)
    logo_url: str | None = Field(None, max_length=500)


class StoreStats(BaseModel):
    products: int
    brands: int
