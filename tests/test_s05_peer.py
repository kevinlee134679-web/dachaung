import json
import sqlite3
import unittest
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urlencode

import test_s02 as existing
import test_s05_services as formal
from medplatform.s05_peer_fixtures import seed_peer_groups

PA, PB = existing.PA, existing.PB
GROUP = "group-peer-routine-demo"
OTHER_GROUP = "group-peer-start-demo"
RESOURCE = {"resource_id": "resource-peer-routine-demo", "resource_version": "resource-demo-v1", "peer_group_id": GROUP}
PRIVATE = "/peer-memberships/me"
POST_FIELDS = {"post_id", "group_id", "author_alias", "content", "moderation_status",
               "created_at", "moderated_at", "revision", "is_simulated"}


class PeerTests(unittest.TestCase):
    def setUp(self):
        self.f = formal.FormalServiceTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.s, self.d = self.f.s, self.f.d
        self.peer = self.s.app.state.s05_peer
        self.assertEqual(seed_peer_groups(self.s.db), dict(groups_added=2, moderators_added=1,
                                                          resources_added=2, recipients_added=2))

    @staticmethod
    def group(identifier=GROUP):
        return "/peer-groups/" + identifier

    def prepare(self, *, patient=PA, client=None, reused=False):
        draft = self.d.call("POST", f"/patients/{patient}/service-drafts",
                            dict(RESOURCE, request_text="本人的虚构入组说明"), client, 201)
        self.assertIsNone(draft["source_suggestion_id"])
        consent = self.d.call("POST", f"/patients/{patient}/service-confirmations",
                              self.d.confirm_body(draft), client, 200 if reused else 201)
        return draft, consent

    def join(self, body, *, key=None, client=None, group=GROUP, expected=201):
        return self.d.call("POST", self.group(group) + "/memberships", body, client, expected, key)

    def activate(self, member, client=None, *, complete=False):
        service = self.d.call("GET", "/services/" + member["service_id"], client=client)
        self.f.run_task(service)
        accepted = self.f.transition(service, "in_progress")
        return self.f.transition(accepted, "completed") if complete else accepted

    def joined(self, *, patient=PA, client=None, complete=False):
        member = self.join(self.f.body(*self.prepare(patient=patient, client=client)), client=client)
        return member, self.activate(member, client, complete=complete)

    def mine(self, *, client=None, expected=200, query=""):
        return self.d.call("GET", PRIVATE + query, client=client, expected=expected)

    def posts(self, *, client=None, expected=200, query="", group=GROUP):
        return self.d.call("GET", self.group(group) + "/posts" + query, client=client, expected=expected)

    def post(self, body=None, *, client=None, key=None, expected=201):
        return self.d.call("POST", self.group() + "/posts",
                           body or dict(client_post_id=existing.key(), content="虚构分享：我把每天的安排写成便签。"),
                           client, expected, key)

    def review(self, doc, decision="visible", *, client=None, key=None, expected=200):
        return self.d.call("POST", f"/peer-posts/{doc['post_id']}/moderation",
                           dict(expected_revision=doc["revision"], decision=decision, reason="本机模拟文字审核"),
                           client or self.f.admin, expected, key)

    def leave(self, doc, revision=2, *, key=None, client=None, expected=200):
        return self.d.call("POST", f"/memberships/{doc['membership_id']}/leave",
                           {"expected_revision": revision}, client, expected, key)

    def test_directory_selection_and_role_safe_cross_session_recovery(self):
        self.assertEqual(seed_peer_groups(self.s.db), dict.fromkeys((
            "groups_added", "moderators_added", "resources_added", "recipients_added"), 0))
        catalog = self.d.call("GET", "/peer-groups?limit=1")
        self.assertEqual(catalog["items"][0]["group_id"], GROUP)
        other = self.d.call("GET", "/peer-groups?" + urlencode(dict(cursor=catalog["next_cursor"], limit=1)))
        self.assertEqual(other["items"][0]["availability"], "unavailable")
        self.assertEqual(self.d.call("GET", self.group(OTHER_GROUP)), other["items"][0])
        self.assertEqual(self.mine(), dict(items=[], next_cursor=None))
        self.d.call("POST", f"/patients/{PA}/service-drafts",
                    dict(RESOURCE, request_text="未启用建议来源", source_suggestion_id="suggestion-offline"),
                    expected=422)
        original, _ = self.joined(complete=True)
        new_session = self.s.login("demo-patient-a")
        current = self.mine(client=new_session)["items"][0]
        self.assertEqual(set(current), {"group_id", "membership_id", "service_id", "alias", "status", "revision", "can_participate"})
        self.assertEqual((current["membership_id"], current["status"], current["revision"], current["can_participate"]),
                         (original["membership_id"], "active", 2, True))
        self.assertEqual(self.mine(client=self.s.b)["items"], [])
        self.mine(client=self.s.b, query="?patient_id=" + PA, expected=422)
        self.mine(client=self.f.admin, expected=403)
        binding, grant = self.s.bind(["peer:read", "peer:participate", "services:prepare", "support:read"])
        self.d.call("PUT", "/auth/current-patient", {"patient_id": PA}, self.s.f)
        self.assertEqual(self.d.call("GET", self.group(), client=self.s.f)["group_id"], GROUP)
        self.mine(client=self.s.f, expected=403)
        self.posts(client=self.s.f, expected=403)
        self.leave(original, client=self.s.f, expected=404)
        self.d.call("POST", f"/patients/{PA}/service-drafts", dict(RESOURCE, request_text="家属越权"), self.s.f, 403)
        self.d.revise_grant(binding, grant["meta"]["revision"], ["support:read"])
        self.d.call("GET", "/peer-groups", client=self.s.f, expected=403)

    def test_pending_invalid_and_cancel_before_acceptance(self):
        draft, consent = self.prepare()
        body = self.f.body(draft, consent)
        self.join(body, client=self.s.b, expected=404)
        self.assertEqual(self.join(body, group=OTHER_GROUP, expected=409)["code"], "PEER_JOIN_CONFIRMATION_REQUIRED")
        self.join(dict(body, draft_revision=9), expected=409)
        key = existing.key()
        member = self.join(body, key=key)
        self.assertEqual(member["status"], "pending")
        self.assertEqual(self.join(body, key=key), member)
        self.assertEqual(self.join(body), member)
        self.posts(expected=403)
        self.post(expected=403)
        self.assertEqual(self.leave(member, revision=2, expected=409)["code"], "MEMBERSHIP_REVISION_CONFLICT")
        second = self.prepare(reused=True)
        self.assertEqual(self.join(self.f.body(*second), expected=409)["code"], "PEER_JOIN_CONFIRMATION_REQUIRED")
        leave_key = existing.key()
        left = self.leave(member, revision=1, key=leave_key)
        self.assertEqual(self.leave(member, revision=1, key=leave_key), left)
        self.assertEqual(left["status"], "left")
        self.assertFalse(self.mine()["items"][0]["can_participate"])
        self.join(body, key=key, expected=403)
        service = self.d.call("GET", "/services/" + member["service_id"])
        self.assertEqual(service["status"], "cancelled")
        self.f.run_task(service, expected=409)
        self.assertEqual(self.join(self.f.body(*second))["status"], "pending")

    def test_atomic_concurrent_direct_referral_and_peer_join(self):
        draft, consent = self.prepare()
        body = self.f.body(draft, consent)
        session = self.d.call("POST", "/sessions", {"patient_id": PA}, expected=201)
        b_body = dict(patient_id=PA, session_id=session["session_id"], resource_id=draft["resource_id"],
                      service_draft_revision=body["draft_revision"],
                      **{k: v for k, v in body.items() if k != "draft_revision"})
        saved = self.peer.attach

        def failure(*args):
            saved(*args)
            raise sqlite3.OperationalError("injected")

        key = existing.key()
        with patch.object(self.peer, "attach", failure):
            self.join(body, key=key, expected=503)
        source = self.d.read(draft)
        self.assertEqual(source["status"], "preparing")
        self.assertEqual(self.mine()["items"], [])
        self.assertEqual(self.f.counts(), (0, 0, 0, 0, 0, 0))
        first, second = self.d.concurrent(
            (self.s.a, self.group() + "/memberships", body, key),
            (self.s.login("demo-patient-a"), "/referrals", b_body, existing.key()),
        )
        self.assertEqual([r.status_code for r in (first, second)], [201, 201], [first.text, second.text])
        member, referral = [r.json()["data"] for r in (first, second)]
        self.assertEqual(member["service_id"], referral["service_id"])
        service = self.f.create(body)
        self.assertEqual(service["service_id"], member["service_id"])
        self.assertEqual(self.f.counts(), (1, 1, 1, 0, 0, 0))
        self.activate(member)
        self.assertEqual(self.d.call("GET", "/referrals/" + referral["referral_id"])["service_status"], "in_progress")

    def test_posts_moderation_scopes_and_anonymous_projection(self):
        first, _ = self.joined()
        self.joined(patient=PB, client=self.s.b)
        for text in ("   ", "a" * 1001, "联系 demo-patient-a-self", "演示患者甲", "139 1234 5678",
                     "https://example.com", "test@example.com", "<img src=x>", first["membership_id"]):
            response = self.post(dict(client_post_id=existing.key(), content=text), expected=422)
            self.assertEqual(response["code"], "INVALID_PEER_POST", text)
        body = dict(client_post_id=existing.key(), content="匿名分享：用便签整理安排。")
        post_key = existing.key()
        draft = self.post(body, key=post_key)
        self.assertEqual(set(draft), POST_FIELDS)
        self.assertEqual(draft["author_alias"], first["alias"])
        self.assertEqual(self.posts()["items"], [draft])
        self.assertEqual(self.posts(client=self.s.b)["items"], [])
        self.posts(client=self.s.b, query="?include_pending=true", expected=403)
        self.assertEqual(self.posts(client=self.f.admin, query="?include_pending=true")["items"], [draft])
        self.posts(client=self.f.admin, group=OTHER_GROUP, query="?include_pending=true", expected=403)
        self.assertEqual(self.review(draft, client=self.s.a, expected=403),
                         self.review(dict(draft, post_id="guessed"), client=self.s.a, expected=403))
        visible = self.review(draft)
        self.assertEqual((visible["revision"], visible["moderation_status"]), (2, "visible"))
        projection = self.posts(client=self.s.b)["items"]
        self.assertEqual(projection, [visible])
        self.assertTrue(all(token not in json.dumps(projection, ensure_ascii=False)
                            for token in (PA, first["membership_id"], first["service_id"], "demo-patient-a")))
        hidden = self.review(visible, "hidden")
        self.assertEqual(self.posts(client=self.s.b)["items"], [])
        self.assertEqual(self.posts()["items"], [])
        self.post(body, key=post_key, expected=404)
        self.post(body, expected=404)
        corrected = self.review(hidden, "visible")
        self.assertEqual(corrected["revision"], 4)
        with self.s.db.connection(readonly=True) as conn:
            history = conn.execute("SELECT status FROM c_peer_post_history ORDER BY revision").fetchall()
        self.assertEqual([row[0] for row in history], ["pending", "visible", "hidden", "visible"])

    def test_post_idempotency_old_cursor_links_and_replay_fail_after_leave(self):
        member, completed = self.joined(complete=True)
        self.joined(patient=PB, client=self.s.b)
        submission = dict(client_post_id=existing.key(), content="虚构短文：记录事项。")
        key = existing.key()
        post = self.post(submission, key=key)
        self.assertEqual(self.post(submission, key=key), post)
        self.assertEqual(self.post(submission), post)
        self.assertEqual(self.post(dict(submission, content="改动"), key=key, expected=409)["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.post(dict(submission, content="改动"), expected=409)["code"], "IDEMPOTENCY_CONFLICT")
        self.review(post)
        self.post()
        cursor = self.posts(query="?limit=1")["next_cursor"]
        target = "?" + urlencode(dict(cursor=cursor, limit=1))
        self.posts(client=self.s.b, query=target, expected=422)
        left = self.leave(member)
        self.assertEqual(left["status"], "left")
        self.assertEqual(self.d.call("GET", "/services/" + completed["service_id"]), completed)
        self.posts(query=target, expected=403)
        self.posts(expected=403)
        self.post(submission, key=key, expected=403)
        self.d.call("GET", "/peer-posts/" + post["post_id"], expected=404)
        self.assertEqual(self.posts(client=self.s.b)["items"][0]["post_id"], post["post_id"])
        self.assertEqual(self.mine(client=self.s.login("demo-patient-a"))["items"][0]["status"], "left")

    def test_explicit_revocation_stops_current_c41_feed_and_replay(self):
        draft, consent = self.prepare()
        member = self.join(self.f.body(draft, consent))
        self.activate(member, complete=True)
        key = existing.key()
        body = dict(client_post_id=existing.key(), content="虚构匿名文字。")
        post = self.post(body, key=key)
        self.review(post)
        self.d.revoke(consent)
        current = self.mine()["items"][0]
        self.assertEqual((current["status"], current["can_participate"]), ("active", False))
        self.assertEqual(self.posts(expected=403)["code"], "PEER_MEMBERSHIP_REQUIRED")
        self.post(body, key=key, expected=403)
        self.leave(member)
        self.assertEqual(self.mine()["items"][0]["status"], "left")

    def test_post_concurrent_write_and_withdrawn_role_replay(self):
        self.joined()
        body = dict(client_post_id=existing.key(), content="虚构匿名来源并发校验。")
        path = self.group() + "/posts"
        one, two = self.d.concurrent((self.s.a, path, body, existing.key()),
                                     (self.s.login("demo-patient-a"), path, body, existing.key()))
        self.assertEqual([r.status_code for r in (one, two)], [201, 201])
        self.assertEqual(one.json()["data"], two.json()["data"])
        pending = one.json()["data"]
        review_key = existing.key()
        self.review(pending, key=review_key)
        with self.s.db.transaction() as conn:
            conn.execute("DELETE FROM c_peer_moderators WHERE group_id=?", (GROUP,))
        self.review(pending, key=review_key, expected=403)
        self.posts(client=self.f.admin, query="?include_pending=true", expected=403)
        self.assertEqual(len(self.posts()["items"]), 1)

    def test_accepted_membership_recovers_after_application_deadline(self):
        member, _ = self.joined(complete=True)
        self.s.time[0] += timedelta(hours=25)
        fresh_session = self.s.login("demo-patient-a")
        self.assertEqual(self.mine(client=fresh_session)["items"][0]["membership_id"], member["membership_id"])
        self.assertTrue(self.mine(client=fresh_session)["items"][0]["can_participate"])
        self.posts(client=fresh_session)
        self.assertEqual(self.leave(member, client=fresh_session)["status"], "left")
