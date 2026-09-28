from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from app.ai.book_router import router as ai_book_router
from app.ai.router import router as ai_router
from app.auth.admin_sync import sync_admin
from app.auth.router import create_limiters
from app.auth.router import router as auth_router
from app.books.admin_router import router as admin_books_router
from app.books.router import router as books_router
from app.config import Settings, get_settings
from app.db import create_db_engine, create_session_factory
from app.errors import register_error_handlers
from app.invites.router import router as invites_router
from app.readers.router import router as readers_router

BACKEND_DIR = Path(__file__).resolve().parents[1]


def run_migrations(database_url: str) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")


def create_app(settings: Settings | None = None) -> FastAPI:
    """应用工厂。启动方式：uvicorn --factory app.main:create_app"""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        # 只有 API 进程执行迁移（Worker 不执行），避免两个进程同时改表结构
        run_migrations(settings.database_url)
        with app.state.session_factory() as db:
            sync_admin(db, settings)
        yield
        app.state.engine.dispose()

    app = FastAPI(
        title="萤火 Firefly Tales",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.engine = create_db_engine(settings.database_url)
    app.state.session_factory = create_session_factory(app.state.engine)
    app.state.limiters = create_limiters()
    register_error_handlers(app)

    # 上传的请求体在进入接口前就会被完整接收，所以先按 Content-Length 挡掉明显超限的上传；
    # 接口里复制文件时还会按实际大小再检查一次
    @app.middleware("http")
    async def reject_oversized_upload(request: Request, call_next):
        length = request.headers.get("content-length")
        upload_limit = settings.max_upload_bytes + 1024 * 1024  # 预留 multipart 包装的开销
        if (
            request.method == "POST"
            and request.url.path == "/api/admin/books"
            and length is not None
            and length.isdigit()
            and int(length) > upload_limit
        ):
            return JSONResponse(
                {"detail": f"文件超过 {settings.max_upload_mb}MB 上限"}, status_code=413
            )
        return await call_next(request)

    api = APIRouter(prefix="/api")
    api.include_router(auth_router)
    api.include_router(invites_router)
    api.include_router(readers_router)
    api.include_router(books_router)
    api.include_router(admin_books_router)
    api.include_router(ai_router)
    api.include_router(ai_book_router)

    @api.get("/health", tags=["系统"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api)
    return app
