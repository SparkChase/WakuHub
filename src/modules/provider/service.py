from sqlalchemy.ext.asyncio import AsyncSession
from src.core.exceptions import BizException
from src.core.base_schema import PageResult
from src.core.depys import PageParams
from src.modules.provider.model import ModelProvider
from src.modules.provider.repository import ProviderRepository
from src.modules.provider.schema import ProviderCreate, ProviderUpdate, ProviderRead


class ProviderService:
    def __init__(self, db: AsyncSession):
        self.repo = ProviderRepository(db)

    async def create_provider(self, data: ProviderCreate) -> ModelProvider:
        # 1. 检查名称是否已存在
        existing = await self.repo.get_by_name(data.name)
        if existing:
            raise BizException(code=40001, message=f"供应商 '{data.name}' 已存在")

        # 2. 创建 ORM 对象
        provider = ModelProvider(
            name=data.name,
            type=data.type,
            endpoint=data.endpoint,
            api_key=data.api_key,
            description=data.description,
            status="disconnected",  # 新建默认未连接
        )

        # 3. 保存到数据库
        return await self.repo.create(provider)

    async def get_provider(self, provider_id: int) -> ModelProvider:
        provider = await self.repo.get_by_id(provider_id)
        if not provider:
            raise BizException(code=40002, message="供应商不存在")
        return provider

    async def list_providers(self, params: PageParams) -> PageResult[ProviderRead]:
        """分页查询供应商列表"""
        items, total = await self.repo.search_page(
            offset=params.offset,
            limit=params.page_size,
            keyword=params.keyword,
        )
        return PageResult(
            items=[ProviderRead.model_validate(p) for p in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def update_provider(self, provider_id: int, data: ProviderUpdate) -> ModelProvider:
        provider = await self.get_provider(provider_id)

        # 只更新非 None 的字段
        if data.name is not None:
            provider.name = data.name
        if data.type is not None:
            provider.type = data.type
        if data.endpoint is not None:
            provider.endpoint = data.endpoint
        if data.api_key is not None:
            provider.api_key = data.api_key
        if data.description is not None:
            provider.description = data.description

        return await self.repo.update(provider)

    async def delete_provider(self, provider_id: int) -> None:
        # 先确认存在
        await self.get_provider(provider_id)
        await self.repo.delete_by_id(provider_id)

    async def test_connection(self, provider_id: int) -> dict:
        """测试供应商连接"""
        provider = await self.get_provider(provider_id)

        # TODO: 实际实现时，根据 provider.type 调用对应的 SDK 测试连接
        # 这里先返回模拟结果，后续可替换为真实逻辑
        try:
            # 示例：检查 endpoint 是否可达
            # async with httpx.AsyncClient() as client:
            #     resp = await client.get(provider.endpoint, timeout=10)
            provider.status = "connected"
            await self.repo.update(provider)
            return {"success": True, "message": "连接成功", "latency_ms": 128}
        except Exception as e:
            provider.status = "error"
            await self.repo.update(provider)
            return {"success": False, "message": f"连接失败: {str(e)}"}
