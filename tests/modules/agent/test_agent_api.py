"""Agent API 集成测试（HTTP 全链路，公开路由，无需鉴权）。"""


def _payload(name="数据分析助手"):
    return {
        "name": name, "description": "api test", "type": "analysis",
        "config": {"model": {"modelId": 1, "temperature": 0.7}},
    }


async def _create(client, name="数据分析助手"):
    resp = await client.post("/api/agents", json=_payload(name))
    assert resp.status_code == 200
    return resp.json()["data"]


async def test_create_and_get_api(client):
    created = await _create(client)
    assert created["status"] == "draft"
    assert created["version"] == "v0.1"
    got = await client.get(f"/api/agents/{created['id']}")
    assert got.json()["data"]["name"] == "数据分析助手"


async def test_list_api(client):
    await _create(client, "a1")
    await _create(client, "a2")
    resp = await client.get("/api/agents", params={"keyword": "a"})
    assert resp.json()["data"]["total"] == 2


async def test_update_api(client):
    created = await _create(client)
    upd = await client.put(f"/api/agents/{created['id']}", json={"name": "改了"})
    assert upd.json()["data"]["name"] == "改了"


async def test_start_stop_api(client):
    created = await _create(client)
    started = await client.post(f"/api/agents/{created['id']}/start")
    assert started.json()["data"]["status"] == "active"
    stopped = await client.post(f"/api/agents/{created['id']}/stop")
    assert stopped.json()["data"]["status"] == "inactive"


async def test_publish_versions_rollback_api(client):
    created = await _create(client)
    aid = created["id"]

    pub = await client.post(f"/api/agents/{aid}/publish", json={"changelog": "go"})
    assert pub.json()["data"]["version"] == "v0.2"
    versions = await client.get(f"/api/agents/{aid}/versions")
    data = versions.json()["data"]
    assert len(data) == 1 and data[0]["is_current"] is True

    v1_id = data[0]["id"]
    rolled = await client.post(f"/api/agents/{aid}/rollback", json={"version_id": v1_id})
    assert rolled.json()["data"]["version"] == "v0.2"


async def test_delete_api(client):
    created = await _create(client)
    await client.delete(f"/api/agents/{created['id']}")
    assert (await client.get(f"/api/agents/{created['id']}")).json()["code"] == 45001
