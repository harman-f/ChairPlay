#!/usr/bin/env python3
"""Luna's local-only, authenticated ChairPlay screenshot runner (stdlib only).

No AirPlay/Live-Lab commands, no MFi or token values in evidence.
API 200/state carView are not proof of a fresh accepted iPhone frame.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import time
from urllib import error, request
import zlib


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class AutomationError(RuntimeError):
    pass


class LocalApi:
    def __init__(self, port: int, token: str, timeout: float = 8.0):
        if not 1 <= port <= 65535 or not token.strip():
            raise AutomationError("Valid local port and explicit bearer token required")
        self.url = "http://127.0.0.1:" + str(port) + "/api/"
        self.token = token.strip()
        # Do not leak localhost traffic through system HTTP proxy configuration.
        self.opener = request.build_opener(request.ProxyHandler({}))
        self.timeout = timeout

    def call(self, route: str, payload: dict | None = None) -> dict:
        if route not in {"state", "settings", "cluster-profiles", "control",
                         "altscreen", "reconnect", "screenshot"}:
            raise AutomationError("Unsupported standard API route")
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Authorization": "Bearer " + self.token, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = request.Request(self.url + route, data=body, headers=headers,
                              method="POST" if body is not None else "GET")
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                result = json.load(response)
        except error.HTTPError as exc:
            # No token, URL or response body in logs.
            raise AutomationError(f"ChairPlay /api/{route} returned HTTP {exc.code}") from None
        except (error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise AutomationError(f"ChairPlay /api/{route} failed: {type(exc).__name__}") from None
        if not isinstance(result, dict):
            raise AutomationError("Unexpected response from /api/" + route)
        return result


def view_index(state: dict) -> int | None:
    controls = state.get("controls") or {}
    value = controls.get("carView") if isinstance(controls, dict) else None
    return value if type(value) is int and value >= 0 else None


def wait_for_view(api: LocalApi, target: int, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        state = api.call("state")
        if state.get("phase") == "active" and view_index(state) == target:
            return state
        if time.monotonic() >= deadline:
            raise AutomationError(f"Controller view {target} not observed (timeout)")
        time.sleep(0.25)


def wait_for_active(api: LocalApi, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        state = api.call("state")
        if state.get("phase") == "active" and view_index(state) is not None:
            return state
        if time.monotonic() >= deadline:
            raise AutomationError("No active CarPlay session with a Controller view")
        time.sleep(0.4)


def select_view(api: LocalApi, target: int, count: int, timeout: float) -> dict:
    if count < 1 or not 0 <= target < count:
        raise AutomationError("Requested View outside selected profile")
    current = view_index(wait_for_active(api, timeout))
    if current is None or current >= count:
        raise AutomationError("Invalid Controller view for this profile")
    for _ in range((target - current) % count):
        # Send explicit down/up pairs, one at a time. A successful HTTP 200 is not a frame ACK.
        try:
            api.call("control", {"action": "altscreen.view", "down": True})
        finally:
            api.call("control", {"action": "altscreen.view", "down": False})
    return wait_for_view(api, target, timeout)


def read_profile(profiles: dict, profile_id: str) -> dict:
    entry = next((item for item in profiles.get("profiles", [])
                  if isinstance(item, dict) and item.get("id") == profile_id), None)
    if not entry or not isinstance(entry.get("text"), str):
        raise AutomationError("Selected vehicle profile is missing")
    try:
        profile = json.loads(entry["text"])
    except ValueError:
        raise AutomationError("Vehicle profile JSON is invalid") from None
    if not isinstance(profile, dict) or not isinstance(profile.get("views"), list) or not profile["views"]:
        raise AutomationError("Profile has no usable Views")
    if not isinstance(profile.get("display"), dict):
        raise AutomationError("Profile has no display descriptor")
    return profile


def png_metadata(path: Path) -> dict:
    """Validate PNG chunks, CRC and compressed image payload, not only file existence."""
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AutomationError("Invalid PNG signature")
    pos, dims, pixels, complete, compressed = 8, None, False, False, bytearray()
    while pos + 12 <= len(data):
        length = struct.unpack_from(">I", data, pos)[0]
        kind = data[pos + 4:pos + 8]
        end = pos + 12 + length
        if end > len(data) or length > 64 * 1024 * 1024:
            raise AutomationError("Incomplete PNG chunk")
        payload = data[pos + 8:pos + 8 + length]
        crc = struct.unpack_from(">I", data, pos + 8 + length)[0]
        if zlib.crc32(kind + payload) & 0xffffffff != crc:
            raise AutomationError("PNG CRC mismatch")
        if kind == b"IHDR":
            if length != 13:
                raise AutomationError("Invalid PNG IHDR")
            width, height = struct.unpack_from(">II", payload)
            if width < 1 or height < 1:
                raise AutomationError("Invalid PNG dimensions")
            dims = [width, height]
        elif kind == b"IDAT":
            pixels = True
            compressed.extend(payload)
        elif kind == b"IEND":
            complete = True
            pos = end
            break
        pos = end
    if not complete or not pixels or not dims or pos != len(data):
        raise AutomationError("PNG incomplete")
    try:
        if not zlib.decompress(bytes(compressed)):
            raise ValueError()
    except zlib.error:
        raise AutomationError("PNG compressed data invalid") from None
    return {"width": dims[0], "height": dims[1], "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def snapshot(folder: Path) -> dict:
    if not folder.is_dir():
        return {}
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns)
            for p in folder.glob("*.png") if p.is_file()}


def wait_for_pair(folder: Path, before: dict, timeout: float) -> dict:
    """Require two newly written *stable*, valid PNG files for one screenshot request."""
    deadline = time.monotonic() + timeout
    stable = {}
    while time.monotonic() < deadline:
        found = {}
        for kind in ("carplay", "altscreen"):
            candidates = []
            for path in folder.glob(kind + "-*.png"):
                st = path.stat()
                stamp = (st.st_size, st.st_mtime_ns)
                if before.get(path.name) != stamp and st.st_size > 64:
                    candidates.append((st.st_mtime_ns, path, stamp))
            if candidates:
                _, path, stamp = max(candidates)
                key = str(path)
                stable[key] = stable.get(key, (None, 0))
                prior, times = stable[key]
                stable[key] = (stamp, times + 1 if prior == stamp else 1)
                if stable[key][1] >= 2:
                    try:
                        png_metadata(path)
                        found[kind] = path
                    except (AutomationError, OSError):
                        pass
        if len(found) == 2:
            return found
        time.sleep(0.25)
    raise AutomationError("Screenshot request did not yield two complete, fresh PNGs")


def capture_pair(api: LocalApi, folder: Path, output: Path, timeout: float) -> dict:
    before = snapshot(folder)
    answer = api.call("screenshot", {})
    if answer.get("ok") is not True:
        raise AutomationError("Screenshot was not accepted")
    paths = wait_for_pair(folder, before, timeout)
    output.mkdir(parents=True, exist_ok=False)
    files = {}
    for kind, path in paths.items():
        destination = output / (kind + ".png")
        shutil.copy2(path, destination)
        files[kind] = {"file": kind + ".png", **png_metadata(destination)}
    return files


def safe_write_json(path: Path, obj: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def run(args, api: LocalApi) -> Path:
    root = args.app_dir.resolve()
    jar = root / "app" / "chairplay.jar"
    if not jar.is_file():
        raise AutomationError("app/chairplay.jar not found; cannot stamp build identity")
    jar_sha = hashlib.sha256(jar.read_bytes()).hexdigest()
    profiles = api.call("cluster-profiles")
    settings = api.call("settings")
    values = settings.get("values")
    if not isinstance(values, dict):
        raise AutomationError("Unexpected settings response; no values map")
    active_id = str(values.get("altscreen.profile") or profiles.get("active") or "")
    requested_id = args.profile or active_id
    if not requested_id:
        raise AutomationError("Choose an actual vehicle profile, not None")
    profile = read_profile(profiles, requested_id)
    if requested_id != active_id:
        if not args.allow_profile_change:
            raise AutomationError("Profile switch requires --allow-profile-change (persistent setting)")
        result = api.call("settings", {"changes": {"altscreen.profile": requested_id}})
        if "errors" in result:
            raise AutomationError("Profile setting was refused")
        args.reconnect = True
    if args.reconnect:
        api.call("reconnect", {})
    wait_for_active(api, args.wait_seconds)
    if args.content:
        response = api.call("altscreen", {"content": args.content})
        if response.get("ok") is not True:
            raise AutomationError("AltScreen content was refused")
    run_id = datetime.now(timezone.utc).strftime("luna-%Y%m%dT%H%M%S%fZ")
    output = args.output.resolve() / run_id
    output.mkdir(parents=True, exist_ok=False)
    display = profile["display"]
    manifest = {
        "schema": 1, "run_id": run_id, "started_utc": utc_now(),
        "status": "IN_PROGRESS", "chairplay_jar_sha256": jar_sha,
        "profile_id": requested_id,
        "display": {key: display.get(key) for key in
                    ("width", "height", "widthMm", "heightMm", "zoomFactor")},
        "content": args.content or "UNCHANGED",
        "verification": {
            "controller_index": "OBSERVABLE_VIA_STATE",
            "iphone_frame_ack": "NOT_AVAILABLE",
            "layout_acceptance": "UNVERIFIED",
        },
        "shots": [],
    }
    manifest_path = output / "manifest.json"
    safe_write_json(manifest_path, manifest)
    last_capture = 0.0
    try:
        for order, target in enumerate(args.views):
            state = select_view(api, target, len(profile["views"]), args.wait_seconds)
            # Controller index is a local observation, *not* evidence of a new iPhone frame.
            time.sleep(max(0.0, args.settle_seconds))
            elapsed = time.monotonic() - last_capture
            if elapsed < 1.25:  # screenshot filenames have second resolution; avoid collisions.
                time.sleep(1.25 - elapsed)
            view = profile["views"][target]
            shot_dir = output / ("shot-%02d-view-%02d" % (order, target))
            files = capture_pair(api, root / "screenshots", shot_dir, args.capture_timeout)
            last_capture = time.monotonic()
            manifest["shots"].append({
                "ordinal": order, "requested_view": target, "observed_view": view_index(state),
                "area": view.get("area"), "view_name": view.get("name", ""),
                "captured_utc": utc_now(), "phase": state.get("phase"),
                "controller_status": "OBSERVED_NOT_FRAME_ACK",
                "directory": shot_dir.name, "files": files,
            })
            safe_write_json(manifest_path, manifest)
        manifest["status"] = "CAPTURED_LIVE_LAYOUT_UNVERIFIED"
    except Exception as exc:
        manifest["status"] = "ABORTED"
        manifest["error"] = str(exc) if isinstance(exc, AutomationError) else type(exc).__name__
        safe_write_json(manifest_path, manifest)
        raise
    manifest["finished_utc"] = utc_now()
    safe_write_json(manifest_path, manifest)
    return manifest_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--token-file", type=Path, help="Private plaintext token file; never copied into evidence")
    parser.add_argument("--app-dir", type=Path, required=True, help="ChairPlay directory containing app/ and screenshots/")
    parser.add_argument("--output", type=Path, required=True, help="Private evidence output directory")
    parser.add_argument("--profile", help="Existing profile id; defaults to currently selected profile")
    parser.add_argument("--allow-profile-change", action="store_true")
    parser.add_argument("--reconnect", action="store_true", help="Full CarPlay reconnect, not soft Stream111 teardown")
    parser.add_argument("--content", choices=["hud", "map", "map-card", "card"])
    parser.add_argument("--views", default="0,1,2,0", help="View sequence, e.g. 0,1,2,0")
    parser.add_argument("--settle-seconds", type=float, default=2.0)
    parser.add_argument("--wait-seconds", type=float, default=45.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    args = parser.parse_args(argv)
    try:
        raw = args.token_file.read_text(encoding="utf-8") if args.token_file else os.environ.get("CHAIRPLAY_API_TOKEN", "")
        if not raw.strip():
            raise AutomationError("Set CHAIRPLAY_API_TOKEN or --token-file; token-free routes are not used")
        args.views = [int(v.strip()) for v in args.views.split(",")]
        if not args.views or any(v < 0 for v in args.views):
            raise AutomationError("--views must contain non-negative indexes")
        for value in (args.settle_seconds, args.wait_seconds, args.capture_timeout):
            if not 0 <= value <= 300:
                raise AutomationError("Invalid timeout/settle setting")
        path = run(args, LocalApi(args.port, raw))
        print("MANIFEST=" + str(path))
        print("STATUS=CAPTURED_LIVE_LAYOUT_UNVERIFIED")
        return 0
    except (AutomationError, OSError, ValueError) as exc:
        print("LUNA_ERROR=" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
