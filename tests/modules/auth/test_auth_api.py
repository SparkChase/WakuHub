"""Auth API 集成测试（登录带验证码、JWT 保护接口 /me，走 HTTP 全链路）。"""
from src.core.config import get_settings

settings = get_settings()


async def _get_captcha(client, redis_client):
    """生成一个验证码，返回 (key, code)，供登录测试携带。"""
    resp = await client.get("/api/v1/captcha")
    key = resp.json()["data"]["key"]
    code = await redis_client.get(f"{settings.CAPTCHA_KEY_PREFIX}{key}")
    return key, code


async def _register(client, username: str):
    return await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "secret"},
    )


async def test_register(client):
    resp = await _register(client, "reg_user")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["username"] == "reg_user"
    assert body["data"]["id"] > 0


async def test_register_duplicate(client):
    await _register(client, "dup_user")
    resp = await _register(client, "dup_user")
    # BizException 由全局处理器捕获，HTTP 200 + 业务码 400
    assert resp.status_code == 200
    assert resp.json()["code"] == 400


async def test_register_invalid_email(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "bad", "email": "not-an-email", "password": "secret"},
    )
    # pydantic 校验失败 -> FastAPI 返回 422
    assert resp.status_code == 422


async def test_login_and_access_me(client, redis_client):
    await _register(client, "login_api")

    # 登录拿 token（带验证码）
    key, code = await _get_captcha(client, redis_client)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "login_api", "password": "secret",
              "captcha_key": key, "captcha_code": code},
    )
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]
    assert token

    # 带 token 访问受保护接口 /me
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    assert me.json()["data"]["username"] == "login_api"


async def test_login_wrong_password(client, redis_client):
    await _register(client, "wrongpw")

    key, code = await _get_captcha(client, redis_client)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "wrongpw", "password": "bad",
              "captcha_key": key, "captcha_code": code},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 400


async def test_login_wrong_captcha(client, redis_client):
    await _register(client, "capfail")

    key, _ = await _get_captcha(client, redis_client)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "capfail", "password": "secret",
              "captcha_key": key, "captcha_code": "0000"},
    )
    # 验证码错误：登录被拒
    assert resp.status_code == 200
    assert resp.json()["code"] == 400


async def test_me_without_token(client):
    # 无 Authorization 头，OAuth2PasswordBearer 直接返回 401
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_with_invalid_token(client):
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer garbage.token.here"}
    )
    # JWTHelper 抛 BizException(401)，由业务异常处理器返回 HTTP 200 + code 401
    assert resp.json()["code"] == 401
