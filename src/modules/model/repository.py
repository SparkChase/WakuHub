from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.base_repository import BaseRepository
from src.modules.model.model import LLMModel


class ModelRepository(BaseRepository[LLMModel]):
    """搜索字段：按模型名称或模型标识符搜索"""
    SEARCH_FIELDS = ["name", "model_id"]

    def __init__(self, db: AsyncSession):
        super().__init__(LLMModel, db)

    async def get_by_model_id(self, model_id: str) -> LLMModel | None:
        """按模型标识符查找（用于去重）"""
        stmt = select(LLMModel).where(LLMModel.model_id == model_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_provider(self, provider_id: int) -> list[LLMModel]:
        """按供应商查询模型列表"""
        stmt = select(LLMModel).where(LLMModel.provider_id == provider_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_default_model(self) -> LLMModel | None:
        """获取默认模型"""
        stmt = select(LLMModel).where(LLMModel.is_default == True)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def search_page(
        self, offset: int, limit: int, keyword: str | None
    ) -> tuple[list[LLMModel], int]:
        """分页 + 搜索"""
        return await self.get_page(
            offset=offset,
            limit=limit,
            keyword=keyword,
            search_fields=self.SEARCH_FIELDS,
        )
