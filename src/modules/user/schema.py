from pydantic import BaseModel, EmailStr

from src.modules.role.schema import RoleRead


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


# 分配角色入参：全量覆盖，传入的 id 列表即为该用户最终拥有的角色
class UserAssignRoles(BaseModel):
    role_ids: list[int]


class UserRead(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool

    # 从 orm 模型中读取数据时，需要设置 from_attributes=True
    # java 以前的beanutils.copyProperties 方法
    model_config = {"from_attributes": True}


# 带角色的用户出参：在 UserRead 基础上内嵌用户拥有的角色列表
class UserWithRolesRead(UserRead):
    roles: list[RoleRead] = []


