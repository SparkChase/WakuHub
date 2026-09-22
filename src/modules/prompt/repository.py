from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.base_repository import BaseRepository
from src.modules.prompt.model import Prompt, PromptVersion


class PromptRepository(BaseRepository[Prompt]):
    """搜索字段：按名称或分类搜索"""
    SEARCH_FIELDS = ["name", "category"]

    def __init__(self, db: AsyncSession):
        super().__init__(Prompt, db)

    async def get_by_name(self, name: str) -> Prompt | None:
        stmt = select(Prompt).where(Prompt.name == name)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def search_page(
        self, offset: int, limit: int, keyword: str | None
    ) -> tuple[list[Prompt], int]:
        """分页 + 搜索"""
        return await self.get_page(
            offset=offset,
            limit=limit,
            keyword=keyword,
            search_fields=self.SEARCH_FIELDS,
        )


class PromptVersionRepository(BaseRepository[PromptVersion]):
    def __init__(self, db: AsyncSession):
        super().__init__(PromptVersion, db)

    async def get_versions_by_prompt(self, prompt_id: int) -> list[PromptVersion]:
        """获取某个 Prompt 的所有版本，按 ID 倒序"""
        stmt = (
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt_id)
            .order_by(PromptVersion.id.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def clear_current(self, prompt_id: int) -> None:
        """将某个 Prompt 的所有版本的 is_current 设为 False"""
        stmt = (
            update(PromptVersion)
            .where(PromptVersion.prompt_id == prompt_id)
            .values(is_current=False)
        )
        await self.db.execute(stmt)
