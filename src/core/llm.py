# src/core/llm.py
"""统一的 Chat 模型工厂。

各 agent 不再各自 new 一遍 chat model，统一走这里，避免 base_url / api_key / model
散落多处、改一处漏一处。provider 无关：走 OpenAI 兼容接口（CHAT_BASE_URL），
具体用哪家模型由 .env 里的 CHAT_BASE_URL / CHAT_MODEL 决定，调用方不感知厂商。
（与 infra/embedding.py 的 get_embedding_model 同一设计。）
"""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from src.core.config import get_settings

settings = get_settings()


def get_llm(model: str | None = None, temperature: float = 0.3) -> BaseChatModel:
    """返回统一的 Chat 模型实例。

    model / temperature 缺省走 settings，调用方按需覆盖（不同 agent 可要不同模型或温度）。
    """
    return ChatOpenAI(
        base_url=settings.CHAT_BASE_URL,
        api_key=settings.CHAT_API_KEY,
        model=model or settings.CHAT_MODEL,
        temperature=temperature,
    )
