"""认证业务逻辑：校验凭证、签发 JWT。

只依赖 db（拿用户）；验证码校验放在路由层编排（CaptchaService 独立）。
"""
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BizException
from src.modules.auth.schema import LoginRequest, TokenResponse
from src.modules.user.repository import UserRepository
from src.utils.password import PasswordHasher
from src.utils.jwt import JWTHelper


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self.repo.get_by_username(data.username)
        # 用户不存在与密码错误返回同一提示，避免暴露用户名是否存在
        if not user or not PasswordHasher.verify(data.password, user.hashed_password):
            raise BizException(code=400, message="用户名或密码错误")
        if not user.is_active:
            raise BizException(code=403, message="账号已被禁用")

        token = JWTHelper.create_access_token(subject=str(user.id))
        return TokenResponse(access_token=token)
