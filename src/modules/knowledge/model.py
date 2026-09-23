from datetime import datetime
from sqlalchemy import String, Text, BigInteger, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.base_model import BaseModel


class KnowledgeBase(BaseModel):
    """知识库表"""
    __tablename__ = "knowledge_bases"

    name: Mapped[str] = mapped_column(String(200), comment="知识库名称")
    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="描述"
    )
    status: Mapped[str] = mapped_column(
        String(50), default="empty", comment="状态: ready/indexing/error/empty"
    )
    document_count: Mapped[int] = mapped_column(Integer, default=0, comment="文档数量")
    segment_count: Mapped[int] = mapped_column(Integer, default=0, comment="分段数量")
    embedding_model: Mapped[str] = mapped_column(
        String(100), default="text-embedding-ada-002", comment="向量化模型"
    )

    # ===== 分段策略 =====
    chunk_method: Mapped[str] = mapped_column(
        String(20), default="fixed", comment="分段方式: fixed/sentence/paragraph"
    )
    chunk_size: Mapped[int] = mapped_column(Integer, default=500, comment="分段大小（tokens）")
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=50, comment="重叠大小（tokens）")

    # ===== 检索策略 =====
    retrieval_strategy: Mapped[str] = mapped_column(
        String(20), default="hybrid", comment="检索策略: vector/fulltext/hybrid"
    )
    top_k: Mapped[int] = mapped_column(Integer, default=5, comment="返回结果数")
    similarity_threshold: Mapped[float] = mapped_column(
        Float, default=0.7, comment="相似度阈值"
    )

    created_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="创建者"
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )


class Document(BaseModel):
    """文档表"""
    __tablename__ = "documents"

    knowledge_base_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        comment="所属知识库ID"
    )
    file_name: Mapped[str] = mapped_column(String(500), comment="文件名")
    file_type: Mapped[str] = mapped_column(
        String(50), comment="文件类型: pdf/docx/md/txt/html/csv"
    )
    file_size: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="文件大小")
    minio_path: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="MinIO 存储路径"
    )
    status: Mapped[str] = mapped_column(
        String(50), default="pending",
        comment="处理状态: pending/processing/completed/failed"
    )
    segment_count: Mapped[int] = mapped_column(Integer, default=0, comment="分段数量")
    word_count: Mapped[int] = mapped_column(Integer, default=0, comment="字数")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")
    uploaded_by: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="上传者")
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="处理完成时间"
    )

    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase", back_populates="documents"
    )
    segments: Mapped[list["Segment"]] = relationship(
        "Segment", back_populates="document",
        cascade="all, delete-orphan",
    )


class Segment(BaseModel):
    """文档分段表"""
    __tablename__ = "segments"

    knowledge_base_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        comment="所属知识库ID"
    )
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"),
        comment="所属文档ID"
    )
    position: Mapped[int] = mapped_column(Integer, comment="在文档中的位置序号")
    content: Mapped[str] = mapped_column(Text, comment="分段内容")
    word_count: Mapped[int] = mapped_column(Integer, default=0, comment="字数")
    token_count: Mapped[int] = mapped_column(Integer, default=0, comment="Token 数")
    hit_count: Mapped[int] = mapped_column(Integer, default=0, comment="检索命中次数")

    document: Mapped["Document"] = relationship("Document", back_populates="segments")
