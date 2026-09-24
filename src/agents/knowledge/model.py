from sqlalchemy import String, SmallInteger, Integer, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.core.base_model import BaseModel


class KnowledgeFeedback(BaseModel):
    """用户对知识问答回答的反馈记录。"""
    __tablename__ = "knowledge_feedback"

    user_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="用户 ID")
    question: Mapped[str] = mapped_column(String(500), nullable=False, comment="用户提问")
    answer_preview: Mapped[str] = mapped_column(String(500), default="", comment="系统回答预览")
    rating: Mapped[int] = mapped_column(SmallInteger, default=0, comment="1=有用, -1=无用, 0=未评价")
    comment: Mapped[str] = mapped_column(String(1000), default="", comment="用户文字反馈")
    intent: Mapped[str] = mapped_column(String(50), default="", comment="检索意图")
    channels: Mapped[str] = mapped_column(String(100), default="", comment="使用的检索通道")

    __table_args__ = (
        Index("ix_knowledge_feedback_user", "user_id"),
        Index("ix_knowledge_feedback_rating", "rating"),
    )


class KnowledgeNotification(BaseModel):
    """知识文档更新通知。"""
    __tablename__ = "knowledge_notifications"

    doc_name: Mapped[str] = mapped_column(String(256), nullable=False, comment="文档名称")
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="文档类型")
    category: Mapped[str] = mapped_column(String(100), nullable=False, comment="所属分类")
    action: Mapped[str] = mapped_column(String(20), default="upload", comment="操作类型")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已读")

    __table_args__ = (
        Index("ix_knowledge_notifications_category", "category"),
        Index("ix_knowledge_notifications_is_read", "is_read"),
    )


class KnowledgeQueryLog(BaseModel):
    """知识检索查询审计日志：记录每次检索的用户、意图、通道、耗时与幻觉检测结果。"""
    __tablename__ = "knowledge_query_logs"

    user_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="用户 ID")
    role: Mapped[str] = mapped_column(String(32), default="patient", comment="用户角色")
    question: Mapped[str] = mapped_column(String(1000), nullable=False, comment="用户提问")
    intent: Mapped[str] = mapped_column(String(50), default="", comment="检索意图")
    channels: Mapped[str] = mapped_column(String(100), default="", comment="使用的检索通道")
    answer_preview: Mapped[str] = mapped_column(String(500), default="", comment="回答预览")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, comment="检索耗时(ms)")
    is_grounded: Mapped[bool | None] = mapped_column(Boolean, nullable=True, comment="幻觉检测是否有据")

    __table_args__ = (
        Index("ix_knowledge_query_logs_user", "user_id"),
        Index("ix_knowledge_query_logs_intent", "intent"),
    )