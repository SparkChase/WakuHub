# scripts/init_symptom_index.py
"""
症状向量索引初始化脚本。
首次部署时执行一次，之后 Neo4j 新增症状时增量执行。

用法：
    python scripts/init_symptom_index.py
"""

import argparse
import asyncio
import sys
import os

# 把项目根目录加入 Python 路径，确保能 import src 下的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymilvus import (
    connections, Collection, CollectionSchema,
    FieldSchema, DataType, utility,
)
from neo4j import AsyncGraphDatabase
from src.core.config import get_settings
from src.infra.embedding import get_embedding_model, probe_embedding_dim

settings = get_settings()

COLLECTION_NAME = "symptom_index"
MILVUS_ALIAS = "symptom_init"


def _get_collection_dim(col: Collection) -> int:
    """读取已存在 collection 的 embedding 字段维度。"""
    for f in col.schema.fields:
        if f.name == "embedding":
            return f.params["dim"]
    raise RuntimeError(f"collection '{COLLECTION_NAME}' 缺少 embedding 字段")


def ensure_symptom_collection(alias: str, dim: int, rebuild: bool = False) -> Collection:
    """
    确保 symptom_index collection 存在且维度与当前模型一致。
    维度一致则复用；维度不符时：默认报错提示，--rebuild 时 drop 重建（清空旧向量）。
    """
    if utility.has_collection(COLLECTION_NAME, using=alias):
        col = Collection(COLLECTION_NAME, using=alias)
        existing_dim = _get_collection_dim(col)
        # 维度一致且非强制重建：直接复用
        if existing_dim == dim and not rebuild:
            print(f"[INFO] collection '{COLLECTION_NAME}'(dim={dim}) 已存在，跳过创建。")
            col.load()
            return col
        # 维度不符但未指定 --rebuild：拒绝静默删数据，报错让用户显式确认
        if existing_dim != dim and not rebuild:
            raise SystemExit(
                f"[ERROR] 已存在 collection 维度为 {existing_dim}，与当前模型输出 {dim} 不符。\n"
                f"        确认 EMBEDDING_MODEL 无误后，加 --rebuild 删除旧 collection 重建（会清空已有向量）。"
            )
        # drop 旧 collection，按新维度重建
        print(f"[WARN] drop 旧 collection '{COLLECTION_NAME}'(dim={existing_dim})，按 dim={dim} 重建。")
        utility.drop_collection(COLLECTION_NAME, using=alias)

    fields = [
        # 用症状名作为主键，天然去重，更新时直接 upsert
        FieldSchema(name="id",        dtype=DataType.VARCHAR, max_length=256, is_primary=True),
        FieldSchema(name="name",      dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
    ]
    schema = CollectionSchema(fields, description="Neo4j Symptom nodes vector index")
    col = Collection(COLLECTION_NAME, schema=schema, using=alias)
    col.create_index(
        field_name="embedding",
        index_params={
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        },
    )
    col.load()
    print(f"[INFO] collection '{COLLECTION_NAME}' 创建成功。")
    return col


async def fetch_all_symptoms(neo4j_driver) -> list[str]:
    """从 Neo4j 取出所有 Symptom 节点的名称。"""
    async with neo4j_driver.session() as session:
        result = await session.run("MATCH (s:Symptom) RETURN s.name AS name")
        records = await result.data()
    names = [r["name"] for r in records if r["name"]]
    print(f"[INFO] 从 Neo4j 获取到 {len(names)} 个症状节点。")
    return names


async def build_symptom_index(rebuild: bool = False):
    """主流程：全量构建症状向量索引。"""
    # 0. 探测 embedding 维度（不同模型维度不同，避免硬编码猜错，也作为 API Key/连通性的前置校验）
    dim = await probe_embedding_dim()
    print(f"[INFO] 探测到 embedding 维度：{dim}")

    # 1. 连接 Milvus
    # .env 里 MILVUS_HOST 可能带 http:// 协议头，而 connect 的 host 参数只接受纯主机名/IP
    # （pymilvus is_legal_host 会拒绝含 ":" 的值），与 infra/milvus_client.py 保持一致，剥掉协议头
    host = settings.MILVUS_HOST.split("://", 1)[-1]
    connections.connect(
        alias=MILVUS_ALIAS,
        host=host,
        port=settings.MILVUS_PORT,
    )
    col = ensure_symptom_collection(MILVUS_ALIAS, dim, rebuild)

    # 2. 连接 Neo4j，获取所有症状名
    neo4j_driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    symptom_names = await fetch_all_symptoms(neo4j_driver)
    await neo4j_driver.close()

    if not symptom_names:
        print("[WARN] Neo4j 中没有 Symptom 节点，请先导入医疗数据。")
        return

    # 3. 批量向量化（每批 100 个，避免单次请求过大）
    embedding_model = get_embedding_model()
    batch_size = 100
    all_data = []
    for i in range(0, len(symptom_names), batch_size):
        batch = symptom_names[i: i + batch_size]
        embeddings = await embedding_model.aembed_documents(batch)
        for name, emb in zip(batch, embeddings):
            all_data.append({"id": name, "name": name, "embedding": emb})
        print(f"[INFO] 已向量化 {min(i + batch_size, len(symptom_names))}/{len(symptom_names)}")

    # 4. 写入 Milvus（upsert 语义：先删同名旧记录，再插入）
    # pymilvus 的 Collection.upsert 在 v2.x 中等价于 delete + insert
    col.upsert(all_data)
    col.flush()
    print(f"[INFO] 症状索引构建完成，共写入 {len(all_data)} 条记录。")

    # 5. 断开连接
    connections.disconnect(alias=MILVUS_ALIAS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="构建/更新症状向量索引")
    parser.add_argument(
        "--rebuild", action="store_true",
        help="模型维度与已存在 collection 不符时，删除旧 collection 重建（会清空已有向量）",
    )
    cli_args = parser.parse_args()
    asyncio.run(build_symptom_index(rebuild=cli_args.rebuild))