from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.infra.database import get_db
from src.core.base_schema import ResponseSchema, PageResult
from src.core.depys import PageParams
from src.modules.agent.schema import (
    AgentCreate, AgentUpdate, AgentRead,
    AgentVersionRead, PublishRequest, RollbackRequest,
)
from src.modules.agent.service import AgentService

router = APIRouter(prefix="/agents", tags=["Agent管理"])


def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    return AgentService(db)


@router.post("", response_model=ResponseSchema[AgentRead], summary="创建Agent")
async def create_agent(
    data: AgentCreate,
    svc: AgentService = Depends(get_agent_service),
):
    result = await svc.create_agent(data)
    return ResponseSchema(data=result)


@router.get("", response_model=ResponseSchema[PageResult[AgentRead]], summary="Agent列表")
async def list_agents(
    params: PageParams = Depends(),
    svc: AgentService = Depends(get_agent_service),
):
    page_result = await svc.list_agents(params)
    return ResponseSchema(data=page_result)


@router.get("/{agent_id}", response_model=ResponseSchema[AgentRead], summary="Agent详情")
async def get_agent(
    agent_id: int,
    svc: AgentService = Depends(get_agent_service),
):
    result = await svc.get_agent(agent_id)
    return ResponseSchema(data=result)


@router.put("/{agent_id}", response_model=ResponseSchema[AgentRead], summary="更新Agent")
async def update_agent(
    agent_id: int, data: AgentUpdate,
    svc: AgentService = Depends(get_agent_service),
):
    result = await svc.update_agent(agent_id, data)
    return ResponseSchema(data=result)


@router.delete("/{agent_id}", response_model=ResponseSchema, summary="删除Agent")
async def delete_agent(
    agent_id: int,
    svc: AgentService = Depends(get_agent_service),
):
    await svc.delete_agent(agent_id)
    return ResponseSchema(message="删除成功")


@router.post("/{agent_id}/start", response_model=ResponseSchema[AgentRead], summary="启动Agent")
async def start_agent(
    agent_id: int,
    svc: AgentService = Depends(get_agent_service),
):
    result = await svc.start_agent(agent_id)
    return ResponseSchema(data=result)


@router.post("/{agent_id}/stop", response_model=ResponseSchema[AgentRead], summary="停止Agent")
async def stop_agent(
    agent_id: int,
    svc: AgentService = Depends(get_agent_service),
):
    result = await svc.stop_agent(agent_id)
    return ResponseSchema(data=result)


@router.post("/{agent_id}/publish", response_model=ResponseSchema[AgentRead], summary="发布版本")
async def publish_agent(
    agent_id: int, data: PublishRequest,
    svc: AgentService = Depends(get_agent_service),
):
    result = await svc.publish(agent_id, data)
    return ResponseSchema(data=result)


@router.get("/{agent_id}/versions", response_model=ResponseSchema[list[AgentVersionRead]], summary="版本列表")
async def get_versions(
    agent_id: int,
    svc: AgentService = Depends(get_agent_service),
):
    results = await svc.get_versions(agent_id)
    return ResponseSchema(data=results)


@router.post("/{agent_id}/rollback", response_model=ResponseSchema[AgentRead], summary="回滚版本")
async def rollback_agent(
    agent_id: int, data: RollbackRequest,
    svc: AgentService = Depends(get_agent_service),
):
    result = await svc.rollback(agent_id, data)
    return ResponseSchema(data=result)