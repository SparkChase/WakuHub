from pydantic import BaseModel


# 创建权限入参：code 是唯一标识（命名如 user:create），创建后不可改
class PermissionCreate(BaseModel):
    code: str
    name: str
    description: str | None = None


# 更新权限入参：只允许改 name / description，code 不在其中（不能修改 code）
class PermissionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


# 权限出参
class PermissionRead(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None

    # from_attributes：允许 model_validate 直接从 ORM 对象读属性
    model_config = {"from_attributes": True}
