"""JWTHelper 工具类单元测试（PyJWT）。"""
from datetime import timedelta

import pytest

from src.core.exceptions import BizException
from src.utils.jwt import JWTHelper


def test_jwt_create_and_decode():
    token = JWTHelper.create_access_token(subject="123")
    payload = JWTHelper.decode_token(token)
    assert payload["sub"] == "123"
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_expired_token():
    # 负的有效期 -> 立即过期
    token = JWTHelper.create_access_token(
        subject="1", expires_delta=timedelta(seconds=-1)
    )
    with pytest.raises(BizException) as exc:
        JWTHelper.decode_token(token)
    assert exc.value.code == 401


def test_jwt_invalid_token():
    with pytest.raises(BizException) as exc:
        JWTHelper.decode_token("not.a.valid.token")
    assert exc.value.code == 401
