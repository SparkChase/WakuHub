# 业务流程：
# 服务端：保存 key & 生成验证码 code + 返回验证码图片
# 客户端：展示验证码图片 + 提交 key & 自己认为的验证码值
from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from src.infra.redis import get_redis_client
from src.core.base_schema import ResponseSchema
from src.modules.captcha.schema import CaptchaResponse, CaptchaVerify
from src.modules.captcha.service import CaptchaService

router = APIRouter(prefix="/captcha", tags=["Captcha"])


def get_captcha_service(redis: Redis = Depends(get_redis_client)) -> CaptchaService:
    return CaptchaService(redis)


# GET /captcha  生成验证码，返回 key + 图片 base64
@router.get("", response_model=ResponseSchema[CaptchaResponse])
async def generate_captcha(
    svc: CaptchaService = Depends(get_captcha_service),
):
    data = await svc.generate()
    return ResponseSchema[CaptchaResponse](data=data)


# POST /captcha/verify  校验验证码
@router.post("/verify", response_model=ResponseSchema[bool])
async def verify_captcha(
    data: CaptchaVerify,
    svc: CaptchaService = Depends(get_captcha_service),
):
    ok = await svc.verify(data.key, data.code)
    return ResponseSchema[bool](data=ok)
