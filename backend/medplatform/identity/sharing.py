"""O owns consent scope and the explicit local demo recipient registrations."""

import json
from datetime import timedelta

from ..core.config import ROOT
from ..core.documents import encode, stamp, uid
from ..core.errors import AppError
from ..core.migrations import status

DEMO_RECIPIENTS = ROOT / "data" / "demo" / "o_support_recipients.json"
VALIDITY = timedelta(hours=24)
REGISTRATION_FIELDS = (
    "resource_id",
    "resource_version",
    "recipient_id",
    "recipient_type",
    "purpose_code",
)


def load_resource(conn, resource_id, resource_version):
    row = conn.execute(
        """SELECT resource_json FROM c_support_resource_versions
           WHERE resource_id=? AND resource_version=?""",
        (resource_id, resource_version),
    ).fetchone()
    return json.loads(row[0]) if row is not None else None


def recipient_identity(resource):
    return (
        resource["provider"]["provider_id"],
        resource["provider"]["provider_type"],
        resource["service_kind"],
    )


def seed_support_recipients(db):
    """Explicit fixture installation. A C catalog seed alone never registers an O recipient."""
    status(db)
    fixtures = json.loads(DEMO_RECIPIENTS.read_bytes())
    with db.transaction() as conn:
        return install_demo_recipients(conn, fixtures)


def install_demo_recipients(conn, fixtures):
    added = 0
    for fixture in fixtures:
        entry = tuple(fixture[key] for key in REGISTRATION_FIELDS)
        resource = load_resource(conn, *entry[:2])
        if (
            resource is None
            or resource["is_simulated"] is not True
            or recipient_identity(resource) != entry[2:]
        ):
            raise AppError(
                409,
                "SHARING_CONFIRMATION_REQUIRED",
                "请先登记与 O 演示主体匹配的目录版本",
            )
        old = conn.execute(
            """SELECT recipient_id,recipient_type,purpose_code FROM o_demo_support_recipients
               WHERE resource_id=? AND resource_version=?""",
            entry[:2],
        ).fetchone()
        if old is not None:
            if tuple(old) != entry[2:]:
                raise AppError(
                    409, "SHARING_CONFIRMATION_REQUIRED", "O 演示接收主体登记不一致"
                )
            continue
        conn.execute("INSERT INTO o_demo_support_recipients VALUES (?,?,?,?,?)", entry)
        added += 1
    return added


class SharingAuthority:
    def __init__(self, auth):
        self.auth = auth

    @staticmethod
    def registered(conn, resource):
        if (
            resource["is_simulated"] is not True
            or resource["provider"]["is_simulated"] is not True
        ):
            return False
        row = conn.execute(
            """SELECT recipient_id,recipient_type,purpose_code FROM o_demo_support_recipients
               WHERE resource_id=? AND resource_version=?""",
            (resource["resource_id"], resource["resource_version"]),
        ).fetchone()
        return row is not None and tuple(row) == recipient_identity(resource)

    def validate_consent(self, conn, principal, patient, resource, categories):
        self.auth.require_patient(principal, patient, "", conn, self_only=True)
        required = set(resource["required_shared_categories"])
        chosen = set(categories)
        if (
            not required
            <= chosen
            <= required | set(resource["optional_shared_categories"])
        ):
            raise AppError(
                409, "SHARING_CONFIRMATION_REQUIRED", "请核对必要及允许共享的资料类别"
            )
        if not self.registered(conn, resource):
            raise AppError(
                409,
                "SHARING_CONFIRMATION_REQUIRED",
                "该资源版本没有有效的 O 接收主体登记",
            )

    def issue(self, conn, principal, patient, resource, categories, now):
        at, end = stamp(now), stamp(now + VALIDITY)
        recipient, kind, purpose = recipient_identity(resource)
        scope = {
            "sharing_scope_ref_id": uid(),
            "scope_version": 1,
            "patient_id": patient,
            "recipient_id": recipient,
            "recipient_type": kind,
            "purpose_code": purpose,
            "data_categories": categories,
            "status": "active",
            "confirmed_at": at,
            "valid_until": end,
            "is_simulated": True,
        }
        raw = encode(scope)
        conn.execute(
            "INSERT INTO o_sharing_scopes VALUES (?,?,?,?,?,?)",
            (
                scope["sharing_scope_ref_id"],
                patient,
                resource["resource_id"],
                resource["resource_version"],
                1,
                raw,
            ),
        )
        conn.execute(
            "INSERT INTO o_sharing_scope_history VALUES (?,?,?,?,?,NULL)",
            (scope["sharing_scope_ref_id"], 1, raw, principal.account_id, at),
        )
        return scope

    def scope(self, conn, identifier, patient, at=None):
        row = conn.execute(
            """SELECT * FROM o_sharing_scopes WHERE sharing_scope_ref_id=? AND patient_id=?""",
            (identifier, patient),
        ).fetchone()
        if row is None:
            raise AppError(
                503, "SHARING_AUTHORITY_UNAVAILABLE", "暂时无法核验 O 共享范围"
            )
        scope = json.loads(row["document_json"])
        if at is not None and scope["status"] == "active":
            resource = load_resource(conn, row["resource_id"], row["resource_version"])
            if (
                resource is None
                or not self.registered(conn, resource)
                or (
                    scope["recipient_id"],
                    scope["recipient_type"],
                    scope["purpose_code"],
                )
                != recipient_identity(resource)
            ):
                scope["status"] = "revoked"
            elif not scope["confirmed_at"] <= at < scope["valid_until"]:
                scope["status"] = "expired"
        return scope

    def revoke(self, conn, principal, identifier, patient, at, reason):
        self.auth.require_patient(principal, patient, "", conn, self_only=True)
        scope = self.scope(conn, identifier, patient)
        if scope["status"] == "revoked":
            return
        scope.update(status="revoked", scope_version=scope["scope_version"] + 1)
        raw = encode(scope)
        conn.execute(
            "UPDATE o_sharing_scopes SET document_json=?,scope_version=? WHERE sharing_scope_ref_id=?",
            (raw, scope["scope_version"], identifier),
        )
        conn.execute(
            "INSERT INTO o_sharing_scope_history VALUES (?,?,?,?,?,?)",
            (identifier, scope["scope_version"], raw, principal.account_id, at, reason),
        )

    def membership_authorized(self, conn, service):
        scope = self.scope(conn, service["sharing_scope_ref_id"], service["patient_id"])
        resource = load_resource(
            conn, service["resource_id"], service["resource_version"]
        )
        return (
            scope["status"] == "active"
            and resource is not None
            and self.registered(conn, resource)
            and (scope["recipient_id"], scope["recipient_type"], scope["purpose_code"])
            == recipient_identity(resource)
        )
