from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.base_repository import BaseRepository
from src.modules.tool.model import Tool


class ToolRepository(BaseRepository[Tool]):
    """搜索字段：按名称或描述搜索"""
    SEARCH_FIELDS = ["name", "description"]

    def __init__(self, db: AsyncSession):
        super().__init__(Tool, db)

    async def get_by_name(self, name: str) -> Tool | None:
        stmt = select(Tool).where(Tool.name == name)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_enabled_tools(self) -> list[Tool]:
        """获取所有启用的工具"""
        stmt = select(Tool).where(Tool.status == "enabled")
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def search_page(
        self, offset: int, limit: int, keyword: str | None
    ) -> tuple[list[Tool], int]:
        """分页 + 搜索"""
        return await self.get_page(
            offset=offset,
            limit=limit,
            keyword=keyword,
            search_fields=self.SEARCH_FIELDS,
        )