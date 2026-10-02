import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.filters import ProductFilters, ProductSort
from app.modules.catalog.models import (
    Brand,
    Category,
    Product,
    ProductImage,
    ProductStatus,
    ProductVariant,
    product_categories,
)


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, product: Product) -> None:
        self.session.add(product)

    async def get(self, product_id: uuid.UUID) -> Product | None:
        # populate_existing => always reload relationships (needed after create/update commits)
        stmt = (
            select(Product)
            .where(Product.id == product_id)
            .execution_options(populate_existing=True)
        )
        return (await self.session.scalars(stmt)).first()

    async def get_published_by_slug(self, slug: str) -> Product | None:
        stmt = select(Product).where(
            Product.slug == slug, Product.status == ProductStatus.published.value
        )
        return (await self.session.scalars(stmt)).first()

    async def slug_exists(self, slug: str) -> bool:
        return bool(await self.session.scalar(select(func.count()).where(Product.slug == slug)))

    @staticmethod
    def _apply_filters(stmt, f: ProductFilters, price_sq, *, public: bool):
        stmt = stmt.outerjoin(price_sq, price_sq.c.pid == Product.id)
        if public:
            stmt = stmt.where(Product.status == ProductStatus.published.value)
        elif f.status:
            stmt = stmt.where(Product.status == f.status)
        if f.q:
            stmt = stmt.where(Product.title.icontains(f.q, autoescape=True))
        if f.brand:
            stmt = stmt.where(
                Product.brand_id.in_(select(Brand.id).where(Brand.slug.in_(f.brand)))
            )
        if f.category:
            cat_sub = (
                select(product_categories.c.product_id)
                .join(Category, Category.id == product_categories.c.category_id)
                .where(Category.slug.in_(f.category))
            )
            stmt = stmt.where(Product.id.in_(cat_sub))
        if f.size or f.color:
            var_sub = select(ProductVariant.product_id).where(ProductVariant.is_active.is_(True))
            if f.size:
                var_sub = var_sub.where(
                    func.lower(ProductVariant.size).in_([s.lower() for s in f.size])
                )
            if f.color:
                var_sub = var_sub.where(
                    func.lower(ProductVariant.color).in_([c.lower() for c in f.color])
                )
            stmt = stmt.where(Product.id.in_(var_sub))
        if f.min_price is not None:
            stmt = stmt.where(price_sq.c.min_price >= f.min_price)
        if f.max_price is not None:
            stmt = stmt.where(price_sq.c.min_price <= f.max_price)
        return stmt

    async def search(
        self, f: ProductFilters, *, offset: int, limit: int, public: bool
    ) -> tuple[list[Product], int]:
        price_sq = (
            select(
                ProductVariant.product_id.label("pid"),
                func.min(ProductVariant.price).label("min_price"),
            )
            .where(ProductVariant.is_active.is_(True))
            .group_by(ProductVariant.product_id)
            .subquery()
        )
        count_stmt = self._apply_filters(
            select(func.count(Product.id)).select_from(Product), f, price_sq, public=public
        )
        total = (await self.session.scalar(count_stmt)) or 0

        order_by = {
            ProductSort.newest: [Product.created_at.desc()],
            ProductSort.best_selling: [Product.sales_count.desc()],
            ProductSort.rating: [Product.rating_avg.desc(), Product.rating_count.desc()],
            ProductSort.price_asc: [price_sq.c.min_price.asc().nulls_last()],
            ProductSort.price_desc: [price_sq.c.min_price.desc().nulls_last()],
        }[f.sort]
        stmt = self._apply_filters(select(Product).select_from(Product), f, price_sq, public=public)
        stmt = stmt.order_by(*order_by, Product.id).offset(offset).limit(limit)
        items = list((await self.session.scalars(stmt)).all())
        return items, total

    async def count_published(self) -> int:
        stmt = select(func.count(Product.id)).where(
            Product.status == ProductStatus.published.value
        )
        return (await self.session.scalar(stmt)) or 0


class VariantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, variant: ProductVariant) -> None:
        self.session.add(variant)

    async def get(self, variant_id: uuid.UUID) -> ProductVariant | None:
        return await self.session.get(ProductVariant, variant_id)

    async def sku_exists(self, sku: str, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(func.count()).where(ProductVariant.sku == sku)
        if exclude_id:
            stmt = stmt.where(ProductVariant.id != exclude_id)
        return bool(await self.session.scalar(stmt))

    async def count_for_product(self, product_id: uuid.UUID, *, active_only: bool = False) -> int:
        stmt = select(func.count()).where(ProductVariant.product_id == product_id)
        if active_only:
            stmt = stmt.where(ProductVariant.is_active.is_(True))
        return (await self.session.scalar(stmt)) or 0


class ImageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, image_id: uuid.UUID) -> ProductImage | None:
        return await self.session.get(ProductImage, image_id)

    async def count_for_product(self, product_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(ProductImage.product_id == product_id)
        return (await self.session.scalar(stmt)) or 0


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, category_id: uuid.UUID) -> Category | None:
        return await self.session.get(Category, category_id)

    async def get_many(self, ids: list[uuid.UUID]) -> list[Category]:
        if not ids:
            return []
        return list((await self.session.scalars(select(Category).where(Category.id.in_(ids)))).all())

    async def list(self, *, active_only: bool) -> list[Category]:
        stmt = select(Category).order_by(Category.position, Category.name)
        if active_only:
            stmt = stmt.where(Category.is_active.is_(True))
        return list((await self.session.scalars(stmt)).all())

    async def slug_exists(self, slug: str) -> bool:
        return bool(await self.session.scalar(select(func.count()).where(Category.slug == slug)))


class BrandRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, brand_id: uuid.UUID) -> Brand | None:
        return await self.session.get(Brand, brand_id)

    async def list(self) -> list[Brand]:
        return list((await self.session.scalars(select(Brand).order_by(Brand.name))).all())

    async def slug_exists(self, slug: str) -> bool:
        return bool(await self.session.scalar(select(func.count()).where(Brand.slug == slug)))

    async def name_exists(self, name: str, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(func.count()).where(func.lower(Brand.name) == name.lower())
        if exclude_id:
            stmt = stmt.where(Brand.id != exclude_id)
        return bool(await self.session.scalar(stmt))

    async def count(self) -> int:
        return (await self.session.scalar(select(func.count(Brand.id)))) or 0
