# src/agents/workers/knowledge_agent.py

from langchain.agents import create_agent
from pymilvus import MilvusClient

from src.infra.embedding import get_embedding_model


from src.core.llm import get_llm
from src.infra.neo4j_client import get_neo4j_driver
from src.infra.milvus_client import get_milvus_client_alias, get_milvus_uri
from src.agents.knowledge.tools import KnowledgeDeps, build_knowledge_tools


KNOWLEDGE_SYSTEM_PROMPT = """你是天宫医疗的知识问答助手，面向医生、药师和企业内部员工提供专业知识服务。

## 你的能力

你拥有五个检索工具，根据问题类型选择最合适的工具：

1. search_knowledge_docs — 文档检索
   适用：查询临床指南、药品说明书、医院制度SOP、医学文献
   示例："高血压诊疗指南推荐的一线用药"、"阿莫西林的禁忌症"

2. search_knowledge_graph — 知识图谱检索
   适用：查询疾病与症状/药物/科室/检查/食物的关系，多跳推理
   示例："糖尿病的常用药有哪些"、"头痛可能是什么疾病需要做什么检查"

3. search_knowledge_sql — 运营数据查询
   适用：统计数据、数量、排名、趋势、库存
   示例："上个月各科室问诊量排名"、"库存不足100的OTC药品"

4. search_knowledge_multi — 多通道融合检索（复杂问题首选）
   适用：需要同时参考文档和知识图谱才能回答的复杂问题
   示例："糖尿病合并肾功能不全的降糖方案"、"高血压患者能用哪些感冒药"

5. review_prescription_tool — 处方审核
   适用：校验处方安全性（剂量、配伍禁忌、过敏冲突、重复用药）
   示例："帮我审核这张处方：阿莫西林0.5g tid + 甲硝唑0.4g bid"

## 工具选择策略

- 简单的文档查询 → search_knowledge_docs
- 实体关系查询 → search_knowledge_graph
- 统计数据查询 → search_knowledge_sql
- 涉及"合并症+用药"、"禁忌+推荐"等复杂问题 → search_knowledge_multi
- 处方审核、用药安全校验 → review_prescription_tool
- 不确定时优先用 search_knowledge_multi，它会自动融合多个来源

## 工作原则

1. 回答必须基于工具返回的检索结果，不要编造信息
2. 回答中必须标注信息来源
3. 如果所有工具都未找到相关信息，明确告知用户
4. 涉及用药安全的问题，必须提醒"请遵医嘱"
5. 语言专业但易懂"""


def _build_deps(db_session=None, user_id="anonymous", role="patient") -> KnowledgeDeps:
    return KnowledgeDeps(
        llm=get_llm(temperature=0.3),
        embedding_model=get_embedding_model(),
        milvus_client=_get_milvus_client(),
        neo4j_driver=get_neo4j_driver(),
        db_session=db_session,
        user_id=user_id,
        role=role,
    )


def create_knowledge_agent(db_session=None, user_id="anonymous", role="patient"):
    deps = _build_deps(db_session, user_id, role)
    tools = build_knowledge_tools(deps)
    llm = get_llm(temperature=0.3)
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=KNOWLEDGE_SYSTEM_PROMPT,
        name="knowledge_agent",
    )


# 重客户端（Milvus 连接）按进程复用，避免每次调用新建 gRPC 连接
_milvus_client: MilvusClient | None = None


def _get_milvus_client() -> MilvusClient:
    global _milvus_client
    if _milvus_client is None:
        get_milvus_client_alias()
        _milvus_client = MilvusClient(uri=get_milvus_uri())
    return _milvus_client


def get_knowledge_agent(db_session=None, user_id="anonymous", role="patient"):
    """按请求构建知识 Agent。

    Agent 本身无状态（无 checkpointer/store），按 user_id/role/db_session
    重新构建以保证审计日志与权限正确；底层重客户端在工厂内复用。
    """
    return create_knowledge_agent(db_session=db_session, user_id=user_id, role=role)



# 工具选择策略  -> search_knowledge_docs
# 简单文档查询
# 实体关系查询
# 统计数据查询
# 涉及 “合并症+用药” “禁忌+推荐”等复杂问题
# 。。。。
# 不确定用。。。。。。