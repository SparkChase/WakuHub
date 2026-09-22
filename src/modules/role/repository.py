from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.base_repository import BaseRepository
from src.modules.role.model import Role


# 角色仓储：继承通用 CRUD，额外提供按 code / id 批量查询
class RoleRepository(BaseRepository[Role]):
    def __init__(self, db: AsyncSession):
        super().__init__(Role, db)

    # 按角色编码查询，用于创建时校验 code 是否重复
    async def get_by_code(self, code: str) -> Role | None:
        stmt = select(Role).where(Role.code == code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # 按 id 列表批量查询，用于给用户分配角色时一次性捞出所有角色对象
    async def get_by_ids(self, ids: list[int]) -> list[Role]:
        # in_：生成 WHERE id IN (...)，避免逐个查询
        stmt = select(Role).where(Role.id.in_(ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
