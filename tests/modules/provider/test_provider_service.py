import pytest

from src.core.depys import PageParams
from src.core.exceptions import BizException
from src.modules.provider.schema import ProviderCreate, ProviderUpdate
from src.modules.provider.service import ProviderService


def _make(name="openai-main"):
    return ProviderCreate(
        name=name, type="openai", endpoint="https://api.openai.com/v1",
        api_key="sk-test", description="主力供应商",
    )


async def test_create_and_get(db_session):
    svc = ProviderService(db_session)
    created = await svc.create_provider(_make())
    assert created.id is not None
    assert created.status == "disconnected"  # 新建默认未连接

    got = await svc.get_provider(created.id)
    assert got.name == "openai-main"


async def test_create_duplicate_name_raises(db_session):
    svc = ProviderService(db_session)
    await svc.create_provider(_make())
    with pytest.raises(BizException) as exc:
        await svc.create_provider(_make())
    assert exc.value.code == 40001


async def test_get_not_found_raises(db_session):
    svc = ProviderService(db_session)
    with pytest.raises(BizException) as exc:
        await svc.get_provider(999999)
    assert exc.value.code == 40002


async def test_list_pagination(db_session):
    svc = ProviderService(db_session)
    for i in range(3):
        await svc.create_provider(_make(name=f"p{i}"))
    page = await svc.list_providers(PageParams(page=1, page_size=20, keyword=None))
    assert page.total == 3
    assert len(page.items) == 3


async def test_update_partial(db_session):
    svc = ProviderService(db_session)
    created = await svc.create_provider(_make())
    updated = await svc.update_provider(created.id, ProviderUpdate(description="改过了"))
    assert updated.description == "改过了"
    assert updated.name == "openai-main"  # 未传的字段保持不变


async def test_delete(db_session):
    svc = ProviderService(db_session)
    created = await svc.create_provider(_make())
    await svc.delete_provider(created.id)
    with pytest.raises(BizException):
        await svc.get_provider(created.id)


async def test_connection_marks_connected(db_session):
    svc = ProviderService(db_session)
    created = await svc.create_provider(_make())
    result = await svc.test_connection(created.id)
    assert result["success"] is True
    refreshed = await svc.get_provider(created.id)
    assert refreshed.status == "connected"
