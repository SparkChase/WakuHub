from pydantic import BaseModel


class ModelCreate(BaseModel):
    name: str
    model_id: str
    provider_id: int
    capabilities: list[str] = []
    context_length: int = 4096
    input_price: float = 0
    output_price: float = 0
    currency: str = "USD"
    is_default: bool = False
    description: str | None = None


class ModelUpdate(BaseModel):
    name: str | None = None
    capabilities: list[str] | None = None
    context_length: int | None = None
    status: str | None = None
    input_price: float | None = None
    output_price: float | None = None
    currency: str | None = None
    is_default: bool | None = None
    description: str | None = None


class ModelRead(BaseModel):
    id: int
    name: str
    model_id: str
    provider_id: int
    provider_name: str = ""       # 从关联对象中取
    capabilities: list[str] = []  # 从逗号分隔字符串转换
    context_length: int
    status: str
    input_price: float
    output_price: float
    currency: str
    is_default: bool
    description: str | None

    model_config = {"from_attributes": True}
