from pydantic import BaseModel, Field
from datetime import datetime


# ===== 知识库 =====

class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str | None = None
    embedding_model: str = "text-embedding-ada-002"
    # 分段策略
    chunk_method: str = "fixed"
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=500)
    # 检索策略
    retrieval_strategy: str = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    embedding_model: str | None = None


class KnowledgeBaseConfigUpdate(BaseModel):
    """单独更新分段/检索配置"""
    embedding_model: str | None = None
    chunk_method: str | None = None
    chunk_size: int | None = Field(default=None, ge=100, le=2000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=500)
    retrieval_strategy: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class KnowledgeBaseRead(BaseModel):
    id: int
    name: str
    description: str | None
    status: str
    document_count: int
    segment_count: int
    embedding_model: str
    chunk_method: str
    chunk_size: int
    chunk_overlap: int
    retrieval_strategy: str
    top_k: int
    similarity_threshold: float
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ===== 文档 =====

class DocumentRead(BaseModel):
    id: int
    knowledge_base_id: int
    file_name: str
    file_type: str
    file_size: str | None
    minio_path: str | None
    status: str
    segment_count: int
    word_count: int
    error_message: str | None
    uploaded_by: str | None
    uploaded_at: datetime | None   # 对应 created_at
    processed_at: datetime | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_alias(cls, doc) -> "DocumentRead":
        """created_at 映射为 uploaded_at"""
        return cls(
            id=doc.id,
            knowledge_base_id=doc.knowledge_base_id,
            file_name=doc.file_name,
            file_type=doc.file_type,
            file_size=doc.file_size,
            minio_path=doc.minio_path,
            status=doc.status,
            segment_count=doc.segment_count,
            word_count=doc.word_count,
            error_message=doc.error_message,
            uploaded_by=doc.uploaded_by,
            uploaded_at=doc.created_at,
            processed_at=doc.processed_at,
        )


# ===== 分段 =====

class SegmentRead(BaseModel):
    id: int
    knowledge_base_id: int
    document_id: int
    position: int
    content: str
    word_count: int
    token_count: int
    hit_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SegmentUpdate(BaseModel):
    content: str | None = None


# ===== 检索测试 =====

class RetrievalTestRequest(BaseModel):
    query: str
    strategy: str = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class RetrievalTestResult(BaseModel):
    segment_id: int
    document_id: int
    document_name: str
    content: str
    score: float
    position: int
