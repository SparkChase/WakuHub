from pydantic import BaseModel


class ProviderCreate(BaseModel):
    """创建供应商请求"""
    name: str
    type: str          # openai / anthropic / aliyun / azure / local / custom
    endpoint: str
    api_key: str | None = None
    description: str | None = None


class ProviderUpdate(BaseModel):
    """更新供应商请求 — 所有字段可选"""
    name: str | None = None
    type: str | None = None
    endpoint: str | None = None
    api_key: str | None = None
    description: str | None = None


class ProviderRead(BaseModel):
    """供应商响应"""
    id: int
    name: str
    type: str
    status: str
    endpoint: str
    description: str | None
    model_count: int = 0       # 关联模型数量，Service 层计算后填入

    model_config = {"from_attributes": True}
