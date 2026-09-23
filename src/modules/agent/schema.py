from pydantic import BaseModel
from datetime import datetime


class AgentConfigSchema(BaseModel):
    """Agent 配置"""
    model: dict | None = None       # {modelId, temperature, maxTokens, topP}
    prompt: dict | None = None      # {systemPrompt, promptTemplateId}
    rag: dict | None = None         # {enabled, knowledgeBaseIds, ...}
    tools: dict | None = None       # {enabled, toolIds}
    advanced: dict | None = None    # {welcomeMessage, suggestedQuestions, ...}


class AgentCreate(BaseModel):
    name: str
    description: str | None = None
    type: str
    model_id: int | None = None
    config: AgentConfigSchema | None = None


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    type: str | None = None
    model_id: int | None = None
    config: AgentConfigSchema | None = None


class AgentRead(BaseModel):
    id: int
    name: str
    description: str | None
    type: str
    status: str
    model_id: int | None
    config: dict | None
    success_rate: float
    call_count_7d: int
    version: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentVersionRead(BaseModel):
    id: int
    agent_id: int
    version: str
    config: dict | None
    changelog: str | None
    is_current: bool
    published_by: str | None
    published_at: datetime | None

    model_config = {"from_attributes": True}


class PublishRequest(BaseModel):
    changelog: str = ""


class RollbackRequest(BaseModel):
    version_id: int