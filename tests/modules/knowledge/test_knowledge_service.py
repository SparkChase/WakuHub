"""KnowledgeService 单元测试（真实 MySQL waku_test 库，事务回滚隔离）。

MinIO 是外部服务，单测里 patch 掉 upload_file / delete_object，只测库内逻辑。
"""
from unittest.mock import patch

import pytest

from src.core.depys import PageParams
from src.core.exceptions import BizException
from src.modules.knowledge.schema import (
    KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseConfigUpdate,
    SegmentUpdate, RetrievalTestRequest,
)
from src.modules.knowledge.service import KnowledgeService


def _make_kb(name="测试知识库"):
    return KnowledgeBaseCreate(
        name=name, description="用于测试的知识库",
        chunk_size=500, chunk_overlap=50, top_k=5,
    )


def _upload_doc_bytes(content: str = "示例文档内容") -> dict:
    return dict(file_name="test.md", file_type="text/markdown",
                file_bytes=content.encode("utf-8"))


async def _kb_with_segment(svc: KnowledgeService, name="带分段的知识库"):
    """造一个知识库 + 一个文档 + 一条分段，返回 (kb_read, doc_read, seg_read)。"""
    kb = await svc.create_kb(_make_kb(name))
    with patch("src.modules.knowledge.service.upload_file"):
        doc = await svc.upload_document(
            kb_id=kb.id, current_user="1", **_upload_doc_bytes("WakuHub 是一个 RAG 平台"),
        )
    # 直接写一条分段（分段处理流水线未实现，手动构造数据）
    from src.modules.knowledge.model import Segment
    seg = Segment(
        knowledge_base_id=kb.id, document_id=doc.id, position=0,
        content="WakuHub 是一个 RAG 平台", word_count=16, token_count=16,
    )
    svc.db.add(seg)
    await svc.db.flush()
    return kb, doc, seg


async def test_create_kb_defaults(db_session):
    svc = KnowledgeService(db_session)
    kb = await svc.create_kb(_make_kb())
    assert kb.status == "empty"  # ORM 层默认值
    assert kb.chunk_method == "fixed"
    assert kb.retrieval_strategy == "hybrid"
    assert kb.document_count == 0


async def test_get_kb_not_found(db_session):
    svc = KnowledgeService(db_session)
    with pytest.raises(BizException) as exc:
        await svc.get_kb(999999)
    assert exc.value.code == 43001


async def test_update_kb(db_session):
    svc = KnowledgeService(db_session)
    kb = await svc.create_kb(_make_kb())
    updated = await svc.update_kb(kb.id, KnowledgeBaseUpdate(name="改名", description="新描述"))
    assert updated.name == "改名"
    assert updated.description == "新描述"
    # 未传字段不受影响
    assert updated.embedding_model == "text-embedding-ada-002"


async def test_update_kb_config(db_session):
    svc = KnowledgeService(db_session)
    kb = await svc.create_kb(_make_kb())
    updated = await svc.update_kb_config(
        kb.id, KnowledgeBaseConfigUpdate(chunk_size=800, top_k=10, similarity_threshold=0.9),
    )
    assert updated.chunk_size == 800
    assert updated.top_k == 10
    assert updated.similarity_threshold == 0.9
    # 普通更新接口不应改配置字段
    same = await svc.update_kb(kb.id, KnowledgeBaseUpdate(name="再改名"))
    assert same.chunk_size == 800


async def test_list_kbs_pagination(db_session):
    svc = KnowledgeService(db_session)
    for i in range(3):
        await svc.create_kb(_make_kb(name=f"kb{i}"))
    page = await svc.list_kbs(PageParams(page=1, page_size=2, keyword="kb"))
    assert page.total == 3
    assert len(page.items) == 2
    # 关键词过滤：description 也能命中
    page2 = await svc.list_kbs(PageParams(page=1, page_size=20, keyword="测试的"))
    assert page2.total == 3


async def test_delete_kb(db_session):
    svc = KnowledgeService(db_session)
    kb = await svc.create_kb(_make_kb())
    await svc.delete_kb(kb.id)
    with pytest.raises(BizException):
        await svc.get_kb(kb.id)


async def test_upload_document(db_session):
    svc = KnowledgeService(db_session)
    kb = await svc.create_kb(_make_kb())
    with patch("src.modules.knowledge.service.upload_file") as mock_upload:
        doc = await svc.upload_document(
            kb_id=kb.id, current_user="1", **_upload_doc_bytes(),
        )
    # MinIO 收到的对象路径带上 kb 前缀
    assert mock_upload.call_args.args[0].startswith(f"kb/{kb.id}/")
    assert doc.status == "pending"
    assert doc.file_type == "md"
    assert doc.uploaded_at is not None  # created_at 映射为 uploaded_at

    # 知识库文档计数 +1
    refreshed = await svc.get_kb(kb.id)
    assert refreshed.document_count == 1


async def test_upload_document_rejects_bad_type(db_session):
    svc = KnowledgeService(db_session)
    kb = await svc.create_kb(_make_kb())
    with pytest.raises(BizException) as exc:
        await svc.upload_document(
            kb_id=kb.id, file_name="evil.exe", file_type="application/x-msdownload",
            file_bytes=b"binary",
        )
    assert exc.value.code == 43002


