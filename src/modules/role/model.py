from sqlalchemy import Table, Column, BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.base_model import Base, BaseModel

# 角色权限关联表 复合主键 天然防止重复
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", BigInteger, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


# 角色表： role.permissions 可以拿到角色对应的所有权限 
class Role(BaseModel):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(100), unique=True, comment="角色编码")
    name: Mapped[str] = mapped_column(String(100), comment="角色名称")
    description: Mapped[str] = mapped_column(String(200), nullable=True, comment="角色描述")

    # 多对多关联：角色拥有多个权限
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary=role_permissions,
        lazy="selectin", # 立即加载关联的权限
        # backref="roles",  # 注释掉的旧写法，现代推荐用 back_populates
    )

# user.roles 可以拿到用户对应的所有角色
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)