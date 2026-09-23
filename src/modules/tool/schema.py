from pydantic import BaseModel


class FunctionDefinitionSchema(BaseModel):
    """OpenAI Function Calling 格式"""
    name: str
    description: str
    parameters: dict  # JSON Schema 格式


class ToolCreate(BaseModel):
    name: str
    description: str | None = None
    type: str                                    # builtin / http_api / custom_function
    config: dict | None = None                   # 工具配置
    function_definition: FunctionDefinitionSchema | None = None


class ToolUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict | None = None
    function_definition: FunctionDefinitionSchema | None = None


class ToolRead(BaseModel):
    id: int
    name: str
    description: str | None
    type: str
    status: str
    config: dict | None
    function_definition: dict | None
    call_count_7d: int
    success_rate: float
    avg_latency: int
    created_by: str | None

    model_config = {"from_attributes": True}


class ToolTestRequest(BaseModel):
    """测试工具请求"""
    input: dict  # 测试输入参数


class ToolTestResponse(BaseModel):
    """测试工具响应"""
    success: bool
    output: dict | None = None
    error: str | None = None
    latency_ms: int = 0