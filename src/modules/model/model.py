from sqlalchemy import String, BigInteger, Integer, Numeric, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.base_model import BaseModel

# Large Language Model
class LLMModel(BaseModel):
    """大语言模型表"""
    __tablename__ = "models"

    name: Mapped[str] = mapped_column(String(100), comment="模型显示名称")
    model_id: Mapped[str] = mapped_column(
        String(100), unique=True, comment="模型标识符，如 gpt-4"
    )

    # ===== 外键关联 =====
    provider_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("model_providers.id", ondelete="CASCADE"),
        comment="所属供应商ID"
    )
    # relationship 让你可以通过 model.provider 直接访问供应商对象
    # lazy="selectin" 表示查询模型时自动加载供应商信息（一条额外 SQL）
    provider: Mapped["ModelProvider"] = relationship(
        "ModelProvider", lazy="selectin"
    )

    # ===== 模型属性 =====
    capabilities: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="能力标签，逗号分隔: function_call,vision,streaming"
    )
    context_length: Mapped[int] = mapped_column(
        Integer, default=4096, comment="上下文窗口大小"
    )
    status: Mapped[str] = mapped_column(
        String(50), default="available",
        comment="状态: available/unavailable/rate_limited"
    )

    # ===== 价格信息 =====
    input_price: Mapped[float] = mapped_column(
        Numeric(10, 6), default=0, comment="输入价格（每1K tokens）"
    )
    output_price: Mapped[float] = mapped_column(
        Numeric(10, 6), default=0, comment="输出价格（每1K tokens）"
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="USD", comment="货币单位"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否为默认模型"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="模型描述"
    )


# 避免循环导入，在此处导入
from src.modules.provider.model import ModelProvider
