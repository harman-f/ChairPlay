# ChairPlay local automation API — Luna (draft, 2026-11-08)

**Scope:** Authenticated standard API on the local Windows test machine. The P6 Type111 ViewArea settling/race guards remain in the JAR. Luna **never** sends experimental `updateInfo`, `showUI`, `stopUI`, `/api/live-lab` or soft teardown. The local Controller index is not an iPhone frame acknowledgement.

## Host, Port, Auth

- Server listens on **127.0.0.1 only**, rejecting other Host headers. Do **not** expose it to LAN, tunnels or proxies.
- The standard routes require a random token: `Authorization: Bearer <token>`. A query token exists but should not be used for automation. Obtain the current token from ChairPlay's local UI URL and privately provision it through `CHAIRPLAY_API_TOKEN` or `--token-file`. Never commit, print, or put it in command-line arguments. Restrict token-file permissions.
- P6 experimental builds default to **port 18765**, overridable by `CHAIRPLAY_UI_PORT`; unpatched upstream can use a dynamic port. A fixed port is not authentication.
- PR #172 makes only `POST /api/live-lab` and `POST /api/screenshot` token-free on localhost. Luna does **not** depend on that and always sends its token. Review this endpoint before release.
- No remote access, browser bridge, credentials in evidence, or MFi/Pairing material.

## Standard routes and schemas (pinned ChairPlay)

Base URL: `http://127.0.0.1:<port>/api/`. POST requests are JSON objects with `Content-Type: application/json`.

| Route | Example body / result | Meaning |
| --- | --- | --- |
| `GET state` | `{"phase":"active","controls":{"carView":0,"altscreen":"map"},...}` | Locally observed phase/controller view; not an iPhone ACK |
| `GET settings` | `{"values":{"altscreen.profile":"mu1440-790",...},...}` | Settings including selected profile |
| `GET cluster-profiles` | `{"profiles":[{"id":"mu1440-790","text":"{...}","builtIn":true}],"active":"mu1440-790"}` | JSON profile display/views/areas; active may be absent |
| `POST settings` | `{"changes":{"altscreen.profile":"mu1440-790"}}` → `{"saved":[...],"applies":{...}}` | Persistent settings change, does not renegotiate until reconnect |
| `POST cluster-profile` | `{"id":"custom-id","text":"{...}"}` → `{"ok":true}` | Writes profile JSON; not used by the screenshot runner |
| `POST reconnect` | `{}` → `{"ok":true}` | Reconnect requested, not completed |
| `POST control` | `{"action":"altscreen.view","down":true}` followed by `{"action":"altscreen.view","down":false}` | Native Controller View button pulse |
| `POST altscreen` | `{"content":"map"}` → `{"ok":true}` | Content `hud` / `map` / `map-card` / `card` |
| `POST screenshot` | `{}` → `{"ok":true}` | Asynchronous request; **no PNG body, file path or completion guarantee** |
| `GET events` | server-sent event state updates | State updates, not decoded iPhone frames |

Other standard routes are out of scope. Typical errors: HTTP 401 bad/missing token; 403 wrong Host; 404 route/button absent; 405 wrong method; 400 invalid JSON or settings; 409 state refusal; 413 oversized request; 415 wrong content type; 500 server error. Treat non-2xx as a failure.

## Controller/ViewArea contract

- Profile `views[index]` maps a Controller index `0..N-1` to a declared Type111 SafeArea through `views[index].area`. Do not assume View number == Area number.
- Previously observed MU1440 profile: View 0 → Area 4; View 1 → Area 5; View 2 → Area 6. Views 3/4 may be overlay-only. **Always read actual profile JSON at runtime.**
- View changes use serialized **down/up** pulses. The number of steps is `(target - current + N) % N`. After each target, poll `GET state` until `controls.carView == target`. HTTP 200 and matching Controller View do not prove that iOS applied `updateViewArea`.
- P6 safeguards prevent stale settle tickets, delayed asynchronous `view-ask` / `showUI` sends, out-of-order Stream111 generation, failures followed by false `showUI`, and unnegotiated live geometry changes. Preserve P6 independent of optional Live Lab.
- Profile/display/SafeArea geometry changes need a **full CarPlay reconnect** to renegotiate descriptors. Luna only changes selected profile if explicitly authorized; it does not dynamically edit zoom or send native protocol experiments.

