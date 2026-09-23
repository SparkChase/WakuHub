from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from src.core.config import get_settings
from src.middlewares.logging import LoggingMiddleware
from src.core.exceptions import register_exception_handlers
from src.core.logger import setup_logger
from src.infra.database import engine
from src.infra.minio_client import ensure_bucket_exists
from src.modules.user.api import router as user_router
from src.modules.captcha.api import router as captcha_router
from src.modules.auth.api import router as auth_router
from src.modules.permission.api import router as permission_router
from src.modules.role.api import router as role_router
from src.modules.provider.api import router as provider_router
from src.modules.model.api import router as model_router
from src.modules.prompt.api import router as prompt_router
from src.modules.knowledge.api import router as knowledge_router

# 使用上下文管理器感知项目的生命周期
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logger()  # 配置日志组建
    settings = get_settings()
    logger.info(f"{settings.APP_NAME} 启动.. | 使用环境： {settings.APP_ENV}")
    # 启动时确保 MinIO 业务桶存在；MinIO 不可用不应阻断应用启动，仅告警
    try:
        ensure_bucket_exists()
    except Exception as e:
        logger.error(f"MinIO 桶初始化失败，文件上传功能将不可用：{e}")
    yield
    # 应用关闭时执行
    # 关闭数据库连接池
    await engine.dispose()
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

    return app


app = create_app()


# 健康检查路由：能访问通，就代表启动成功
@app.get("/health")
async def health():
    # prometheus 规范约束，返回的 status 必须是 ok
    return {"status": "ok"}
