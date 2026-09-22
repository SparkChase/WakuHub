import pytest

from src.core.depys import PageParams
from src.core.exceptions import BizException
from src.modules.model.schema import ModelCreate, ModelUpdate
from src.modules.model.service import ModelService
from src.modules.provider.schema import ProviderCreate
from src.modules.provider.service import ProviderService


async def _make_provider(db_session, name="prov"):
    p = await ProviderService(db_session).create_provider(
        ProviderCreate(name=name, type="openai", endpoint="https://x")
    )
    return p.id


def _model(provider_id, model_id="gpt-4", is_default=False):
    return ModelCreate(
        name="GPT-4", model_id=model_id, provider_id=provider_id,
        capabilities=["function_call", "vision"], context_length=8192,
        input_price=0.03, output_price=0.06, is_default=is_default,
    )


async def test_create_reads_provider_name_and_capabilities(db_session):
    pid = await _make_provider(db_session)
    svc = ModelService(db_session)
    created = await svc.create_model(_model(pid))
    assert created.provider_name == "prov"       # 关联供应商名回填
    assert created.capabilities == ["function_call", "vision"]  # 逗号串转 list
    assert float(created.input_price) == 0.03


async def test_create_duplicate_model_id_raises(db_session):
    pid = await _make_provider(db_session)
    svc = ModelService(db_session)
    await svc.create_model(_model(pid))
    with pytest.raises(BizException) as exc:
        await svc.create_model(_model(pid))
    assert exc.value.code == 41001


async def test_create_provider_missing_raises(db_session):
    svc = ModelService(db_session)
    with pytest.raises(BizException) as exc:
        await svc.create_model(_model(999999))
    assert exc.value.code == 41002


async def test_default_switch_unsets_previous(db_session):
    pid = await _make_provider(db_session)
    svc = ModelService(db_session)
    m1 = await svc.create_model(_model(pid, model_id="m1", is_default=True))
    m2 = await svc.create_model(_model(pid, model_id="m2", is_default=True))
    # 新默认设置后，旧默认应被取消
    assert (await svc.get_model(m1.id)).is_default is False
    assert (await svc.get_model(m2.id)).is_default is True


async def test_list_and_filter_by_provider(db_session):
    p1 = await _make_provider(db_session, name="p1")
    p2 = await _make_provider(db_session, name="p2")
    svc = ModelService(db_session)
    await svc.create_model(_model(p1, model_id="a"))
    await svc.create_model(_model(p1, model_id="b"))
    await svc.create_model(_model(p2, model_id="c"))

    all_page = await svc.list_models(PageParams(page=1, page_size=20, keyword=None))
    assert all_page.total == 3

    p1_page = await svc.list_models(PageParams(page=1, page_size=20, keyword=None), provider_id=p1)
    assert p1_page.total == 2


async def test_update_and_delete(db_session):
    pid = await _make_provider(db_session)
    svc = ModelService(db_session)
    created = await svc.create_model(_model(pid))
    updated = await svc.update_model(created.id, ModelUpdate(status="unavailable"))
    assert updated.status == "unavailable"
    await svc.delete_model(created.id)
    with pytest.raises(BizException):
        await svc.get_model(created.id)
