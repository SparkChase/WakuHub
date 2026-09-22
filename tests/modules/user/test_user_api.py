"""User API 集成测试（走 HTTP，经过路由 -> service -> repository 全链路）。"""


async def test_create_user_api(client):
    resp = await client.post(
        "/api/v1/users",
        json={"username": "api_user", "email": "api@example.com", "password": "secret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["username"] == "api_user"
    assert body["data"]["email"] == "api@example.com"
    assert body["data"]["is_active"] is True
    assert body["data"]["id"] > 0


async def test_create_user_api_duplicate(client):
    payload = {"username": "dup_api", "email": "dup_api@example.com", "password": "secret"}
    first = await client.post("/api/v1/users", json=payload)
    assert first.status_code == 200

    second = await client.post("/api/v1/users", json=payload)
    # BizException 由全局处理器捕获，HTTP 200 + 业务码 400
    assert second.status_code == 200
    assert second.json()["code"] == 400


async def test_create_user_api_invalid_email(client):
    resp = await client.post(
        "/api/v1/users",
        json={"username": "bad", "email": "not-an-email", "password": "secret"},
    )
    # pydantic 校验失败 -> FastAPI 返回 422
    assert resp.status_code == 422


async def test_get_user_api(client):
    created = await client.post(
        "/api/v1/users",
        json={"username": "get_api", "email": "get_api@example.com", "password": "secret"},
    )
    user_id = created.json()["data"]["id"]

    resp = await client.get(f"/api/v1/users/{user_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == user_id


async def test_get_user_api_not_found(client):
    resp = await client.get("/api/v1/users/999999")
    assert resp.status_code == 200
    assert resp.json()["code"] == 404


async def test_list_users_api(client):
    for i in range(2):
        await client.post(
            "/api/v1/users",
            json={"username": f"list{i}", "email": f"list{i}@example.com", "password": "secret"},
        )

    resp = await client.get("/api/v1/users")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2
