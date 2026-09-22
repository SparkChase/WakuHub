from typing import TypeVar, Generic, Optional
from pydantic import BaseModel

T = TypeVar("T")


class ResponseSchema(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: Optional[T] = None

class PageResult(BaseModel, Generic[T]):
    """分页结果包装"""
    items: list[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 20

    # 由 repo.get_page 返回的 (items, total) + 分页参数组装分页结果
    @classmethod
    def build(
        cls, items: list[T], total: int, page: int, page_size: int
    ) -> "PageResult[T]":
        return cls(items=items, total=total, page=page, page_size=page_size)

