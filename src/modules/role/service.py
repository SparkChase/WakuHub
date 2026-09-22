from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BizException
from src.modules.permission.repository import PermissionRepository
from src.modules.role.model import Role
from src.modules.role.repository import RoleRepository
from src.modules.role.schema import RoleCreate, RoleUpdate


class RoleService:
    def __init__(self, db: AsyncSession):
        self.repo = RoleRepository(db)
        # 分配权限时要校验权限是否存在，故同时持有 PermissionRepository
        self.perm_repo = PermissionRepository(db)

    # 创建角色
    async def create_role(self, data: RoleCreate) -> Role:
        # 1. 校验 code 唯一：已存在则拒绝
        if await self.repo.get_by_code(data.code):
            raise BizException(code=400, message="角色编码已存在")

        # 2. 构造 ORM 对象
        role = Role(
            code=data.code,
            name=data.name,
            description=data.description,
        )
        # 3. 落库并返回（拿到自增 id）
        return await self.repo.create(role)

    # 按 id 查询单个角色，查不到直接抛 404
    async def get_role(self, role_id: int) -> Role:
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise BizException(code=404, message="角色不存在")
        return role

    # 更新角色（code 不可改，只更新 name / description）
    async def update_role(self, role_id: int, data: RoleUpdate) -> Role:
        # 1. 先取出已存在的对象（不存在会抛 404）
        role = await self.get_role(role_id)
        # 2. 按需覆盖：字段为 None 表示本次不修改，跳过
        if data.name is not None:
            role.name = data.name
        if data.description is not None:
            role.description = data.description
        # 3. 持久化改动
        return await self.repo.update(role)

    # 删除角色
    async def delete_role(self, role_id: int) -> None:
        # 1. 先确认存在（不存在抛 404）
        role = await self.get_role(role_id)
        # 2. 删除；role_permissions / user_roles 关联行由外键 CASCADE 自动清理
        await self.repo.delete(role)

    # 分页列出角色
    async def list_roles(self, offset: int = 0, limit: int = 100):
        return await self.repo.get_all(offset=offset, limit=limit)

    # 给角色分配权限（全量覆盖：传入的 id 列表即为角色最终的权限集合）
    async def assign_permissions(self, role_id: int, permission_ids: list[int]) -> Role:
        # 1. 取出角色（不存在抛 404）
        role = await self.get_role(role_id)
        # 2. 按 id 批量捞权限对象
        perms = await self.perm_repo.get_by_ids(permission_ids)
        # 3. 数量对比校验：查出的权限数 != 去重后的入参 id 数，说明有 id 不存在，拒绝
        if len(perms) != len(set(permission_ids)):
            raise BizException(code=400, message="部分权限不存在")

        # 4. 全量覆盖：直接替换关联集合，SQLAlchemy 会自动增删 role_permissions 关联行
        role.permissions = perms
        # 5. 持久化
        return await self.repo.update(role)
