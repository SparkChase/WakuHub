"""AgentService 单元测试（真实 MySQL waku_test 库，事务回滚隔离）。"""
import pytest

from src.core.depys import PageParams
from src.core.exceptions import BizException
from src.modules.agent.schema import (
    AgentCreate, AgentUpdate, AgentConfigSchema, PublishRequest, RollbackRequest,
)
from src.modules.agent.service import AgentService


def _make(name="数据分析助手"):
    return AgentCreate(
        name=name, description="用于测试的 Agent", type="analysis",
        config=AgentConfigSchema(
            model={"modelId": 1, "temperature": 0.7},
            prompt={"systemPrompt": "你是一个测试助手"},
        ),
    )


async def test_create_defaults(db_session):
    svc = AgentService(db_session)
    agent = await svc.create_agent(_make())
    assert agent.status == "draft"
    assert agent.version == "v0.1"
    assert agent.config["model"]["temperature"] == 0.7  # schema 展开为 dict


async def test_get_not_found(db_session):
    svc = AgentService(db_session)
    with pytest.raises(BizException) as exc:
        await svc.get_agent(999999)
    assert exc.value.code == 45001


async def test_update(db_session):
    svc = AgentService(db_session)
    agent = await svc.create_agent(_make())
    updated = await svc.update_agent(
        agent.id, AgentUpdate(name="改名", config=AgentConfigSchema(
            model={"modelId": 2, "temperature": 0.9},
        )),
    )
    assert updated.name == "改名"
    assert updated.config["model"]["modelId"] == 2
    # 未传字段不受影响
    assert updated.type == "analysis"


async def test_list_pagination(db_session):
    svc = AgentService(db_session)
    for i in range(3):
        await svc.create_agent(_make(name=f"agent{i}"))
    page = await svc.list_agents(PageParams(page=1, page_size=2, keyword="agent"))
    assert page.total == 3
    assert len(page.items) == 2


async def test_delete(db_session):
    svc = AgentService(db_session)
    agent = await svc.create_agent(_make())
    await svc.delete_agent(agent.id)
    with pytest.raises(BizException):
        await svc.get_agent(agent.id)


async def test_start_stop_lifecycle(db_session):
    svc = AgentService(db_session)
    agent = await svc.create_agent(_make())
    started = await svc.start_agent(agent.id)
    assert started.status == "active"
    # 已在运行中再次 start 应报错
    with pytest.raises(BizException) as exc:
        await svc.start_agent(agent.id)
    assert exc.value.code == 45002
    stopped = await svc.stop_agent(agent.id)
    assert stopped.status == "inactive"


async def test_publish_and_versions(db_session):
    svc = AgentService(db_session)
    agent = await svc.create_agent(_make())
    published = await svc.publish(agent.id, PublishRequest(changelog="首发"))
    assert published.version == "v0.2"  # v0.1 -> v0.2
    # 发布后默认停止，需要手动启动
    assert published.status == "inactive"

    versions = await svc.get_versions(agent.id)
    assert len(versions) == 1
    assert versions[0].is_current is True
    assert versions[0].changelog == "首发"
    assert versions[0].config == agent.config  # 配置快照


async def test_rollback(db_session):
    svc = AgentService(db_session)
    agent = await svc.create_agent(_make())
    # 发布 v0.2（快照 modelId=1）
    await svc.publish(agent.id, PublishRequest(changelog="v1"))
    v1 = (await svc.get_versions(agent.id))[0]
    # 改配置并再发布 v0.3
    await svc.update_agent(agent.id, AgentUpdate(config=AgentConfigSchema(
        model={"modelId": 2, "temperature": 0.9},
    )))
    await svc.publish(agent.id, PublishRequest(changelog="v2"))
    # 回滚到 v1
    rolled = await svc.rollback(agent.id, RollbackRequest(version_id=v1.id))
    assert rolled.version == v1.version
    assert rolled.config["model"]["modelId"] == 1
    # is_current 指回 v1
    versions = await svc.get_versions(agent.id)
    current = [v for v in versions if v.is_current]
    assert len(current) == 1 and current[0].id == v1.id


async def test_rollback_cross_agent_rejected(db_session):
    svc = AgentService(db_session)
    a1 = await svc.create_agent(_make(name="agent-a"))
    a2 = await svc.create_agent(_make(name="agent-b"))
    await svc.publish(a1.id, PublishRequest(changelog="v1"))
    v1 = (await svc.get_versions(a1.id))[0]
    # 用 a2 的身份回滚 a1 的版本应被拒绝
    with pytest.raises(BizException) as exc:
        await svc.rollback(a2.id, RollbackRequest(version_id=v1.id))
    assert exc.value.code == 45004


async def test_next_version_format():
    assert AgentService._next_version("v0.1") == "v0.2"
    assert AgentService._next_version("v1.9") == "v1.10"
    assert AgentService._next_version("bad") == "v1.0"  # 非法格式回退