## Luna screenshot runner

File: `automation/luna_capture.py` (Python 3.10+, standard library). It never installs or changes a JAR.

1. Authenticate; read state, settings and JSON vehicle profile; record SHA-256 of local `app/chairplay.jar`.
2. Optionally select an existing profile (requires `--allow-profile-change`, persistent setting) and perform full reconnect; require active CarPlay and a Controller index.
3. Request Views in order with button pulses, observe local Controller index, and settle for configurable time (default 2 s). No iPhone/new-frame ACK is available.
4. Before each `POST /api/screenshot` snapshot existing PNGs. Then require **new and stable** `carplay-*.png` and `altscreen-*.png` in `<appdir>/screenshots/`. Validate PNG signature, dimensions, CRC, compressed data and IEND, then copy both to a private output directory. The API has no direct PNG download.
5. A new run directory contains `shot-00-view-00/{carplay,altscreen}.png` etc. `manifest.json` records run ID, timestamp, local JAR SHA, selected profile, actual display geometry, View index, mapped Area, sanitized view name, capture time and each PNG SHA/dimensions/bytes. No auth token, pairing/MFi data or navigation URL is recorded.
6. Screenshot filenames have **second-resolution timestamps** and the two files need not share a timestamp. The runner spaces captures and refuses missing or stale images. It fails closed and marks incomplete evidence `ABORTED`.
7. Completed manifests are marked `CAPTURED_LIVE_LAYOUT_UNVERIFIED`, **not** LIVE_PASS. Visual content and iOS acceptance require separate corroboration.

### Local example (PowerShell)

Use a privately protected token file. Evidence belongs in a private location outside Git.

```powershell
python projects/chairplay-skoda-vc-eval/automation/luna_capture.py `
  --port 18765 `
  --token-file 'E:\ChairPlay_private\ui-token.txt' `
  --app-dir 'E:\CharPlay_Beta' `
  --output 'E:\ChairPlay_private\luna-evidence' `
  --views 0,1,2,0 --settle-seconds 2
```

In PowerShell replace the trailing ` (here shown as generic continuation) with PowerShell's line continuation character, or invoke as a single line.

Selecting another stored profile requires explicit permission:
```powershell
python projects/chairplay-skoda-vc-eval/automation/luna_capture.py --port 18765 --token-file 'E:\ChairPlay_private\ui-token.txt' --app-dir 'E:\CharPlay_Beta' --output 'E:\ChairPlay_private\luna-evidence' --profile mu1440-790 --allow-profile-change --views 0,1,2,0
```

## Lifecycle, recovery, versioning, acceptance

- Target pinned upstream `zakklmv/ChairPlay@fd7a22fa1f503695309ec9efad0e48b2d900349f` plus UI v4→v5, optional experimental Live Lab and P6 guards. Evidence manifest schema: `1`.
- Do **not** auto-retry non-idempotent View pulses after an ambiguous timeout; re-read Controller state. Stop on missing profile, invalid token, unsupported route, inactive state, missing PNG, or image corruption.
- Do not claim `LIVE_PASS` on local send, state transition or visually different screenshots alone: map URL/overlay changes may explain the difference. Correlate video/stream111 frames and payloads in a separately approved iPhone test.
- Restore previously selected profile through the normal UI/settings and fully reconnect after changing native display properties. Do not perform selective Stream111 teardown or unreviewed packet replay. Leave the Live-Lab sender disarmed.
- Unit tests and CI validate offline transformations/packing only. Manual approval is needed for any iPhone session/device test. Do not operate in a moving vehicle.
- Review gates: 1010×376 selected as profile Custom despite fallback 1440×540; no fallback overwrite; correct 0→1→2→0 mappings, two complete PNGs per View, full sanitized manifest, P6 regression guard tests, and manual acceptance before merging/releasing.
