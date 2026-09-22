from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.infra.database import get_db
from src.core.base_schema import ResponseSchema
from src.modules.user.schema import (
    UserAssignRoles,
    UserCreate,
    UserRead,
    UserWithRolesRead,
)
from src.modules.user.service import UserService
from src.modules.auth.deps import require_permission, get_permission_cache
from src.modules.auth.cache import PermissionCache
from src.core.permissions import PermCode

router = APIRouter(prefix="/users", tags=["User"])


# 依赖注入 UserService
def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


# GET /users/{user_id}  查询单个用户
@router.get("/{user_id}", response_model=ResponseSchema[UserRead])
async def get_user(
    user_id: int,
    svc: UserService = Depends(get_user_service),
):
    user = await svc.get_user(user_id)
    return ResponseSchema[UserRead](data=UserRead.model_validate(user))


# GET /users  分页列出用户
@router.get("", response_model=ResponseSchema[list[UserRead]])
async def list_users(
    offset: int = 0,
    limit: int = 100,
    svc: UserService = Depends(get_user_service),
):
    users = await svc.list_users(offset, limit)
    return ResponseSchema[list[UserRead]](data=[UserRead.model_validate(u) for u in users])


# PUT /users/{user_id}/roles  全量覆盖用户的角色（传入的 id 列表即最终角色集，需 user:manage），返回带角色的用户
@router.put(
    "/{user_id}/roles",
    response_model=ResponseSchema[UserWithRolesRead],
    dependencies=[Depends(require_permission(PermCode.USER_MANAGE))],
)
async def assign_roles(
    user_id: int,
    data: UserAssignRoles,
    svc: UserService = Depends(get_user_service),
    cache: PermissionCache = Depends(get_permission_cache),
):
    user = await svc.assign_roles(user_id, data.role_ids)
    # 角色变了 → 失效该用户的权限缓存，下次请求回源重建
    await cache.invalidate(user_id)
    return ResponseSchema[UserWithRolesRead](data=UserWithRolesRead.model_validate(user))