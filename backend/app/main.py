"""FastAPI 应用入口。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.error_handlers import register_error_handlers
from app.api.routes import chat, documents, evaluations, health
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.observability import configure_observability


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""
    configure_logging()
    configure_observability()
    logger = get_logger(__name__)

    app = FastAPI(title=settings.app_name)

    # CORS 中间件配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册全局错误处理器
    register_error_handlers(app)

    # 注册路由
    app.include_router(health.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(evaluations.router, prefix="/api")

    logger.info("app initialized: %s", settings.app_name)
    return app


app = create_app()