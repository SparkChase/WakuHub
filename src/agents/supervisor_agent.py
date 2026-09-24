from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.redis import AsyncRedisSaver
from langchain.agents import create_agent
from src.core.llm import get_llm
from src.agents.tools.worker_tools import UserContext
from src.agents.tools.store_tools import save_memory, search_memory
from src.agents.tools.worker_tools import WORKER_TOOLS
from src.infra.milvus_client import get_milvus_client_alias
from src.infra.milvus_store import MilvusStore
from src.infra.redis import get_checkpointer_redis
from src.infra.embedding import get_embedding_model, probe_embedding_dim
from dotenv import load_dotenv
load_dotenv()


# 创建出 监督 Agent
async def create_supervisor_agent():
    # 1. 复用项目已有的 checkpointer 专用 Redis 客户端（bytes 模式）
    redis_client = get_checkpointer_redis()

    # 2. 创建 AsyncRedisSaver，并调用 asetup() 初始化 RediSearch 索引
    # asetup() 会在 Redis Stack 中创建 checkpoint / checkpoint_write 两个索引
    # 必须在首次使用前调用一次，索引已存在时自动跳过，可以重复调用
    checkpointer = AsyncRedisSaver(redis_client=redis_client)
    await checkpointer.asetup()


    # 3. 长期记忆
    # ── 长期记忆：Milvus Store ─────────────────────────────────────────
    milvus_alias = get_milvus_client_alias()
    embedding_model = get_embedding_model()
    store = MilvusStore(
        alias=milvus_alias,
        embeddings=embedding_model,
        dims=await probe_embedding_dim(),   # 探测实际维度，与症状索引/检索侧保持一致
    )

    # 4. 长期记忆工具
    tools = [save_memory, search_memory] + WORKER_TOOLS
    SUPERVISOR_SYSTEM_PROMPT = """你是天宫医疗的智能总助手（Supervisor）。

    你的核心职责：
    1. 与患者/医生/运营人员进行多轮对话
    2. 准确识别用户意图，将任务分派给合适的专项助手
    3. 整合专项助手的结果，给出清晰、友好的最终回复
    4. 主动收集必要信息（如症状描述不清时追问）
    5. 管理对话上下文，保持对话连贯性

    可调用的专项助手：
    - call_inquiry_agent：智慧问诊（症状分诊、挂号建议）
    - call_report_agent：报告解读（检验单、影像报告）
    - call_drug_agent：药物咨询（用药推荐、药物交互、处方审查）
    - call_knowledge_agent：医学知识问答（疾病科普、治疗方案）
    - call_operation_agent：运营数据查询（仅限内部运营人员）

    记忆工具：
    - save_memory：将重要信息（病史、过敏史、用药偏好等）保存到长期记忆
    - search_memory：从长期记忆中检索用户历史信息

    工作原则：
    - 优先从长期记忆中检索用户历史信息，避免重复询问
    - 需要调用专项助手进行处理，你不做回答只做调用
    - 遇到复杂问题可以串联多个专项助手（先问诊再查药）
    - 始终以患者安全为第一优先级
    - 对话语气温和、专业、易懂"""
    # 4. 创建 Agent
    agent = create_agent(
        model=get_llm(),
        tools=tools,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        context_schema=UserContext,
        middleware=[
            SummarizationMiddleware( # 会话总结压缩
                model=get_llm(),
                trigger=[
                    ("tokens", 4000),  # token数达到4k时触发
                    ("messages", 6),  # 或消息数达到 4条时触发
                    # ("fraction", 0.8)  # 或80%消息时触发
                ],
                keep=("messages", 6),  # 摘要后保留最近 4 条消息
            )
        ],
        checkpointer=checkpointer, # 短期记忆. agent chat ui（禁用你配置 checkpointer）
        store=store # 长期记忆. 把同一个用户，任意会话的有价值信息进行存储。
    )
    return agent


# 模块级单例：避免每次请求都重新创建 agent 和 checkpointer
_supervisor_agent = None

# 返回 agent
async def get_supervisor_agent():
    """返回全局单例 Agent，首次调用时初始化。"""
    global _supervisor_agent
    if _supervisor_agent is None:
        _supervisor_agent = await create_supervisor_agent()
    return _supervisor_agent


# FastAPI 路由中使用
async def chat_endpoint(user_id: str, session_id: str, message: str):
    # 使用单例，不重复初始化。获取 agent
    agent = await get_supervisor_agent()

    # thread_id 用来区分不同会话。  用户id:会话id:日期（前端传来一个会话id）
    config = {"configurable": {"thread_id": f"{user_id}:{session_id}"}}

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": message}]},
        config=config,
        context=UserContext
    )
    return result["messages"][-1].content
