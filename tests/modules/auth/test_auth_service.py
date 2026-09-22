"""AuthService 单元测试（直接走 db_session，不经过 HTTP）。"""
import pytest

from src.core.exceptions import BizException
from src.modules.auth.schema import LoginRequest
from src.modules.auth.service import AuthService
from src.modules.user.schema import UserCreate
from src.modules.user.service import UserService
from src.utils.jwt import JWTHelper


def _make(username: str, email: str) -> UserCreate:
    return UserCreate(username=username, email=email, password="secret")


def _login(username: str, password: str) -> LoginRequest:
    # service.login 不校验验证码（那是 api 层的事），captcha 字段填占位即可
    return LoginRequest(
        username=username, password=password, captcha_key="x", captcha_code="x"
    )


async def test_login_success(db_session):
    await UserService(db_session).create_user(_make("frank", "frank@example.com"))

    svc = AuthService(db_session)
    token = await svc.login(_login("frank", "secret"))
    assert token.access_token
    assert token.token_type == "bearer"

    # token 能解出正确的 sub
    payload = JWTHelper.decode_token(token.access_token)
    user = await svc.repo.get_by_username("frank")
    assert payload["sub"] == str(user.id)


async def test_login_wrong_password(db_session):
    await UserService(db_session).create_user(_make("grace", "grace@example.com"))

    svc = AuthService(db_session)
    with pytest.raises(BizException) as exc:
        await svc.login(_login("grace", "wrong"))
    assert exc.value.code == 400


async def test_login_user_not_found(db_session):
    svc = AuthService(db_session)
    with pytest.raises(BizException) as exc:
        await svc.login(_login("nobody", "secret"))
    assert exc.value.code == 400