async def test_upload_document_kb_not_found(db_session):
    svc = KnowledgeService(db_session)
    with patch("src.modules.knowledge.service.upload_file"):
        with pytest.raises(BizException) as exc:
            await svc.upload_document(kb_id=999999, **_upload_doc_bytes())
    assert exc.value.code == 43001


async def test_list_documents_and_delete(db_session):
    svc = KnowledgeService(db_session)
    kb = await svc.create_kb(_make_kb())
    with patch("src.modules.knowledge.service.upload_file"):
        doc = await svc.upload_document(
            kb_id=kb.id, current_user="1", **_upload_doc_bytes(),
        )
    page = await svc.list_documents(kb.id, PageParams(page=1, page_size=20, keyword=None))
    assert page.total == 1 and page.items[0].id == doc.id

    with patch("src.modules.knowledge.service.delete_object") as mock_del:
        await svc.delete_document(kb.id, doc.id)
    mock_del.assert_called_once()  # MinIO 对象同步删除

    page2 = await svc.list_documents(kb.id, PageParams(page=1, page_size=20, keyword=None))
    assert page2.total == 0
    # 知识库计数回退
    refreshed = await svc.get_kb(kb.id)
    assert refreshed.document_count == 0


async def test_delete_document_not_found(db_session):
    svc = KnowledgeService(db_session)
    kb = await svc.create_kb(_make_kb())
    with pytest.raises(BizException) as exc:
        await svc.delete_document(kb.id, 999999)
    assert exc.value.code == 43002


async def test_retry_document_only_failed(db_session):
    svc = KnowledgeService(db_session)
    kb, doc, _ = await _kb_with_segment(svc)
    # pending 状态不允许重试
    with pytest.raises(BizException) as exc:
        await svc.retry_document(kb.id, doc.id, background_tasks=None)
    assert exc.value.code == 43011

    # 置为 failed 后可重试，旧分段被清空
    doc_row = await svc.doc_repo.get_by_kb_and_id(kb.id, doc.id)
    doc_row.status = "failed"
    await svc.doc_repo.update(doc_row)
    retried = await svc.retry_document(kb.id, doc.id, background_tasks=None)
    assert retried.status == "pending"
    assert retried.segment_count == 0


async def test_update_segment(db_session):
    svc = KnowledgeService(db_session)
    kb, doc, seg = await _kb_with_segment(svc)
    updated = await svc.update_segment(kb.id, seg.id, SegmentUpdate(content="修改后的分段内容"))
    assert updated.content == "修改后的分段内容"
    assert updated.word_count == len("修改后的分段内容")


async def test_update_segment_cross_kb_rejected(db_session):
    """跨知识库访问分段应被拒绝"""
    svc = KnowledgeService(db_session)
    kb1, _, seg = await _kb_with_segment(svc, name="kb-one")
    kb2 = await svc.create_kb(_make_kb(name="kb-two"))
    with pytest.raises(BizException) as exc:
        await svc.update_segment(kb2.id, seg.id, SegmentUpdate(content="越权修改"))
    assert exc.value.code == 43003


async def test_delete_segment_updates_counts(db_session):
    svc = KnowledgeService(db_session)
    kb, doc, seg = await _kb_with_segment(svc)
    # 手动把计数抬起来，模拟分段流水线已写计数
    kb_row = await svc.kb_repo.get_by_id(kb.id)
    kb_row.segment_count = 1
    doc_row = await svc.doc_repo.get_by_kb_and_id(kb.id, doc.id)
    doc_row.segment_count = 1
    await svc.seg_repo.update(seg)

    await svc.delete_segment(kb.id, seg.id)
    refreshed_kb = await svc.get_kb(kb.id)
    assert refreshed_kb.segment_count == 0
    doc_after = await svc.doc_repo.get_by_kb_and_id(kb.id, doc.id)
    assert doc_after.segment_count == 0


async def test_retrieval_test_scoring(db_session):
    svc = KnowledgeService(db_session)
    kb, doc, seg = await _kb_with_segment(svc)
    # 再造一条无关分段，验证打分能区分
    from src.modules.knowledge.model import Segment
    svc.db.add(Segment(
        knowledge_base_id=kb.id, document_id=doc.id, position=1,
        content="完全无关的内容，讲的是菜谱", word_count=10, token_count=10,
    ))
    await svc.db.flush()

    results = await svc.retrieval_test(kb.id, RetrievalTestRequest(query="WakuHub RAG 平台"))
    assert len(results) == 1  # 无关分段低于阈值被过滤
    assert results[0].segment_id == seg.id
    assert results[0].document_name == doc.file_name
    assert results[0].score > 0


async def test_retrieval_test_kb_not_found(db_session):
    svc = KnowledgeService(db_session)
    with pytest.raises(BizException) as exc:
        await svc.retrieval_test(999999, RetrievalTestRequest(query="任意"))
    assert exc.value.code == 43001
