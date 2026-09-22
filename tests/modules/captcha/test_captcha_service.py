"""CaptchaService 单元测试（直接走 redis_client，不经过 HTTP）。"""
import pytest

from src.core.config import get_settings
from src.core.exceptions import BizException
from src.modules.captcha.service import CaptchaService

settings = get_settings()


async def test_generate_returns_key_and_img(redis_client):
    svc = CaptchaService(redis_client)
    resp = await svc.generate()

    assert resp.key
    assert resp.img.startswith("data:image/png;base64,")

    # code 已按 key 存进 redis，且长度符合配置
    stored = await redis_client.get(f"{settings.CAPTCHA_KEY_PREFIX}{resp.key}")
    assert stored is not None
    assert len(stored) == settings.CAPTCHA_LENGTH


async def test_generate_sets_ttl(redis_client):
    svc = CaptchaService(redis_client)
    resp = await svc.generate()

    ttl = await redis_client.ttl(f"{settings.CAPTCHA_KEY_PREFIX}{resp.key}")
    assert 0 < ttl <= settings.CAPTCHA_TTL


async def test_verify_success_and_consumed(redis_client):
    svc = CaptchaService(redis_client)
    resp = await svc.generate()
    stored = await redis_client.get(f"{settings.CAPTCHA_KEY_PREFIX}{resp.key}")

    assert await svc.verify(resp.key, stored) is True
    # 一次性：校验成功后 key 已删除
    assert await redis_client.get(f"{settings.CAPTCHA_KEY_PREFIX}{resp.key}") is None


async def test_verify_case_insensitive(redis_client):
    svc = CaptchaService(redis_client)
    resp = await svc.generate()
    stored = await redis_client.get(f"{settings.CAPTCHA_KEY_PREFIX}{resp.key}")

    # 大写提交也应通过（存储时转小写、比对时也转小写）
    assert await svc.verify(resp.key, stored.upper()) is True


async def test_verify_wrong_code(redis_client):
    svc = CaptchaService(redis_client)
    resp = await svc.generate()

    with pytest.raises(BizException) as exc:
        await svc.verify(resp.key, "wrong")
    assert exc.value.code == 400
    # 校验失败不删除，允许重试
    assert await redis_client.get(f"{settings.CAPTCHA_KEY_PREFIX}{resp.key}") is not None


async def test_verify_key_not_found(redis_client):
    svc = CaptchaService(redis_client)
    with pytest.raises(BizException) as exc:
        await svc.verify("nonexistent-key", "abcd")
    assert exc.value.code == 400
