import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import BackgroundTasks

from src.infra.minio_client import delete_object, upload_file
from src.core.exceptions import BizException
from src.core.base_schema import PageResult
from src.core.depys import PageParams
from src.modules.knowledge.model import KnowledgeBase, Document
from src.modules.knowledge.repository import (
    KnowledgeBaseRepository, DocumentRepository, SegmentRepository,
)
from src.modules.knowledge.schema import (
    KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseConfigUpdate,
    KnowledgeBaseRead, DocumentRead, SegmentRead, SegmentUpdate,
    RetrievalTestRequest, RetrievalTestResult,
)


class KnowledgeService:
    def __init__(self, db: AsyncSession):
        self.kb_repo = KnowledgeBaseRepository(db)
        self.doc_repo = DocumentRepository(db)
        self.seg_repo = SegmentRepository(db)
        self.db = db

    # ===== 知识库 CRUD =====

    async def create_kb(self, data: KnowledgeBaseCreate, current_user: str | None = None) -> KnowledgeBaseRead:
        kb = KnowledgeBase(
            name=data.name,
            description=data.description,
            embedding_model=data.embedding_model,
            chunk_method=data.chunk_method,
            chunk_size=data.chunk_size,
            chunk_overlap=data.chunk_overlap,
            retrieval_strategy=data.retrieval_strategy,
            top_k=data.top_k,
            similarity_threshold=data.similarity_threshold,
            created_by=current_user,
        )
        kb = await self.kb_repo.create(kb)
        return KnowledgeBaseRead.model_validate(kb)

    async def get_kb(self, kb_id: int) -> KnowledgeBaseRead:
        kb = await self.kb_repo.get_by_id(kb_id)
        if not kb:
            raise BizException(code=43001, message="知识库不存在")
        return KnowledgeBaseRead.model_validate(kb)

    async def list_kbs(self, params: PageParams) -> PageResult[KnowledgeBaseRead]:
        items, total = await self.kb_repo.search_page(
            offset=params.offset, limit=params.page_size, keyword=params.keyword,
        )
        return PageResult(
            items=[KnowledgeBaseRead.model_validate(kb) for kb in items],
            total=total, page=params.page, page_size=params.page_size,
        )

    async def update_kb(self, kb_id: int, data: KnowledgeBaseUpdate) -> KnowledgeBaseRead:
        kb = await self.kb_repo.get_by_id(kb_id)
        if not kb:
            raise BizException(code=43001, message="知识库不存在")
        if data.name is not None:
            kb.name = data.name
        if data.description is not None:
            kb.description = data.description
        if data.embedding_model is not None:
            kb.embedding_model = data.embedding_model
        kb = await self.kb_repo.update(kb)
        return KnowledgeBaseRead.model_validate(kb)

    async def update_kb_config(self, kb_id: int, data: KnowledgeBaseConfigUpdate) -> KnowledgeBaseRead:
        """更新分段策略和检索策略配置"""
        kb = await self.kb_repo.get_by_id(kb_id)
        if not kb:
            raise BizException(code=43001, message="知识库不存在")
        if data.embedding_model is not None:
            kb.embedding_model = data.embedding_model
        if data.chunk_method is not None:
            kb.chunk_method = data.chunk_method
        if data.chunk_size is not None:
            kb.chunk_size = data.chunk_size
        if data.chunk_overlap is not None:
            kb.chunk_overlap = data.chunk_overlap
        if data.retrieval_strategy is not None:
            kb.retrieval_strategy = data.retrieval_strategy
        if data.top_k is not None:
            kb.top_k = data.top_k
        if data.similarity_threshold is not None:
            kb.similarity_threshold = data.similarity_threshold
        kb = await self.kb_repo.update(kb)
        return KnowledgeBaseRead.model_validate(kb)

    async def delete_kb(self, kb_id: int) -> None:
        kb = await self.kb_repo.get_by_id(kb_id)
        if not kb:
            raise BizException(code=43001, message="知识库不存在")
        await self.kb_repo.delete(kb)

    # ===== 文档管理 =====
    async def upload_document(
        self,
        kb_id: int,
        file_name: str,
        file_type: str,
        file_bytes: bytes,
        current_user: str | None = None,
        background_tasks: BackgroundTasks | None = None,  # 预留接口
    ) -> DocumentRead:
        """上传文档到 MinIO 并写库"""
        # 检查知识库是否存在
        kb = await self.kb_repo.get_by_id(kb_id)
        if not kb:
            raise BizException(code=43001, message="知识库不存在")

        # 校验文件类型（MIME 类型白名单）
        allowed_mime = {
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown",
            "text/html",
            "text/csv",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        if file_type not in allowed_mime:
            raise BizException(code=43002, message=f"不支持的文件类型: {file_type}")

        # 提取扩展名
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "bin"

        # 上传到 MinIO，文件名加 UUID 避免重复
        object_name = f"kb/{kb_id}/{uuid.uuid4().hex}.{ext}"
        upload_file(object_name, file_bytes, content_type=file_type)

        # 计算文件大小（人类可读）
        size_bytes = len(file_bytes)
        if size_bytes >= 1024 * 1024:
            file_size_str = f"{size_bytes / 1024 / 1024:.1f}MB"
        else:
            file_size_str = f"{size_bytes / 1024:.1f}KB"

        # 写入数据库
        doc = Document(
            knowledge_base_id=kb_id,
            file_name=file_name,
            file_type=ext,
            file_size=file_size_str,
            minio_path=object_name,
            status="pending",
            uploaded_by=current_user,
        )
        doc = await self.doc_repo.create(doc)

        # 更新知识库文档计数
        kb.document_count += 1
        await self.kb_repo.update(kb)

        # TODO 触发后台异步处理（分段 + 向量化 + 写入向量库）
        return DocumentRead.from_orm_with_alias(doc)

    async def list_documents(self, kb_id: int, params: PageParams) -> PageResult[DocumentRead]:
        items, total = await self.doc_repo.get_page_by_kb(
            kb_id, offset=params.offset, limit=params.page_size, keyword=params.keyword,
        )
        return PageResult(
            items=[DocumentRead.from_orm_with_alias(d) for d in items],
            total=total, page=params.page, page_size=params.page_size,
        )

    async def delete_document(self, kb_id: int, doc_id: int) -> None:
        doc = await self.doc_repo.get_by_kb_and_id(kb_id, doc_id)
        if not doc:
            raise BizException(code=43002, message="文档不存在")

        # 从 MinIO 删除文件
        if doc.minio_path:
            delete_object(doc.minio_path)

        # 更新知识库计数
        kb = await self.kb_repo.get_by_id(kb_id)
        kb.document_count = max(0, kb.document_count - 1)
        kb.segment_count = max(0, kb.segment_count - doc.segment_count)
        await self.kb_repo.update(kb)

        # cascade 自动删除关联分段
        await self.doc_repo.delete(doc)

    async def retry_document(self, kb_id: int, doc_id: int, background_tasks: BackgroundTasks) -> DocumentRead:
        """重试失败的文档"""
        doc = await self.doc_repo.get_by_kb_and_id(kb_id, doc_id)
        if not doc:
            raise BizException(code=43002, message="文档不存在")
        if doc.status != "failed":
            raise BizException(code=43011, message="只有失败的文档才能重试")

        # 清除旧分段
        await self.seg_repo.delete_by_document(doc_id)

        # 重置状态
        doc.status = "pending"
        doc.error_message = None
        doc.segment_count = 0
        await self.doc_repo.update(doc)

        # TODO 重新触发后台处理
        return DocumentRead.from_orm_with_alias(doc)

    # ===== 分段管理 =====

    async def list_segments(
        self, kb_id: int, params: PageParams, document_id: int | None = None
    ) -> PageResult[SegmentRead]:
        items, total = await self.seg_repo.get_page_by_kb(
            kb_id, offset=params.offset, limit=params.page_size, document_id=document_id,
        )
        return PageResult(
            items=[SegmentRead.model_validate(s) for s in items],
            total=total, page=params.page, page_size=params.page_size,
        )

    async def list_document_segments(
        self, kb_id: int, doc_id: int, params: PageParams
    ) -> PageResult[SegmentRead]:
        items, total = await self.seg_repo.get_page_by_document(
            kb_id, doc_id, offset=params.offset, limit=params.page_size,
        )
        return PageResult(
            items=[SegmentRead.model_validate(s) for s in items],
            total=total, page=params.page, page_size=params.page_size,
        )

    async def update_segment(self, kb_id: int, seg_id: int, data: SegmentUpdate) -> SegmentRead:
        seg = await self.seg_repo.get_by_id(seg_id)
        if not seg or seg.knowledge_base_id != kb_id:
            raise BizException(code=43003, message="分段不存在")
        if data.content is not None:
            seg.content = data.content
            seg.word_count = len(data.content)
            # TODO 精确 token 计数未实现，暂用字符数占位
            seg.token_count = len(data.content)
        seg = await self.seg_repo.update(seg)
        return SegmentRead.model_validate(seg)

    async def delete_segment(self, kb_id: int, seg_id: int) -> None:
        seg = await self.seg_repo.get_by_id(seg_id)
        if not seg or seg.knowledge_base_id != kb_id:
            raise BizException(code=43003, message="分段不存在")
        # 更新文档和知识库的分段计数
        doc = await self.doc_repo.get_by_kb_and_id(kb_id, seg.document_id)
        if doc:
            doc.segment_count = max(0, doc.segment_count - 1)
            await self.doc_repo.update(doc)
        kb = await self.kb_repo.get_by_id(kb_id)
        if kb:
            kb.segment_count = max(0, kb.segment_count - 1)
            await self.kb_repo.update(kb)
        await self.seg_repo.delete(seg)

    # ===== 检索测试 =====

    async def retrieval_test(
        self, kb_id: int, data: RetrievalTestRequest
    ) -> list[RetrievalTestResult]:
        """检索测试：查询与分段做字符 bigram 词面重合度打分，不依赖向量数据库。

        生产环境应替换为 pgvector / Milvus 向量相似度检索，当前实现用于联调分段效果。
        """
        kb = await self.kb_repo.get_by_id(kb_id)
        if not kb:
            raise BizException(code=43001, message="知识库不存在")

        # 拉全量分段 + 文档名映射（检索测试数据量可控，不分页）
        segments = await self.seg_repo.get_all_by_kb(kb_id)
        documents = await self.doc_repo.get_all_by_kb(kb_id)
        doc_names = {d.id: d.file_name for d in documents}

        query_grams = self._bigrams(data.query)
        if not query_grams:
            return []

        results = []
        for seg in segments:
            score = len(query_grams & self._bigrams(seg.content)) / len(query_grams)
            if score < data.similarity_threshold:
                continue
            results.append(RetrievalTestResult(
                segment_id=seg.id,
                document_id=seg.document_id,
                document_name=doc_names[seg.document_id],
                content=seg.content,
                score=round(score, 4),
                position=seg.position,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:data.top_k]

    @staticmethod
    def _bigrams(text: str) -> set[str]:
        """字符 bigram 集合：中文无空格分词场景下比整词匹配更稳健的词面相似度"""
        return {text[i:i + 2] for i in range(len(text) - 1)}
