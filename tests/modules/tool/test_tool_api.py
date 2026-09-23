"""Tool API 集成测试（HTTP 全链路，公开路由，无需鉴权）。"""

def _payload(name="weather-api"):
    return {
        "name": name, "description": "天气查询", "type": "http_api",
        "config": {"url": "https://api.example.com"},
    }


async def _create(client, name="weather-api"):
    resp = await client.post("/api/tools", json=_payload(name))
    assert resp.status_code == 200
    return resp.json()["data"]


async def test_create_and_get_api(client):
    created = await _create(client)
    assert created["status"] == "disabled"
    got = await client.get(f"/api/tools/{created['id']}")
    assert got.json()["data"]["name"] == "weather-api"


async def test_list_api(client):
    await _create(client, "t1")
    await _create(client, "t2")
    resp = await client.get("/api/tools", params={"keyword": "t"})
    assert resp.json()["data"]["total"] == 2


async def test_update_and_enable_api(client):
    created = await _create(client)
    upd = await client.put(f"/api/tools/{created['id']}", json={"description": "改了"})
    assert upd.json()["data"]["description"] == "改了"
    enabled = await client.post(f"/api/tools/{created['id']}/enable")
    assert enabled.json()["data"]["status"] == "enabled"


async def test_duplicate_name_api(client):
    await _create(client, "dup")
    resp = await client.post("/api/tools", json=_payload("dup"))
    assert resp.json()["code"] == 44001


async def test_delete_api(client):
    created = await _create(client)
    await client.delete(f"/api/tools/{created['id']}")
    assert (await client.get(f"/api/tools/{created['id']}")).json()["code"] == 44002


async def test_test_tool_api(client):
    created = await _create(client)
    resp = await client.post(f"/api/tools/{created['id']}/test", json={"input": {"city": "上海"}})
    assert resp.json()["data"]["success"] is True
