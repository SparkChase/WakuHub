"""UserService / UserRepository 单元测试（直接走 db_session，不经过 HTTP）。"""
import pytest

from src.core.exceptions import BizException
from src.modules.user.schema import UserCreate
from src.modules.user.service import UserService


def _make(username: str = "alice", email: str = "alice@example.com") -> UserCreate:
    return UserCreate(username=username, email=email, password="secret")


async def test_create_user_success(db_session):
    svc = UserService(db_session)
    user = await svc.create_user(_make())

    assert user.id is not None
    assert user.username == "alice"
    assert user.email == "alice@example.com"
    assert user.is_active is True
    assert user.created_at is not None
    # 密码应被 bcrypt 哈希，不能明文存储
    assert user.hashed_password != "secret"
    assert user.hashed_password.startswith("$2")


async def test_create_user_duplicate_username(db_session):
    svc = UserService(db_session)
    await svc.create_user(_make(username="bob", email="bob@example.com"))

    with pytest.raises(BizException) as exc:
        await svc.create_user(_make(username="bob", email="other@example.com"))
    assert exc.value.code == 400
    assert "用户名" in exc.value.message


async def test_create_user_duplicate_email(db_session):
    svc = UserService(db_session)
    await svc.create_user(_make(username="carol", email="dup@example.com"))

    with pytest.raises(BizException) as exc:
        await svc.create_user(_make(username="carol2", email="dup@example.com"))
    assert exc.value.code == 400
    assert "邮箱" in exc.value.message


async def test_get_user_success(db_session):
    svc = UserService(db_session)
    created = await svc.create_user(_make(username="dave", email="dave@example.com"))

    fetched = await svc.get_user(created.id)
    assert fetched.id == created.id
    assert fetched.username == "dave"


async def test_get_user_not_found(db_session):
    svc = UserService(db_session)
    with pytest.raises(BizException) as exc:
        await svc.get_user(999999)
    assert exc.value.code == 404


async def test_list_users(db_session):
    svc = UserService(db_session)
    for i in range(3):
        await svc.create_user(_make(username=f"u{i}", email=f"u{i}@example.com"))

    users, total = await svc.list_users(offset=0, limit=100)
    assert len(users) == 3
    assert total == 3


async def test_repository_get_by_username(db_session):
    svc = UserService(db_session)
    await svc.create_user(_make(username="erin", email="erin@example.com"))

    found = await svc.repo.get_by_username("erin")
    assert found is not None
    assert found.email == "erin@example.com"

    missing = await svc.repo.get_by_username("nobody")
    assert missing is None
