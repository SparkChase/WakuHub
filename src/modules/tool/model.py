from sqlalchemy import String, Text, Integer, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from src.core.base_model import BaseModel


class Tool(BaseModel):
    """工具表"""
    __tablename__ = "tools"

    name: Mapped[str] = mapped_column(String(200), unique=True, comment="工具名称")
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="工具描述"
    )
    type: Mapped[str] = mapped_column(
        String(50), comment="工具类型: builtin/http_api/custom_function"
    )
    status: Mapped[str] = mapped_column(
        String(50), default="disabled", comment="状态: enabled/disabled/error"
    )
    config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="工具配置（因类型而异）"
    )
    function_definition: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="Function Calling 定义（OpenAI 格式）"
    )
    call_count_7d: Mapped[int] = mapped_column(
        Integer, default=0, comment="近7天调用次数"
    )
    success_rate: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0, comment="成功率 %"
    )
    avg_latency: Mapped[int] = mapped_column(
        Integer, default=0, comment="平均延迟 ms"
    )
    created_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="创建者"
    )