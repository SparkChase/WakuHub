"""JWT 工具（PyJWT）。

无状态工具类，方法均为 @staticmethod：
    JWTHelper.create_access_token(subject="1") / JWTHelper.decode_token(token)
"""
from datetime import datetime, timedelta, timezone

import jwt

from src.core.config import get_settings
from src.core.exceptions import BizException

settings = get_settings()


class JWTHelper:
    """基于 PyJWT 的 access token 签发与校验。"""

    @staticmethod
    def create_access_token(
        subject: str, expires_delta: timedelta | None = None
    ) -> str:
        """签发 access token。

        subject: 放进 sub 声明的主体标识（一般是用户 id）。
        expires_delta: 自定义有效期，缺省用配置里的默认值。
        """
        now = datetime.now(timezone.utc)
        expire = now + (
            expires_delta
            or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        payload = {
            "sub": subject,
            "iat": now,
            "exp": expire,
        }
        return jwt.encode(
            payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

    @staticmethod
    def decode_token(token: str) -> dict:
        """校验并解码 token，失败抛 BizException（401）。"""
        try:
            return jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except jwt.ExpiredSignatureError:
            raise BizException(code=401, message="登录已过期，请重新登录")
        except jwt.InvalidTokenError:
            raise BizException(code=401, message="无效的凭证")
