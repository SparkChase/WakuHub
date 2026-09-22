from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.infra.database import get_db
from src.core.base_schema import ResponseSchema, PageResult
from src.core.depys import PageParams
from src.modules.provider.schema import ProviderCreate, ProviderUpdate, ProviderRead
from src.modules.provider.service import ProviderService

router = APIRouter(prefix="/providers", tags=["模型供应商"])


# 依赖注入：每次请求创建一个 ProviderService 实例
def get_provider_service(db: AsyncSession = Depends(get_db)) -> ProviderService:
    return ProviderService(db)


@router.post("", response_model=ResponseSchema[ProviderRead], summary="创建供应商")
async def create_provider(
    data: ProviderCreate,
    svc: ProviderService = Depends(get_provider_service),
):
    provider = await svc.create_provider(data)
    return ResponseSchema(data=ProviderRead.model_validate(provider))


@router.get("", response_model=ResponseSchema[PageResult[ProviderRead]], summary="供应商列表")
async def list_providers(
    params: PageParams = Depends(),
    svc: ProviderService = Depends(get_provider_service),
):
    page_result = await svc.list_providers(params)
    return ResponseSchema(data=page_result)


@router.get("/{provider_id}", response_model=ResponseSchema[ProviderRead], summary="供应商详情")
async def get_provider(
    provider_id: int,
    svc: ProviderService = Depends(get_provider_service),
):
    provider = await svc.get_provider(provider_id)
    return ResponseSchema(data=ProviderRead.model_validate(provider))


@router.put("/{provider_id}", response_model=ResponseSchema[ProviderRead], summary="更新供应商")
async def update_provider(
    provider_id: int,
    data: ProviderUpdate,
    svc: ProviderService = Depends(get_provider_service),
):
    provider = await svc.update_provider(provider_id, data)
    return ResponseSchema(data=ProviderRead.model_validate(provider))


@router.delete("/{provider_id}", response_model=ResponseSchema, summary="删除供应商")
async def delete_provider(
    provider_id: int,
    svc: ProviderService = Depends(get_provider_service),
):
    await svc.delete_provider(provider_id)
    return ResponseSchema(message="删除成功")


@router.post("/{provider_id}/test", response_model=ResponseSchema[dict], summary="测试连接")
async def test_connection(
    provider_id: int,
    svc: ProviderService = Depends(get_provider_service),
):
    result = await svc.test_connection(provider_id)
    return ResponseSchema(data=result)
