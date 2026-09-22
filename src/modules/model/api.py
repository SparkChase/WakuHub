from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.infra.database import get_db
from src.core.base_schema import ResponseSchema, PageResult
from src.core.depys import PageParams
from src.modules.model.schema import ModelCreate, ModelUpdate, ModelRead
from src.modules.model.service import ModelService

router = APIRouter(prefix="/models", tags=["模型管理"])


def get_model_service(db: AsyncSession = Depends(get_db)) -> ModelService:
    return ModelService(db)


@router.post("", response_model=ResponseSchema[ModelRead], summary="添加模型")
async def create_model(
    data: ModelCreate,
    svc: ModelService = Depends(get_model_service),
):
    result = await svc.create_model(data)
    return ResponseSchema(data=result)


@router.get("", response_model=ResponseSchema[PageResult[ModelRead]], summary="模型列表")
async def list_models(
    params: PageParams = Depends(),
    provider_id: int | None = Query(None, description="按供应商筛选"),
    svc: ModelService = Depends(get_model_service),
):
    page_result = await svc.list_models(params, provider_id)
    return ResponseSchema(data=page_result)


@router.get("/{model_id}", response_model=ResponseSchema[ModelRead], summary="模型详情")
async def get_model(
    model_id: int,
    svc: ModelService = Depends(get_model_service),
):
    result = await svc.get_model(model_id)
    return ResponseSchema(data=result)


@router.put("/{model_id}", response_model=ResponseSchema[ModelRead], summary="更新模型")
async def update_model(
    model_id: int,
    data: ModelUpdate,
    svc: ModelService = Depends(get_model_service),
):
    result = await svc.update_model(model_id, data)
    return ResponseSchema(data=result)


@router.delete("/{model_id}", response_model=ResponseSchema, summary="删除模型")
async def delete_model(
    model_id: int,
    svc: ModelService = Depends(get_model_service),
):
    await svc.delete_model(model_id)
    return ResponseSchema(message="删除成功")
