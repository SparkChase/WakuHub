"""短期记忆（LangGraph checkpointer）探针测试。

目的：不是测业务正确性，而是用最小可运行的 Agent 复现 supervisor_agent.py 的
「短期记忆」机制（AsyncRedisSaver + create_agent + checkpointer），让你能：
  1. 确认「同一 thread_id 的多轮对话，历史会被 checkpointer 持久化并自动带入下一轮」
  2. 直接打印出 langgraph-checkpoint-redis 到底往 Redis 里塞了哪些 key、什么结构

为什么用 fake model 而不是真实 LLM：
  短期记忆的本质是「checkpointer 把 message 历史存进 Redis、下一轮再读回来」，
  这跟模型答得对不对无关。用 GenericFakeChatModel 返回固定回复，测试才能确定性、
  不依赖网络和 API key，而 Redis 里存下来的 key/JSON 结构与真实 LLM 运行时**完全一致**
  （只有 message 的 content 是假的）——这正是你想看的东西。

注意：这里刻意用独立 bytes 模式客户端连测试库 db 15（AsyncRedisSaver 要求 bytes，
不能 decode_responses），与业务 db 0 隔离，不污染真实数据。测试跑完保留数据供你翻，
清理命令见文件末尾。
"""
import json

import pytest
import redis.asyncio as aredis
from langchain_core.messages import AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain.agents import create_agent
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from src.core.config import get_settings

_settings = get_settings()

# 探针数据固定放测试库 db 15，用可辨识的 thread_id 前缀方便你事后在 redis-cli 里 grep
INSPECT_DB = 15
THREAD_ID = "demo-user:demo-session"


def _make_agent(checkpointer, replies: list[str]):
    """构造一个最小 Agent：只挂 checkpointer（短期记忆），不挂 store / tools。
    replies 是 fake model 按顺序吐出的固定回复，每次 ainvoke（无工具）消耗一条。
    """
    model = GenericFakeChatModel(messages=iter([AIMessage(content=r) for r in replies]))
    return create_agent(model=model, tools=[], checkpointer=checkpointer)


async def _scan(client, pattern: bytes) -> list[bytes]:
    """SCAN 出所有匹配 key（不用 KEYS，避免大库阻塞的坏习惯）。"""
    keys, cursor = [], 0
    while True:
        cursor, batch = await client.scan(cursor, match=pattern, count=200)
        keys += batch
        if cursor == 0:
            break
    return keys


@pytest.fixture
async def checkpointer_client():
    """bytes 模式的 Redis 客户端（db 15）。测试前清掉本 thread 的残留 key，保证可重复跑；
    测试后**不清理**，方便你去 redis 里翻。"""
    client = aredis.Redis(
        host=_settings.REDIS_HOST,
        port=_settings.REDIS_PORT,
        db=INSPECT_DB,
        password=_settings.REDIS_PASSWORD or None,
        decode_responses=False,  # AsyncRedisSaver 要求 bytes
    )
    stale = await _scan(client, f"*{THREAD_ID}*".encode())
    if stale:
        await client.delete(*stale)
    yield client
    await client.aclose()


async def test_short_term_memory_persists_across_agent_instances(checkpointer_client):
    """核心断言：短期记忆存在 Redis 里，不在 Agent 对象里。

    用两个**不同的** Agent 实例（agent_a / agent_b）共享同一个 checkpointer + thread_id：
    agent_a 跑第一轮，agent_b 跑第二轮。如果 agent_b 能看到第一轮的历史，
    就证明记忆是从 Redis checkpointer 读回来的，而非进程内存。
    """
    checkpointer = AsyncRedisSaver(redis_client=checkpointer_client)
    await checkpointer.asetup()  # 首次建 RediSearch 索引，幂等，可重复调
    config = {"configurable": {"thread_id": THREAD_ID}}

    # 第一轮：agent_a
    agent_a = _make_agent(checkpointer, replies=["你好，我记住了。"])
    await agent_a.ainvoke(
        {"messages": [{"role": "user", "content": "我叫 Trace，在做医疗 Agent。"}]},
        config=config,
    )

    # 第二轮：换一个全新的 agent_b（同 checkpointer、同 thread_id）
    agent_b = _make_agent(checkpointer, replies=["当然记得。"])
    result = await agent_b.ainvoke(
        {"messages": [{"role": "user", "content": "你还记得我叫什么吗？"}]},
        config=config,
    )

    # agent_b 的对话历史里应包含第一轮 agent_a 的用户消息 —— 记忆确实来自 Redis
    contents = [m.content for m in result["messages"]]
    assert any("我叫 Trace" in c for c in contents), \
        "第二个 Agent 实例没读到第一轮历史，短期记忆未生效"
    # 累计 4 条：h1, ai1, h2, ai2
    assert len(result["messages"]) == 4


