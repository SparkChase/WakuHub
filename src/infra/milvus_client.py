from loguru import logger
from pymilvus import connections, utility

from src.core.config import get_settings

settings = get_settings()
MILVUS_ALIAS = "waku_milvus"


def get_milvus_client_alias() -> str:
    """
    返回 Milvus 连接别名。
    若连接不存在会自动创建，供业务层复用。
    """
    # .env 里 MILVUS_HOST 可能带 http:// 协议头，而 connect 的 host 参数只接受纯主机名/IP，
    # 带协议头会被 pymilvus 解析成非 str 而报错，这里统一剥掉协议头
    host = settings.MILVUS_HOST.split("://", 1)[-1]
    connections.connect(
        alias=MILVUS_ALIAS,
        host=host,
        port=settings.MILVUS_PORT,
    )
    return MILVUS_ALIAS


def get_milvus_dependency() -> str:
    """
    FastAPI Depends 注入用。
    返回可复用的 Milvus 连接别名。
    """
    return get_milvus_client_alias()


def check_milvus_health() -> bool:
    """
    检查 Milvus 连通性。
    通过拉取集合列表验证连接是否可用。
    """
    alias = get_milvus_client_alias()
    collections = utility.list_collections(using=alias)
    logger.info(f"Milvus 连接成功，当前集合数量：{len(collections)}")
    return True


def close_milvus_client() -> None:
    """关闭 Milvus 连接。"""
    connections.disconnect(alias=MILVUS_ALIAS)
