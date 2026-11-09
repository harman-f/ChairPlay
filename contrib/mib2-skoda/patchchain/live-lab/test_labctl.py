"""Offline tests only; never connect to an actual iPhone or expose credentials."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import labctl


ROOT = Path(__file__).resolve().parent


class FakeClient:
    def __init__(self, change_after=None, fail_command=None):
        self.generation = "session-A"
        self.armed = True
        self.writes = []
        self.change_after = change_after
        self.fail_command = fail_command
        self.status_count = 0

    def status(self):
        self.status_count += 1
        if self.change_after is not None and self.status_count >= self.change_after:
            self.generation = "session-B"
        return {
            "state": "ARMED", "sessionActive": True, "armed": self.armed,
            "generation": self.generation, "remaining": 12,
        }

    def post(self, route, payload):
        if route == "screenshot":
            return {"ok": True}
        if payload == {"op": "status"}:
            return self.status()
        assert route == "live-lab" and payload.get("op") == "command"
        assert payload["expectedGeneration"] == self.generation
        self.writes.append(dict(payload))
        if self.fail_command == payload.get("command"):
            return {"state": "REJECTED", "reason": "TEST_REJECT"}
        return {
            "state": "LOCAL_SENT", "command": payload["command"],
            "ack": "NOT_OBSERVED", "visualEffect": "UNKNOWN",
        }


class LabCtlTests(unittest.TestCase):
    def test_p3_plan_is_strict_and_bounded(self):
        plan = labctl.load_plan(ROOT / "scenarios" / "p3-updateinfo70.json")
        self.assertEqual("p3-updateinfo70", plan["id"])
        self.assertEqual([100, 70, 100], [
            step["zoomPercent"] for step in plan["steps"]
            if step.get("command") == "updateInfo"
        ])
        self.assertLessEqual(sum(s["op"] == "command" for s in plan["steps"]), 12)

    def test_reject_raw_commands_and_extra_keys(self):
        plan = labctl.load_plan(ROOT / "scenarios" / "p3-updateinfo70.json")
        step = plan["steps"][2]
        step["command"] = "RTSP_TEARDOWN"
        with self.assertRaises(labctl.LabError):
            labctl.validate_plan(plan)
        step["command"] = "updateInfo"
        step["rawPlist"] = "untrusted"
        with self.assertRaises(labctl.LabError):
            labctl.validate_plan(plan)

    def test_reject_both_bad_zoom_and_boolean_zoom(self):
        plan = labctl.load_plan(ROOT / "scenarios" / "p3-updateinfo70.json")
        plan["steps"][2]["zoomPercent"] = 85
        with self.assertRaises(labctl.LabError):
            labctl.validate_plan(plan)
        plan["steps"][2]["zoomPercent"] = True
        with self.assertRaises(labctl.LabError):
            labctl.validate_plan(plan)

    def test_token_free_localhost_only(self):
        for url in (
            "http://0.0.0.0:8080/",
            "http://example.com:8080/",
            "https://127.0.0.1:8080/",
            "http://127.0.0.1:8080/?token=x",
            "http://127.0.0.1:8080/?extra=1",
            "http://user:pass@127.0.0.1:8080/",
            "http://127.0.0.1/",
        ):
            with self.subTest(url=url), self.assertRaises(labctl.LabError):
                labctl.Client(url)
        valid = labctl.Client("http://localhost:18765/")
        self.assertEqual("http://127.0.0.1:18765", valid.base)
        self.assertFalse(hasattr(valid, "_token"))

    def test_no_auth_header_or_token_in_local_request(self):
        client = labctl.Client("http://127.0.0.1:18765/")
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, n):
                return b'{"state":"NOT_ARMED"}'
        class FakeOpener:
            def open(self, request, timeout):
                self.request = request
                return FakeResponse()
        fake = FakeOpener()
        client._opener = fake
        result = client.status()
        self.assertEqual("NOT_ARMED", result["state"])
        self.assertFalse(any(k.lower() == "authorization" for k, _ in fake.request.header_items()))
        self.assertNotIn("token", fake.request.full_url.lower())

    def test_run_command_auto_arms_and_always_disarms(self):
        plan_file = ROOT / "scenarios" / "p3-updateinfo70.json"
        with tempfile.TemporaryDirectory() as td:
            calls = []
            class ClientStub:
                def __init__(self, url):
                    self.url = url
                def status(self):
                    return {"armed": False}
                def post(self, route, body):
                    calls.append(body["op"])
                    return {"state": "ARMED" if body["op"] == "arm" else "NOT_ARMED"}
            with mock.patch.object(labctl, "Client", ClientStub), mock.patch.object(
                labctl, "run", side_effect=labctl.LabError("synthetic failure")
            ):
                code = labctl.main(["run", str(plan_file), "--audit", str(Path(td, "a.jsonl"))])
            self.assertEqual(2, code)
            self.assertEqual(["arm", "disarm"], calls)

    def test_run_does_not_change_session_or_log_tokens(self):
        plan = labctl.load_plan(ROOT / "scenarios" / "p3-updateinfo70.json")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td, "private.jsonl")
            fake = FakeClient()
            labctl.run(fake, plan, path)
            self.assertEqual(["updateInfo", "updateInfo", "stopUI", "showUI", "updateInfo"],
                             [item["command"] for item in fake.writes])
            self.assertEqual([100, 70, 100],
                             [item["zoomPercent"] for item in fake.writes if item["command"] == "updateInfo"])
            self.assertTrue(all(item["expectedGeneration"] == "session-A" for item in fake.writes))
            audit = path.read_text(encoding="utf-8")
            self.assertNotIn("token=", audit)
            self.assertNotIn("rawPlist", audit)
            self.assertIn("NOT_OBSERVED", audit)

    def test_generation_change_aborts_before_any_write(self):
        plan = labctl.load_plan(ROOT / "scenarios" / "p3-updateinfo70.json")
        fake = FakeClient(change_after=2)
        with tempfile.TemporaryDirectory() as td, self.assertRaises(labctl.LabError):
            labctl.run(fake, plan, Path(td, "private.jsonl"))
        self.assertEqual([], fake.writes)

    def test_unarmed_refuses_before_any_write(self):
        plan = labctl.load_plan(ROOT / "scenarios" / "p3-updateinfo70.json")
        fake = FakeClient()
        fake.armed = False
        with tempfile.TemporaryDirectory() as td, self.assertRaises(labctl.LabError):
            labctl.run(fake, plan, Path(td, "private.jsonl"))
        self.assertEqual([], fake.writes)

    def test_failed_showUI_attempts_same_session_restore(self):
        plan = labctl.load_plan(ROOT / "scenarios" / "p3-updateinfo70.json")
        fake = FakeClient(fail_command="showUI")
        with tempfile.TemporaryDirectory() as td, self.assertRaises(labctl.LabError):
            labctl.run(fake, plan, Path(td, "private.jsonl"))
        self.assertEqual(100, fake.writes[-1]["zoomPercent"])
        self.assertEqual("updateInfo", fake.writes[-1]["command"])

    def test_no_live_call_in_check(self):
        self.assertEqual(0, labctl.main(["check", str(ROOT / "scenarios" / "p3-updateinfo70.json")]))


if __name__ == "__main__":
    unittest.main()
