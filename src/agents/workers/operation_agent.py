# src/agents/workers/operation_agent.py

from langchain.agents import create_agent
from pymilvus import MilvusClient

from src.infra.embedding import get_embedding_model

from src.core.llm import get_llm
from src.infra.neo4j_client import get_neo4j_driver
from src.infra.milvus_client import get_milvus_client_alias, get_milvus_uri
from src.agents.knowledge.tools import KnowledgeDeps, build_knowledge_tools


OPERATION_SYSTEM_PROMPT = """你是天宫医疗的运营数据助手。

## 你的职责
1. 根据运营人员的自然语言问题，查询统计数据
2. 生成数据报表和趋势分析
3. 辅助医院管理层做运营决策

## 你的工具
- search_knowledge_sql：查询运营数据库中的统计数据（问诊量、药品库存、科室排名等）

## 安全规则
- 只允许查询聚合统计数据，严禁返回患者个人信息
- 所有查询结果需脱敏处理
- 如果问题涉及患者隐私，拒绝回答并说明原因

回复格式：
- 数据摘要：xxx
- 关键指标：xxx
- 趋势分析：xxx
- 决策建议：xxx

注意：数据查询结果仅供内部运营参考。"""


def create_operation_agent(db_session=None):
    llm = get_llm(temperature=0.2)
    deps = KnowledgeDeps(
        llm=llm,
        embedding_model=get_embedding_model(),
        milvus_client=_get_milvus_client(),
        neo4j_driver=get_neo4j_driver(),
        db_session=db_session,
    )
    knowledge_tools = build_knowledge_tools(deps)
    tools = [t for t in knowledge_tools if t.name == "search_knowledge_sql"]

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=OPERATION_SYSTEM_PROMPT,
        name="operation_agent",
    )


# 重客户端（Milvus 连接）按进程复用
_milvus_client: MilvusClient | None = None


def _get_milvus_client() -> MilvusClient:
    global _milvus_client
    if _milvus_client is None:
        get_milvus_client_alias()
        _milvus_client = MilvusClient(uri=get_milvus_uri())
    return _milvus_client


def get_operation_agent(db_session=None):
    """按请求构建运营 Agent。

    其唯一工具 search_knowledge_sql 依赖 db_session，缓存单例会把
    db_session=None 固化导致 SQL 永久不可用，故每次按传入会话重建。
    """
    return create_operation_agent(db_session=db_session)