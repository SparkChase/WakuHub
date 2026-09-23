from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.base_repository import BaseRepository
from src.modules.agent.model import Agent, AgentVersion


class AgentRepository(BaseRepository[Agent]):
    """搜索字段：按名称或描述搜索"""
    SEARCH_FIELDS = ["name", "description"]

    def __init__(self, db: AsyncSession):
        super().__init__(Agent, db)

    async def get_by_status(self, status: str) -> list[Agent]:
        stmt = select(Agent).where(Agent.status == status)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def search_page(
        self, offset: int, limit: int, keyword: str | None
    ) -> tuple[list[Agent], int]:
        """分页 + 搜索"""
        return await self.get_page(
            offset=offset,
            limit=limit,
            keyword=keyword,
            search_fields=self.SEARCH_FIELDS,
        )


class AgentVersionRepository(BaseRepository[AgentVersion]):
    def __init__(self, db: AsyncSession):
        super().__init__(AgentVersion, db)

    async def get_versions_by_agent(self, agent_id: int) -> list[AgentVersion]:
        stmt = (
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.id.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def clear_current(self, agent_id: int) -> None:
        stmt = (
            update(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .values(is_current=False)
        )
        await self.db.execute(stmt)