import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from .. import __version__
from ..core.config import Settings, load_settings
from ..core.database import Database
from ..core.errors import AppError, SchemaError
from ..core.migrations import status
from ..identity.auth import DemoAuthority
from ..identity.authority import PersistentAuthority
from .models import ConfigStatus, Envelope, Health
from .registry import ModuleRegistry

logger = logging.getLogger("medplatform.requests")
STATIC = Path(__file__).parent.parent / "static"


def envelope(request: Request, data=None, *, code=None, message=None):
    return {
        "request_id": request.state.request_id,
        "status": "error" if code else "success",
        "data": None if code else data,
        "error": {"code": code, "message": message} if code else None,
    }


def create_app(
    settings: Settings | None = None,
    authority: DemoAuthority | PersistentAuthority | None = None,
    *,
    clock=None,
) -> FastAPI:
    settings = settings or load_settings()
    db = Database(settings.database_path)
    from ..core.documents import now
    from ..dialogue import api as dialogue_routes
    from ..dialogue.service import DialogueService
    from ..identity.api import router as identity_router
    from ..identity.service import IdentityService
    from ..medication import (
        analytics as analytics_routes,
    )
    from ..medication import (
        execution as execution_routes,
    )
    from ..medication import (
        records as record_routes,
    )
    from ..support.catalog import api as catalog_routes
    from ..support.catalog.service import Catalog, catalog_registered
    from ..support.drafts import api as draft_routes
    from ..support.drafts.service import Drafts
    from ..support.feedback import api as feedback_routes
    from ..support.feedback.service import Feedback
    from ..support.peer import api as peer_routes
    from ..support.peer.service import Peer
    from ..support.points import api as points_routes
    from ..support.points.service import Points
    from ..support.rewards import api as rewards_routes
    from ..support.rewards.service import Rewards
    from ..support.services import api as service_routes
    from ..support.services.dispatch import MockServiceDispatch
    from ..support.services.service import Services
    from .routes import router as domain_router

    service = IdentityService(db, clock or now)
    records = record_routes.Records(db, service.auth, service.receipts, clock or now)
    analytics = analytics_routes.Analytics(
        db, service.auth, service.receipts, clock or now, records
    )
    execution = execution_routes.Execution(
        db, service.auth, service.receipts, clock or now, analytics=analytics
    )
    support = DialogueService(
        db, service.auth, service.receipts, clock or now, settings, analytics, execution
    )
    catalog = Catalog(db, service, clock or now)
    drafts = Drafts(db, service, clock or now)
    services = Services(db, drafts, execution, settings, clock or now)
    feedback = Feedback(db, services, clock or now)
    peer = Peer(db, services, clock or now)
    points = Points(db, service.auth, service.receipts, analytics, peer, clock or now)
    rewards = Rewards(db, points, services, settings, clock or now)
    services.rewards = rewards
    execution.reward_fulfillment = rewards.fulfillment
    services.peer = peer
    execution.service_dispatch = MockServiceDispatch(db, services, clock or now)
    support.formal_services = drafts.formal_services = services
    execution.support_state = support.state
    analytics.support_feedback = support.feedback_source
    analytics.service_feedback = feedback
    authority = authority if authority is not None else service.auth
    app = FastAPI(
        title="Medication platform foundation",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings, app.state.db, app.state.authority = settings, db, authority
    app.state.registry = ModuleRegistry()
    app.state.identity = service
    app.state.records, app.state.analytics, app.state.execution = (
        records,
        analytics,
        execution,
    )
    app.state.dialogue = support
    app.state.catalog = catalog
    app.state.drafts = drafts
    app.state.services = services
    app.state.feedback = feedback
    app.state.peer = peer
    app.state.points = points
    app.state.rewards = rewards

    def error_response(request, error):
        return JSONResponse(
            envelope(request, code=error.code, message=error.message),
            status_code=error.status,
        )

    @app.middleware("http")
    async def request_boundary(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        try:
            if request.headers.get("host") not in settings.allowed_hosts:
                raise AppError(403, "HOST_REJECTED", "仅允许已配置的本地服务地址")
            if request.url.path.startswith("/api/") and request.method not in {
                "GET",
                "HEAD",
                "OPTIONS",
            }:
                if request.url.path == "/api/v1/auth/demo-session":
                    if request.headers.get("origin") not in settings.allowed_origins:
                        raise AppError(403, "CSRF_REJECTED", "演示登录需要同源操作")
                elif (
                    request.url.path == service_routes.RECEIPT_PATH
                    and request.method == "POST"
                ):
                    request.state.integration_principal = (
                        services.authenticate_provider(
                            request.headers.get("Authorization")
                        )
                    )
                elif (
                    request.url.path == rewards_routes.RECEIPT_PATH
                    and request.method == "POST"
                ):
                    request.state.integration_principal = (
                        rewards.fulfillment.authenticate(
                            request.headers.get("Authorization")
                        )
                    )
                elif (
                    request.url.path == "/api/v1/auth/logout"
                    and authority is service.auth
                ):
                    principal = authority.resolve(
                        request.cookies.get("session"), logout_receipt=True
                    )
                    authority.require_write(
                        principal,
                        request.headers.get("X-CSRF-Token"),
                        request.headers.get("origin"),
                        settings.allowed_origins,
                        logout_receipt=True,
                    )
                else:
                    principal = authority.resolve(request.cookies.get("session"))
                    authority.require_write(
                        principal,
                        request.headers.get("X-CSRF-Token"),
                        request.headers.get("origin"),
                        settings.allowed_origins,
                    )
                key = request.headers.get("Idempotency-Key", "")
                if not 16 <= len(key) <= 128:
                    raise AppError(422, "VALIDATION_ERROR", "写操作需要有效幂等键")
                # Bounded transport parsing, including chunked multipart requests.
                raw = bytearray()
                async for chunk in request.stream():
                    raw.extend(chunk)
                    if len(raw) > 10485760 + 65536:
                        raise AppError(
                            413, "REQUEST_TOO_LARGE", "请求超过本地服务大小限制"
                        )
                request._body = bytes(raw)
            response = await call_next(request)
        except AppError as exc:
            response = error_response(request, exc)
            if exc.code == "OPERATION_IN_PROGRESS":
                response.headers["Retry-After"] = "1"
        except sqlite3.Error, SchemaError:
            response = error_response(
                request, AppError(503, "DEPENDENCY_NOT_READY", "必要存储依赖未就绪")
            )
        except Exception:  # noqa: BLE001
            # Never log exception text/traceback, body, query, cookies or URL.
            logger.error("request_failed request_id=%s", request.state.request_id)
            response = error_response(
                request, AppError(500, "INTERNAL_ERROR", "服务处理失败")
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        logger.info(
            "request_id=%s method=%s status=%s",
            request.state.request_id,
            request.method,
            response.status_code,
        )
        return response

    @app.exception_handler(AppError)
    async def application_error(request, exc):
        response = error_response(request, exc)
        if exc.code == "OPERATION_IN_PROGRESS":
            response.headers["Retry-After"] = "1"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        codes = {
            404: ("RESOURCE_NOT_FOUND", "接口或资源不存在"),
            405: ("METHOD_NOT_ALLOWED", "不支持该请求方法"),
        }
        code, message = codes.get(exc.status_code, ("HTTP_ERROR", "请求未能完成"))
        return error_response(request, AppError(exc.status_code, code, message))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error_response(
            request, AppError(422, "VALIDATION_ERROR", "请求结构不合法")
        )

    @app.exception_handler(sqlite3.Error)
    @app.exception_handler(SchemaError)
    async def database_error(request, exc):
        return error_response(
            request, AppError(503, "DEPENDENCY_NOT_READY", "必要存储依赖未就绪")
        )

    def no_query(request):
        if request.query_params:
            raise AppError(422, "VALIDATION_ERROR", "此接口不接受查询参数")

    def ready():
        try:
            return status(db)
        except sqlite3.Error, SchemaError, OSError:
            raise AppError(
                503,
                "DEPENDENCY_NOT_READY",
                "数据库或schema未就绪，请运行显式初始化或迁移",
            ) from None

    router = APIRouter()

    @router.get(
        "/api/v1/health",
        response_model=Envelope[Health],
        operation_id="foundation_health",
    )
    def health(request: Request):
        no_query(request)
        ready()
        return envelope(
            request,
            {
                "process_status": "running",
                "readiness": "ready",
                "dependencies": [
                    {"name": "database", "status": "available", "reason": None},
                    {"name": "schema", "status": "available", "reason": None},
                ],
                "app_version": __version__,
                "checked_at": datetime.now(UTC).isoformat(timespec="milliseconds"),
            },
        )

    @router.get(
        "/api/v1/config/status",
        response_model=Envelope[ConfigStatus],
        operation_id="foundation_config_status",
    )
    def configuration(request: Request):
        principal = authority.resolve(request.cookies.get("session"))
        authority.require_admin(principal)
        no_query(request)
        schema = ready()
        with db.connection(readonly=True) as conn:
            profile = support.profile(conn)
            directory_ready = catalog_registered(conn)
            rule_version = support.state.rule_reference(conn)
        dialogue_ready = profile["configuration_status"] == "ready"
        return envelope(
            request,
            {
                "auth_mode": settings.AUTH_MODE,
                "llm_mode": settings.LLM_MODE,
                "requested_pipeline": profile["requested_pipeline"],
                "model_configured": bool(
                    settings.LLM_BASE_URL
                    and settings.LLM_MODEL
                    and settings.LLM_API_KEY.get_secret_value()
                ),
                "model_connectivity": "unverified",
                "capabilities": [
                    {"code": "foundation_storage", "available": True, "reason": None},
                    *[
                        {
                            "code": code,
                            "available": False,
                            "reason": "尚未到对应业务阶段或真实依赖未接入",
                        }
                        for code in ("system_notification", "external_auth", "cas")
                    ],
                    {
                        "code": "dialogue",
                        "available": dialogue_ready,
                        "reason": f"本地 mock {profile['requested_pipeline']}"
                        if dialogue_ready
                        else "已请求的流水线尚未接入",
                    },
                    {
                        "code": "real_model",
                        "available": False,
                        "reason": "真实模型尚未接入",
                    },
                    {
                        "code": "explicit_runner",
                        "available": True,
                        "reason": "通过 worker 明确启动；网页启动不自动运行任务",
                    },
                    {
                        "code": "support_intensity_mapping",
                        "available": False,
                        "reason": "支持强度方法尚未接入",
                    },
                    {"code": "demo_login", "available": True, "reason": None},
                    {
                        "code": "in_app_notification",
                        "available": True,
                        "reason": "仅显式执行的本地模拟提交；不等于送达、展示或响应",
                    },
                    {"code": "s03_data_loop", "available": True, "reason": None},
                    {
                        "code": "support_catalog",
                        "available": directory_ready,
                        "reason": "本地虚构资源目录与候选"
                        if directory_ready
                        else "模拟资源目录尚未显式登记",
                    },
                ],
                "version_refs": [
                    {"kind": "application", "version": __version__},
                    {"kind": "schema", "version": f"{schema:04d}"},
                    {"kind": "contract", "version": "flow-v0.1"},
                    {"kind": "contract", "version": "B-v0.4"},
                    {"kind": "contract", "version": "C-v0.2"},
                    {"kind": "runner", "version": "s06-runner-v1"},
                    {"kind": "rule", "version": rule_version},
                    {
                        "kind": "model_config",
                        "version": profile["model_config_version"],
                    },
                ],
            },
        )

    app.state.registry.include_router(app, router)
    app.state.registry.include_router(app, identity_router(service, envelope))
    app.state.registry.include_router(
        app,
        domain_router(
            [
                (record_routes, records),
                (analytics_routes, analytics),
                (execution_routes, execution),
                (dialogue_routes, support),
                (catalog_routes, catalog),
                (draft_routes, drafts),
                (service_routes, services),
                (feedback_routes, feedback),
                (peer_routes, peer),
                (points_routes, points),
                (rewards_routes, rewards),
            ],
            envelope,
        ),
    )

    @app.get("/", include_in_schema=False)
    def index():
        if not (STATIC / "index.html").is_file():
            raise AppError(
                503, "FRONTEND_NOT_BUILT", "前端尚未构建，请先运行 pnpm build"
            )
        return FileResponse(STATIC / "index.html")

    # build output is gitignored, so the app must start before the first pnpm build
    app.mount("/static", StaticFiles(directory=STATIC, check_dir=False), name="static")
    return app
