import math
from dataclasses import dataclass
from typing import Annotated, Any, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Standard list envelope used by every paginated endpoint."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


@dataclass
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


PageDep = Annotated[PageParams, Depends(page_params)]


def make_page(items: list[Any], total: int, params: PageParams) -> dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "pages": math.ceil(total / params.page_size) if total else 0,
    }
