"""C-owned anonymous memberships, scoped review, and public post projections."""

import json
import re
import secrets
import sqlite3
import unicodedata

from ...core.documents import changed, encode, fingerprint, get, meta, stamp, uid
from ...core.errors import AppError
from ...core.idempotency import Result
from ..catalog.service import CURRENT
from ..common import CONTRACT, missing
from ..points.sources import points_notice

POSTS = """SELECT p.*,m.alias,h.revision,h.status,h.recorded_at AS status_at
           FROM c_peer_posts p JOIN c_peer_memberships m USING(membership_id)
           JOIN c_peer_post_history h ON h.post_id=p.post_id AND h.revision=(
               SELECT MAX(v.revision) FROM c_peer_post_history v WHERE v.post_id=p.post_id
           )"""
MEMBERSHIPS = """SELECT h.document_json FROM c_peer_memberships m JOIN c_peer_membership_history h
                ON h.membership_id=m.membership_id AND h.revision=m.revision"""
LINK_OR_CONTACT = re.compile(
    r"(?i)(?:[a-z][a-z0-9+.-]*://|www\.|\b(?:mailto|tel|data|javascript)\s*:|"
    r"\b[\w.+-]+@[\w.-]+|\b[a-z0-9][a-z0-9.-]+\.[a-z]{2,12}\b|"
    r"\b(?:\d[ .-]?){7,}|[\w-]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|"
    r"(?:微信|QQ|手机号|身份证号|联系方式)\s*[:：]\s*\S|[<>])"
)


def join_required():
    return AppError(
        409,
        "PEER_JOIN_CONFIRMATION_REQUIRED",
        "请核对本人的小组、草稿修订及有效共享确认",
    )


def membership_required():
    return AppError(
        403, "PEER_MEMBERSHIP_REQUIRED", "需要此组有效的本人资格或受控审核权限"
    )


def moderator_required():
    return AppError(403, "PEER_MODERATOR_REQUIRED", "缺少该组审核权限")


