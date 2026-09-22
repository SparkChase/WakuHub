from sqlalchemy import String, Text, BigInteger, ForeignKey, Boolean, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.base_model import BaseModel
from datetime import datetime


class Prompt(BaseModel):
    """Prompt 模板表"""
    __tablename__ = "prompts"

    name: Mapped[str] = mapped_column(String(200), comment="Prompt 名称")
    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="描述"
    )
    category: Mapped[str] = mapped_column(
        String(50), default="general", comment="分类"
    )
    tags: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="标签列表，JSON 数组"
    )
    content: Mapped[str] = mapped_column(Text, comment="Prompt 正文内容")
    variables: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="变量定义，JSON 数组"
    )
    version: Mapped[str] = mapped_column(
        String(50), default="v0.1", comment="当前版本号"
    )
    status: Mapped[str] = mapped_column(
        String(50), default="draft", comment="状态: draft/published"
    )
    created_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="创建者"
    )

    # 关联版本列表
    versions: Mapped[list["PromptVersion"]] = relationship(
        "PromptVersion", back_populates="prompt",
        order_by="PromptVersion.id.desc()",
        lazy="selectin",
    )


class PromptVersion(BaseModel):
    """Prompt 版本表"""
    __tablename__ = "prompt_versions"

    prompt_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("prompts.id", ondelete="CASCADE"),
        comment="所属 Prompt ID"
    )
    version: Mapped[str] = mapped_column(String(50), comment="版本号")
    content: Mapped[str] = mapped_column(Text, comment="该版本的内容快照")
    changelog: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="变更说明"
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否为当前版本"
    )
    published_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="发布者"
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="发布时间"
    )

    # 反向关联
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="versions")
