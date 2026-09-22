from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.database import get_db
from src.core.base_schema import ResponseSchema
from src.modules.permission.schema import (
    PermissionCreate,
    PermissionRead,
    PermissionUpdate,
)
from src.modules.permission.service import PermissionService
from src.modules.auth.deps import require_permission
from src.core.permissions import PermCode

router = APIRouter(prefix="/permissions", tags=["Permission"])


# 依赖注入：从请求作用域的 db 会话构造 PermissionService
def get_permission_service(db: AsyncSession = Depends(get_db)) -> PermissionService:
    return PermissionService(db)


# POST /permissions  创建权限（需 permission:manage）
@router.post(
    "",
    response_model=ResponseSchema[PermissionRead],
    dependencies=[Depends(require_permission(PermCode.PERMISSION_MANAGE))],
)
async def create_permission(
    data: PermissionCreate,
    svc: PermissionService = Depends(get_permission_service),
):
    perm = await svc.create_permission(data)
    return ResponseSchema[PermissionRead](data=PermissionRead.model_validate(perm))


# GET /permissions/{perm_id}  查询单个权限
@router.get("/{perm_id}", response_model=ResponseSchema[PermissionRead])
async def get_permission(
    perm_id: int,
    svc: PermissionService = Depends(get_permission_service),
):
    perm = await svc.get_permission(perm_id)
    return ResponseSchema[PermissionRead](data=PermissionRead.model_validate(perm))


# GET /permissions  分页列出权限
@router.get("", response_model=ResponseSchema[list[PermissionRead]])
async def list_permissions(
    offset: int = 0,
    limit: int = 100,
    svc: PermissionService = Depends(get_permission_service),
):
    perms = await svc.list_permissions(offset, limit)
    return ResponseSchema[list[PermissionRead]](
        data=[PermissionRead.model_validate(p) for p in perms]
    )


# PUT /permissions/{perm_id}  更新权限（code 不可改，需 permission:manage）
@router.put(
    "/{perm_id}",
    response_model=ResponseSchema[PermissionRead],
    dependencies=[Depends(require_permission(PermCode.PERMISSION_MANAGE))],
)
async def update_permission(
    perm_id: int,
    data: PermissionUpdate,
    svc: PermissionService = Depends(get_permission_service),
):
    perm = await svc.update_permission(perm_id, data)
    return ResponseSchema[PermissionRead](data=PermissionRead.model_validate(perm))


# DELETE /permissions/{perm_id}  删除权限（需 permission:manage）
@router.delete(
    "/{perm_id}",
    response_model=ResponseSchema[bool],
    dependencies=[Depends(require_permission(PermCode.PERMISSION_MANAGE))],
)
async def delete_permission(
    perm_id: int,
    svc: PermissionService = Depends(get_permission_service),
):
    await svc.delete_permission(perm_id)
    return ResponseSchema[bool](data=True)
