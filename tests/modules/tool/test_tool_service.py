"""ToolService 单元测试（真实 MySQL waku_test 库，事务回滚隔离）。"""
import pytest

from src.core.depys import PageParams
from src.core.exceptions import BizException
from src.modules.tool.schema import ToolCreate, ToolUpdate, ToolTestRequest, FunctionDefinitionSchema
from src.modules.tool.service import ToolService


def _make(name="weather-api"):
    return ToolCreate(
        name=name, description="天气查询工具", type="http_api",
        config={"url": "https://api.example.com/weather"},
        function_definition=FunctionDefinitionSchema(
            name="get_weather", description="查询天气",
            parameters={"type": "object", "properties": {"city": {"type": "string"}}},
        ),
    )


async def test_create_defaults(db_session):
    svc = ToolService(db_session)
    tool = await svc.create_tool(_make())
    assert tool.status == "disabled"  # 注册后默认禁用
    assert tool.function_definition["name"] == "get_weather"  # schema 展开为 dict
    assert tool.call_count_7d == 0


async def test_create_duplicate_name(db_session):
    svc = ToolService(db_session)
    await svc.create_tool(_make("dup-tool"))
    with pytest.raises(BizException) as exc:
        await svc.create_tool(_make("dup-tool"))
    assert exc.value.code == 44001


async def test_get_not_found(db_session):
    svc = ToolService(db_session)
    with pytest.raises(BizException) as exc:
        await svc.get_tool(999999)
    assert exc.value.code == 44002


async def test_update(db_session):
    svc = ToolService(db_session)
    tool = await svc.create_tool(_make())
    updated = await svc.update_tool(
        tool.id,
        ToolUpdate(description="新描述", function_definition=FunctionDefinitionSchema(
            name="get_weather_v2", description="改", parameters={},
        )),
    )
    assert updated.description == "新描述"
    assert updated.function_definition["name"] == "get_weather_v2"
    # 未传字段不受影响
    assert updated.name == "weather-api"


async def test_list_pagination(db_session):
    svc = ToolService(db_session)
    for i in range(3):
        await svc.create_tool(_make(name=f"tool{i}"))
    page = await svc.list_tools(PageParams(page=1, page_size=2, keyword="tool"))
    assert page.total == 3
    assert len(page.items) == 2


async def test_enable_disable(db_session):
    svc = ToolService(db_session)
    tool = await svc.create_tool(_make())
    enabled = await svc.enable_tool(tool.id)
    assert enabled.status == "enabled"
    disabled = await svc.disable_tool(tool.id)
    assert disabled.status == "disabled"


async def test_delete(db_session):
    svc = ToolService(db_session)
    tool = await svc.create_tool(_make())
    await svc.delete_tool(tool.id)
    with pytest.raises(BizException):
        await svc.get_tool(tool.id)


async def test_test_tool(db_session):
    svc = ToolService(db_session)
    tool = await svc.create_tool(_make())
    result = await svc.test_tool(tool.id, ToolTestRequest(input={"city": "北京"}))
    assert result.success is True
    assert result.output["input"] == {"city": "北京"}