class Peer:
    def __init__(self, db, services, clock):
        self.db, self.auth, self.receipts = db, services.auth, services.receipts
        self.services, self.clock = services, clock

    def group(self, conn, identifier):
        row = conn.execute(
            """SELECT document_json FROM c_peer_groups WHERE group_id=?""",
            (identifier,),
        ).fetchone()
        if row is None:
            raise missing()
        group = json.loads(row[0])
        resource = conn.execute(
            CURRENT + " WHERE r.resource_id=?", (group["resource_id"],)
        ).fetchone()
        if not resource:
            return dict(group, availability="unavailable")
        doc = json.loads(resource["resource_json"])
        if (
            doc["service_kind"] != "peer_support"
            or doc["peer_group_id"] != identifier
            or not doc["is_simulated"]
        ):
            return dict(group, availability="unavailable")
        return dict(group, availability=doc["availability"])

    def membership(self, conn, column, identifier):
        # Fixed internal selection columns only.
        where = {"membership_id": "m.membership_id", "service_id": "m.service_id"}[
            column
        ]
        row = conn.execute(MEMBERSHIPS + f" WHERE {where}=?", (identifier,)).fetchone()
        if row is None:
            raise missing()
        return json.loads(row[0])

    def own_patient(self, conn, principal):
        account = self.auth.account(principal, conn)
        patient = account["self_patient_id"]
        if not patient or patient != account["current_patient_id"]:
            raise membership_required()
        if not get(conn, "Patient", patient)["meta"]["is_simulated"]:
            raise membership_required()
        return patient

    def directory_patient(self, conn, principal):
        patient = self.auth.account(principal, conn)["current_patient_id"]
        if not patient:
            raise membership_required()
        self.auth.require_patient(principal, patient, "peer:read", conn)
        if not get(conn, "Patient", patient)["meta"]["is_simulated"]:
            raise membership_required()
        return patient

    def is_moderator(self, conn, principal, group):
        return bool(
            self.auth.account(principal, conn)["is_admin"]
            and conn.execute(
                "SELECT 1 FROM c_peer_moderators WHERE group_id=? AND account_id=?",
                (group, principal.account_id),
            ).fetchone()
        )

    def active(self, conn, principal, group, permission):
        patient = self.own_patient(conn, principal)
        self.auth.require_patient(principal, patient, permission, conn, self_only=True)
        row = conn.execute(
            "SELECT membership_id,service_id,revision FROM c_peer_memberships WHERE patient_id=? AND group_id=? AND status='active'",
            (patient, group),
        ).fetchone()
        if not row or not self.access_current(conn, group, row["service_id"]):
            raise membership_required()
        return row["membership_id"], row["revision"]

    def access_current(self, conn, group, service_id):
        if self.group(conn, group)["availability"] != "available":
            return False
        service = self.services.service(conn, service_id)
        return self.services.drafts.sharing.membership_authorized(
            conn, service, stamp(self.clock())
        )

    def authorize(self, conn, action, principal, path, query):
        identifier = path.get("id")
        if action in {"groups", "group"}:
            return self.directory_patient(conn, principal)
        if action == "my_memberships":
            patient = self.own_patient(conn, principal)
            self.auth.require_patient(
                principal, patient, "peer:read", conn, self_only=True
            )
            return patient
        if action == "join":
            patient = self.own_patient(conn, principal)
            self.auth.require_patient(
                principal, patient, "peer:participate", conn, self_only=True
            )
            self.group(conn, identifier)
            return patient
        if action == "leave":
            member = self.membership(conn, "membership_id", identifier)
            if not self.auth.is_self(principal, member["patient_id"], conn):
                raise missing()
            return member
        if action == "moderate":
            # A foreign or nonexistent post ID has exactly the same denial.
            row = conn.execute(
                "SELECT group_id FROM c_peer_posts WHERE post_id=?", (identifier,)
            ).fetchone()
            if not row or not self.is_moderator(conn, principal, row["group_id"]):
                raise moderator_required()
            return row["group_id"]
        if query.get("include_pending"):
            if not self.is_moderator(conn, principal, identifier):
                raise membership_required()
            return None
        return self.active(
            conn,
            principal,
            identifier,
            "peer:participate" if action == "post" else "peer:read",
        )

    def handle(self, action, principal, path, query, body, key):
        identifier = path.get("id")

        def guard(conn):
            return self.authorize(conn, action, principal, path, query)

        if action in {"groups", "group", "posts", "my_memberships"}:
            try:
                with self.db.connection(readonly=True) as conn:
                    conn.execute("BEGIN")
                    authorized = guard(conn)
                    if action == "groups":
                        data = self.groups(conn, principal, authorized, query)
                    elif action == "group":
                        data = self.group(conn, identifier)
                    elif action == "my_memberships":
                        data = self.my_memberships(conn, principal, authorized, query)
                    else:
                        data = self.posts(
                            conn, principal, identifier, authorized, query
                        )
                    conn.commit()
                    if guard(conn) != authorized:
                        raise membership_required()
                    return Result(data)
            except sqlite3.DatabaseError:
                if action in {"groups", "group"}:
                    raise AppError(
                        503, "PEER_GROUPS_UNAVAILABLE", "小组目录暂不可用"
                    ) from None
                raise

        def operate(conn):
            authorized = guard(conn)
            if action == "join":
                doc = self.join(conn, principal, authorized, identifier, body)
            elif action == "leave":
                doc = self.leave(conn, principal, authorized, body)
            elif action == "post":
                doc = self.submit_post(conn, principal, identifier, authorized[0], body)
            else:
                doc = self.moderate(conn, principal, identifier, body)
            is_member = action in {"join", "leave"}
            return Result(
                doc,
                201 if action in {"join", "post"} else 200,
                resource_type="Membership" if is_member else "PeerPost",
                resource_id=doc["membership_id" if is_member else "post_id"],
            )

        def replay(conn, result):
            if action == "join":
                patient = guard(conn)
                self.validate_join(conn, principal, patient, identifier, body)
                doc = self.membership(conn, "membership_id", result.resource_id)
                if doc["status"] == "left":
                    raise membership_required()
                result.data = doc
            elif action == "leave":
                result.data = guard(conn)
            else:
                current = self.post(conn, result.resource_id)
                if action == "post" and (
                    current["membership_id"] != guard(conn)[0]
                    or current["status"] == "hidden"
                ):
                    raise missing()
                result.data = self.public_post(current)
            return result

        return self.receipts.run(
            ["demo", "account", principal.account_id, "C-peer", action, identifier],
            key,
            body,
            guard,
            operate,
            replay,
        )

    def groups(self, conn, principal, patient, query):
        if not conn.execute("SELECT 1 FROM c_peer_groups LIMIT 1").fetchone():
            raise AppError(503, "PEER_GROUPS_UNAVAILABLE", "模拟小组目录尚未登记")
        wanted, limit = query.get("group_id"), query.get("limit", 20)
        context = [principal.account_id, "C16", patient, wanted]
        after = self.after(query, context, [""])[0]
        rows = conn.execute(
            """
            SELECT group_id FROM c_peer_groups WHERE group_id>? AND (? IS NULL OR group_id=?)
            ORDER BY group_id LIMIT ?
        """,
            (after, wanted, wanted, limit + 1),
        ).fetchall()
        ids = [r[0] for r in rows[:limit]]
        return {
            "items": [self.group(conn, identifier) for identifier in ids],
            "next_cursor": self.auth.cursor(context, [ids[-1]])
            if len(rows) > limit
            else None,
        }

    def my_memberships(self, conn, principal, patient, query):
        context = [principal.account_id, "C41", patient]
        after = self.after(query, context, [""])[0]
        limit = query.get("limit", 20)
        rows = conn.execute(
            """
            SELECT membership_id,group_id,service_id,alias,status,revision FROM c_peer_memberships
            WHERE patient_id=? AND membership_id>? ORDER BY membership_id LIMIT ?
        """,
            (patient, after, limit + 1),
        ).fetchall()
        items = [
            dict(
                row,
                can_participate=(
                    row["status"] == "active"
                    and self.access_current(conn, row["group_id"], row["service_id"])
                ),
            )
            for row in rows[:limit]
        ]
        cursor = (
            self.auth.cursor(context, [items[-1]["membership_id"]])
            if len(rows) > limit
            else None
        )
        return {"items": items, "next_cursor": cursor}

    def after(self, query, context, defaults):
        if not query.get("cursor"):
            return defaults
        result = self.auth.read_cursor(query["cursor"], context)
        if len(result) != len(defaults) or not all(
            isinstance(value, str) for value in result
        ):
            raise AppError(422, "INVALID_CURSOR", "分页位置无效，请重新读取")
        return result

    def validate_join(self, conn, principal, patient, group, body):
        try:
            draft, resource, _ = self.services.prepared(
                conn, principal, patient, body, stamp(self.clock())
            )
        except AppError as exc:
            if exc.code in {
                "SERVICE_CONFIRMATION_REQUIRED",
                "SHARING_CONFIRMATION_REQUIRED",
            }:
                raise join_required() from None
            raise
        if (
            resource["service_kind"] != "peer_support"
            or resource["peer_group_id"] != group
            or draft["peer_group_id"] != group
        ):
            raise join_required()
        return resource

    def join(self, conn, principal, patient, group, body):
        resource = self.validate_join(conn, principal, patient, group, body)
        service = self.services.submit(
            conn, principal, patient, body, resource_id=resource["resource_id"]
        )
        member = self.membership(conn, "service_id", service["service_id"])
        if member["status"] == "left":
            raise join_required()
        return member

    def check_submission(self, conn, principal, patient, resource):
        self.auth.require_patient(
            principal, patient, "peer:participate", conn, self_only=True
        )
        group = self.group(conn, resource["peer_group_id"])
        if (
            group["resource_id"] != resource["resource_id"]
            or group["availability"] != "available"
        ):
            raise join_required()
        if conn.execute(
            """SELECT 1 FROM c_peer_memberships WHERE patient_id=? AND group_id=?
                          AND status IN ('pending','active')""",
            (patient, group["group_id"]),
        ).fetchone():
            raise join_required()

    def attach(self, conn, principal, service, group, at):
        doc = {
            "membership_id": uid(),
            "patient_id": service["patient_id"],
            "group_id": group,
            "service_id": service["service_id"],
            "alias": "同伴-" + secrets.token_hex(6),
            "status": "pending",
            "joined_at": at,
            "activated_at": None,
            "left_at": None,
            "leave_reason": None,
            "meta": meta(at, CONTRACT),
        }
        conn.execute(
            "INSERT INTO c_peer_memberships VALUES (?,?,?,?,?,'pending',1)",
            tuple(
                doc[field]
                for field in (
                    "membership_id",
                    "patient_id",
                    "group_id",
                    "service_id",
                    "alias",
                )
            ),
        )
        self.record_member(conn, doc, principal.account_id, at)

    def record_member(self, conn, doc, actor, at):
        revision = doc["meta"]["revision"]
        if revision > 1:
            conn.execute(
                "UPDATE c_peer_memberships SET status=?,revision=? WHERE membership_id=?",
                (doc["status"], revision, doc["membership_id"]),
            )
        conn.execute(
            "INSERT INTO c_peer_membership_history VALUES (?,?,?,?,?,?)",
            (doc["membership_id"], revision, doc["status"], actor, at, encode(doc)),
        )

    def accept(self, conn, service, actor, occurred, at):
        doc = self.membership(conn, "service_id", service["service_id"])
        if doc["status"] != "pending":
            raise join_required()
        self.record_member(
            conn,
            dict(changed(doc, at), status="active", activated_at=occurred),
            actor,
            at,
        )

    def leave(self, conn, principal, doc, body):
        if (
            doc["status"] not in {"pending", "active"}
            or doc["meta"]["revision"] != body["expected_revision"]
        ):
            raise AppError(
                409, "MEMBERSHIP_REVISION_CONFLICT", "成员资格已变化，请核对原记录"
            )
        at = stamp(self.clock())
        result = dict(
            changed(doc, at), status="left", left_at=at, leave_reason=body["reason"]
        )
        self.record_member(conn, result, principal.account_id, at)
        service = self.services.service(conn, doc["service_id"])
        if service["status"] in {"submitted", "in_progress"}:
            self.services.cancel(
                conn,
                principal,
                service,
                {
                    "expected_revision": service["meta"]["revision"],
                    "reason": body["reason"] or "本人退出模拟同辈小组",
                },
            )
        return result

    def posts(self, conn, principal, group, member, query):
        self.group(conn, group)
        cursor_context = [
            principal.account_id,
            "C20",
            group,
            list(member) if member else "moderation",
        ]
        after = self.after(query, cursor_context, ["", ""])
        limit = query.get("limit", 20)
        rows = conn.execute(
            POSTS
            + """
            WHERE p.group_id=? AND (p.created_at,p.post_id)>(?,?)
              AND (h.status='visible' OR (h.status='pending' AND (? OR p.membership_id=?)))
            ORDER BY p.created_at,p.post_id LIMIT ?
        """,
            (group, *after, member is None, member[0] if member else None, limit + 1),
        ).fetchall()
        items = [self.public_post(row) for row in rows[:limit]]
        cursor = (
            self.auth.cursor(
                cursor_context, [items[-1]["created_at"], items[-1]["post_id"]]
            )
            if len(rows) > limit
            else None
        )
        return {"items": items, "next_cursor": cursor}

    def post(self, conn, identifier):
        row = conn.execute(POSTS + " WHERE p.post_id=?", (identifier,)).fetchone()
        if row is None:
            raise missing()
        return row

    @staticmethod
    def public_post(row):
        return {
            "post_id": row["post_id"],
            "group_id": row["group_id"],
            "author_alias": row["alias"],
            "content": row["content"],
            "moderation_status": row["status"],
            "created_at": row["created_at"],
            "moderated_at": None if row["status"] == "pending" else row["status_at"],
            "revision": row["revision"],
            "is_simulated": True,
        }

    def validate_text(self, conn, content):
        normalized = unicodedata.normalize("NFKC", content)
        invalid = (
            not 1 <= len(content) <= 1000
            or any(
                unicodedata.category(char) in {"Cc", "Cf", "Cs"}
                and char not in "\t\n\r"
                for char in normalized
            )
            or LINK_OR_CONTACT.search(normalized)
        )
        if not invalid:
            identities = {
                value
                for row in conn.execute(
                    "SELECT account_id,self_patient_id,display_name FROM o_accounts"
                )
                for value in row
                if value
            }
            identities.update(
                row[0]
                for row in conn.execute("""
                SELECT json_extract(document_json,'$.display_name') FROM s02_documents
                WHERE resource_type='Patient'
            """)
                if row[0]
            )
            text = normalized.casefold()
            invalid = any(
                unicodedata.normalize("NFKC", value).casefold() in text
                for value in identities
            )
        if invalid:
            raise AppError(
                422, "INVALID_PEER_POST", "请提交不含身份、联系方式、附件或外链的短文字"
            )

    def submit_post(self, conn, principal, group, membership, body):
        request_hash = fingerprint(body)
        old = conn.execute(
            """SELECT post_id,request_fingerprint FROM c_peer_posts
                              WHERE membership_id=? AND client_post_id=?""",
            (membership, body["client_post_id"]),
        ).fetchone()
        if old:
            if old["request_fingerprint"] != request_hash:
                raise AppError(409, "IDEMPOTENCY_CONFLICT", "同一提交号对应不同文字")
            post = self.post(conn, old["post_id"])
            if post["status"] == "hidden":
                raise missing()
            return self.public_post(post)
        self.validate_text(conn, body["content"])
        identifier, at = uid(), stamp(self.clock())
        conn.execute(
            "INSERT INTO c_peer_posts VALUES (?,?,?,?,?,?,?)",
            (
                identifier,
                group,
                membership,
                body["client_post_id"],
                request_hash,
                body["content"],
                at,
            ),
        )
        conn.execute(
            "INSERT INTO c_peer_post_history VALUES (?,1,'pending',?,NULL,?)",
            (identifier, principal.account_id, at),
        )
        return self.public_post(self.post(conn, identifier))

    def moderate(self, conn, principal, identifier, body):
        row = self.post(conn, identifier)
        if (
            row["revision"] != body["expected_revision"]
            or row["status"] == body["decision"]
        ):
            raise AppError(409, "REVISION_CONFLICT", "审核修订已变化，请重新读取")
        if body["decision"] == "visible":
            self.validate_text(conn, row["content"])
        revision, at = row["revision"] + 1, stamp(self.clock())
        conn.execute(
            "INSERT INTO c_peer_post_history VALUES (?,?,?,?,?,?)",
            (
                identifier,
                revision,
                body["decision"],
                principal.account_id,
                body["reason"],
                at,
            ),
        )
        owner = conn.execute(
            "SELECT patient_id FROM c_peer_memberships WHERE membership_id=?",
            (row["membership_id"],),
        ).fetchone()
        points_notice(conn, owner["patient_id"], "PeerPost", identifier, revision, at)
        return self.public_post(self.post(conn, identifier))
