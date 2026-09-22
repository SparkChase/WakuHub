"""密码哈希工具（bcrypt）。

无状态工具类，方法均为 @staticmethod：
    PasswordHasher.hash("plain") / PasswordHasher.verify("plain", hashed)
"""
import bcrypt


class PasswordHasher:
    """基于 bcrypt 的密码哈希工具。bcrypt 自带盐，无需单独存盐。"""

    @staticmethod
    def hash(password: str) -> str:
        # bcrypt 处理 bytes，最长 72 字节；返回带盐的哈希串，存库直接用 str
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        return hashed.decode("utf-8")

    @staticmethod
    def verify(password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
