from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.infra.database import get_db
from src.core.base_schema import ResponseSchema, PageResult
from src.core.depys import PageParams
from src.modules.tool.schema import (
    ToolCreate, ToolUpdate, ToolRead,
    ToolTestRequest, ToolTestResponse,
)
from src.modules.tool.service import ToolService

router = APIRouter(prefix="/tools", tags=["工具管理"])


def get_tool_service(db: AsyncSession = Depends(get_db)) -> ToolService:
    return ToolService(db)


@router.post("", response_model=ResponseSchema[ToolRead], summary="注册工具")
async def create_tool(
    data: ToolCreate,
    svc: ToolService = Depends(get_tool_service),
):
    result = await svc.create_tool(data)
    return ResponseSchema(data=result)


@router.get("", response_model=ResponseSchema[PageResult[ToolRead]], summary="工具列表")
async def list_tools(
    params: PageParams = Depends(),
    svc: ToolService = Depends(get_tool_service),
):
    page_result = await svc.list_tools(params)
    return ResponseSchema(data=page_result)


@router.get("/{tool_id}", response_model=ResponseSchema[ToolRead], summary="工具详情")
async def get_tool(
    tool_id: int,
    svc: ToolService = Depends(get_tool_service),
):
    result = await svc.get_tool(tool_id)
    return ResponseSchema(data=result)


@router.put("/{tool_id}", response_model=ResponseSchema[ToolRead], summary="更新工具")
async def update_tool(
    tool_id: int, data: ToolUpdate,
    svc: ToolService = Depends(get_tool_service),
):
    result = await svc.update_tool(tool_id, data)
    return ResponseSchema(data=result)


@router.delete("/{tool_id}", response_model=ResponseSchema, summary="删除工具")
async def delete_tool(
    tool_id: int,
    svc: ToolService = Depends(get_tool_service),
):
    await svc.delete_tool(tool_id)
    return ResponseSchema(message="删除成功")


@router.post("/{tool_id}/enable", response_model=ResponseSchema[ToolRead], summary="启用工具")
async def enable_tool(
    tool_id: int,
    svc: ToolService = Depends(get_tool_service),
):
    result = await svc.enable_tool(tool_id)
    return ResponseSchema(data=result)


@router.post("/{tool_id}/disable", response_model=ResponseSchema[ToolRead], summary="禁用工具")
async def disable_tool(
    tool_id: int,
    svc: ToolService = Depends(get_tool_service),
):
    result = await svc.disable_tool(tool_id)
    return ResponseSchema(data=result)


@router.post("/{tool_id}/test", response_model=ResponseSchema[ToolTestResponse], summary="测试工具")
async def test_tool(
    tool_id: int, data: ToolTestRequest,
    svc: ToolService = Depends(get_tool_service),
):
    result = await svc.test_tool(tool_id, data)
    return ResponseSchema(data=result)