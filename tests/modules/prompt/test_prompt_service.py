import pytest

from src.core.depys import PageParams
from src.core.exceptions import BizException
from src.modules.prompt.schema import (
    PromptCreate, PromptUpdate, PublishRequest, RollbackRequest, PromptVariableSchema,
)
from src.modules.prompt.service import PromptService


def _make(name="greeting"):
    return PromptCreate(
        name=name, category="chat", tags=["hi"], content="你好 {{name}}",
        variables=[PromptVariableSchema(name="name", type="string")],
    )


async def test_create_defaults(db_session):
    svc = PromptService(db_session)
    p = await svc.create_prompt(_make())
    assert p.version == "v0.1"
    assert p.status == "draft"
    assert p.variables[0].name == "name"  # JSON 变量回读为 schema


async def test_get_not_found(db_session):
    svc = PromptService(db_session)
    with pytest.raises(BizException) as exc:
        await svc.get_prompt(999999)
    assert exc.value.code == 42001


async def test_update(db_session):
    svc = PromptService(db_session)
    p = await svc.create_prompt(_make())
    updated = await svc.update_prompt(p.id, PromptUpdate(content="改了", tags=["a", "b"]))
    assert updated.content == "改了"
    assert updated.tags == ["a", "b"]


async def test_publish_creates_version_and_bumps(db_session):
    svc = PromptService(db_session)
    p = await svc.create_prompt(_make())
    published = await svc.publish(p.id, PublishRequest(changelog="首发"))
    assert published.status == "published"
    assert published.version == "v0.2"  # v0.1 -> v0.2
    versions = await svc.get_versions(p.id)
    assert len(versions) == 1
    assert versions[0].is_current is True
    assert versions[0].changelog == "首发"


async def test_rollback(db_session):
    svc = PromptService(db_session)
    p = await svc.create_prompt(_make())
    # 发布 v0.2（快照内容 "你好 {{name}}"）
    await svc.publish(p.id, PublishRequest(changelog="v1"))
    v1 = (await svc.get_versions(p.id))[0]
    # 改内容并再次发布 v0.3
    await svc.update_prompt(p.id, PromptUpdate(content="全新内容"))
    await svc.publish(p.id, PublishRequest(changelog="v2"))
    # 回滚到 v1
    rolled = await svc.rollback(p.id, RollbackRequest(version_id=v1.id))
    assert rolled.content == "你好 {{name}}"
    assert rolled.version == v1.version


async def test_list_pagination(db_session):
    svc = PromptService(db_session)
    for i in range(3):
        await svc.create_prompt(_make(name=f"p{i}"))
    page = await svc.list_prompts(PageParams(page=1, page_size=20, keyword=None))
    assert page.total == 3


async def test_delete(db_session):
    svc = PromptService(db_session)
    p = await svc.create_prompt(_make())
    await svc.delete_prompt(p.id)
    with pytest.raises(BizException):
        await svc.get_prompt(p.id)
