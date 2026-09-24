# src/infra/embedding.py
"""统一的 Embedding 工厂。

建索引（scripts/init_symptom_index.py）与检索（workers/*.py）必须使用同一个
Embedding 模型，否则向量空间不一致、检索无效。统一收敛到此处，避免各处各写一份。

走 Gitee AI 的 OpenAI 兼容接口（EMBEDDING_BASE_URL / EMBEDDING_API_KEY / EMBEDDING_MODEL）。
"""

from langchain_openai import OpenAIEmbeddings

from src.core.config import get_settings

settings = get_settings()


def get_embedding_model() -> OpenAIEmbeddings:
    """返回统一的 Embedding 模型实例（Gitee AI，OpenAI 兼容接口）。"""
    return OpenAIEmbeddings(
        base_url=settings.EMBEDDING_BASE_URL,
        api_key=settings.EMBEDDING_API_KEY,
        model=settings.EMBEDDING_MODEL,
        # 第三方 OpenAI 兼容服务不识别 tiktoken 的 token-id 输入，
        # 关掉 langchain 的 token 长度预处理，直接把原文发给服务端分词
        check_embedding_ctx_length=False,
    )


async def probe_embedding_dim() -> int:
    """探测当前 Embedding 模型的输出维度。

    不同模型维度不同（如 Qwen3-Embedding 0.6B=1024 / 4B=2560 / 8B=4096），
    建 Milvus collection 前用一次探针请求拿到真实维度，避免硬编码猜错。
    """
    model = get_embedding_model()
    vec = await model.aembed_query("探针")
    return len(vec)
