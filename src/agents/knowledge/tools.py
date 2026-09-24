from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool
from pymilvus import MilvusClient
from neo4j import AsyncDriver
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.knowledge.audit import QueryAuditLog, Timer


class KnowledgeDeps:
    """知识 Agent 的依赖注入容器。"""

    def __init__(
        self,
        llm: BaseChatModel,
        embedding_model: Embeddings,
        milvus_client: MilvusClient,
        neo4j_driver: AsyncDriver,
        db_session: AsyncSession | None = None,
        user_id: str = "anonymous",
        role: str = "patient",
    ):
        self.llm = llm
        self.embedding_model = embedding_model
        self.milvus_client = milvus_client
        self.neo4j_driver = neo4j_driver
        self.db_session = db_session
        self.user_id = user_id
        self.role = role


async def _rewrite(question: str, deps: KnowledgeDeps) -> str:
    """Query 改写：口语->医学术语。返回改写后的首条查询。"""
    from src.agents.knowledge.query_rewriter import rewrite_query

    result = await rewrite_query(question, deps.llm, deps.role)
    return result["queries"][0] if result.get("queries") else question


def build_knowledge_tools(deps: KnowledgeDeps) -> list:
    """构建知识 Agent 的工具集（含 Query 改写预处理）。"""

    @tool
    async def search_knowledge_docs(question: str, doc_type: str = "") -> str:
        """从知识文档库中检索信息并生成回答。
        适用：查询临床指南、药品说明书、医院制度SOP、医学文献等文档内容。
        question: 用户的问题
        doc_type: 可选，文档类型过滤 (guideline/drug_instruction/sop/literature)"""
        from src.agents.knowledge.doc_rag import search_docs

        rewritten = await _rewrite(question, deps)
        with Timer() as t:
            result = await search_docs(
                question=rewritten,
                embedding_model=deps.embedding_model,
                milvus_client=deps.milvus_client,
                llm=deps.llm,
                doc_type=doc_type or None,
                role=deps.role,
            )
        await QueryAuditLog.log(
            deps.user_id,
            deps.role,
            question,
            intent="doc_rag",
            channels=["doc_rag"],
            answer_preview=result[:80],
            duration_ms=t.elapsed_ms,
        )
        return result

    @tool
    async def search_knowledge_graph(question: str) -> str:
        """从医学知识图谱中检索实体关系并生成回答。
        适用：查询疾病病因、症状、并发症、用药禁忌、科室归属等关系型知识。
        question: 用户的问题"""
        from src.agents.knowledge.graph_rag import search_graph

        rewritten = await _rewrite(question, deps)
        with Timer() as t:
            result = await search_graph(
                question=rewritten,
                neo4j_driver=deps.neo4j_driver,
                llm=deps.llm,
                role=deps.role,
            )
        await QueryAuditLog.log(
            deps.user_id,
            deps.role,
            question,
            intent="graph_rag",
            channels=["graph_rag"],
            answer_preview=result[:80],
            duration_ms=t.elapsed_ms,
        )
        return result

    @tool
    async def search_knowledge_sql(question: str) -> str:
        """从运营数据库中查询统计数据并生成回答。
        适用：查询问诊量、药品库存、科室排名、收入统计等结构化数据。
        question: 用户的问题"""
        if deps.db_session is None:
            return "数据库连接不可用，无法执行查询。"
        from src.agents.knowledge.nl2sql import search_sql

        with Timer() as t:
            result = await search_sql(
                question=question,
                llm=deps.llm,
                db=deps.db_session,
            )
        await QueryAuditLog.log(
            deps.user_id,
            deps.role,
            question,
            intent="sql",
            channels=["sql"],
            answer_preview=result[:80],
            duration_ms=t.elapsed_ms,
        )
        return result

    @tool
    async def search_knowledge_multi(question: str) -> str:
        """多通道融合检索：同时查文档库和知识图谱，综合多个来源生成回答。
        适用：复杂问题，需要同时参考指南文档和实体关系才能回答。
        例如："糖尿病合并肾功能不全的降糖方案"需要同时查指南和药物禁忌。
        question: 用户的问题"""
        from src.agents.knowledge.fusion import multi_channel_search

        rewritten = await _rewrite(question, deps)
        with Timer() as t:
            result = await multi_channel_search(
                question=rewritten,
                llm=deps.llm,
                embedding_model=deps.embedding_model,
                milvus_client=deps.milvus_client,
                neo4j_driver=deps.neo4j_driver,
                db_session=deps.db_session,
                role=deps.role,
            )
        await QueryAuditLog.log(
            deps.user_id,
            deps.role,
            question,
            intent="multi",
            channels=["doc_rag", "graph_rag"],
            answer_preview=result[:80],
            duration_ms=t.elapsed_ms,
        )
        return result

    @tool
    async def review_prescription_tool(question: str) -> str:
        """处方审核：审查处方配伍禁忌、适应症、用法用量等用药合理性。
        question: 用户的问题或处方信息"""
        from src.agents.knowledge.prescription_review import review_prescription

        rewritten = await _rewrite(question, deps)
        with Timer() as t:
            result = await review_prescription(
                question=rewritten,
                llm=deps.llm,
                embedding_model=deps.embedding_model,
                milvus_client=deps.milvus_client,
                neo4j_driver=deps.neo4j_driver,
            )
        await QueryAuditLog.log(
            deps.user_id,
            deps.role,
            question,
            intent="prescription",
            channels=["doc_rag", "graph_rag"],
            answer_preview=result[:80],
            duration_ms=t.elapsed_ms,
        )
        return result

    return [
        search_knowledge_docs,
        search_knowledge_graph,
        search_knowledge_sql,
        search_knowledge_multi,
        review_prescription_tool,
    ]