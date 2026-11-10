# Live Lab integration review — exact Kotlin / DiPlay anchors

This file is the **integration handoff after UI-v5 acceptance**, not a claim that live commands are already wired. Target source is pinned \`zakklmv/ChairPlay@fd7a22fa1f503695309ec9efad0e48b2d900349f\`, Git submodule \`shihabal3amri/DiPlay@28d6002ba00320f0ba745212160b08759e4f60b9\`, with the UI-v5 patch sequence from \`work/chairplay-ui-v5-view-sync-20261107\` commit \`ea107abbf64fa536d03563de4ab820e38b978f37\`.

## Wire/API audit 2026-11-07

1. **Real event writer exists:** \`AirPlaySession.kt\` public \`sendCommand(command: Map<String,Any?>): Boolean\` synchronizes on \`eventWriteLock\`, encodes a binary plist and writes an encrypted \`POST /command RTSP/1.0\`, incrementing a private \`eventCseq\`. The return value means **local write success only**.
2. **Scene commands already supported:** \`setClusterUiShown(false)\` sends \`stopUI\` for \`AirPlayInfoPlist.ALT_UUID\`; \`setClusterUiShown(true)\` calls the existing cluster URL path, which sends \`showUI\` followed by \`forceKeyFrame\`. Do not send raw \`showUI\` from the lab unless the state-machine effects (retained URL, \`clusterContent\`, stream token) have been reconciled.
3. **RTSP answers not currently correlated:** \`AirPlaySession.runEventRead\` explicitly skips incoming \`RTSP/\` and \`HTTP/\` messages. A private event CSeq increment and \`trace\` output do **not** constitute iOS acknowledgement. S2 needs a *narrow*, redacted send-result callback and actual response matching, if the iPhone sends such a reply. Do not expose binary plist dumps: the existing \`trace\` currently logs full hex.
4. **Full advertised /info is not yet retained:** \`AirPlaySession\` currently builds \`AirPlayInfoPlist.build(config)\` for incoming \`GET /info\`. UI/profile modifications might affect the effective \`info\` in that build path. We must capture the **exact final dictionary serialized on the active session** immediately before \`BplistCodec.encode(info)\`; reconstructing it from current settings afterwards is not safe. Capture a defensive immutable snapshot under the same connection generation, not a raw dumped log.
5. **\`updateInfo\` wire format is research-supported**: \`{type:"updateInfo", value:<full info dictionary>}\`. The staged \`UpdateInfoScaleBuilder.kt\` edits the sole Type111 \`zoomFactor\`, but currently refuses \`displayPanels\`-bearing descriptors. Do not remove \`displayPanels\` merely to bypass this guard; determine the exact schema/field relationship first.
6. **No phone-side scale proof:** the exact iOS 27.2 research rules out a direct \`updateInfo\` -> CarKit display remap in the examined path. A local POST success is not proof of iOS receiving, applying or redrawing 70%. Compare Type111 screenshots and same-session \`SETUP\`/TEARDOWN counters.

## Proposed in-app integration after approval

Patch application sequence should be:
1. Clone/checkout exact pinned ChairPlay source as current build does. Run existing UI v5 patch steps unchanged.
2. Apply a **separate fail-closed live-lab integration script** after \`finalize-ui-v5.py\`, never before, and never to a separate unexpected source revision.
3. Register \`POST /api/live-lab\` in \`UiServer\` alongside existing authenticated endpoints; preserve bearer auth, localhost-only binding, host validation, JSON request limit and no-store response.
4. Delegate through \`UiApi\` / \`AppUiApi\` to a new transient \`LiveLabController\` created in \`Main.kt\` using \`active\`, \`touchSender\` and an increment-on-session-change opaque generation. Expose read-only \`status\` first.
5. Integrate \`LiveLabGate.kt\`. \`arm\` explicit operator action; app's first startup/reconnect always disarmed. Per-action authorization must execute **after** queueing on \`touchSender\`, immediately before an outgoing write, and check exact \`active.get() === capturedSession\` plus generation. Reject on unknown topology, disabled mode, TTL/budget exhaustion or concurrent new session. Lab operations must not modify persistent settings.
6. Introduce one \`LiveLabSender\` interface (small, injectable, mock-tested): \`status\`, \`sendUpdateInfo\`, \`stopUi111\`, \`showUi111\`. There must be no arbitrary \`sendCommand\` passthrough, raw plist input or HTTP-provided UUID. Until protocol audit and tests pass, \`sendUpdateInfo\` must answer \`NOT_SUPPORTED\`, rather than report \`LOCAL_SENT\`.
7. Add redacted event evidence: timeUTC, monotonic sequence, opaque generation, command, zoom only, actual local-write status, outbound CSeq if instrumented, *correlated* reply status if available (otherwise \`NOT_OBSERVED\`), Type110/111 setup counters and screenshot references. Don't log negotiated /info bytes, route data, phone identifiers, local token, MFi, Wi-Fi credentials or full URLs.
8. Unit & integration gate: \`LiveLabGateTest\`, API allowlist/auth/HTTP errors, simulated concurrent session change at executor dequeue, roundtrip 100->70->100 with duplicate UUID rejection, DDP conflict, no automatic reconnect, log redaction. The offline Python CLI tests already cover plan/host/token/cancellation logic.
9. Build one experimental JAR in the **separate** integration branch, verify UI-v5 marker, all existing tests and source pins, deliver only \`app/chairplay.jar\` relative to Build #44 installation. No auto-replacement of the accepted JAR and no automatic iPhone connection.
10. Parked bench test: collect baseline at 100% and positive-control 70% after full reconnect first. Run at most one P3 sequence; if unsupported or image unchanged, stop and document the result. No Type111 socket kill.

## What is already staged vs blocked

| Component | State |
| --- | --- |
| \`labctl.py\` bounded local Codex CLI | staged; tests in same directory |
| \`scenarios/p3-updateinfo70.json\` | staged; no network action by itself |
| \`LiveLabGate.kt\` + tests | staged, independent; not yet linked to ChairPlay |
| Offline-only GitHub Actions gate | staged; no Windows JAR or network sending |
| \`/api/live-lab\` inside ChairPlay | **not installed**, integration only after UI-v5 acceptance |
| Final \`/info\` snapshot and DiPlay sender | **blocked on S2 audit**, no runtime replacement or verified ACK |
| Device test / session effect | **not performed** |

### Risk to pay attention to

\`setClusterUiShown\` changes retained session UI state; independently issuing it may conflict with the ordinary \`AltscreenView.show()\` selection while controls are used. Serialize lab actions with touchSender, either suspend normal competing UI actions under explicit Lab mode or route through the existing \`AltscreenUi\` state machine. On disarm, restore normal view selection; do not silently make a different view active.

The existing UI-v5 staging branch is the baseline **only**. If the pending build acceptance leads to new commits, rebase this preparation on that exact accepted SHA before authorizing a runtime build.
