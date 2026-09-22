# WakuHub

FastAPI 异步后端，RAG / Agent 方向。数据层用 SQLAlchemy async + PostgreSQL，配套 Redis、MinIO、Milvus、Neo4j，接入 DeepSeek / DashScope 模型。

## 技术栈

- **Python 3.13**，依赖用 **uv** 管理（`pyproject.toml` + `uv.lock`）
- **FastAPI** + **uvicorn/fastapi dev**
- **SQLAlchemy 2.0 async** + **asyncpg**，迁移用 **alembic**（async 模板）
- **pydantic-settings** 读环境变量，**loguru** 日志

## 常用命令

```bash
uv sync                      # 安装依赖
uv add <包名>                 # 添加依赖（会更新 uv.lock，需一并提交）
fastapi dev src/main.py      # 本地开发启动
uv run main.py               # 运行入口

cd docker && docker compose -f docker-compose.yaml up -d   # 起依赖中间件

alembic revision --autogenerate -m "<描述>"   # 生成迁移
alembic upgrade head                          # 执行迁移
```

健康检查：`GET /health` 返回 `{"status": "ok"}`。

## 目录结构

```
src/
├── main.py              # FastAPI 应用工厂 create_app + lifespan
├── core/                # 基础设施抽象
│   ├── config.py        # Settings（pydantic-settings）+ get_settings() 单例
│   ├── base_model.py    # ORM 基类：Base / TimestampMixin / BaseModel
│   ├── base_repository.py # 泛型仓储 BaseRepository[T]（类 mybatis BaseMapper）
│   ├── base_schema.py   # ResponseSchema / PageResult 响应包装
│   ├── exceptions.py    # BizException + 全局异常处理器
│   └── logger.py        # loguru 配置
├── infra/
│   └── database.py      # async engine / session 工厂 / get_db 依赖
└── middlewares/
    └── logging.py       # 请求日志中间件
```

## 架构约定

- **分层**：路由 → service → repository → model。DB 访问统一走 `BaseRepository[T]`，不在路由里直接写 SQL。
- **配置**：所有配置项加到 `core/config.py` 的 `Settings`，通过 `get_settings()` 获取（`@lru_cache` 单例）。不要散落读 `os.environ`。
- **数据库会话**：路由用 `Depends(get_db)` 注入 `AsyncSession`；`get_db` 已处理 commit / rollback，业务代码里不手动 commit。
- **ORM 模型**：继承 `BaseModel`，自动带 `id / created_at / updated_at`，时间戳由数据库维护。
- **响应格式**：统一 `{code, message, data}`，用 `ResponseSchema[T]` / 分页用 `PageResult[T]`。
- **异常**：业务错误抛 `BizException(code, message)`，由全局处理器捕获；错误码集中定义在 `exceptions.py`。
- **异步**：全链路 async，DB / IO 操作必须 `await`。
- **日志**：用 `from loguru import logger`，不用标准 `logging`。

## 编码规范

- 禁止 fallback：不静默降级、不空值兜底、不 try-catch 吞异常，异常直接抛出
- 逻辑上不可能为空就不写空值检查
- 新增依赖用 `uv add`，锁定版本，提交时带上 `uv.lock`
- 敏感配置（DB 密码、API Key）只放 `.env`（已 gitignore），代码里给非敏感默认值

## Git

- 不自动 commit / push，除非明确要求
- commit message 用简洁英文，遵循 Conventional Commits（见 `.claude/commands/commit.md`）
- 推送前先展示变更摘要
