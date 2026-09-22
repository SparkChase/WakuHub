"""鉴权 / 鉴权依赖，供所有受保护路由复用。

单独成文件（不放 auth/api.py）：role、permission 等模块要引用 require_permission，
若从 auth/api 引会把整个路由文件也拖进来，且容易和 user 模块绕成循环 import。
这里只依赖 user.service / jwt / database，是干净的下游。
"""
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BizException
from src.core.permissions import PermCode
from src.infra.database import get_db
from src.modules.user.model import User
from src.modules.user.service import UserService
from src.utils.jwt import JWTHelper

# 从 Authorization: Bearer <token> 头取 token；tokenUrl 指向登录接口，供 Swagger 授权用
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


# 鉴权依赖：从 token 解析出当前登录用户
# 返回 ORM User（roles / permissions 已由 selectin 预加载），供权限校验直接用
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    svc: UserService = Depends(get_user_service),
) -> User:
    payload = JWTHelper.decode_token(token)
    return await svc.get_user(int(payload["sub"]))


# 鉴权依赖工厂：require_permission(PermCode.ROLE_MANAGE) 挂到路由 dependencies 即可守门
# 入参用 PermCode 枚举，避免手写字符串拼错
def require_permission(code: PermCode):
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        # 1. 超级管理员无视权限检查，直接放行（解决"没人有权限就没人能授权"的自锁死）
        if current_user.is_superuser:
            return current_user
        # 2. 收集该用户所有角色下的权限 code，扁平成一个集合
        owned = {p.code for role in current_user.roles for p in role.permissions}
        # 3. 目标权限不在集合里 → 无权，抛 403
        if code not in owned:
            raise BizException(code=403, message="无权限访问")
        return current_user

    return checker
