from sqlalchemy import String, Text, Integer, JSON, Numeric, Boolean, BigInteger, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.base_model import BaseModel
from datetime import datetime


class Agent(BaseModel):
    """Agent 表"""
    __tablename__ = "agents"

    name: Mapped[str] = mapped_column(String(200), comment="Agent 名称")
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="描述"
    )
    type: Mapped[str] = mapped_column(
        String(50), comment="类型: conversation/tool/analysis/creative/workflow"
    )
    status: Mapped[str] = mapped_column(
        String(50), default="draft",
        comment="状态: active/inactive/error/draft"
    )

    # 关联模型（外键）
    model_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("models.id", ondelete="SET NULL"),
        nullable=True, comment="关联的模型ID"
    )

    # 核心配置（JSON 存储）
    config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Agent 完整配置"
    )

    # 运行统计
    success_rate: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0, comment="成功率 %"
    )
    call_count_7d: Mapped[int] = mapped_column(
        Integer, default=0, comment="近7天调用次数"
    )

    # 版本管理
    version: Mapped[str] = mapped_column(
        String(50), default="v0.1", comment="当前版本号"
    )

    created_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="创建者"
    )

    # 关联版本列表
    versions: Mapped[list["AgentVersion"]] = relationship(
        "AgentVersion", back_populates="agent",
        order_by="AgentVersion.id.desc()",
        cascade="all, delete-orphan",
    )


class AgentVersion(BaseModel):
    """Agent 版本表"""
    __tablename__ = "agent_versions"

    agent_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agents.id", ondelete="CASCADE"),
        comment="所属 Agent ID"
    )
    version: Mapped[str] = mapped_column(String(50), comment="版本号")
    config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="该版本的配置快照"
    )
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

    agent: Mapped["Agent"] = relationship("Agent", back_populates="versions")