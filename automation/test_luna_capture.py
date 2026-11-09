"""Offline unit tests; fake API and synthetic PNGs. No iPhone or HTTP writes."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

import luna_capture as luna


def chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))


def png():
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
            + chunk(b"IEND", b""))


class FakeApi:
    def __init__(self, folder=None):
        self.current = 0
        self.calls = []
        self.folder = folder

    def call(self, route, payload=None):
        self.calls.append((route, payload))
        if route == "state":
            return {"phase": "active", "controls": {"carView": self.current}}
        if route == "control":
            if payload == {"action": "altscreen.view", "down": True}:
                self.current = (self.current + 1) % 3
            return {"ok": True}
        if route == "screenshot":
            if self.folder:
                self.folder.mkdir(exist_ok=True)
                for name in ("carplay", "altscreen"):
                    (self.folder / (name + "-2099-010101.png")).write_bytes(png())
            return {"ok": True}
        raise AssertionError("Unexpected call: " + route)


class LunaUnitTests(unittest.TestCase):
    def test_unauthenticated_access_not_allowed(self):
        with self.assertRaises(luna.AutomationError):
            luna.LocalApi(18765, "  ")

    def test_controller_pulses_use_count_and_observed_index(self):
        api = FakeApi()
        state = luna.select_view(api, 2, 3, 2)
        self.assertEqual(luna.view_index(state), 2)
        pulses = [p for name, p in api.calls if name == "control"]
        self.assertEqual(pulses, [
            {"action": "altscreen.view", "down": True},
            {"action": "altscreen.view", "down": False},
            {"action": "altscreen.view", "down": True},
            {"action": "altscreen.view", "down": False}])
        luna.select_view(api, 0, 3, 2)
        self.assertEqual(api.current, 0)

    def test_invalid_view_fails_closed(self):
        with self.assertRaises(luna.AutomationError):
            luna.select_view(FakeApi(), 3, 3, 0.5)

    def test_profile_comes_from_current_api_json_not_hardcoded_areas(self):
        profiles = {"profiles": [{"id": "mu1440-790", "text": json.dumps({
            "views": [{"area": 4}, {"area": 5}, {"area": 6}],
            "display": {"width": 1010, "height": 376}
        })}]}
        parsed = luna.read_profile(profiles, "mu1440-790")
        self.assertEqual([v["area"] for v in parsed["views"]], [4, 5, 6])
        self.assertEqual(parsed["display"]["width"], 1010)

    def test_validates_actual_image_chunks_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "shot.png"
            p.write_bytes(png())
            info = luna.png_metadata(p)
            self.assertEqual((info["width"], info["height"]), (1, 1))
            broken = bytearray(png())
            broken[-10] ^= 1
            p.write_bytes(broken)
            with self.assertRaises(luna.AutomationError):
                luna.png_metadata(p)

    def test_pairs_new_images_after_api_call(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, out = root / "screenshots", root / "out"
            api = FakeApi(source)
            result = luna.capture_pair(api, source, out, 2)
            self.assertEqual(set(result), {"carplay", "altscreen"})
            self.assertTrue((out / "carplay.png").exists())
            self.assertTrue((out / "altscreen.png").exists())
            self.assertEqual(result["altscreen"]["sha256"], result["carplay"]["sha256"])

    def test_missing_second_frame_is_error_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            root.joinpath("carplay-2099.png").write_bytes(png())
            with self.assertRaises(luna.AutomationError):
                luna.wait_for_pair(root, {}, 0.45)

    def test_existing_pngs_not_accepted_as_new_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("carplay", "altscreen"):
                (root / (name + "-already.png")).write_bytes(png())
            before = luna.snapshot(root)
            with self.assertRaises(luna.AutomationError):
                luna.wait_for_pair(root, before, 0.45)


if __name__ == "__main__":
    unittest.main()
