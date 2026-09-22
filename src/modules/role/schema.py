from pydantic import BaseModel

from src.modules.permission.schema import PermissionRead


# 创建角色入参：code 唯一标识，创建后不可改
class RoleCreate(BaseModel):
    code: str
    name: str
    description: str | None = None


# 更新角色入参：只允许改 name / description
class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


# 分配权限入参：全量覆盖，传入的 id 列表即为该角色最终拥有的权限
class RoleAssignPermissions(BaseModel):
    permission_ids: list[int]


# 角色出参：内嵌该角色拥有的权限列表
class RoleRead(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    permissions: list[PermissionRead] = []

    # from_attributes：允许 model_validate 直接从 ORM 对象读属性（含关联的 permissions）
    model_config = {"from_attributes": True}
