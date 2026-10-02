import uuid

from slugify import slugify
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationFailed
from app.modules.catalog.filters import ProductFilters
from app.modules.catalog.models import (
    Brand,
    Category,
    Product,
    ProductImage,
    ProductStatus,
    ProductVariant,
)
from app.modules.catalog.repository import (
    BrandRepository,
    CategoryRepository,
    ImageRepository,
    ProductRepository,
    VariantRepository,
)
from app.modules.catalog.schemas import (
    BrandCreate,
    BrandUpdate,
    CategoryCreate,
    CategoryUpdate,
    ImageCreate,
    ProductCreate,
    ProductUpdate,
    VariantCreate,
    VariantUpdate,
)


class CatalogService:
    """All catalog business rules. Routers stay thin; repositories only run queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.products = ProductRepository(session)
        self.variants = VariantRepository(session)
        self.images = ImageRepository(session)
        self.categories = CategoryRepository(session)
        self.brands = BrandRepository(session)

    # ------------------------------------------------------------------ helpers
    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise ConflictError(
                "The change conflicts with existing data (duplicate slug/SKU or invalid reference)"
            ) from None

    @staticmethod
    async def _resolve_slug(exists, explicit: str | None, fallback_text: str, code: str) -> str:
        """Explicit slug must be free (409 otherwise); derived slug gets -2, -3... suffixes."""
        if explicit:
            slug = slugify(explicit)
            if not slug:
                raise ValidationFailed("Invalid slug", code="invalid_slug")
            if await exists(slug):
                raise ConflictError("Slug is already in use", code=code)
            return slug
        base = slugify(fallback_text) or "item"
        slug, n = base, 2
        while await exists(slug):
            slug = f"{base}-{n}"
            n += 1
        return slug

    async def _require_brand(self, brand_id: uuid.UUID) -> None:
        if await self.brands.get(brand_id) is None:
            raise ValidationFailed("Brand does not exist", code="brand_not_found")

    async def _load_categories(self, ids: list[uuid.UUID]) -> list[Category]:
        unique_ids = list(dict.fromkeys(ids))
        found = await self.categories.get_many(unique_ids)
        if len(found) != len(unique_ids):
            raise ValidationFailed("One or more categories do not exist", code="category_not_found")
        return found

    async def _check_skus(self, skus: list[str]) -> None:
        if len(set(skus)) != len(skus):
            raise ValidationFailed("Duplicate SKUs in request", code="duplicate_sku")
        for sku in skus:
            if await self.variants.sku_exists(sku):
                raise ConflictError(f"SKU '{sku}' already exists", code="sku_already_exists")

    @staticmethod
    def _build_variant(data: VariantCreate, position: int) -> ProductVariant:
        title = data.title or " / ".join(x for x in (data.size, data.color) if x) or data.sku
        return ProductVariant(
            sku=data.sku,
            title=title,
            size=data.size,
            color=data.color,
            price=data.price,
            compare_at_price=data.compare_at_price,
            stock_quantity=data.stock_quantity,
            is_active=data.is_active,
            position=position,
        )

    @staticmethod
    def _ensure_publishable(product: Product) -> None:
        if product.status == ProductStatus.published.value and not product.active_variants:
            raise ConflictError(
                "A product needs at least one active variant before it can be published",
                code="product_not_publishable",
            )

    # ------------------------------------------------------------------ storefront reads
    async def list_products(self, f: ProductFilters, *, offset: int, limit: int, public: bool):
        return await self.products.search(f, offset=offset, limit=limit, public=public)

    async def get_published_product(self, slug: str) -> Product:
        product = await self.products.get_published_by_slug(slug)
        if product is None:
            raise NotFoundError("Product not found", code="product_not_found")
        return product

    async def stats(self) -> dict[str, int]:
        return {"products": await self.products.count_published(), "brands": await self.brands.count()}

    # ------------------------------------------------------------------ products (admin)
    async def get_product(self, product_id: uuid.UUID) -> Product:
        product = await self.products.get(product_id)
        if product is None:
            raise NotFoundError("Product not found", code="product_not_found")
        return product

    async def create_product(self, data: ProductCreate) -> Product:
        if data.brand_id:
            await self._require_brand(data.brand_id)
        categories = await self._load_categories(data.category_ids)
        slug = await self._resolve_slug(
            self.products.slug_exists, data.slug, data.title, "slug_already_exists"
        )
        await self._check_skus([v.sku for v in data.variants])

        product = Product(
            title=data.title,
            slug=slug,
            description=data.description,
            brand_id=data.brand_id,
            status=data.status.value,
            thumbnail_url=data.thumbnail_url or (data.images[0].url if data.images else None),
            hsn_code=data.hsn_code,
            tax_rate_bps=data.tax_rate_bps,
        )
        product.categories = categories
        product.variants = [self._build_variant(v, i) for i, v in enumerate(data.variants)]
        product.images = [
            ProductImage(url=img.url, alt=img.alt, position=i) for i, img in enumerate(data.images)
        ]
        self._ensure_publishable(product)
        self.products.add(product)
        await self._commit()
        return await self.get_product(product.id)

    async def update_product(self, product_id: uuid.UUID, data: ProductUpdate) -> Product:
        product = await self.get_product(product_id)
        fields = data.model_dump(exclude_unset=True)

        if fields.get("brand_id"):
            await self._require_brand(fields["brand_id"])
        if "category_ids" in fields and fields["category_ids"] is not None:
            product.categories = await self._load_categories(fields["category_ids"])
        if fields.get("slug") and slugify(fields["slug"]) != product.slug:
            product.slug = await self._resolve_slug(
                self.products.slug_exists, fields["slug"], "", "slug_already_exists"
            )

        for key in ("description", "brand_id", "thumbnail_url", "hsn_code"):  # nullable
            if key in fields:
                setattr(product, key, fields[key])
        for key in ("title", "tax_rate_bps"):  # not nullable
            if fields.get(key) is not None:
                setattr(product, key, fields[key])
        if fields.get("status") is not None:
            product.status = fields["status"].value

        self._ensure_publishable(product)
        await self._commit()
        return await self.get_product(product_id)

    async def archive_product(self, product_id: uuid.UUID) -> None:
        """Soft delete: keeps history for past orders; hides the product from the storefront."""
        product = await self.get_product(product_id)
        product.status = ProductStatus.archived.value
        await self._commit()

    # ------------------------------------------------------------------ variants & images
    async def add_variant(self, product_id: uuid.UUID, data: VariantCreate) -> ProductVariant:
        await self.get_product(product_id)
        await self._check_skus([data.sku])
        position = await self.variants.count_for_product(product_id)
        variant = self._build_variant(data, position)
        variant.product_id = product_id
        self.variants.add(variant)
        await self._commit()
        return variant

    async def update_variant(self, variant_id: uuid.UUID, data: VariantUpdate) -> ProductVariant:
        variant = await self.variants.get(variant_id)
        if variant is None:
            raise NotFoundError("Variant not found", code="variant_not_found")
        fields = data.model_dump(exclude_unset=True)
        if fields.get("sku") and await self.variants.sku_exists(fields["sku"], variant.id):
            raise ConflictError(f"SKU '{fields['sku']}' already exists", code="sku_already_exists")
        for key in ("size", "color", "compare_at_price"):  # nullable
            if key in fields:
                setattr(variant, key, fields[key])
        for key in ("sku", "title", "price", "stock_quantity", "is_active"):
            if fields.get(key) is not None:
                setattr(variant, key, fields[key])
        if variant.compare_at_price is not None and variant.compare_at_price < variant.price:
            raise ValidationFailed("compare_at_price must be >= price", code="invalid_price")
        await self.session.flush()
        await self._ensure_product_keeps_active_variant(variant.product_id)
        await self._commit()
        return variant

    async def delete_variant(self, variant_id: uuid.UUID) -> None:
        variant = await self.variants.get(variant_id)
        if variant is None:
            raise NotFoundError("Variant not found", code="variant_not_found")
        product_id = variant.product_id
        await self.session.delete(variant)
        await self.session.flush()
        await self._ensure_product_keeps_active_variant(product_id)
        await self._commit()

    async def _ensure_product_keeps_active_variant(self, product_id: uuid.UUID) -> None:
        product = await self.session.get(Product, product_id)
        if (
            product is not None
            and product.status == ProductStatus.published.value
            and await self.variants.count_for_product(product_id, active_only=True) == 0
        ):
            await self.session.rollback()
            raise ConflictError(
                "A published product needs at least one active variant; unpublish it first",
                code="product_not_publishable",
            )

    async def add_image(self, product_id: uuid.UUID, data: ImageCreate) -> ProductImage:
        product = await self.get_product(product_id)
        image = ProductImage(
            product_id=product_id,
            url=data.url,
            alt=data.alt,
            position=await self.images.count_for_product(product_id),
        )
        self.session.add(image)
        if not product.thumbnail_url:
            product.thumbnail_url = data.url
        await self._commit()
        return image

    async def delete_image(self, image_id: uuid.UUID) -> None:
        image = await self.images.get(image_id)
        if image is None:
            raise NotFoundError("Image not found", code="image_not_found")
        await self.session.delete(image)
        await self._commit()

    # ------------------------------------------------------------------ categories
    async def list_categories(self, *, active_only: bool) -> list[Category]:
        return await self.categories.list(active_only=active_only)

    async def create_category(self, data: CategoryCreate) -> Category:
        if data.parent_id and await self.categories.get(data.parent_id) is None:
            raise ValidationFailed("Parent category does not exist", code="category_not_found")
        slug = await self._resolve_slug(
            self.categories.slug_exists, data.slug, data.name, "slug_already_exists"
        )
        category = Category(
            name=data.name,
            slug=slug,
            description=data.description,
            image_url=data.image_url,
            parent_id=data.parent_id,
            position=data.position,
            is_active=data.is_active,
        )
        self.session.add(category)
        await self._commit()
        return category

    async def update_category(self, category_id: uuid.UUID, data: CategoryUpdate) -> Category:
        category = await self.categories.get(category_id)
        if category is None:
            raise NotFoundError("Category not found", code="category_not_found")
        fields = data.model_dump(exclude_unset=True)
        if "parent_id" in fields and fields["parent_id"] is not None:
            await self._check_no_cycle(category.id, fields["parent_id"])
        if fields.get("slug") and slugify(fields["slug"]) != category.slug:
            category.slug = await self._resolve_slug(
                self.categories.slug_exists, fields["slug"], "", "slug_already_exists"
            )
        for key in ("description", "image_url", "parent_id"):  # nullable
            if key in fields:
                setattr(category, key, fields[key])
        for key in ("name", "position", "is_active"):
            if fields.get(key) is not None:
                setattr(category, key, fields[key])
        await self._commit()
        return category

    async def _check_no_cycle(self, category_id: uuid.UUID, new_parent_id: uuid.UUID) -> None:
        current: uuid.UUID | None = new_parent_id
        seen: set[uuid.UUID] = set()
        while current is not None:
            if current == category_id:
                raise ValidationFailed(
                    "A category cannot be its own ancestor", code="category_cycle"
                )
            if current in seen:
                break
            seen.add(current)
            parent = await self.categories.get(current)
            if parent is None:
                raise ValidationFailed("Parent category does not exist", code="category_not_found")
            current = parent.parent_id

    async def delete_category(self, category_id: uuid.UUID) -> None:
        category = await self.categories.get(category_id)
        if category is None:
            raise NotFoundError("Category not found", code="category_not_found")
        await self.session.delete(category)
        await self._commit()

    # ------------------------------------------------------------------ brands
    async def list_brands(self) -> list[Brand]:
        return await self.brands.list()

    async def create_brand(self, data: BrandCreate) -> Brand:
        if await self.brands.name_exists(data.name):
            raise ConflictError("Brand name already exists", code="brand_already_exists")
        slug = await self._resolve_slug(
            self.brands.slug_exists, data.slug, data.name, "slug_already_exists"
        )
        brand = Brand(name=data.name, slug=slug, logo_url=data.logo_url)
        self.session.add(brand)
        await self._commit()
        return brand

    async def update_brand(self, brand_id: uuid.UUID, data: BrandUpdate) -> Brand:
        brand = await self.brands.get(brand_id)
        if brand is None:
            raise NotFoundError("Brand not found", code="brand_not_found")
        fields = data.model_dump(exclude_unset=True)
        if fields.get("name") and await self.brands.name_exists(fields["name"], brand.id):
            raise ConflictError("Brand name already exists", code="brand_already_exists")
        if fields.get("slug") and slugify(fields["slug"]) != brand.slug:
            brand.slug = await self._resolve_slug(
                self.brands.slug_exists, fields["slug"], "", "slug_already_exists"
            )
        if "logo_url" in fields:
            brand.logo_url = fields["logo_url"]
        if fields.get("name"):
            brand.name = fields["name"]
        await self._commit()
        return brand

    async def delete_brand(self, brand_id: uuid.UUID) -> None:
        brand = await self.brands.get(brand_id)
        if brand is None:
            raise NotFoundError("Brand not found", code="brand_not_found")
        await self.session.delete(brand)
        await self._commit()
