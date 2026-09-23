import time
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.exceptions import BizException
from src.core.base_schema import PageResult
from src.core.depys import PageParams
from src.modules.tool.model import Tool
from src.modules.tool.repository import ToolRepository
from src.modules.tool.schema import (
    ToolCreate, ToolUpdate, ToolRead,
    ToolTestRequest, ToolTestResponse,
)


class ToolService:
    def __init__(self, db: AsyncSession):
        self.repo = ToolRepository(db)

    def _to_read(self, tool: Tool) -> ToolRead:
        return ToolRead(
            id=tool.id,
            name=tool.name,
            description=tool.description,
            type=tool.type,
            status=tool.status,
            config=tool.config,
            function_definition=tool.function_definition,
            call_count_7d=tool.call_count_7d,
            success_rate=float(tool.success_rate),
            avg_latency=tool.avg_latency,
            created_by=tool.created_by,
        )

    async def create_tool(self, data: ToolCreate, current_user: str = None) -> ToolRead:
        existing = await self.repo.get_by_name(data.name)
        if existing:
            raise BizException(code=44001, message=f"工具 '{data.name}' 已存在")

        tool = Tool(
            name=data.name,
            description=data.description,
            type=data.type,
            config=data.config,
            function_definition=data.function_definition.model_dump() if data.function_definition else None,
            status="disabled",
            created_by=current_user,
        )
        tool = await self.repo.create(tool)
        return self._to_read(tool)

    async def get_tool(self, tool_id: int) -> ToolRead:
        tool = await self.repo.get_by_id(tool_id)
        if not tool:
            raise BizException(code=44002, message="工具不存在")
        return self._to_read(tool)

    async def list_tools(self, params: PageParams) -> PageResult[ToolRead]:
        """分页查询工具列表"""
        items, total = await self.repo.search_page(
            offset=params.offset,
            limit=params.page_size,
            keyword=params.keyword,
        )
        return PageResult(
            items=[self._to_read(t) for t in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def update_tool(self, tool_id: int, data: ToolUpdate) -> ToolRead:
        tool = await self.repo.get_by_id(tool_id)
        if not tool:
            raise BizException(code=44002, message="工具不存在")

        if data.name is not None:
            tool.name = data.name
        if data.description is not None:
            tool.description = data.description
        if data.config is not None:
            tool.config = data.config
        if data.function_definition is not None:
            tool.function_definition = data.function_definition.model_dump()

        tool = await self.repo.update(tool)
        return self._to_read(tool)

    async def delete_tool(self, tool_id: int) -> None:
        tool = await self.repo.get_by_id(tool_id)
        if not tool:
            raise BizException(code=44002, message="工具不存在")
        await self.repo.delete_by_id(tool_id)

    async def enable_tool(self, tool_id: int) -> ToolRead:
        tool = await self.repo.get_by_id(tool_id)
        if not tool:
            raise BizException(code=44002, message="工具不存在")
        tool.status = "enabled"
        tool = await self.repo.update(tool)
        return self._to_read(tool)

    async def disable_tool(self, tool_id: int) -> ToolRead:
        tool = await self.repo.get_by_id(tool_id)
        if not tool:
            raise BizException(code=44002, message="工具不存在")
        tool.status = "disabled"
        tool = await self.repo.update(tool)
        return self._to_read(tool)

    async def test_tool(self, tool_id: int, data: ToolTestRequest) -> ToolTestResponse:
        """测试工具执行"""
        tool = await self.repo.get_by_id(tool_id)
        if not tool:
            raise BizException(code=44002, message="工具不存在")

        start = time.time()
        try:
            # TODO: 根据 tool.type 执行不同的测试逻辑
            # if tool.type == "http_api":
            #     result = await self._test_http_api(tool, data.input)
            # elif tool.type == "custom_function":
            #     result = await self._test_custom_function(tool, data.input)

            latency = int((time.time() - start) * 1000)
            return ToolTestResponse(
                success=True,
                output={"message": "测试成功", "input": data.input},
                latency_ms=latency,
            )
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            return ToolTestResponse(
                success=False,
                error=str(e),
                latency_ms=latency,
            )