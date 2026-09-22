from fastapi import Query


# 通用分页查询参数依赖：路由用 page: PageParams = Depends() 注入
# 前端传 page / page_size / keyword，这里换算成仓储层要的 offset / limit
class PageParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码，从 1 开始"),
        page_size: int = Query(20, ge=1, le=100, description="每页条数，最大 100"),
        keyword: str | None = Query(None, description="模糊搜索关键词"),
    ):
        self.page = page
        self.page_size = page_size
        self.keyword = keyword
        # offset/limit 一次算好，route 直接透传给 repo.get_page，不用重复计算
        self.offset = (page - 1) * page_size
        self.limit = page_size
