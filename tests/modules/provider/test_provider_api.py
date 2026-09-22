def _payload(name="anthropic-main"):
    return {
        "name": name,
        "type": "anthropic",
        "endpoint": "https://api.anthropic.com",
        "api_key": "sk-ant",
        "description": "备用供应商",
    }


async def _create(client, name="anthropic-main"):
    resp = await client.post("/api/providers", json=_payload(name))
    assert resp.status_code == 200
    return resp.json()["data"]


async def test_create_provider_api(client):
    data = await _create(client)
    assert data["id"] > 0
    assert data["status"] == "disconnected"


async def test_list_providers_api(client):
    for i in range(2):
        await _create(client, name=f"prov{i}")
    resp = await client.get("/api/providers")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 2


async def test_get_provider_api(client):
    created = await _create(client)
    resp = await client.get(f"/api/providers/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "anthropic-main"


async def test_get_provider_api_not_found(client):
    resp = await client.get("/api/providers/999999")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40002


async def test_update_provider_api(client):
    created = await _create(client)
    resp = await client.put(
        f"/api/providers/{created['id']}", json={"description": "更新描述"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["description"] == "更新描述"


async def test_delete_provider_api(client):
    created = await _create(client)
    resp = await client.delete(f"/api/providers/{created['id']}")
    assert resp.status_code == 200
    assert (await client.get(f"/api/providers/{created['id']}")).json()["code"] == 40002


async def test_test_connection_api(client):
    created = await _create(client)
    resp = await client.post(f"/api/providers/{created['id']}/test")
    assert resp.status_code == 200
    assert resp.json()["data"]["success"] is True
