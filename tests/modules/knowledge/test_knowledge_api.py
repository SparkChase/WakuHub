"""Knowledge API 集成测试（HTTP 全链路，走 create_app + 依赖覆盖）。

上传接口走 MinIO mock；鉴权接口先注册登录拿 token；
分段数据用 db_session fixture 直接写库（client 与它共享同一事务）。
"""
from unittest.mock import patch

from src.modules.knowledge.model import Segment
from src.core.config import get_settings

settings = get_settings()


async def _auth_headers(client, redis_client) -> dict:
    """注册 + 验证码登录，返回 Authorization 头。"""
    await client.post(
        "/api/auth/register",
        json={"username": "kb_user", "email": "kb_user@example.com", "password": "secret"},
    )
    cap = (await client.get("/api/captcha")).json()["data"]
    code = await redis_client.get(f"{settings.CAPTCHA_KEY_PREFIX}{cap['key']}")
    login = await client.post(
        "/api/auth/login",
        json={"username": "kb_user", "password": "secret",
              "captcha_key": cap["key"], "captcha_code": code},
    )
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _kb_payload(name="知识库API测试"):
    return {"name": name, "description": "api test", "chunk_size": 500}


async def _create_kb(client, headers, name="知识库API测试") -> dict:
    resp = await client.post("/api/knowledge-bases", json=_kb_payload(name), headers=headers)
    assert resp.status_code == 200
    return resp.json()["data"]


async def _upload_doc(client, headers, kb_id: int, filename="hello.md") -> dict:
    with patch("src.modules.knowledge.service.upload_file"):
        up = await client.post(
            f"/api/knowledge-bases/{kb_id}/documents",
            files={"file": (filename, "hello waku".encode(), "text/markdown")},
            headers=headers,
        )
    assert up.status_code == 200
    return up.json()["data"]


async def test_kb_crud_flow(client, redis_client):
    headers = await _auth_headers(client, redis_client)

    # create
    created = await _create_kb(client, headers, "crud-flow")
    assert created["id"] > 0 and created["status"] == "empty"

    # get
    got = await client.get(f"/api/knowledge-bases/{created['id']}", headers=headers)
    assert got.json()["data"]["name"] == "crud-flow"

    # list 分页 + 关键词
    await _create_kb(client, headers, "crud-flow-2")
    lst = await client.get(
        "/api/knowledge-bases", params={"keyword": "crud-flow"}, headers=headers,
    )
    assert lst.json()["data"]["total"] == 2

    # update
    upd = await client.put(
        f"/api/knowledge-bases/{created['id']}",
        json={"name": "crud-flow-updated"}, headers=headers,
    )
    assert upd.json()["data"]["name"] == "crud-flow-updated"

    # update config
    cfg = await client.put(
        f"/api/knowledge-bases/{created['id']}/config",
        json={"chunk_size": 800, "top_k": 10}, headers=headers,
    )
    assert cfg.json()["data"]["chunk_size"] == 800

    # delete
    await client.delete(f"/api/knowledge-bases/{created['id']}", headers=headers)
    deleted = await client.get(f"/api/knowledge-bases/{created['id']}", headers=headers)
    assert deleted.json()["code"] == 43001


async def test_kb_not_found(client, redis_client):
    headers = await _auth_headers(client, redis_client)
    resp = await client.get("/api/knowledge-bases/999999", headers=headers)
    assert resp.json()["code"] == 43001


async def test_document_upload_list_delete(client, redis_client):
    headers = await _auth_headers(client, redis_client)
    kb = await _create_kb(client, headers, "doc-flow")

    doc = await _upload_doc(client, headers, kb["id"])
    assert doc["file_name"] == "hello.md"
    assert doc["status"] == "pending"
    assert doc["uploaded_at"] is not None

    # 列表（带关键词过滤）
    lst = await client.get(
        f"/api/knowledge-bases/{kb['id']}/documents",
        params={"keyword": "hello"}, headers=headers,
    )
    assert lst.json()["data"]["total"] == 1

    # 删除（MinIO delete mock 掉）
    with patch("src.modules.knowledge.service.delete_object"):
        dele = await client.delete(
            f"/api/knowledge-bases/{kb['id']}/documents/{doc['id']}", headers=headers,
        )
    assert dele.json()["message"] == "删除成功"
    lst2 = await client.get(f"/api/knowledge-bases/{kb['id']}/documents", headers=headers)
    assert lst2.json()["data"]["total"] == 0


async def test_document_upload_bad_type(client, redis_client):
    headers = await _auth_headers(client, redis_client)
    kb = await _create_kb(client, headers, "badtype")
    resp = await client.post(
        f"/api/knowledge-bases/{kb['id']}/documents",
        files={"file": ("evil.exe", b"binary", "application/x-msdownload")},
        headers=headers,
    )
    assert resp.json()["code"] == 43002


async def test_retry_document(client, redis_client):
    headers = await _auth_headers(client, redis_client)
    kb = await _create_kb(client, headers, "retry")
    doc = await _upload_doc(client, headers, kb["id"])

    # pending 不能重试
    resp = await client.post(
        f"/api/knowledge-bases/{kb['id']}/documents/{doc['id']}/retry", headers=headers,
    )
    assert resp.json()["code"] == 43011


async def test_segments_flow(db_session, client, redis_client):
    """分段列表 / 编辑 / 删除走 HTTP 全链路，分段数据直接写库构造。"""
    headers = await _auth_headers(client, redis_client)
    kb = await _create_kb(client, headers, "seg-flow")
    doc = await _upload_doc(client, headers, kb["id"])

    seg = Segment(
        knowledge_base_id=kb["id"], document_id=doc["id"], position=0,
        content="这是第一段内容", word_count=7, token_count=7,
    )
    db_session.add(seg)
    await db_session.flush()
    seg_id = seg.id

    # 文档分段列表
    lst = await client.get(
        f"/api/knowledge-bases/{kb['id']}/documents/{doc['id']}/segments", headers=headers,
    )
    assert lst.json()["data"]["total"] == 1

    # 知识库分段列表
    lst2 = await client.get(f"/api/knowledge-bases/{kb['id']}/segments", headers=headers)
    assert lst2.json()["data"]["total"] == 1

    # 编辑分段
    upd = await client.put(
        f"/api/knowledge-bases/{kb['id']}/segments/{seg_id}",
        json={"content": "编辑后的分段"}, headers=headers,
    )
    assert upd.json()["data"]["content"] == "编辑后的分段"

    # 删除分段
    dele = await client.delete(
        f"/api/knowledge-bases/{kb['id']}/segments/{seg_id}", headers=headers,
    )
    assert dele.json()["message"] == "删除成功"


async def test_retrieval_test_api(client, redis_client):
    headers = await _auth_headers(client, redis_client)
    kb = await _create_kb(client, headers, "retrieval")
    resp = await client.post(
        f"/api/knowledge-bases/{kb['id']}/retrieval-test",
        json={"query": "测试查询", "top_k": 3, "similarity_threshold": 0.1},
        headers=headers,
    )
    # 无分段时返回空数组（而非 None / 500）
    assert resp.json()["data"] == []
