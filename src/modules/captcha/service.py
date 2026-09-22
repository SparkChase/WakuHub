"""验证码业务逻辑：生成图片 + 存 Redis + 校验。

流程：
- generate：随机生成 code + uuid key，code 存 Redis（带 TTL），返回图片 base64 + key
- verify：按 key 取出 code 比对，成功即删除（一次性，防重放）
"""
import base64
import random
import string
import uuid
from io import BytesIO

from captcha.image import ImageCaptcha
from redis.asyncio import Redis

from src.core.config import get_settings
from src.core.exceptions import BizException
from src.modules.captcha.schema import CaptchaResponse

settings = get_settings()

# ImageCaptcha 实例可复用，无状态
_image = ImageCaptcha(width=162, height=54)
# 去掉易混淆字符（0/O、1/I/l），提升可读性
_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


class CaptchaService:
    def __init__(self, redis: Redis):
        self.redis = redis

    def _redis_key(self, key: str) -> str:
        return f"{settings.CAPTCHA_KEY_PREFIX}{key}"

    async def generate(self) -> CaptchaResponse:
        code = "".join(random.choices(_ALPHABET, k=settings.CAPTCHA_LENGTH))
        key = uuid.uuid4().hex

        # code 统一转小写存储，比对时大小写不敏感
        await self.redis.set(
            self._redis_key(key), code.lower(), ex=settings.CAPTCHA_TTL
        )

        buf: BytesIO = _image.generate(code)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return CaptchaResponse(key=key, img=f"data:image/png;base64,{b64}")

    async def verify(self, key: str, code: str) -> bool:
        redis_key = self._redis_key(key)
        stored = await self.redis.get(redis_key)
        if stored is None:
            raise BizException(code=400, message="验证码已过期或不存在")

        if stored != code.strip().lower():
            raise BizException(code=400, message="验证码错误")

        # 校验通过即删除，防止重放
        await self.redis.delete(redis_key)
        return True
