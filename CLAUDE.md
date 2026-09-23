# WakuHub

FastAPI 异步后端，RAG / Agent 方向。数据层用 SQLAlchemy async + MySQL（aiomysql），配套 Redis、MinIO、Milvus、Neo4j，接入 DeepSeek / DashScope 模型。前端在 `app/`（React + Vite + TS），本文件以后端为主。

## 技术栈

- **Python 3.13**，依赖用 **uv** 管理（`pyproject.toml` + `uv.lock`）
- **FastAPI** + **uvicorn/fastapi dev**
- **SQLAlchemy 2.0 async** + **aiomysql**（MySQL），迁移用 **alembic**（async 模板）
- **pydantic-settings** 读环境变量，**loguru** 日志
- **Redis**（验证码 / 权限缓存）、**MinIO**（文档对象存储）

## 常用命令

```bash
uv sync                      # 安装依赖
uv add <包名>                 # 添加依赖（会更新 uv.lock，需一并提交）
fastapi dev src/main.py      # 本地开发启动（默认 8000；前端默认认 8080）
uv run main.py               # 运行入口
uv run pytest tests/ -q      # 跑测试（连真实 MySQL 的 waku_test 库）

cd docker && docker compose -f docker-compose.yaml up -d   # 起依赖中间件

alembic revision --autogenerate -m "<描述>"   # 生成迁移
alembic upgrade head                          # 执行迁移
```

健康检查：`GET /health` 返回 `{"status": "ok"}`。

## 目录结构

```
src/
├── main.py              # FastAPI 应用工厂 create_app + lifespan + CORS + 路由注册
├── core/                # 基础设施抽象
│   ├── config.py        # Settings（pydantic-settings）+ get_settings() 单例
│   ├── base_model.py    # ORM 基类：Base / TimestampMixin / BaseModel
│   ├── base_repository.py # 泛型仓储 BaseRepository[T]（类 mybatis BaseMapper，含 get_page）
│   ├── base_schema.py   # ResponseSchema / PageResult 响应包装
│   ├── depys.py         # PageParams 分页查询参数依赖（注意：文件名就是 depys）
│   ├── permissions.py   # PermCode 权限编码枚举
│   ├── exceptions.py    # BizException + 全局异常处理器
│   └── logger.py        # loguru 配置
├── infra/
│   ├── database.py      # async engine / session 工厂 / get_db 依赖
│   ├── redis.py         # Redis 客户端单例 / get_redis_client 依赖
│   └── minio_client.py  # MinIO 单例：upload_file / download_file / delete_object
├── middlewares/
│   └── logging.py       # 请求日志中间件
├── utils/
│   ├── jwt.py           # JWTHelper（create_access_token / decode_token）
│   └── password.py      # 密码哈希
└── modules/             # 业务模块，开发范式见 src/modules/CLAUDE.md
    ├── auth/  captcha/  user/  role/  permission/        # ✅ RBAC + 认证
    ├── provider/  model/  prompt/                        # ✅ 模型 / Prompt
    ├── knowledge/  tool/  agent/                         # ✅ 知识库 / 工具 / Agent
    └── (conversation/ analytics/ 待开发，源项目无后端代码)

app/                      # React 前端（Vite），services 层 mock/api 双实现
└── src/services/         # USE_MOCK 由 VITE_USE_MOCK 控制；API_BASE 默认 http://localhost:8080/api
tests/                    # pytest，范式见 src/modules/CLAUDE.md 测试节
├── conftest.py           # 连 waku_test 库，外层事务回滚隔离；client fixture 走 ASGI
└── modules/{module}/     # test_{module}_service.py + test_{module}_api.py
```

## 架构约定

- **分层**：路由 → service → repository → model。DB 访问统一走 `BaseRepository[T]`，不在路由里直接写 SQL。
- **新模块**：照 `src/modules/CLAUDE.md` 的标准清单（model/schema/repository/service/api 五件套）和 8 步开发流程做，不要发明新结构。
- **配置**：所有配置项加到 `core/config.py` 的 `Settings`，通过 `get_settings()` 获取（`@lru_cache` 单例）。不要散落读 `os.environ`。
- **数据库会话**：路由用 `Depends(get_db)` 注入 `AsyncSession`；`get_db` 已处理 commit / rollback，业务代码里不手动 commit。
- **ORM 模型**：继承 `BaseModel`，自动带 `id / created_at / updated_at`，时间戳由数据库维护。
- **响应格式**：统一 `{code, message, data}`，用 `ResponseSchema[T]` / 分页用 `PageResult[T]`；列表接口一律 `PageParams`（`core/depys.py`）+ `PageResult`。
- **异常**：业务错误抛 `BizException(code, message)`，由全局处理器捕获；错误码按模块分段（42xxx prompt、43xxx knowledge、44xxx tool、45xxx agent），集中在 `exceptions.py`。
- **鉴权**：`auth/deps.py` 的 `get_current_user` / `require_permission`；权限编码登记在 `core/permissions.py` 的 `PermCode`。
- **异步**：全链路 async，DB / IO 操作必须 `await`；同步 SDK（minio）封装在 `infra/` 里再给 service 用。
- **日志**：用 `from loguru import logger`，不用标准 `logging`。

## 编码规范

- 禁止 fallback：不静默降级、不空值兜底、不 try-catch 吞异常，异常直接抛出
- 逻辑上不可能为空就不写空值检查
- 新增依赖用 `uv add`，锁定版本，提交时带上 `uv.lock`
- 敏感配置（DB 密码、API Key）只放 `.env`（已 gitignore），代码里给非敏感默认值

## 注释规范

- 用中文注释，清晰写出功能，不写废话（不解释"这是什么"，要解释"做了什么/为什么"）
- 不常见的 API、非直观的写法要注释说明用途和原理
- service 层逐步注释：每一步业务操作（查询、校验、赋值、持久化）都写清楚在做什么

## Git

- 不自动 commit / push，除非明确要求
- commit message 用简洁英文，遵循 Conventional Commits（见 `.claude/commands/commit.md`）
- 推送前先展示变更摘要
