from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from src.core.config import get_settings
from src.middlewares.logging import LoggingMiddleware
from src.core.exceptions import register_exception_handlers
from src.core.logger import setup_logger
from src.infra.database import engine, check_db_health
from src.infra.redis import check_redis_health
from src.infra.minio_client import ensure_bucket_exists
from src.infra.milvus_client import check_milvus_health, close_milvus_client
from src.infra.neo4j_client import check_neo4j_health, close_neo4j_driver
from src.modules.user.api import router as user_router
from src.modules.captcha.api import router as captcha_router
from src.modules.auth.api import router as auth_router
from src.modules.permission.api import router as permission_router
from src.modules.role.api import router as role_router
from src.modules.provider.api import router as provider_router
from src.modules.model.api import router as model_router
from src.modules.prompt.api import router as prompt_router
from src.modules.knowledge.api import router as knowledge_router
from src.modules.tool.api import router as tool_router
from src.modules.agent.api import router as agent_router

# 使用上下文管理器感知项目的生命周期
import inspect
from contextlib import asynccontextmanager


async def _probe(name: str, check) -> tuple[str, bool]:
    """执行单个组件的探测函数（兼容同步 / 异步），把结果收敛成 (名称, 是否可用)。
    这里刻意 try 住异常：健康检查的职责就是逐个上报状态，失败要 error 打印出来而不是中断，
    从而让下面能汇总出完整的一张健康表；这不是业务层的静默吞错。
    """
    try:
        result = check()
        if inspect.isawaitable(result):
            await result
        return (name, True)
    except Exception as e:
        logger.error(f"{name} 健康检查失败：{e}")
        return (name, False)


async def check_infra_health() -> None:
    """启动时逐个探测各基础组件连通性并打印健康汇总；单个组件不可用不阻断启动，仅告警。"""
    # MinIO 复用 ensure_bucket_exists：既验证连通性又顺带建业务桶
    checks = [
        ("MySQL", check_db_health),
        ("Redis", check_redis_health),
        ("MinIO", ensure_bucket_exists),
        ("Milvus", check_milvus_health),
        ("Neo4j", check_neo4j_health),
    ]
    results = [await _probe(name, check) for name, check in checks]

    healthy = sum(1 for _, ok in results if ok)
    lines = [f"  {'✓' if ok else '✗'} {name}" for name, ok in results]
    logger.info(f"基础组件健康检查（{healthy}/{len(results)} 可用）:\n" + "\n".join(lines))


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logger()  # 配置日志组建
    settings = get_settings()
    logger.info(f"{settings.APP_NAME} 启动.. | 使用环境： {settings.APP_ENV}")
    # 启动时逐个探测 MySQL / Redis / MinIO / Milvus / Neo4j 并打印健康汇总
    await check_infra_health()
    yield
    # 应用关闭时释放各组件连接
    await engine.dispose()      # MySQL 连接池
    close_milvus_client()       # Milvus 连接（同步 SDK）
    await close_neo4j_driver()  # Neo4j 异步 Driver
    logger.info(f"{settings.APP_NAME} 关闭..")


def create_app() -> FastAPI:
    settings = get_settings()

    # 创建应用
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        debug=settings.APP_DEBUG,
        lifespan=lifespan,
    )

    # 注册中间件
    app.add_middleware(LoggingMiddleware)
    # 跨域：允许前端开发服务器（Vite 5173，端口被占时 Vite 顺延 5174 / 备用 3000）携带凭证访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册异常处理器
    register_exception_handlers(app)

    # 注册路由：统一 /api 前缀，与前端默认 baseURL 对齐
    app.include_router(user_router, prefix="/api")
    app.include_router(captcha_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(permission_router, prefix="/api")
    app.include_router(role_router, prefix="/api")
    app.include_router(provider_router, prefix="/api")
    app.include_router(model_router, prefix="/api")
    app.include_router(prompt_router, prefix="/api")
    app.include_router(knowledge_router, prefix="/api")
    app.include_router(tool_router, prefix="/api")
    app.include_router(agent_router, prefix="/api")

    return app


app = create_app()


# 健康检查路由：能访问通，就代表启动成功
@app.get("/health")
async def health():
    # prometheus 规范约束，返回的 status 必须是 ok
    return {"status": "ok"}
