import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from . import __version__
from .auth import DemoAuthority
from .config import Settings, load_settings
from .database import Database
from .errors import AppError, SchemaError
from .migrations import status
from .models import ConfigStatus, Envelope, Health
from .registry import ModuleRegistry

logger = logging.getLogger("medplatform.requests")
STATIC = Path(__file__).parent / "static"


def envelope(request: Request, data=None, *, code=None, message=None):
    return {"request_id": request.state.request_id, "status": "error" if code else "success",
            "data": None if code else data, "error": {"code": code, "message": message} if code else None}


def create_app(settings: Settings | None = None, authority: DemoAuthority | None = None) -> FastAPI:
    settings = settings or load_settings()
    authority = authority if authority is not None else DemoAuthority()
    db = Database(settings.database_path)
    app = FastAPI(title="Medication platform foundation", version=__version__,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings, app.state.db, app.state.authority = settings, db, authority
    app.state.registry = ModuleRegistry()

    def error_response(request, error):
        return JSONResponse(envelope(request, code=error.code, message=error.message), status_code=error.status)

    @app.middleware("http")
    async def request_boundary(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        try:
            if request.headers.get("host") not in settings.allowed_hosts:
                raise AppError(403, "HOST_REJECTED", "仅允许已配置的本地服务地址")
            if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
                principal = authority.resolve(request.cookies.get("session"))
                authority.require_write(principal, request.headers.get("X-CSRF-Token"),
                                        request.headers.get("origin"), settings.allowed_origins)
                key = request.headers.get("Idempotency-Key", "")
                if not 16 <= len(key) <= 128:
                    raise AppError(422, "VALIDATION_ERROR", "写操作需要有效幂等键")
            response = await call_next(request)
        except AppError as exc:
            response = error_response(request, exc)
        except Exception:
            # Never log exception text/traceback, body, query, cookies or URL.
            logger.error("request_failed request_id=%s", request.state.request_id)
            response = error_response(request, AppError(500, "INTERNAL_ERROR", "服务处理失败"))
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        logger.info("request_id=%s method=%s status=%s", request.state.request_id,
                    request.method, response.status_code)
        return response

    @app.exception_handler(AppError)
    async def application_error(request, exc):
        return error_response(request, exc)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        codes = {404: ("RESOURCE_NOT_FOUND", "接口或资源不存在"), 405: ("METHOD_NOT_ALLOWED", "不支持该请求方法")}
        code, message = codes.get(exc.status_code, ("HTTP_ERROR", "请求未能完成"))
        return error_response(request, AppError(exc.status_code, code, message))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error_response(request, AppError(422, "VALIDATION_ERROR", "请求结构不合法"))

    @app.exception_handler(sqlite3.Error)
    @app.exception_handler(SchemaError)
    async def database_error(request, exc):
        return error_response(request, AppError(503, "DEPENDENCY_NOT_READY", "必要存储依赖未就绪"))

    def no_query(request):
        if request.query_params:
            raise AppError(422, "VALIDATION_ERROR", "此接口不接受查询参数")

    def ready():
        try:
            return status(db)
        except (sqlite3.Error, SchemaError, OSError):
            raise AppError(503, "DEPENDENCY_NOT_READY", "数据库或schema未就绪，请运行显式初始化或迁移") from None

    router = APIRouter()

    @router.get("/api/v1/health", response_model=Envelope[Health], operation_id="foundation_health")
    def health(request: Request):
        no_query(request)
        ready()
        return envelope(request, {"process_status": "running", "readiness": "ready",
            "dependencies": [{"name": "database", "status": "available", "reason": None},
                             {"name": "schema", "status": "available", "reason": None}],
            "app_version": __version__, "checked_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds")})

    @router.get("/api/v1/config/status", response_model=Envelope[ConfigStatus], operation_id="foundation_config_status")
    def configuration(request: Request):
        principal = authority.resolve(request.cookies.get("session"))
        authority.require_admin(principal)
        no_query(request)
        schema = ready()
        return envelope(request, {"auth_mode": settings.AUTH_MODE, "llm_mode": settings.LLM_MODE,
            "requested_pipeline": settings.DIALOGUE_PIPELINE,
            "model_configured": bool(settings.LLM_BASE_URL and settings.LLM_MODEL and settings.LLM_API_KEY.get_secret_value()),
            "model_connectivity": "unverified",
            "capabilities": [{"code": "foundation_storage", "available": True, "reason": None},
                *[{"code": code, "available": False, "reason": "尚未到对应业务阶段或真实依赖未接入"}
                  for code in ("demo_login", "dialogue", "in_app_notification", "system_notification", "external_auth", "cas")]],
            "version_refs": [{"kind": "application", "version": __version__},
                             {"kind": "schema", "version": f"{schema:04d}"},
                             {"kind": "contract", "version": "flow-v0.1"}]})

    app.state.registry.include_router(app, router)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
