import enum
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProductStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


product_categories = Table(
    "product_categories",
    Base.metadata,
    Column("product_id", Uuid, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Uuid, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Brand(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "brands"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    logo_url: Mapped[str | None] = mapped_column(String(500))


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_status_created_at", "status", "created_at"),)

    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(280), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default=ProductStatus.draft.value, index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brands.id", ondelete="SET NULL"), index=True
    )
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))

    # India/GST: HSN code + GST rate in basis points (1800 = 18%). Used by the tax module later.
    hsn_code: Mapped[str | None] = mapped_column(String(10))
    tax_rate_bps: Mapped[int] = mapped_column(Integer, default=0)

    # Denormalised counters, maintained by the orders / reviews modules.
    sales_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)

    brand: Mapped[Brand | None] = relationship(lazy="selectin")
    categories: Mapped[list[Category]] = relationship(
        secondary=product_categories, lazy="selectin", order_by="Category.position"
    )
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ProductVariant.position",
    )
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ProductImage.position",
    )

    # ---- computed, read-only values exposed through the API schemas ----
    @property
    def active_variants(self) -> list["ProductVariant"]:
        return [v for v in self.variants if v.is_active]

    @property
    def _cheapest(self) -> "ProductVariant | None":
        active = self.active_variants
        return min(active, key=lambda v: v.price) if active else None

    @property
    def price(self) -> int | None:
        c = self._cheapest
        return c.price if c else None

    @property
    def compare_at_price(self) -> int | None:
        c = self._cheapest
        return c.compare_at_price if c else None

    @property
    def currency(self) -> str:
        c = self._cheapest
        return c.currency if c else "INR"

    @property
    def discount_percent(self) -> int:
        c = self._cheapest
        if c and c.compare_at_price and c.compare_at_price > c.price:
            return round((c.compare_at_price - c.price) * 100 / c.compare_at_price)
        return 0

    @property
    def in_stock(self) -> bool:
        return any(v.stock_quantity > 0 for v in self.active_variants)

    @property
    def sizes(self) -> list[str]:
        return list(dict.fromkeys(v.size for v in self.active_variants if v.size))

    @property
    def colors(self) -> list[str]:
        return list(dict.fromkeys(v.color for v in self.active_variants if v.color))


class ProductImage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "product_images"

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(500))
    alt: Mapped[str | None] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[Product] = relationship(back_populates="images")


class ProductVariant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A purchasable SKU (e.g. size M / colour Black). All money is integer paise."""

    __tablename__ = "product_variants"
    __table_args__ = (
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="stock_non_negative"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    size: Mapped[str | None] = mapped_column(String(20))
    color: Mapped[str | None] = mapped_column(String(30))
    price: Mapped[int] = mapped_column(Integer)  # paise
    compare_at_price: Mapped[int | None] = mapped_column(Integer)  # MRP / strike-through price
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    # Simple stock counter for now; the inventory module (reservations) will own this later.
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[Product] = relationship(back_populates="variants")

    @property
    def in_stock(self) -> bool:
        return self.is_active and self.stock_quantity > 0
