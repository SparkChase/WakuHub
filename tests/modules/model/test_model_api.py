async def _make_provider(client, name="prov-api"):
    resp = await client.post(
        "/api/providers",
        json={"name": name, "type": "openai", "endpoint": "https://x"},
    )
    return resp.json()["data"]["id"]


async def _create_model(client, provider_id, model_id="gpt-4o"):
    resp = await client.post(
        "/api/models",
        json={
            "name": "GPT-4o", "model_id": model_id, "provider_id": provider_id,
            "capabilities": ["function_call"], "context_length": 128000,
        },
    )
    assert resp.status_code == 200
    return resp.json()["data"]


async def test_create_model_api(client):
    pid = await _make_provider(client)
    data = await _create_model(client, pid)
    assert data["id"] > 0
    assert data["provider_name"] == "prov-api"


async def test_list_models_api(client):
    pid = await _make_provider(client)
    await _create_model(client, pid, model_id="m1")
    await _create_model(client, pid, model_id="m2")
    resp = await client.get("/api/models")
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 2


async def test_filter_models_by_provider_api(client):
    p1 = await _make_provider(client, name="p1-api")
    p2 = await _make_provider(client, name="p2-api")
    await _create_model(client, p1, model_id="x1")
    await _create_model(client, p2, model_id="x2")
    resp = await client.get("/api/models", params={"provider_id": p1})
    assert resp.json()["data"]["total"] == 1


async def test_get_update_delete_model_api(client):
    pid = await _make_provider(client)
    created = await _create_model(client, pid)
    mid = created["id"]

    assert (await client.get(f"/api/models/{mid}")).json()["data"]["model_id"] == "gpt-4o"

    upd = await client.put(f"/api/models/{mid}", json={"context_length": 200000})
    assert upd.json()["data"]["context_length"] == 200000

    assert (await client.delete(f"/api/models/{mid}")).status_code == 200
    assert (await client.get(f"/api/models/{mid}")).json()["code"] == 41003
