from sqlalchemy.ext.asyncio import AsyncSession
from src.core.exceptions import BizException
from src.core.base_schema import PageResult
from src.core.depys import PageParams
from src.modules.model.model import LLMModel
from src.modules.model.repository import ModelRepository
from src.modules.model.schema import ModelCreate, ModelUpdate, ModelRead
from src.modules.provider.repository import ProviderRepository


class ModelService:
    def __init__(self, db: AsyncSession):
        self.repo = ModelRepository(db)
        self.provider_repo = ProviderRepository(db)

    def _to_read(self, model: LLMModel) -> ModelRead:
        """将 ORM 对象转换为 Read Schema（处理关联字段和格式转换）"""
        return ModelRead(
            id=model.id,
            name=model.name,
            model_id=model.model_id,
            provider_id=model.provider_id,
            provider_name=model.provider.name if model.provider else "",
            capabilities=model.capabilities.split(",") if model.capabilities else [],
            context_length=model.context_length,
            status=model.status,
            input_price=float(model.input_price),
            output_price=float(model.output_price),
            currency=model.currency,
            is_default=model.is_default,
            description=model.description,
        )

    async def create_model(self, data: ModelCreate) -> ModelRead:
        # 1. 检查 model_id 是否已存在
        existing = await self.repo.get_by_model_id(data.model_id)
        if existing:
            raise BizException(code=41001, message=f"模型 '{data.model_id}' 已存在")

        # 2. 检查供应商是否存在
        provider = await self.provider_repo.get_by_id(data.provider_id)
        if not provider:
            raise BizException(code=41002, message="供应商不存在")

        # 3. 如果设为默认，先取消其他默认
        if data.is_default:
            current_default = await self.repo.get_default_model()
            if current_default:
                current_default.is_default = False
                await self.repo.update(current_default)

        # 4. 创建模型
        model = LLMModel(
            name=data.name,
            model_id=data.model_id,
            provider_id=data.provider_id,
            capabilities=",".join(data.capabilities) if data.capabilities else None,
            context_length=data.context_length,
            input_price=data.input_price,
            output_price=data.output_price,
            currency=data.currency,
            is_default=data.is_default,
            description=data.description,
        )
        model = await self.repo.create(model)
        return self._to_read(model)

    async def get_model(self, model_id: int) -> ModelRead:
        model = await self.repo.get_by_id(model_id)
        if not model:
            raise BizException(code=41003, message="模型不存在")
        return self._to_read(model)

    async def list_models(
        self, params: PageParams, provider_id: int | None = None
    ) -> PageResult[ModelRead]:
        """分页查询模型列表，支持按供应商筛选"""
        if provider_id:
            # 按供应商筛选时，不走通用分页（数据量通常较少）
            models = await self.repo.get_by_provider(provider_id)
            items = [self._to_read(m) for m in models]
            return PageResult(
                items=items,
                total=len(items),
                page=1,
                page_size=len(items),
            )
        else:
            items, total = await self.repo.search_page(
                offset=params.offset,
                limit=params.page_size,
                keyword=params.keyword,
            )
            return PageResult(
                items=[self._to_read(m) for m in items],
                total=total,
                page=params.page,
                page_size=params.page_size,
            )

    async def update_model(self, model_id: int, data: ModelUpdate) -> ModelRead:
        model = await self.repo.get_by_id(model_id)
        if not model:
            raise BizException(code=41003, message="模型不存在")

        if data.name is not None:
            model.name = data.name
        if data.capabilities is not None:
            model.capabilities = ",".join(data.capabilities) if data.capabilities else None
        if data.context_length is not None:
            model.context_length = data.context_length
        if data.status is not None:
            model.status = data.status
        if data.input_price is not None:
            model.input_price = data.input_price
        if data.output_price is not None:
            model.output_price = data.output_price
        if data.currency is not None:
            model.currency = data.currency
        if data.is_default is not None:
            if data.is_default:
                current_default = await self.repo.get_default_model()
                if current_default and current_default.id != model_id:
                    current_default.is_default = False
                    await self.repo.update(current_default)
            model.is_default = data.is_default
        if data.description is not None:
            model.description = data.description

        model = await self.repo.update(model)
        return self._to_read(model)

    async def delete_model(self, model_id: int) -> None:
        model = await self.repo.get_by_id(model_id)
        if not model:
            raise BizException(code=41003, message="模型不存在")
        await self.repo.delete_by_id(model_id)
