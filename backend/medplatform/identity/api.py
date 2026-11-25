from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from ..core.documents import fingerprint_bytes
from ..core.errors import AppError
from ..core.migrations import status
from ..core.strict_json import loads
from ..medication import inputs as medication_inputs
from ..profile import inputs as profile_inputs
from ..web.inputs import (
    Empty,
    Revoke,
    query_fields,
    query_limit,
    query_window,
)
from ..web.routes import dispatch
from . import inputs

# Only registered contract routes. No generic CRUD/command endpoint.
ROUTES = [
    ("O01", "POST", "/auth/demo-session", "login", inputs.Login),
    ("O02", "GET", "/auth/me", "me", None),
    ("O03", "POST", "/auth/logout", "logout", Empty),
    ("O04", "GET", "/patients", "patients", None),
    ("O05", "PUT", "/auth/current-patient", "current_patient", inputs.CurrentPatient),
    ("O06", "GET", "/patients/{p}", "patient", None),
    ("O07", "PATCH", "/patients/{p}", "patient_patch", inputs.PatientPatch),
    ("O08", "POST", "/patients/{p}/family-binding-codes", "binding_code", Empty),
    ("O09", "POST", "/family-bindings/redeem", "redeem", inputs.Redeem),
    ("O10", "GET", "/patients/{p}/family-bindings", "bindings", None),
    ("O11", "POST", "/family-bindings/{id}/revoke", "revoke_binding", Revoke),
    ("O12", "PUT", "/family-bindings/{id}/grant", "grant_put", inputs.GrantPut),
    ("O13", "GET", "/patients/{p}/grants", "grants", None),
    ("O14", "POST", "/grants/{id}/revoke", "revoke_grant", Revoke),
    ("O15", "GET", "/questionnaires/initial", "definition", None),
    (
        "O16",
        "POST",
        "/patients/{p}/questionnaire-responses",
        "response_create",
        profile_inputs.ResponseCreate,
    ),
    (
        "O17",
        "PUT",
        "/questionnaire-responses/{id}/answers",
        "answers",
        profile_inputs.AnswersPut,
    ),
    ("O18", "GET", "/questionnaire-responses/{id}", "response", None),
    (
        "O19",
        "POST",
        "/questionnaire-responses/{id}/submit",
        "submit_response",
        profile_inputs.Submit,
    ),
    ("O20", "GET", "/patients/{p}/profiles/current", "current_profile", None),
    (
        "O32",
        "GET",
        "/patients/{p}/questionnaire-responses/latest-submitted",
        "latest_submission",
        None,
    ),
    ("O21", "GET", "/profiles/{id}", "profile", None),
    (
        "O22",
        "POST",
        "/patients/{p}/profiles",
        "profile_create",
        profile_inputs.ProfileCreate,
    ),
    ("O23", "GET", "/patients/{p}/medications", "medications", None),
    (
        "O24",
        "POST",
        "/patients/{p}/medications",
        "medication_create",
        medication_inputs.MedicationCreate,
    ),
    (
        "O25",
        "PATCH",
        "/medications/{id}",
        "medication_patch",
        medication_inputs.MedicationPatch,
    ),
    ("O26", "GET", "/patients/{p}/plans", "plans", None),
    ("O27", "GET", "/plans/{id}/versions/{version}", "plan", None),
    (
        "O28",
        "POST",
        "/patients/{p}/plan-confirmations",
        "plan_confirm",
        medication_inputs.PlanConfirm,
    ),
    ("O29", "GET", "/patients/{p}/dose-slots", "slots", None),
    ("O30", "GET", "/patients/{p}/reminder-preferences", "reminder", None),
    (
        "O31",
        "PUT",
        "/patients/{p}/reminder-preferences",
        "reminder_put",
        medication_inputs.ReminderPut,
    ),
    (
        "A01",
        "POST",
        "/patients/{p}/files",
        "file_upload",
        medication_inputs.FileSemantic,
    ),
    ("A02", "GET", "/patients/{p}/files", "files", None),
    ("A03", "GET", "/files/{id}", "file", None),
    ("A04", "GET", "/files/{id}/content", "file_content", None),
    (
        "A42",
        "GET",
        "/files/{id}/medication-recognition",
        "file_medication_recognition",
        None,
    ),
    (
        "A05",
        "POST",
        "/patients/{p}/drafts",
        "draft_create",
        medication_inputs.DraftCreate,
    ),
    ("A06", "GET", "/drafts/{id}", "draft", None),
    ("A07", "PUT", "/drafts/{id}", "draft_put", medication_inputs.DraftPut),
    (
        "A08",
        "POST",
        "/drafts/{id}/submit",
        "draft_submit",
        medication_inputs.DraftSubmit,
    ),
    ("A09", "GET", "/patients/{p}/drafts", "drafts", None),
]
LISTS = {
    "patients",
    "bindings",
    "grants",
    "medications",
    "plans",
    "slots",
    "files",
    "drafts",
}


