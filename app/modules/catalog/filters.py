import enum
from dataclasses import dataclass, field

from fastapi import Query

from app.core.errors import ValidationFailed


class ProductSort(str, enum.Enum):
    newest = "newest"  # "New Arrivals"
    best_selling = "best_selling"  # "Top Selling"
    price_asc = "price_asc"
    price_desc = "price_desc"
    rating = "rating"


@dataclass
class ProductFilters:
    q: str | None = None
    brand: list[str] = field(default_factory=list)
    category: list[str] = field(default_factory=list)
    size: list[str] = field(default_factory=list)
    color: list[str] = field(default_factory=list)
    min_price: int | None = None
    max_price: int | None = None
    sort: ProductSort = ProductSort.newest
    status: str | None = None  # admin only


def product_filters(
    q: str | None = Query(None, max_length=100, description="Search in product title"),
    brand: list[str] | None = Query(None, description="Brand slug; repeat for multiple"),
    category: list[str] | None = Query(None, description="Category slug; repeat for multiple"),
    size: list[str] | None = Query(None, description="e.g. size=M&size=L"),
    color: list[str] | None = Query(None, description="e.g. color=black"),
    min_price: int | None = Query(None, ge=0, description="Paise"),
    max_price: int | None = Query(None, ge=0, description="Paise"),
    sort: ProductSort = Query(ProductSort.newest),
) -> ProductFilters:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise ValidationFailed("min_price must be <= max_price", code="invalid_price_range")
    return ProductFilters(
        q=q,
        brand=brand or [],
        category=category or [],
        size=size or [],
        color=color or [],
        min_price=min_price,
        max_price=max_price,
        sort=sort,
    )
