from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.base_repository import BaseRepository
from src.modules.knowledge.model import KnowledgeBase, Document, Segment


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    SEARCH_FIELDS = ["name", "description"]

    def __init__(self, db: AsyncSession):
        super().__init__(KnowledgeBase, db)

    async def search_page(
        self, offset: int, limit: int, keyword: str | None
    ) -> tuple[list[KnowledgeBase], int]:
        return await self.get_page(
            offset=offset, limit=limit,
            keyword=keyword, search_fields=self.SEARCH_FIELDS,
        )


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: AsyncSession):
        super().__init__(Document, db)

    async def get_page_by_kb(
        self, kb_id: int, offset: int = 0, limit: int = 20, keyword: str | None = None
    ) -> tuple[list[Document], int]:
        stmt = select(Document).where(Document.knowledge_base_id == kb_id)
        if keyword:
            stmt = stmt.where(Document.file_name.like(f"%{keyword}%"))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = stmt.offset(offset).limit(limit).order_by(Document.id.desc())
        items = list((await self.db.execute(stmt)).scalars().all())
        return items, total

    async def get_by_kb_and_id(self, kb_id: int, doc_id: int) -> Document | None:
        stmt = select(Document).where(
            Document.id == doc_id,
            Document.knowledge_base_id == kb_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_kb(self, kb_id: int) -> list[Document]:
        """获取知识库所有文档（用于检索测试时构建文档名映射）"""
        stmt = select(Document).where(Document.knowledge_base_id == kb_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class SegmentRepository(BaseRepository[Segment]):
    def __init__(self, db: AsyncSession):
        super().__init__(Segment, db)

    async def get_page_by_kb(
        self,
        kb_id: int,
        offset: int = 0,
        limit: int = 20,
        document_id: int | None = None,
    ) -> tuple[list[Segment], int]:
        """按知识库分页查询分段，支持按 document_id 过滤"""
        stmt = select(Segment).where(Segment.knowledge_base_id == kb_id)
        if document_id is not None:
            stmt = stmt.where(Segment.document_id == document_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Segment.document_id, Segment.position).offset(offset).limit(limit)
        items = list((await self.db.execute(stmt)).scalars().all())
        return items, total

    async def get_page_by_document(
        self, kb_id: int, doc_id: int, offset: int = 0, limit: int = 20
    ) -> tuple[list[Segment], int]:
        """按文档分页查询分段"""
        stmt = select(Segment).where(
            Segment.knowledge_base_id == kb_id,
            Segment.document_id == doc_id,
        )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Segment.position).offset(offset).limit(limit)
        items = list((await self.db.execute(stmt)).scalars().all())
        return items, total

    async def get_all_by_kb(self, kb_id: int) -> list[Segment]:
        """获取知识库所有分段（用于检索测试）"""
        stmt = select(Segment).where(Segment.knowledge_base_id == kb_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def bulk_create(self, segments: list[Segment]) -> None:
        """批量插入分段"""
        for seg in segments:
            self.db.add(seg)
        await self.db.flush()

    async def delete_by_document(self, doc_id: int) -> None:
        """删除文档的所有分段"""
        from sqlalchemy import delete
        stmt = delete(Segment).where(Segment.document_id == doc_id)
        await self.db.execute(stmt)
