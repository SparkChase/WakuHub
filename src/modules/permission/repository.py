from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.base_repository import BaseRepository
from src.modules.permission.model import Permission


# 权限仓储：继承通用 CRUD，额外提供按 code / id 批量查询
class PermissionRepository(BaseRepository[Permission]):
    def __init__(self, db: AsyncSession):
        super().__init__(Permission, db)

    # 按权限编码查询，用于创建时校验 code 是否重复
    async def get_by_code(self, code: str) -> Permission | None:
        stmt = select(Permission).where(Permission.code == code)
        result = await self.db.execute(stmt)
        # scalar_one_or_none：期望 0 或 1 条，命中返回对象，无命中返回 None
        return result.scalar_one_or_none()

    # 按 id 列表批量查询，用于给角色分配权限时一次性捞出所有权限对象
    async def get_by_ids(self, ids: list[int]) -> list[Permission]:
        # in_：生成 SQL 的 WHERE id IN (...)，避免逐个查询
        stmt = select(Permission).where(Permission.id.in_(ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
