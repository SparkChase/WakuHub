"""鉴权 / 鉴权依赖，供所有受保护路由复用。

单独成文件（不放 auth/api.py）：role、permission 等模块要引用 require_permission，
若从 auth/api 引会把整个路由文件也拖进来，且容易和 user 模块绕成循环 import。
这里只依赖 user.service / jwt / database，是干净的下游。
"""
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BizException
from src.core.permissions import PermCode
from src.infra.database import get_db
from src.infra.redis import get_redis_client
from src.modules.auth.cache import PermissionCache
from src.modules.user.model import User
from src.modules.user.service import UserService
from src.utils.jwt import JWTHelper

# 从 Authorization: Bearer <token> 头取 token；tokenUrl 指向登录接口，供 Swagger 授权用
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


def get_permission_cache(redis: Redis = Depends(get_redis_client)) -> PermissionCache:
    return PermissionCache(redis)


# 从 token 解析出用户 id（不查库）
def _user_id_from_token(token: str) -> int:
    payload = JWTHelper.decode_token(token)
    return int(payload["sub"])


# 鉴权依赖：从 token 解析出当前登录用户
# 返回 ORM User（roles / permissions 已由 selectin 预加载），供需要完整用户信息的接口用
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    svc: UserService = Depends(get_user_service),
) -> User:
    return await svc.get_user(_user_id_from_token(token))


# 取当前用户的权限数据（Cache-Aside）：{"is_superuser": bool, "perms": [code...]}
# 缓存命中省掉 user + roles + permissions 三次 DB 查询
async def get_current_perms(
    token: str = Depends(oauth2_scheme),
    svc: UserService = Depends(get_user_service),
    cache: PermissionCache = Depends(get_permission_cache),
) -> dict:
    user_id = _user_id_from_token(token)
    # 1. 先查缓存
    cached = await cache.get(user_id)
    if cached is not None:
        return cached
    # 2. 未命中回源 DB（get_user 内部 selectin 已加载 roles / permissions）
    user = await svc.get_user(user_id)
    # 3. 回填缓存并返回
    return await cache.set(user)


# 鉴权依赖工厂：require_permission(PermCode.ROLE_MANAGE) 挂到路由 dependencies 即可守门
# 入参用 PermCode 枚举，避免手写字符串拼错；权限数据走缓存，不每次查库
def require_permission(code: PermCode):
    async def checker(perms: dict = Depends(get_current_perms)) -> None:
        # 1. 超级管理员无视权限检查，直接放行（解决"没人有权限就没人能授权"的自锁死）
        if perms["is_superuser"]:
            return
        # 2. 目标权限不在用户权限集合里 → 无权，抛 403
        if code not in perms["perms"]:
            raise BizException(code=403, message="无权限访问")

    return checker
