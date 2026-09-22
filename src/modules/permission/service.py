from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BizException
from src.modules.permission.model import Permission
from src.modules.permission.repository import PermissionRepository
from src.modules.permission.schema import PermissionCreate, PermissionUpdate


class PermissionService:
    def __init__(self, db: AsyncSession):
        self.repo = PermissionRepository(db)

    # 创建权限
    async def create_permission(self, data: PermissionCreate) -> Permission:
        # 1. 校验 code 唯一：已存在则拒绝，避免重复权限编码
        if await self.repo.get_by_code(data.code):
            raise BizException(code=400, message="权限编码已存在")

        # 2. 构造 ORM 对象
        perm = Permission(
            code=data.code,
            name=data.name,
            description=data.description,
        )
        # 3. 落库并返回（create 内部 flush + refresh，拿到自增 id）
        return await self.repo.create(perm)

    # 按 id 查询单个权限，查不到直接抛 404
    async def get_permission(self, perm_id: int) -> Permission:
        perm = await self.repo.get_by_id(perm_id)
        if not perm:
            raise BizException(code=404, message="权限不存在")
        return perm

    # 更新权限（code 不可改，只更新 name / description）
    async def update_permission(self, perm_id: int, data: PermissionUpdate) -> Permission:
        # 1. 先取出已存在的对象（不存在会抛 404）
        perm = await self.get_permission(perm_id)
        # 2. 按需覆盖：字段为 None 表示本次不修改，跳过
        if data.name is not None:
            perm.name = data.name
        if data.description is not None:
            perm.description = data.description
        # 3. 持久化改动（对象已在会话中，update 只需 flush + refresh）
        return await self.repo.update(perm)

    # 删除权限
    async def delete_permission(self, perm_id: int) -> None:
        # 1. 先确认存在（不存在抛 404）
        perm = await self.get_permission(perm_id)
        # 2. 删除；role_permissions 关联行由外键 ondelete=CASCADE 自动清理
        await self.repo.delete(perm)

    # 分页列出权限
    async def list_permissions(self, offset: int = 0, limit: int = 100):
        return await self.repo.get_all(offset=offset, limit=limit)
