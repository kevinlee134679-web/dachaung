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


def create_app(settings: Settings | None = None, authority: DemoAuthority | None = None, *, clock=None) -> FastAPI:
    settings = settings or load_settings()
    db = Database(settings.database_path)
    from .s02_service import S02Service
    from .documents import now
    from .s02_api import router as s02_router
    from . import s03_records, s03_analytics, s03_execution
    from .s03_api import router as s03_router
    from . import s04_api, s05_api, s05_draft_api, s05_service_api, s05_feedback_api, s05_peer_api
    from .s04_service import S04Service
    from .s05_catalog import S05Catalog, catalog_registered
    from .s05_drafts import S05Drafts
    from .s05_dispatch import MockServiceDispatch
    from .s05_services import S05Services
    from .s05_feedback import S05Feedback
    from .s05_peer import S05Peer
    service = S02Service(db,clock or now)
    records = s03_records.S03Records(db,service.auth,service.receipts,clock or now)
    analytics = s03_analytics.S03Analytics(db,service.auth,service.receipts,clock or now,records)
    execution = s03_execution.S03Execution(db,service.auth,service.receipts,clock or now,analytics=analytics)
    support = S04Service(db, service.auth, service.receipts, clock or now, settings, analytics, execution)
    catalog = S05Catalog(db, service, clock or now)
    drafts = S05Drafts(db, service, clock or now)
    services = S05Services(db, drafts, execution, settings, clock or now)
    feedback = S05Feedback(db, services, clock or now)
    peer = S05Peer(db, services, clock or now)
    services.peer = peer
    execution.service_dispatch = MockServiceDispatch(db, services, clock or now)
    support.formal_services = drafts.formal_services = services
    execution.support_state = support.state
    analytics.support_feedback = support.feedback_source
    analytics.service_feedback = feedback
    authority = authority if authority is not None else service.auth
    app = FastAPI(title="Medication platform foundation", version=__version__,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings, app.state.db, app.state.authority = settings, db, authority
    app.state.registry = ModuleRegistry()
    app.state.s02 = service
    app.state.s03_records, app.state.s03_analytics, app.state.s03_execution = records, analytics, execution
    app.state.s04 = support
    app.state.s05_catalog = catalog
    app.state.s05_drafts = drafts
    app.state.s05_services = services
    app.state.s05_feedback = feedback
    app.state.s05_peer = peer

    def error_response(request, error):
        return JSONResponse(envelope(request, code=error.code, message=error.message), status_code=error.status)

    @app.middleware("http")
    async def request_boundary(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        try:
            if request.headers.get("host") not in settings.allowed_hosts:
                raise AppError(403, "HOST_REJECTED", "仅允许已配置的本地服务地址")
            if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
                if request.url.path == '/api/v1/auth/demo-session':
                    if request.headers.get('origin') not in settings.allowed_origins:
                        raise AppError(403,'CSRF_REJECTED','演示登录需要同源操作')
                elif request.url.path == s05_service_api.RECEIPT_PATH and request.method == "POST":
                    request.state.integration_principal = services.authenticate_provider(request.headers.get("Authorization"))
                elif request.url.path == '/api/v1/auth/logout' and authority is service.auth:
                    principal=authority.resolve(request.cookies.get('session'),logout_receipt=True)
                    authority.require_write(principal,request.headers.get('X-CSRF-Token'),request.headers.get('origin'),settings.allowed_origins,logout_receipt=True)
                else:
                    principal = authority.resolve(request.cookies.get("session"))
                    authority.require_write(principal, request.headers.get("X-CSRF-Token"),
                                            request.headers.get("origin"), settings.allowed_origins)
                key = request.headers.get("Idempotency-Key", "")
                if not 16 <= len(key) <= 128:
                    raise AppError(422, "VALIDATION_ERROR", "写操作需要有效幂等键")
                # Bounded transport parsing, including chunked multipart requests.
                raw=bytearray()
                async for chunk in request.stream():
                    raw.extend(chunk)
                    if len(raw)>10485760+65536:
                        raise AppError(413,'REQUEST_TOO_LARGE','请求超过本地服务大小限制')
                request._body=bytes(raw)
            response = await call_next(request)
        except AppError as exc:
            response = error_response(request, exc)
            if exc.code=='OPERATION_IN_PROGRESS':
                response.headers['Retry-After']='1'
        except (sqlite3.Error, SchemaError):
            response=error_response(request,AppError(503,'DEPENDENCY_NOT_READY','必要存储依赖未就绪'))
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
        response=error_response(request, exc)
        if exc.code=='OPERATION_IN_PROGRESS':
            response.headers['Retry-After']='1'
        return response

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
        with db.connection(readonly=True) as conn:
            profile = support.profile(conn)
            directory_ready = catalog_registered(conn)
        dialogue_ready = profile["configuration_status"] == "ready"
        return envelope(request, {"auth_mode": settings.AUTH_MODE, "llm_mode": settings.LLM_MODE,
            "requested_pipeline": profile["requested_pipeline"],
            "model_configured": bool(settings.LLM_BASE_URL and settings.LLM_MODEL and settings.LLM_API_KEY.get_secret_value()),
            "model_connectivity": "unverified",
            "capabilities": [{"code": "foundation_storage", "available": True, "reason": None},
                *[{"code": code, "available": False, "reason": "尚未到对应业务阶段或真实依赖未接入"}
                  for code in ("system_notification", "external_auth", "cas")],
                {"code":"dialogue","available":dialogue_ready,
                 "reason":"本地 mock single_pass" if dialogue_ready else "已请求的流水线尚未接入"},
                {"code":"real_model","available":False,"reason":"真实模型尚未接入"},
                {"code":"support_intensity_mapping","available":False,"reason":"支持强度方法尚未接入"},
                {"code":"demo_login","available":True,"reason":None},
                {"code":"in_app_notification","available":True,"reason":"仅显式执行的本地模拟提交；不等于送达、展示或响应"},
                {"code":"s03_data_loop","available":True,"reason":None},
                {"code":"support_catalog","available":directory_ready,
                 "reason":"本地虚构资源目录与候选" if directory_ready else "模拟资源目录尚未显式登记"}],
            "version_refs": [{"kind": "application", "version": __version__},
                             {"kind": "schema", "version": f"{schema:04d}"},
                             {"kind": "contract", "version": "flow-v0.1"},
                             {"kind": "contract", "version": "B-v0.4"},
                             {"kind": "contract", "version": "C-v0.2"},
                             {"kind": "model_config", "version": profile["model_config_version"]}]})

    app.state.registry.include_router(app, router)
    app.state.registry.include_router(app, s02_router(service,envelope))
    app.state.registry.include_router(app, s03_router([
        (s03_records,records),(s03_analytics,analytics),(s03_execution,execution),(s04_api,support),
        (s05_api,catalog),
        (s05_draft_api,drafts),
        (s05_service_api,services),
        (s05_feedback_api,feedback),
        (s05_peer_api,peer),
    ],envelope))

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
