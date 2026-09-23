# CRUD 模块开发范式

所有业务模块遵循同一套分层结构和请求流转。新模块照此复制，不要发明新花样。

## 标准文件清单

```
src/modules/{module}/
├── __init__.py      # 空文件
├── model.py         # ORM 模型 (数据库表映射)
├── schema.py        # Pydantic 模型 (请求/响应校验)
├── repository.py    # 数据库操作 (继承 BaseRepository)
├── service.py       # 业务逻辑
└── api.py           # HTTP 路由 (FastAPI Router)
```

## 分层与依赖方向

```
API Router ──使用──> Pydantic Schema
     │
     └──调用──> Service ──使用──> Pydantic Schema
                    │
                    └──调用──> Repository ──操作──> ORM Model
```

- **API**：收 HTTP 请求、做依赖注入（`get_db` / `get_current_user` / `PageParams`）、包 `ResponseSchema` 返回。不写业务逻辑、不碰 Session。
- **Service**：业务校验（存在性、状态流转）、构造 ORM 对象、组装 `PageResult`。事务由 `get_db` 统一 commit，service 内不手动 commit。
- **Repository**：继承 `BaseRepository[T]`，只做数据访问。跨模块复用的查询放这里。

## 接口范式

### 1. 创建

前端 `POST` → API 收 `CreateSchema` → Service 校验 → 构造 ORM 对象 → `repo.create()` → 返回 `ReadSchema`。

### 2. 更新

前端 `PUT` → API 收 `UpdateSchema` → Service 查找对象（不存在抛 `BizException`）→ 逐字段更新非 None 值 → `repo.update()` → 返回 `ReadSchema`。

### 3. 删除

前端 `DELETE` → API 收 ID → Service 确认存在 → `repo.delete()` → 返回成功消息。

### 4. 列表（分页）

前置设施：`PageResult[T]`（`core/base_schema.py`）、`PageParams`（`core/depys.py`）、`get_page()`（`core/base_repository.py`）。

```
GET ?page=1&page_size=20&keyword=xxx
→ API: params: PageParams = Depends()
→ Service: repo.search_page(offset, limit, keyword)
→ Repo.get_page() 返回 (items, total)
→ Service: PageResult(items, total, page, page_size)
→ API: ResponseSchema[PageResult[XxxRead]]
```

**每个 Repository 必须定义 `SEARCH_FIELDS` 并实现 `search_page()` 便捷方法**，搜索字段按模块业务定（如 user 是 `["username", "email"]`，knowledge 是 `["name", "description"]`）。

## 开发流程

1. 创建 ORM Model（继承 `BaseModel`，自动带 `id/created_at/updated_at`）
2. 生成数据库迁移：`alembic revision --autogenerate -m "..."` → `alembic upgrade head`
3. 定义 Pydantic schema（`Create` / `Update` / `Read` 三件套；`Read` 加 `model_config = {"from_attributes": True}`）
4. 编写 repository（继承 `BaseRepository`，定义 `SEARCH_FIELDS` + `search_page()`）
5. 编写 service（业务校验 + 抛 `BizException`，错误码集中登记在 `core/exceptions.py`）
6. 编写 API router（`ResponseSchema` 包返回，`Depends` 注入）
7. 注册路由：`main.py` import router 并 `include_router(..., prefix="/api")`；`alembic/env.py` import model
8. 写测试：`tests/modules/{module}/test_{module}_service.py` + `test_{module}_api.py`

## 测试范式

- 测试连真实 MySQL 的 `waku_test` 库（`tests/conftest.py`），每个测试跑在外层事务里，结束整体回滚
- service 测试直接拿 `db_session` fixture 实例化 Service 调方法
- API 测试拿 `client` fixture 走 HTTP 全链路，鉴权接口先注册登录拿 token
- 外部服务（Redis 已有 fixture；MinIO / 模型调用等）用 `unittest.mock.patch` 打断点，只测库内逻辑

## 模块进度

| 模块 | 状态 | 说明 |
|------|------|------|
| auth | ✅ | 登录认证（JWT + 验证码） |
| captcha | ✅ | 验证码 |
| user | ✅ | 用户管理 |
| role | ✅ | 角色管理 |
| permission | ✅ | 权限管理 |
| provider | 📝 | 模型供应商 |
| model | 📝 | 模型管理 |
| prompt | 📝 | Prompt 管理 |
| knowledge | 📝 | 知识库管理（分段流水线 / 向量检索待接入 Milvus） |
| tool | 📝 | 工具管理 |
| agent | 📝 | Agent 管理 |
| conversation | 📝 | 对话日志 |
| analytics | 📝 | 数据统计 |
