"""PasswordHasher 工具类单元测试（bcrypt）。"""
from src.utils.password import PasswordHasher


def test_password_hash_and_verify():
    hashed = PasswordHasher.hash("my-secret")
    assert hashed != "my-secret"
    assert hashed.startswith("$2")  # bcrypt 前缀
    assert PasswordHasher.verify("my-secret", hashed) is True
    assert PasswordHasher.verify("wrong", hashed) is False


def test_password_hash_is_salted():
    # 同一明文两次哈希结果不同（盐随机），但都能校验通过
    h1 = PasswordHasher.hash("same")
    h2 = PasswordHasher.hash("same")
    assert h1 != h2
    assert PasswordHasher.verify("same", h1)
    assert PasswordHasher.verify("same", h2)
