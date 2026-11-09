#!/usr/bin/env python3
"""ChairPlay Live Lab client (stdlib only). No ability to send without an integrated lab API.

Usage:
    python labctl.py check scenarios/p3-updateinfo70.json
    python labctl.py status
    python labctl.py run scenarios/p3-updateinfo70.json --audit PRIVATE.jsonl

The experimental Lab port is 18765 by default. No token, login or environment setup.
The run command automatically arms and disarms the current session.
The existing one-session and reversible-protocol checks remain in place.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

COMMANDS = {"updateInfo", "stopUI", "showUI"}
SCALE = {70, 100}
MAX_STEPS = 16
MAX_BYTES = 64 * 1024


class LabError(RuntimeError):
    pass


def validate_plan(raw: object) -> dict:
    if not isinstance(raw, dict) or set(raw) != {"schema", "id", "description", "steps"}:
        raise LabError("plan must contain only schema, id, description, steps")
    if type(raw["schema"]) is not int or raw["schema"] != 1:
        raise LabError("unsupported schema")
    if not isinstance(raw["id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", raw["id"]):
        raise LabError("invalid plan id")
    if not isinstance(raw["description"], str) or len(raw["description"]) > 600:
        raise LabError("invalid plan description")
    steps = raw["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise LabError("plan must have 1..16 steps")
    writes = 0
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or not isinstance(step.get("op"), str):
            raise LabError(f"step {i}: invalid step")
        op = step["op"]
        if op == "status":
            allowed = {"op", "tag"}
        elif op == "capture":
            allowed = {"op", "tag"}
            if not isinstance(step.get("tag"), str):
                raise LabError(f"step {i}: capture requires tag")
        elif op == "pause":
            allowed = {"op", "milliseconds", "tag"}
            ms = step.get("milliseconds")
            if type(ms) is not int or not 0 <= ms <= 2000:
                raise LabError(f"step {i}: pause must be 0..2000 milliseconds")
        elif op == "command":
            allowed = {"op", "command", "zoomPercent", "tag"}
            command = step.get("command")
            if command not in COMMANDS:
                raise LabError(f"step {i}: unsupported command")
            if command == "updateInfo":
                if type(step.get("zoomPercent")) is not int or step["zoomPercent"] not in SCALE:
                    raise LabError(f"step {i}: updateInfo zoom must be 70 or 100")
            elif "zoomPercent" in step:
                raise LabError(f"step {i}: non-scale command cannot carry zoom")
            writes += 1
        else:
            raise LabError(f"step {i}: unsupported op")
        if set(step) - allowed:
            raise LabError(f"step {i}: unknown fields")
        if "tag" in step and (not isinstance(step["tag"], str) or
                              not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", step["tag"])):
            raise LabError(f"step {i}: invalid tag")
    if writes > 12:
        raise LabError("plan exceeds 12 write budget")
    return raw


def load_plan(path: Path) -> dict:
    if path.stat().st_size > MAX_BYTES:
        raise LabError("plan file too large")
    return validate_plan(json.loads(path.read_text(encoding="utf-8")))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LabError("redirect forbidden for local API")


class Client:
    def __init__(self, url: str):
        parsed = urlsplit(url)
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost"):
            raise LabError("only local http://127.0.0.1 or localhost is accepted")
        if parsed.username or parsed.password or parsed.fragment or parsed.path not in ("", "/"):
            raise LabError("unexpected UI URL shape")
        try:
            port = parsed.port
        except ValueError as exc:
            raise LabError("invalid local port") from exc
        if port is None or not 1 <= port <= 65535:
            raise LabError("UI URL needs a valid port")
        if parsed.query:
            raise LabError("experimental Lab URL must not have a token or query parameters")
        self.base = f"http://127.0.0.1:{port}"
        self._opener = build_opener(ProxyHandler({}), NoRedirect())

    def post(self, route: str, data: dict) -> dict:
        if route not in ("live-lab", "screenshot"):
            raise LabError("route not allowed")
        encoded = json.dumps(data, separators=(",", ":")).encode("utf-8")
        req = Request(
            self.base + "/api/" + route,
            data=encoded,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener.open(req, timeout=5) as resp:
                body = resp.read(MAX_BYTES + 1)
        except HTTPError as exc:
            raise LabError(f"local API rejected request (HTTP {exc.code}); no success implied") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise LabError("local ChairPlay API unreachable (or Live Lab not integrated)") from exc
        if len(body) > MAX_BYTES:
            raise LabError("oversized local API response")
        try:
            answer = json.loads(body)
        except ValueError as exc:
            raise LabError("invalid JSON from local API") from exc
        if not isinstance(answer, dict):
            raise LabError("local API response is not an object")
        return answer

    def status(self) -> dict:
        return self.post("live-lab", {"op": "status"})


def summary(answer: dict) -> dict:
    """Only explicit evidence fields, never arbitrary response payloads or token."""
    fields = (
        "state", "sessionActive", "generation", "armed", "remaining", "command",
        "localSent", "ack", "visualEffect", "eventCSeq", "responseCode",
        "stream111SetupCount", "stream110SetupCount", "reason", "capabilities",
        "descriptorReady", "descriptorReason", "stream111Active", "mainFrameRendered",
    )
    return {key: answer[key] for key in fields if key in answer and
            isinstance(answer[key], (str, int, bool, type(None), list))}


def audit(out: Path, plan_id: str, index: int, action: str, answer: dict) -> None:
    row = {
        "timeUTC": datetime.now(timezone.utc).isoformat(),
        "plan": plan_id, "step": index, "action": action,
        "result": summary(answer),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    # Owner-specified private path. Never include device identifiers, route URLs or full plist.
    with out.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def require_same_session(client: Client, generation: str) -> dict:
    status = client.status()
    if not status.get("sessionActive") or status.get("generation") != generation:
        raise LabError("session generation changed; abort without sending")
    if not status.get("armed"):
        raise LabError("Live Lab is not armed locally")
    return status


def run(client: Client, plan: dict, output: Path) -> None:
    initial = client.status()
    generation = initial.get("generation")
    if (not initial.get("sessionActive") or not initial.get("armed") or
            not isinstance(generation, str) or not generation):
        raise LabError("requires one active, explicitly armed session with a generation")
    writes = sum(step["op"] == "command" for step in plan["steps"])
    if type(initial.get("remaining")) is not int or initial["remaining"] < writes:
        raise LabError("insufficient Live Lab write budget")
    print(f"Running {plan['id']} on one armed session; {writes} bounded writes")
    restore_needed = False
    restored = False
    try:
        for i, step in enumerate(plan["steps"], start=1):
            op = step["op"]
            if op == "pause":
                time.sleep(step["milliseconds"] / 1000)
                continue
            status = require_same_session(client, generation)
            if op == "status":
                result = status
            elif op == "capture":
                result = client.post("screenshot", {})
                if result.get("ok") is not True:
                    raise LabError(f"screenshot {i} failed")
            else:
                payload = {
                    "op": "command", "command": step["command"],
                    "expectedGeneration": generation,
                }
                if step["command"] == "updateInfo":
                    payload["zoomPercent"] = step["zoomPercent"]
                result = client.post("live-lab", payload)
                if result.get("state") != "LOCAL_SENT":
                    raise LabError(f"step {i} was not locally sent; no iOS acceptance claimed")
                if step["command"] == "updateInfo":
                    if step["zoomPercent"] == 70:
                        restore_needed = True
                    elif step["zoomPercent"] == 100:
                        restore_needed = False
                        restored = True
            audit(output, plan["id"], i, step.get("tag", op), result)
            print(f" {i:02d} {step.get('tag', op)}: {summary(result).get('state', 'RECORDED')}")
    finally:
        if restore_needed:
            # Best effort only when same generation is STILL armed. No destructive fallback.
            try:
                require_same_session(client, generation)
                result = client.post("live-lab", {
                    "op": "command", "command": "updateInfo",
                    "zoomPercent": 100, "expectedGeneration": generation,
                })
                audit(output, plan["id"], 999, "best-effort-restore-100", result)
                if result.get("state") == "LOCAL_SENT":
                    print("Restore 100% locally sent; iOS effect unverified")
                else:
                    print("WARNING: restoration not locally sent; manual full reconnect required", file=sys.stderr)
            except LabError:
                print("WARNING: session changed or restoration refused; manual known-good reconnect required", file=sys.stderr)
    if restored:
        print("Sequence ended with 100% restoration request; verify image/phone state manually.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ChairPlay same-session lab client; no remote endpoint exposure")
    sub = parser.add_subparsers(dest="action", required=True)
    check = sub.add_parser("check", help="offline syntax/safety check, never contacts ChairPlay")
    check.add_argument("plan", type=Path)
    sub.add_parser("status", help="local Lab API status on port 18765; no token")
    arm = sub.add_parser("arm", help="explicitly arm one live session for 10 minutes")
    arm.add_argument("--confirm-live", action="store_true", help="optional legacy alias")
    sub.add_parser("disarm", help="stop accepting experimental writes")
    sub.add_parser("events", help="show redacted in-memory command history")
    launch = sub.add_parser("run", help="execute in current armed session only")
    launch.add_argument("plan", type=Path)
    launch.add_argument("--confirm-live", action="store_true", help="optional legacy alias")
    launch.add_argument("--audit", type=Path, required=True, help="private JSONL audit output path")
    args = parser.parse_args(argv)
    try:
        if args.action == "check":
            plan = load_plan(args.plan)
            print(f"PASS: {plan['id']}; {len(plan['steps'])} bounded steps, no traffic")
            return 0
        # An explicit nondefault Lab port is supported, but no tokens or credentials are read.
        url = os.environ.get("CHAIRPLAY_LAB_URL") or "http://127.0.0.1:18765/"
        client = Client(url)
        if args.action == "status":
            print(json.dumps(summary(client.status()), indent=2, sort_keys=True))
            return 0
        if args.action == "events":
            result = client.post("live-lab", {"op": "events"})
            print(json.dumps({"state": result.get("state"), "generation": result.get("generation"),
                              "history": result.get("history", [])}, indent=2, sort_keys=True))
            return 0
        if args.action == "disarm":
            print(json.dumps(summary(client.post("live-lab", {"op": "disarm"})), indent=2))
            return 0
        if args.action == "arm":
            result = client.post("live-lab", {"op": "arm", "confirm": "LIVE_LAB_LOCAL"})
            print(json.dumps(summary(result), indent=2, sort_keys=True))
            if result.get("state") != "ARMED":
                raise LabError("Live Lab not armed")
            return 0
        plan = load_plan(args.plan)
        # One command does the complete local test, including arming and cleanup.
        try:
            state = client.status()
            if not state.get("armed"):
                armed = client.post("live-lab", {"op": "arm", "confirm": "LIVE_LAB_LOCAL"})
                if armed.get("state") != "ARMED":
                    raise LabError("cannot arm the active ChairPlay session: " + str(armed.get("reason")))
            run(client, plan, args.audit)
        finally:
            try:
                client.post("live-lab", {"op": "disarm"})
            except LabError:
                print("WARNING: could not disarm the local lab; check ChairPlay status", file=sys.stderr)
        return 0
    except (LabError, OSError, ValueError) as exc:
        print(f"LAB_STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
