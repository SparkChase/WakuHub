from src.core.base_repository import BaseRepository
from src.modules.user.model import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# 用户仓储：继承通用 CRUD，额外提供按用户名 / 邮箱查询
class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    # 按用户名查询，用于登录鉴权和创建时校验唯一
    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # 按邮箱查询，用于创建时校验唯一
    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()