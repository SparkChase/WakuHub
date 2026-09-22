"""Captcha API 集成测试（走 HTTP 全链路）。"""
from src.core.config import get_settings

settings = get_settings()


async def test_generate_captcha_api(client):
    resp = await client.get("/api/captcha")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["key"]
    assert body["data"]["img"].startswith("data:image/png;base64,")


async def test_verify_captcha_api_success(client, redis_client):
    gen = await client.get("/api/captcha")
    key = gen.json()["data"]["key"]
    code = await redis_client.get(f"{settings.CAPTCHA_KEY_PREFIX}{key}")

    resp = await client.post("/api/captcha/verify", json={"key": key, "code": code})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    assert body["data"] is True


async def test_verify_captcha_api_wrong_code(client):
    gen = await client.get("/api/captcha")
    key = gen.json()["data"]["key"]

    resp = await client.post("/api/captcha/verify", json={"key": key, "code": "0000"})
    # BizException -> HTTP 200 + 业务码 400
    assert resp.status_code == 200
    assert resp.json()["code"] == 400


async def test_verify_captcha_api_expired_key(client):
    resp = await client.post(
        "/api/captcha/verify", json={"key": "no-such-key", "code": "abcd"}
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 400


async def test_verify_captcha_api_one_time_use(client, redis_client):
    gen = await client.get("/api/captcha")
    key = gen.json()["data"]["key"]
    code = await redis_client.get(f"{settings.CAPTCHA_KEY_PREFIX}{key}")

    first = await client.post("/api/captcha/verify", json={"key": key, "code": code})
    assert first.json()["data"] is True

    # 第二次用同一 key 应失败（已被消费）
    second = await client.post("/api/captcha/verify", json={"key": key, "code": code})
    assert second.json()["code"] == 400