async def test_inspect_what_checkpointer_writes_to_redis(checkpointer_client, capsys):
    """跑一段对话，然后把 checkpointer 写进 Redis 的 key 和结构完整打印出来。
    用 `uv run pytest tests/modules/agents/test_supervisor_memory.py -s` 看输出。
    """
    checkpointer = AsyncRedisSaver(redis_client=checkpointer_client)
    await checkpointer.asetup()
    config = {"configurable": {"thread_id": THREAD_ID}}

    agent = _make_agent(checkpointer, replies=["第一条回复", "第二条回复"])
    await agent.ainvoke(
        {"messages": [{"role": "user", "content": "第一句话"}]}, config=config
    )
    await agent.ainvoke(
        {"messages": [{"role": "user", "content": "第二句话"}]}, config=config
    )

    client = checkpointer_client
    with capsys.disabled():  # 让 print 直接进终端，不被 pytest 捕获
        # ① 按前缀分组统计所有 key
        keys = sorted(await _scan(client, f"*{THREAD_ID}*".encode()))
        groups: dict[str, list[str]] = {}
        for k in keys:
            ks = k.decode()
            prefix = ks.split(":", 1)[0]  # checkpoint / checkpoint_write / checkpoint_latest / write_keys_zset
            groups.setdefault(prefix, []).append(ks)

        print("\n" + "=" * 70)
        print(f"checkpointer 在 Redis(db {INSPECT_DB}) 为 thread='{THREAD_ID}' 写入的 key：")
        print("=" * 70)
        for prefix, ks in sorted(groups.items()):
            print(f"\n▶ {prefix}  （{len(ks)} 个）")
            for k in ks:
                # key 结构：<prefix>:<thread_id>:<checkpoint_ns>:<checkpoint_id>...
                print(f"    {k}")

        # ② RediSearch 索引（asetup 建的，langgraph 靠它按 thread 检索 checkpoint）
        indexes = await client.execute_command("FT._LIST")
        print(f"\n▶ RediSearch 索引（asetup 创建）：{[i.decode() for i in indexes]}")

        # ③ 挑一个 checkpoint 文档，看它是 RedisJSON、里面存了什么
        cp_keys = [k for k in keys if k.decode().startswith("checkpoint:")]
        sample = cp_keys[-1]  # 最后一个，含完整 message 历史
        key_type = (await client.type(sample)).decode()
        raw = await client.execute_command("JSON.GET", sample)
        # redis-py 对 JSON.GET 已自动反序列化成 Python 对象；旧版本可能返回 bytes/str
        doc = raw if isinstance(raw, dict) else json.loads(raw)
        print("\n" + "=" * 70)
        print(f"抽样 checkpoint 文档：{sample.decode()}")
        print(f"Redis 类型：{key_type}（RedisJSON 文档，标准 redis 存不了，需 Redis 8 / redis-stack）")
        print(f"顶层字段：{list(doc.keys())}")
        print(f"step={doc.get('step')}  source={doc.get('source')}  ns='{doc.get('checkpoint_ns')}'")

        # channel_values.messages 就是被持久化的对话历史
        channel_values = doc.get("checkpoint", {}).get("channel_values", {})
        print(f"\ncheckpoint.channel_values 通道：{list(channel_values.keys())}")
        msgs = channel_values.get("messages", [])
        print(f"messages 通道里持久化了 {len(msgs)} 条消息：")
        for m in msgs:
            # 每条 message 被序列化成带 lc/type/kwargs 的字典
            kwargs = m.get("kwargs", m) if isinstance(m, dict) else {}
            print(f"    - {kwargs.get('type', '?'):10s} | {str(kwargs.get('content', m))[:40]}")
        print("=" * 70)

    # 断言：确实写了 checkpoint、且 message 历史被存进 RedisJSON
    assert any(k.decode().startswith("checkpoint:") for k in keys)
    assert channel_values.get("messages"), "checkpoint 里没存到 messages 通道"


# ── 事后在 Redis 里手动翻看（测试保留了数据，db 15）────────────────────────────
# 列出本次 thread 的所有 key：
#   docker exec redis-latest redis-cli -a 123456 -n 15 --scan --pattern '*demo-user:demo-session*'
# 看某个 checkpoint 的 JSON：
#   docker exec redis-latest redis-cli -a 123456 -n 15 JSON.GET '<上面某个 checkpoint:... key>'
# 看 RediSearch 索引信息：
#   docker exec redis-latest redis-cli -a 123456 -n 15 FT._LIST
# 清理本次探针数据：
#   docker exec redis-latest redis-cli -a 123456 -n 15 --scan --pattern '*demo-user:demo-session*' | xargs docker exec -i redis-latest redis-cli -a 123456 -n 15 DEL
