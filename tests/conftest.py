"""pytest 全局 fixtures。

测试连真实 MySQL 的 waku_test 库（不用 sqlite，避开 BigInteger 自增主键的兼容问题，
也更贴近生产环境）。每个测试跑在一个外层事务里，结束时整体回滚，测试之间互不污染。
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from redis.asyncio import Redis

from src.core.config import get_settings
from src.core.base_model import Base
from src.infra.database import get_db
from src.infra.redis import get_redis_client

# 导入所有 ORM 模型，保证 Base.metadata 注册了全部表（与 alembic/env.py 对齐）。
# 只导入 user.model 时，跨模块外键（如 role_permissions→permissions）无法解析，
# 单独跑某个模块的测试会因建表阶段外键找不到目标表而报错。
import src.modules.user.model        # noqa: F401
import src.modules.permission.model  # noqa: F401
import src.modules.role.model        # noqa: F401
import src.modules.provider.model    # noqa: F401
import src.modules.model.model       # noqa: F401
import src.modules.prompt.model      # noqa: F401
import src.modules.knowledge.model   # noqa: F401
import src.modules.tool.model        # noqa: F401
import src.modules.agent.model       # noqa: F401
import src.modules.medical.model     # noqa: F401

_settings = get_settings()

# 测试库固定为 waku_test，只改库名，其余连接参数复用 .env / 默认值
TEST_DATABASE_URL = (
    f"mysql+aiomysql://{_settings.DB_USER}:{_settings.DB_PASSWORD}"
    f"@{_settings.DB_HOST}:{_settings.DB_PORT}/waku_test"
)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine():
    """会话级引擎：整个测试进程共用一个连接池，跑完销毁。"""
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _create_schema(engine):
    """整轮测试开始前按 ORM 元数据建表，结束后清表。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(engine):
    """函数级会话：绑定到外层事务，测试结束整体回滚。

    join_transaction_mode="create_savepoint" 让业务代码里的 session.commit()
    只提交到 savepoint，外层事务 rollback 时一并撤销，实现测试隔离。
    """
    connection = await engine.connect()
    trans = await connection.begin()
    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    yield session
    await session.close()
    await trans.rollback()
    await connection.close()


@pytest_asyncio.fixture(loop_scope="session")
async def redis_client():
    """函数级 redis：用独立的 db 15 隔离测试数据，每个测试前后 flushdb。"""
    test_db = 15
    url = (
        f"redis://{':' + _settings.REDIS_PASSWORD + '@' if _settings.REDIS_PASSWORD else ''}"
        f"{_settings.REDIS_HOST}:{_settings.REDIS_PORT}/{test_db}"
    )
    client = Redis.from_url(url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture(loop_scope="session")
async def client(db_session, redis_client):
    """HTTP 测试客户端：用 ASGI 直连应用，把 get_db / get_redis 依赖替换成测试实例。"""
    # 延迟导入：create_app 会拉起 supervisor/worker/api 整条链路，
    # 只有真正用到 client 的测试才需要它，避免拖累不依赖 HTTP 的单元/集成测试。
    from src.main import create_app

    app = create_app()

    async def _override_get_db():
        yield db_session

    async def _override_get_redis():
        return redis_client

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis_client] = _override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
