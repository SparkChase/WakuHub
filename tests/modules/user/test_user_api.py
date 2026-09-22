"""User API 集成测试（查询类，走 HTTP 全链路）。注册在 auth 模块，见 tests/modules/auth。"""


async def _register(client, username: str, email: str):
    return await client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": "secret"},
    )


async def test_get_user_api(client):
    created = await _register(client, "get_api", "get_api@example.com")
    user_id = created.json()["data"]["id"]

    resp = await client.get(f"/api/users/{user_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == user_id


async def test_get_user_api_not_found(client):
    resp = await client.get("/api/users/999999")
    assert resp.status_code == 200
    assert resp.json()["code"] == 404


async def test_list_users_api(client):
    for i in range(2):
        await _register(client, f"list{i}", f"list{i}@example.com")

    resp = await client.get("/api/users")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 2
