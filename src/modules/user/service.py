from sqlalchemy.ext.asyncio import AsyncSession
from src.core.exceptions import BizException
from src.modules.user.model import User
from src.modules.user.schema import UserCreate
from src.modules.user.repository import UserRepository


class UserService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)

    async def create_user(self, data: UserCreate) -> User:
        if await self.repo.get_by_username(data.username):
            raise BizException(code=400, message="用户名已存在")
        if await self.repo.get_by_email(data.email):
            raise BizException(code=400, message="邮箱已存在")

        user = User(
            username=data.username,
            email=data.email,
            hashed_password=data.password,  # 项目开发时用 bcrypt 等加密
        )
        return await self.repo.create(user)

    async def get_user(self, user_id: int) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise BizException(code=404, message="用户不存在")
        return user

    async def list_users(self, offset: int = 0, limit: int = 100):
        return await self.repo.get_all(offset=offset, limit=limit)