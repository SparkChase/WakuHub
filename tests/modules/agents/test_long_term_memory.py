"""长期记忆（LangGraph store / Milvus）探针测试。

目的：复现 supervisor_agent.py 的「长期记忆」机制（MilvusStore + BaseStore 的
aput/aget/asearch），让你能：
  1. 确认「跨会话的记忆真的写进了 Milvus，并能按 namespace 精确取回 / 语义检索」
  2. 亲眼看到 MilvusStore 懒建的 collection（agent_long_term_memory）里到底存了什么行

为什么用 fake embedding 而不是真实 embedding 服务：
  长期记忆的本质是「把 value 向量化后存进 Milvus、按 id 取回、按向量相似度检索」，
  这跟 embedding 模型好不好无关。DeterministicFakeEmbedding 对相同文本恒定产出相同
  向量（COSINE=1.0），测试才能确定性、不依赖网络和 embedding API 费用，而 Milvus 里
  存下来的行结构与真实 embedding 运行时**完全一致**（只有向量数值是假的）。

注意：连的是项目真实 Milvus（core/config 里的 MILVUS_HOST），collection 由
MilvusStore 首次实例化时懒建。测试用独立 namespace 前缀（test-ltm-*）与业务数据隔离，
测试前后各清一次本 namespace 的行，不污染真实记忆；Milvus 不可达时整体 skip。
"""
import asyncio
import time
import uuid

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from pymilvus import utility

from src.infra.milvus_client import get_milvus_client_alias
from src.infra.milvus_store import MilvusStore, COLLECTION_NAME

DIMS = 1024  # 与 supervisor_agent.py 统一 embedding（moark Qwen3-Embedding，1024 维）一致


@pytest.fixture
def milvus_alias():
    """建立/复用项目 Milvus 连接别名；连不上则 skip（远程服务未就绪时不让整套测试红）。"""
    try:
        alias = get_milvus_client_alias()
        utility.list_collections(using=alias)  # 一次真实往返，探连通性
    except Exception as e:  # noqa: BLE001 - 探针性质：任何连接异常都转为 skip
        pytest.skip(f"Milvus 不可达，跳过长期记忆测试：{e}")
    return alias


@pytest.fixture
def store(milvus_alias):
    """真实 MilvusStore + 确定性 fake embedding。实例化即触发 collection 懒建。"""
    return MilvusStore(
        alias=milvus_alias,
        embeddings=DeterministicFakeEmbedding(size=DIMS),
        dims=DIMS,
    )


async def _wait_visible(coro_factory, timeout=8.0, interval=0.3):
    """Milvus 默认 Bounded 一致性，写入后读可能有秒级延迟；轮询直到可见或超时。
    coro_factory 是一个返回协程的无参函数（每次重试需要新协程）。"""
    deadline = time.time() + timeout
    while True:
        result = await coro_factory()
        if result:
            return result
        if time.time() > deadline:
            return result
        await asyncio.sleep(interval)


async def test_put_get_search_delete(store):
    """核心断言：记忆写进 Milvus 后能精确取回、能语义检索、能删除。"""
    # 独立 namespace，避免与其它测试/业务数据串扰
    uid = f"test-ltm-{uuid.uuid4().hex[:8]}"
    ns = ("users", uid, "memories")
    content = "用户对青霉素过敏，禁用头孢类药物"

    # ① 写入一条记忆（aput -> _aput：embed + upsert + flush）
    await store.aput(ns, "m1", {"content": content, "timestamp": time.time()})

    # ② 精确取回（aget -> _aget：按 id 标量查询）。轮询等 Bounded 一致性可见
    got = await _wait_visible(lambda: store.aget(ns, "m1"))
    assert got is not None, "写入后按 (namespace, key) 取不回记忆"
    assert got.value["content"] == content

    # ③ 语义检索（asearch -> _asearch：向量 COSINE 相似度）。
    # 注意 store 的实际行为：写入时向量化的是 json.dumps(value)（含 content+timestamp 的整串），
    # 检索时向量化的是纯 query 文本，两段文本不同 —— 用确定性 fake embedding 时分数不会接近 1.0，
    # 故不对绝对分数做断言。本 namespace 只有这一条记忆，检索必然命中它；
    # 真实 embedding 下语义相近才会给出高分。这里验证的是「向量检索链路通 + namespace 过滤 + 返回正确记忆」。
    hits = await _wait_visible(lambda: store.asearch(ns, query=content, limit=5))
    assert hits, "语义检索取不到刚写入的记忆"
    assert hits[0].value["content"] == content, "检索返回的记忆内容不对"

    # ④ 删除（adelete -> PutOp value=None -> _aput 走 delete 分支）
    await store.adelete(ns, "m1")
    deleted = False
    for _ in range(20):
        if await store.aget(ns, "m1") is None:
            deleted = True
            break
        await asyncio.sleep(0.3)
    assert deleted, "删除后仍能取到记忆"


async def test_isolation_and_inspect(store, milvus_alias, capsys):
    """跨用户隔离 + 打印 Milvus 里实际存的行，让你亲眼看到长期记忆落库结构。
    用 `uv run pytest tests/modules/agents/test_long_term_memory.py -s` 看输出。
    """
    ua, ub = f"test-ltm-{uuid.uuid4().hex[:8]}", f"test-ltm-{uuid.uuid4().hex[:8]}"
    ns_a = ("users", ua, "memories")
    ns_b = ("users", ub, "memories")

    await store.aput(ns_a, "m1", {"content": "A 用户：有高血压病史", "timestamp": time.time()})
    await store.aput(ns_b, "m1", {"content": "B 用户：孕期，慎用药物", "timestamp": time.time()})

    # A 用户检索只能看到 A 自己的记忆（namespace 前缀过滤）
    hits_a = await _wait_visible(lambda: store.asearch(ns_a, query="A 用户：有高血压病史", limit=5))
    assert hits_a and all(h.namespace == ns_a for h in hits_a), "namespace 隔离失效，串到别的用户"

    with capsys.disabled():
        # ① collection 是 MilvusStore 懒建的，不走 alembic —— 确认它确实存在
        exists = utility.has_collection(COLLECTION_NAME, using=milvus_alias)
        print("\n" + "=" * 70)
        print(f"Milvus collection '{COLLECTION_NAME}' 存在：{exists}（由 MilvusStore 首次实例化懒建）")
        coll = store._collection
        print(f"schema 字段：{[f.name for f in coll.schema.fields]}")

        # ② 直接查底层 collection，打印本次两个测试用户写入的行
        rows = coll.query(
            expr='namespace like "users/test-ltm-%"',
            output_fields=["id", "namespace", "key", "value_json", "created_at"],
            limit=50,
        )
        print(f"\n本次写入 Milvus 的记忆行（{len(rows)} 条）：")
        for r in rows:
            print(f"    id={r['id']}")
            print(f"       namespace={r['namespace']}  key={r['key']}")
            print(f"       value_json={r['value_json']}")
        print("=" * 70)

    assert exists

    # 清理本次两个测试用户的行，不留残渣
    for ns in (ns_a, ns_b):
        await store.adelete(ns, "m1")
