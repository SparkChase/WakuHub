"""pytest 全局 fixtures。

测试连真实 MySQL 的 waku_test 库（不用 sqlite，避开 BigInteger 自增主键的兼容问题，
也更贴近生产环境）。每个测试跑在一个外层事务里，结束时整体回滚，测试之间互不污染。
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from src.core.config import get_settings
from src.core.base_model import Base
from src.infra.database import get_db
from src.main import create_app

# 导入所有 ORM 模型，保证 Base.metadata 里注册了对应的表
import src.modules.user.model  # noqa: F401

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
async def client(db_session):
    """HTTP 测试客户端：用 ASGI 直连应用，并把 get_db 依赖替换成测试事务会话。"""
    app = create_app()

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
