from sqlalchemy.ext.asyncio import AsyncSession
from src.core.exceptions import BizException
from src.modules.role.repository import RoleRepository
from src.modules.user.model import User
from src.modules.user.schema import UserCreate
from src.modules.user.repository import UserRepository
from src.utils.password import PasswordHasher


class UserService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)
        self.role_repo = RoleRepository(db)

    # 创建用户
    async def create_user(self, data: UserCreate) -> User:
        # 1. 校验用户名唯一
        if await self.repo.get_by_username(data.username):
            raise BizException(code=400, message="用户名已存在")
        # 2. 校验邮箱唯一
        if await self.repo.get_by_email(data.email):
            raise BizException(code=400, message="邮箱已存在")

        # 3. 构造 ORM 对象：密码经哈希后存储，绝不存明文
        user = User(
            username=data.username,
            email=data.email,
            hashed_password=PasswordHasher.hash(data.password),
        )
        # 4. 落库并返回（拿到自增 id）
        return await self.repo.create(user)

    # 按 id 查询单个用户，查不到直接抛 404
    async def get_user(self, user_id: int) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise BizException(code=404, message="用户不存在")
        return user

    # 分页 + 模糊搜索列出用户，返回 (数据列表, 总条数)
    async def list_users(
        self, offset: int, limit: int, keyword: str | None = None
    ) -> tuple[list[User], int]:
        # 按 username / email 模糊匹配 keyword
        return await self.repo.get_page(
            offset=offset,
            limit=limit,
            keyword=keyword,
            search_fields=["username", "email"],
        )

    # 给用户分配角色（全量覆盖：传入的 id 列表即为用户最终的角色集合）
    async def assign_roles(self, user_id: int, role_ids: list[int]) -> User:
        # 1. 取出用户（不存在抛 404）
        user = await self.get_user(user_id)
        # 2. 按 id 批量捞角色对象
        roles = await self.role_repo.get_by_ids(role_ids)
        # 3. 数量对比校验：查出的角色数 != 去重后的入参 id 数，说明有 id 不存在，拒绝
        if len(roles) != len(set(role_ids)):
            raise BizException(code=400, message="部分角色不存在")

        # 4. 全量覆盖：直接替换关联集合，SQLAlchemy 会自动增删 user_roles 关联行
        user.roles = roles
        # 5. 持久化
        return await self.repo.update(user)