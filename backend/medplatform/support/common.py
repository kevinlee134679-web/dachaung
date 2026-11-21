import secrets
from contextlib import contextmanager

from ..core.errors import AppError

CONTRACT = "C-v0.2"


def missing():
    return AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问")


def page_after(auth, query, context, default):
    return (
        auth.read_cursor(query["cursor"], context) if query.get("cursor") else default
    )


def next_cursor(rows, limit, auth, context, key):
    return auth.cursor(context, key(rows[limit - 1])) if len(rows) > limit else None


@contextmanager
def read_guarded(conn, guard, verify=None):
    conn.execute("BEGIN")
    authorized = guard(conn)
    yield authorized
    conn.commit()
    current = guard(conn)
    if verify is not None:
        verify(authorized, current)


def authenticate_provider(
    header, secret, subject, unavailable_code, unavailable_message, auth_message
):
    if not subject or len(secret) < 32:
        raise AppError(503, unavailable_code, unavailable_message)
    scheme, _, supplied = (header or "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(
        supplied.encode(), secret.encode()
    ):
        raise AppError(401, "AUTH_REQUIRED", auth_message)
    return subject
