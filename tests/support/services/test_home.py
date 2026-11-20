"""Home's recent-service contract: stable descending pages, exact scope and no writes."""

import unittest
from urllib.parse import quote

from support.services import test_services as services


class HomeServiceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = services.FormalServiceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_newest_three_and_cursor_direction_are_authoritative(self):
        f = self.fixture
        originals = []
        for n in range(5):
            draft = f.d.create(text=f"第 {n} 项虚构服务问题")
            consent = f.d.confirm(draft, expected=201 if n == 0 else 200)
            originals.append(f.create(f.body(draft, consent)))
        first = f.d.call("GET", services.SERVICES + "?order=desc&limit=3")
        ordered = sorted(
            originals, key=lambda d: (d["submitted_at"], d["service_id"]), reverse=True
        )
        self.assertEqual(
            [d["service_id"] for d in first["items"]],
            [d["service_id"] for d in ordered[:3]],
        )
        cursor = quote(first["next_cursor"], safe="")
        second = f.d.call(
            "GET", services.SERVICES + "?order=desc&limit=3&cursor=" + cursor
        )
        self.assertEqual(
            [d["service_id"] for d in second["items"]],
            [d["service_id"] for d in ordered[3:]],
        )
        self.assertIsNone(second["next_cursor"])
        f.d.call("GET", services.SERVICES + "?limit=3&cursor=" + cursor, expected=422)
        f.d.call("GET", services.SERVICES + "?order=invalid", expected=422)
        ascending = f.d.call("GET", services.SERVICES + "?limit=3")
        self.assertEqual(
            [d["service_id"] for d in ascending["items"]],
            [d["service_id"] for d in reversed(ordered)][0:3],
        )
        self.assertEqual(f.counts()[0], 5)