def query_input(request, action):
    allowed = set()
    if action in LISTS:
        allowed.update(("cursor", "limit"))
    allowed.update(
        {
            "plans": {"plan_id"},
            "slots": {"window_start", "window_end"},
            "drafts": {"status"},
        }.get(action, set())
    )
    try:
        q = query_fields(request.query_params.multi_items(), allowed)
    except ValueError:
        raise AppError(422, "VALIDATION_ERROR", "查询字段不合法或重复")
    try:
        if "limit" in q:
            query_limit(q["limit"])
        if "cursor" in q and not q["cursor"]:
            raise ValueError()
        if action == "slots":
            query_window(q)
        if (
            action == "drafts"
            and "status" in q
            and q["status"]
            not in ("editing", "pending_confirmation", "confirmed", "returned")
        ):
            raise ValueError()
    except KeyError, ValueError, TypeError:
        raise AppError(
            422, "VALIDATION_ERROR", "查询值、时区或窗口范围不合法"
        ) from None
    return q


def router(service, envelope):
    result = APIRouter()
    for card, method, path, action, schema in ROUTES:

        def endpoint(action=action, schema=schema, method=method):
            async def handle(request: Request):
                await run_in_threadpool(status, service.db)
                principal = (
                    None
                    if action == "login"
                    else service.auth.resolve(
                        request.cookies.get("session"),
                        logout_receipt=action == "logout",
                    )
                )
                params = dict(request.path_params)
                try:
                    for value in params.values():
                        if not 1 <= len(value) <= 128:
                            raise ValueError()
                    if "version" in params and (
                        not params["version"].isdigit() or int(params["version"]) < 1
                    ):
                        raise ValueError()
                    q = query_input(request, action)
                    b = {}
                    content = None
                    if schema is not None:
                        if action == "file_upload":
                            if (
                                request.headers.get("content-type", "").split(";")[0]
                                != "multipart/form-data"
                            ):
                                raise AppError(
                                    415,
                                    "UNSUPPORTED_MEDIA_TYPE",
                                    "上传需要multipart单文件表单",
                                )
                            async with request.form(
                                max_files=1, max_fields=1, max_part_size=10485760
                            ) as form:
                                if (
                                    set(form) != {"file", "source_event_id"}
                                    or len(form.multi_items()) != 2
                                    or not isinstance(form["file"], UploadFile)
                                ):
                                    raise ValueError()
                                file = form["file"]
                                content = await file.read(10485761)
                                if len(content) > 10485760:
                                    raise AppError(
                                        413, "FILE_TOO_LARGE", "文件不能超过10MiB"
                                    )
                                if not content:
                                    raise ValueError()
                                media = file.content_type
                                signatures = {
                                    "application/pdf": content.startswith(b"%PDF-"),
                                    "image/png": content.startswith(
                                        b"\x89PNG\r\n\x1a\n"
                                    ),
                                    "image/jpeg": content.startswith(b"\xff\xd8\xff"),
                                }
                                if not signatures.get(media, False):
                                    raise AppError(
                                        415,
                                        "UNSUPPORTED_MEDIA_TYPE",
                                        "仅支持内容格式一致的PDF、PNG、JPEG",
                                    )
                                b = {
                                    "source_event_id": form["source_event_id"],
                                    "original_name": file.filename,
                                    "media_type": media,
                                    "size_bytes": len(content),
                                    "sha256": fingerprint_bytes(content),
                                }
                        else:
                            if (
                                request.headers.get("content-type", "").split(";")[0]
                                != "application/json"
                            ):
                                raise AppError(
                                    415, "UNSUPPORTED_MEDIA_TYPE", "此操作需要JSON请求"
                                )
                            b = loads(await request.body())
                        model = schema.model_validate(b)
                        b = model.model_dump(
                            exclude_unset=action
                            in ("patient_patch", "medication_patch", "submit_response")
                        )
                    elif await request.body():
                        raise ValueError()
                except ValidationError, ValueError, TypeError, KeyError:
                    raise AppError(
                        422, "VALIDATION_ERROR", "请求结构或字段不合法，请核对当前表单"
                    ) from None
                response, http = await dispatch(
                    request,
                    service,
                    envelope,
                    action,
                    principal,
                    params,
                    q,
                    b,
                    request.headers.get("Idempotency-Key"),
                    content,
                    method == "GET",
                )
                if response.token:
                    remaining = max(
                        0,
                        int(
                            (
                                datetime.fromisoformat(response.sensitive_until)
                                - service.clock()
                            ).total_seconds()
                        ),
                    )
                    http.set_cookie(
                        "session",
                        response.token,
                        max_age=remaining,
                        expires=datetime.fromisoformat(response.sensitive_until),
                        httponly=True,
                        samesite="lax",
                        secure=request.url.scheme == "https",
                        path="/",
                    )
                if action == "logout":
                    http.delete_cookie(
                        "session", path="/", httponly=True, samesite="lax"
                    )
                return http

            return handle

        result.add_api_route(
            "/api/v1" + path, endpoint(), methods=[method], operation_id=card, name=card
        )
    return result
