def _payload(name="sys-prompt"):
    return {
        "name": name, "category": "chat", "tags": ["x"],
        "content": "You are {{role}}",
        "variables": [{"name": "role", "type": "string"}],
    }


async def _create(client, name="sys-prompt"):
    resp = await client.post("/api/prompts", json=_payload(name))
    assert resp.status_code == 200
    return resp.json()["data"]


async def test_create_and_get_api(client):
    created = await _create(client)
    assert created["version"] == "v0.1"
    got = await client.get(f"/api/prompts/{created['id']}")
    assert got.json()["data"]["name"] == "sys-prompt"


async def test_list_api(client):
    await _create(client, "p1")
    await _create(client, "p2")
    resp = await client.get("/api/prompts")
    assert resp.json()["data"]["total"] == 2


async def test_publish_and_versions_api(client):
    created = await _create(client)
    pub = await client.post(f"/api/prompts/{created['id']}/publish", json={"changelog": "go"})
    assert pub.json()["data"]["status"] == "published"
    versions = await client.get(f"/api/prompts/{created['id']}/versions")
    data = versions.json()["data"]
    assert len(data) == 1 and data[0]["is_current"] is True


async def test_rollback_api(client):
    created = await _create(client)
    pid = created["id"]
    await client.post(f"/api/prompts/{pid}/publish", json={"changelog": "v1"})
    v1_id = (await client.get(f"/api/prompts/{pid}/versions")).json()["data"][0]["id"]
    await client.put(f"/api/prompts/{pid}", json={"content": "changed"})
    await client.post(f"/api/prompts/{pid}/publish", json={"changelog": "v2"})
    rolled = await client.post(f"/api/prompts/{pid}/rollback", json={"version_id": v1_id})
    assert rolled.json()["data"]["content"] == "You are {{role}}"


async def test_delete_api(client):
    created = await _create(client)
    await client.delete(f"/api/prompts/{created['id']}")
    assert (await client.get(f"/api/prompts/{created['id']}")).json()["code"] == 42001
