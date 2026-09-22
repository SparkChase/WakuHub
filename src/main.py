from fastapi import FastAPI
from loguru import logger
from src.core.config import get_settings
from src.middlewares.logging import LoggingMiddleware
from src.core.exceptions import register_exception_handlers
from src.core.logger import setup_logger
from src.infra.database import engine
from src.modules.user.api import router as user_router
from src.modules.captcha.api import router as captcha_router

# 使用上下文管理器感知项目的生命周期
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logger()  # 配置日志组建
    settings = get_settings()
    logger.info(f"{settings.APP_NAME} 启动.. | 使用环境： {settings.APP_ENV}")
    # 应用启动时执行
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

    # 注册异常处理器
    register_exception_handlers(app)

    # 注册路由
    app.include_router(user_router,prefix="/api/v1")
    app.include_router(captcha_router,prefix="/api/v1")

    return app


app = create_app()


# 健康检查路由：能访问通，就代表启动成功
@app.get("/health")
async def health():
    # prometheus 规范约束，返回的 status 必须是 ok
    return {"status": "ok"}
