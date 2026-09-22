from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.database import get_db
from src.core.base_schema import ResponseSchema
from src.modules.role.schema import (
    RoleAssignPermissions,
    RoleCreate,
    RoleRead,
    RoleUpdate,
)
from src.modules.role.service import RoleService
from src.modules.auth.deps import require_permission
from src.core.permissions import PermCode

router = APIRouter(prefix="/roles", tags=["Role"])


# 依赖注入：从请求作用域的 db 会话构造 RoleService
def get_role_service(db: AsyncSession = Depends(get_db)) -> RoleService:
    return RoleService(db)


# POST /roles  创建角色（需 role:manage）
@router.post(
    "",
    response_model=ResponseSchema[RoleRead],
    dependencies=[Depends(require_permission(PermCode.ROLE_MANAGE))],
)
async def create_role(
    data: RoleCreate,
    svc: RoleService = Depends(get_role_service),
):
    role = await svc.create_role(data)
    return ResponseSchema[RoleRead](data=RoleRead.model_validate(role))


# GET /roles/{role_id}  查询单个角色（含权限列表）
@router.get("/{role_id}", response_model=ResponseSchema[RoleRead])
async def get_role(
    role_id: int,
    svc: RoleService = Depends(get_role_service),
):
    role = await svc.get_role(role_id)
    return ResponseSchema[RoleRead](data=RoleRead.model_validate(role))


# GET /roles  分页列出角色
@router.get("", response_model=ResponseSchema[list[RoleRead]])
async def list_roles(
    offset: int = 0,
    limit: int = 100,
    svc: RoleService = Depends(get_role_service),
):
    roles = await svc.list_roles(offset, limit)
    return ResponseSchema[list[RoleRead]](
        data=[RoleRead.model_validate(r) for r in roles]
    )


# PUT /roles/{role_id}  更新角色（code 不可改，需 role:manage）
@router.put(
    "/{role_id}",
    response_model=ResponseSchema[RoleRead],
    dependencies=[Depends(require_permission(PermCode.ROLE_MANAGE))],
)
async def update_role(
    role_id: int,
    data: RoleUpdate,
    svc: RoleService = Depends(get_role_service),
):
    role = await svc.update_role(role_id, data)
    return ResponseSchema[RoleRead](data=RoleRead.model_validate(role))


# DELETE /roles/{role_id}  删除角色（需 role:manage）
@router.delete(
    "/{role_id}",
    response_model=ResponseSchema[bool],
    dependencies=[Depends(require_permission(PermCode.ROLE_MANAGE))],
)
async def delete_role(
    role_id: int,
    svc: RoleService = Depends(get_role_service),
):
    await svc.delete_role(role_id)
    return ResponseSchema[bool](data=True)


# PUT /roles/{role_id}/permissions  全量覆盖角色的权限（传入的 id 列表即最终权限集，需 role:manage）
@router.put(
    "/{role_id}/permissions",
    response_model=ResponseSchema[RoleRead],
    dependencies=[Depends(require_permission(PermCode.ROLE_MANAGE))],
)
async def assign_permissions(
    role_id: int,
    data: RoleAssignPermissions,
    svc: RoleService = Depends(get_role_service),
):
    role = await svc.assign_permissions(role_id, data.permission_ids)
    return ResponseSchema[RoleRead](data=RoleRead.model_validate(role))
