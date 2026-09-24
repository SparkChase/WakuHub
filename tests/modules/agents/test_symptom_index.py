"""症状向量索引 & 统一 embedding 工厂的冒烟测试。

注意：这些测试会真实调用 embedding API（moark），每次调用都会产生费用，
因此刻意保持最小规模——全文件累计仅 2 次 embedding 请求。
依赖：远程 Milvus 中已存在 symptom_index（由 scripts/init_symptom_index.py 构建）。
"""
from pymilvus import MilvusClient

from src.infra.embedding import get_embedding_model, probe_embedding_dim
from src.infra.milvus_client import get_milvus_uri
from src.agents.inquiry.symptom_normalizer import semantic_match_symptoms

SYMPTOM_COLLECTION = "symptom_index"


def _milvus_client() -> MilvusClient:
    return MilvusClient(uri=get_milvus_uri())


async def test_embedding_factory_dim():
    """统一工厂能连通并返回向量；维度应与症状索引一致（1024）。消耗 1 次 embedding 调用。"""
    dim = await probe_embedding_dim()
    assert dim == 1024


async def test_symptom_semantic_self_match():
    """用索引中真实存在的症状名做语义检索，应命中自己（cosine≈1）。消耗 1 次 embedding 调用。

    先从 Milvus 取一条真实 name（query 不消耗 embedding 费用），
    再走 semantic_match_symptoms 检索，验证 embedding→检索 端到端链路及维度匹配。
    """
    client = _milvus_client()
    # query 一条真实症状名，不产生 embedding 费用
    rows = client.query(
        collection_name=SYMPTOM_COLLECTION,
        filter='id != ""',
        limit=1,
        output_fields=["name"],
    )
    assert rows, "symptom_index 为空，请先运行 scripts/init_symptom_index.py"
    name = rows[0]["name"]

    model = get_embedding_model()
    mapped, still_unmatched = await semantic_match_symptoms([name], model, client)

    # 用自己检索自己，必然命中且相似度高于阈值
    assert mapped.get(name) == name
    assert not still_unmatched
