from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.exceptions import BizException
from src.core.base_schema import PageResult
from src.core.depys import PageParams
from src.modules.agent.model import Agent, AgentVersion
from src.modules.agent.repository import AgentRepository, AgentVersionRepository
from src.modules.agent.schema import (
    AgentCreate, AgentUpdate, AgentRead,
    AgentVersionRead, PublishRequest, RollbackRequest,
)


class AgentService:
    def __init__(self, db: AsyncSession):
        self.repo = AgentRepository(db)
        self.version_repo = AgentVersionRepository(db)

    def _to_read(self, agent: Agent) -> AgentRead:
        return AgentRead(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            type=agent.type,
            status=agent.status,
            model_id=agent.model_id,
            config=agent.config,
            success_rate=float(agent.success_rate),
            call_count_7d=agent.call_count_7d,
            version=agent.version,
            created_by=agent.created_by,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    # ===== CRUD =====

    async def create_agent(self, data: AgentCreate, current_user: str = None) -> AgentRead:
        agent = Agent(
            name=data.name,
            description=data.description,
            type=data.type,
            model_id=data.model_id,
            config=data.config.model_dump() if data.config else None,
            status="draft",
            version="v0.1",
            created_by=current_user,
        )
        agent = await self.repo.create(agent)
        return self._to_read(agent)

    async def get_agent(self, agent_id: int) -> AgentRead:
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise BizException(code=45001, message="Agent 不存在")
        return self._to_read(agent)

    async def list_agents(self, params: PageParams) -> PageResult[AgentRead]:
        """分页查询 Agent 列表"""
        items, total = await self.repo.search_page(
            offset=params.offset,
            limit=params.page_size,
            keyword=params.keyword,
        )
        return PageResult(
            items=[self._to_read(a) for a in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def update_agent(self, agent_id: int, data: AgentUpdate) -> AgentRead:
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise BizException(code=45001, message="Agent 不存在")

        if data.name is not None:
            agent.name = data.name
        if data.description is not None:
            agent.description = data.description
        if data.type is not None:
            agent.type = data.type
        if data.model_id is not None:
            agent.model_id = data.model_id
        if data.config is not None:
            agent.config = data.config.model_dump()

        agent = await self.repo.update(agent)
        return self._to_read(agent)

    async def delete_agent(self, agent_id: int) -> None:
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise BizException(code=45001, message="Agent 不存在")
        await self.repo.delete(agent)

    # ===== 生命周期管理 =====

    async def start_agent(self, agent_id: int) -> AgentRead:
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise BizException(code=45001, message="Agent 不存在")
        if agent.status == "active":
            raise BizException(code=45002, message="Agent 已在运行中")

        # TODO: 实际启动逻辑（加载模型、初始化连接等）
        agent.status = "active"
        agent = await self.repo.update(agent)
        return self._to_read(agent)

    async def stop_agent(self, agent_id: int) -> AgentRead:
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise BizException(code=45001, message="Agent 不存在")
        if agent.status == "inactive":
            raise BizException(code=45003, message="Agent 已停止")

        agent.status = "inactive"
        agent = await self.repo.update(agent)
        return self._to_read(agent)

    # ===== 版本管理 =====

    async def publish(self, agent_id: int, data: PublishRequest, current_user: str = None) -> AgentRead:
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise BizException(code=45001, message="Agent 不存在")

        new_version = self._next_version(agent.version)

        await self.version_repo.clear_current(agent_id)

        version = AgentVersion(
            agent_id=agent_id,
            version=new_version,
            config=agent.config,
            changelog=data.changelog,
            is_current=True,
            published_by=current_user,
            published_at=datetime.now(),
        )
        await self.version_repo.create(version)

        agent.version = new_version
        agent.status = "inactive"  # 发布后默认停止，需要手动启动
        await self.repo.update(agent)

        return self._to_read(agent)

    async def get_versions(self, agent_id: int) -> list[AgentVersionRead]:
        versions = await self.version_repo.get_versions_by_agent(agent_id)
        return [AgentVersionRead.model_validate(v) for v in versions]

    async def rollback(self, agent_id: int, data: RollbackRequest) -> AgentRead:
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise BizException(code=45001, message="Agent 不存在")

        target = await self.version_repo.get_by_id(data.version_id)
        if not target or target.agent_id != agent_id:
            raise BizException(code=45004, message="版本不存在")

        agent.config = target.config
        agent.version = target.version

        await self.version_repo.clear_current(agent_id)
        target.is_current = True
        await self.version_repo.update(target)
        await self.repo.update(agent)

        return self._to_read(agent)

    @staticmethod
    def _next_version(current: str) -> str:
        try:
            prefix = current[0]
            parts = current[1:].split(".")
            major, minor = int(parts[0]), int(parts[1])
            return f"{prefix}{major}.{minor + 1}"
        except (IndexError, ValueError):
            return "v1.0"