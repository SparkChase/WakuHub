from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.user.model import User
from src.modules.auth.deps import get_current_user
from src.infra.database import get_db
from src.core.base_schema import ResponseSchema, PageResult
from src.core.depys import PageParams
from src.modules.knowledge.schema import (
    KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseConfigUpdate, KnowledgeBaseRead,
    DocumentRead, SegmentRead, SegmentUpdate,
    RetrievalTestRequest, RetrievalTestResult,
)
from src.modules.knowledge.service import KnowledgeService
from loguru import logger

router = APIRouter(prefix="/knowledge-bases", tags=["知识库管理"])


def get_knowledge_service(db: AsyncSession = Depends(get_db)) -> KnowledgeService:
    return KnowledgeService(db)


# ===== 知识库 CRUD =====

@router.post("", response_model=ResponseSchema[KnowledgeBaseRead], summary="创建知识库")
async def create_kb(
    data: KnowledgeBaseCreate,
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    result = await svc.create_kb(data)
    return ResponseSchema(data=result)


@router.get("", response_model=ResponseSchema[PageResult[KnowledgeBaseRead]], summary="知识库列表")
async def list_kbs(
    params: PageParams = Depends(),
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    page_result = await svc.list_kbs(params)
    return ResponseSchema(data=page_result)


@router.get("/{kb_id}", response_model=ResponseSchema[KnowledgeBaseRead], summary="知识库详情")
async def get_kb(
    kb_id: int,
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    result = await svc.get_kb(kb_id)
    return ResponseSchema(data=result)


@router.put("/{kb_id}", response_model=ResponseSchema[KnowledgeBaseRead], summary="更新知识库")
async def update_kb(
    kb_id: int, data: KnowledgeBaseUpdate,
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    result = await svc.update_kb(kb_id, data)
    return ResponseSchema(data=result)


@router.put("/{kb_id}/config", response_model=ResponseSchema[KnowledgeBaseRead], summary="更新分段/检索配置")
async def update_kb_config(
    kb_id: int, data: KnowledgeBaseConfigUpdate,
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    result = await svc.update_kb_config(kb_id, data)
    return ResponseSchema(data=result)


@router.delete("/{kb_id}", response_model=ResponseSchema, summary="删除知识库")
async def delete_kb(
    kb_id: int,
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    await svc.delete_kb(kb_id)
    return ResponseSchema(message="删除成功")


# ===== 文档管理 =====

@router.post("/{kb_id}/documents", response_model=ResponseSchema[DocumentRead], summary="上传文档")
async def upload_document(
    kb_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    file_bytes = await file.read()
    logger.info(f"上传文档: {file.filename} ({file.content_type})")
    resp = await svc.upload_document(
        kb_id=kb_id,
        file_name=file.filename,
        file_type=file.content_type,
        file_bytes=file_bytes,
        current_user=str(user.id),
        background_tasks=background_tasks,
    )
    return ResponseSchema(data=resp)


@router.get("/{kb_id}/documents", response_model=ResponseSchema[PageResult[DocumentRead]], summary="文档列表")
async def list_documents(
    kb_id: int,
    params: PageParams = Depends(),
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    page_result = await svc.list_documents(kb_id, params)
    return ResponseSchema(data=page_result)


@router.delete("/{kb_id}/documents/{doc_id}", response_model=ResponseSchema, summary="删除文档")
async def delete_document(
    kb_id: int, doc_id: int,
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    await svc.delete_document(kb_id, doc_id)
    return ResponseSchema(message="删除成功")


@router.post("/{kb_id}/documents/{doc_id}/retry", response_model=ResponseSchema[DocumentRead], summary="重试失败文档")
async def retry_document(
    kb_id: int, doc_id: int,
    background_tasks: BackgroundTasks,
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    result = await svc.retry_document(kb_id, doc_id, background_tasks)
    return ResponseSchema(data=result)


@router.get("/{kb_id}/documents/{doc_id}/segments", response_model=ResponseSchema[PageResult[SegmentRead]], summary="文档分段列表")
async def list_document_segments(
    kb_id: int, doc_id: int,
    params: PageParams = Depends(),
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    page_result = await svc.list_document_segments(kb_id, doc_id, params)
    return ResponseSchema(data=page_result)


# ===== 分段管理 =====

@router.get("/{kb_id}/segments", response_model=ResponseSchema[PageResult[SegmentRead]], summary="分段列表")
async def list_segments(
    kb_id: int,
    params: PageParams = Depends(),
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    page_result = await svc.list_segments(kb_id, params)
    return ResponseSchema(data=page_result)


@router.put("/{kb_id}/segments/{seg_id}", response_model=ResponseSchema[SegmentRead], summary="编辑分段")
async def update_segment(
    kb_id: int, seg_id: int, data: SegmentUpdate,
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    result = await svc.update_segment(kb_id, seg_id, data)
    return ResponseSchema(data=result)


@router.delete("/{kb_id}/segments/{seg_id}", response_model=ResponseSchema, summary="删除分段")
async def delete_segment(
    kb_id: int, seg_id: int,
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    await svc.delete_segment(kb_id, seg_id)
    return ResponseSchema(message="删除成功")


@router.post("/{kb_id}/retrieval-test", response_model=ResponseSchema[list[RetrievalTestResult]], summary="检索测试")
async def retrieval_test(
    kb_id: int, data: RetrievalTestRequest,
    svc: KnowledgeService = Depends(get_knowledge_service),
):
    results = await svc.retrieval_test(kb_id, data)
    return ResponseSchema(data=results)
