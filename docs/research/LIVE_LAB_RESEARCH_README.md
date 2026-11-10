# ChairPlay Live Lab — staged integration, not in the accepted build

**State:** source-only preparation on a branch forked from ChairPlay UI v5 commit \`ea107abbf64fa536d03563de4ab820e38b978f37\` (2026-11-07). **Do not merge, run a patched app, alter the accepted Build #44 JAR, or enable packet transmission during the ongoing UI acceptance.** The work here is a lab client, a deterministic safety gate and an integration contract. No runtime HTTP endpoint or phone sender is installed by these files alone.

## Goal

One reviewed experimental Windows JAR after UI v5 acceptance; subsequently run bounded P1–P4 sequences against the *same* authenticated AirPlaySession from local Codex/PowerShell without rebuilding between experiments. Retain a clean baseline and allow a full known-good reconnect as manual recovery. Initial target is P3: 100% -> \`updateInfo\` with 111 zoomFactor 70 -> \`stopUI\`/ \`showUI\` -> 100%. Do not conflate successful local send with iOS ACK or visual scale.

## Verified anchors in pinned upstream

- \`UiServer.kt\`: existing \`HttpServer\` bound to 127.0.0.1, random bearer token, strict Host check, route whitelist; SSE \`/api/events\` exists.
- \`UiPosts.kt\`: typed route dispatch.
- \`UiApi.kt\` + \`AppUiApi.kt\` + \`ChairPlayUi.kt\`: API adapter and controller delegation; Main instantiates \`ChairPlayUi\`.
- \`Main.kt\`: active \`AtomicReference<AirPlaySession?>\` and dedicated \`touchSender\` serial executor.
- \`AltscreenUi.kt\`: already uses \`setClusterUrl\` / \`setClusterUiShown\`; \`AltscreenView\` logs outgoing *local write* only.
- \`UpdateInfoScaleBuilder.kt\` on \`codex/ios27-scaling-audit\`: **candidate builder, not wired to live session.** It currently rejects a payload containing \`displayPanels\`.
- UI v5 integration order is *live-profile -> manual-scaling -> UI consolidation -> smart-update -> finalize-ui-v4 -> finalize-ui-v5*. Recheck this order and pin before integration. Avoid the old panel POC in the same trial.

## Implementation slices after UI acceptance

**S0 — read-only instrumentation**: add a single new authenticated \`POST /api/live-lab\` route and delegate into a transient LabController, with \`op=status\`. Report session generation, armed status, remaining command budget, experimental sender capability, and sanitized counters. Never reveal token, MFi material, display UUID, navigation URLs or pairing identifiers. Add UTC timestamps and monotonic timing.

**S1 — local safety gate**: integrate \`staging/LiveLabGate.kt\` (unit tests in \`staging/LiveLabGateTest.kt\`) under package \`io.github.numberonebot.chairplay.livelab\`. An explicit \`arm\` operation requires a live session and local operator opt-in; arm expires in 10 minutes, at 12 writes, on session change, on disconnect or when disarmed. No persistent settings; no auto retry or network listener beyond the existing authenticated localhost server. Commands execute sequentially on \`touchSender\`, with a final identity/generation check *inside* the executor before writing.

**S2 — evidence adaptor (no speculative wire format)**: bind a narrow native sender interface only after checking the exact DiPlay/AirPlay API and the negotiated, complete **live** /info value. \`updateInfo\` must replace only the single Type111 zoomFactor, retain every other field, preserve current UUID, reject DDP overlap and unknown topology, and log outbound CSeq/response status when the lower layer provides them. \`stopUI\` / \`showUI\` target the already-negotiated Type111 UUID via existing session APIs. Never send arbitrary caller-supplied plist, UUID, URLs, RTSP, socket closes or transport teardown.

**S3 — tests/rollout**: integrate after UI v5 passes owner acceptance. Unit checks for auth rejection, fail-closed defaults, duplicated UUID, Type110 unchanged, disarmed/reconnect session mismatch, command quotas, race at executor dequeue, serialization, privacy and status. CI compiles the patch; run first live at 100% parked/bench only, take positive-control full reconnect 70%, then one P3 run. Record JAR hash and source SHA.

## Endpoint contract (future; NOT currently implemented)

Existing localhost host/token/CORS/size protections must remain active. **Only POST**, JSON objects, no arbitrary properties:

| Request | Result |
| --- | --- |
| \`{"op":"status"}\` | \`{"state":"NOT_ARMED","sessionActive":true,"generation":"opaque-per-session","armed":false,"remaining":12,"capabilities":["showUI","stopUI"],"ack":"NOT_OBSERVED"}\` |
| \`{"op":"arm","confirm":"LIVE_LAB_LOCAL"}\` | \`{"state":"ARMED",...}\`; local, per-session, time-limited |
| \`{"op":"disarm"}\` | \`{"state":"NOT_ARMED",...}\`; safe even after disconnect |
| \`{"op":"command","command":"showUI","expectedGeneration":"..."}\` | only if active + armed; return \`LOCAL_SENT\` or \`REJECTED\` / \`NOT_SUPPORTED\` |
| \`{"op":"command","command":"stopUI","expectedGeneration":"..."}\` | same |
| \`{"op":"command","command":"updateInfo","zoomPercent":70,"expectedGeneration":"..."}\` | initial zoom allowlist **70, 100 only**; Type111 only, complete negotiated /info, no DDP |

A \`LOCAL_SENT\` response says only the socket write was attempted/succeeded; \`ack: NOT_OBSERVED\` unless an actual correlated response was captured. A scene repaint or screenshot is not equivalent to a re-negotiation.

All mutating requests must be refused if lab not explicitly armed, no active session, mismatch, cooldown/quota exceeded, missing negotiated baseline, DDP conflict, unexpected payload shape or interface unavailable. The server must not silently switch to full reconnect or close Type111.

## Local Codex client

\`labctl.py\` is Python standard library, so no additional service or Python packages are necessary. Before integration it can validate the test plan offline:

\`\`\`powershell
python projects/chairplay-skoda-vc-eval/live-lab/labctl.py check projects/chairplay-skoda-vc-eval/live-lab/scenarios/p3-updateinfo70.json
\`\`\`

After a reviewed LabController is integrated in a **separate** Windows build, get the ChairPlay URL from its own UI/log and set \`CHAIRPLAY_UI_URL\` locally without committing it. \`python labctl.py status\` performs an authenticated health probe. \`python labctl.py run scenarios/p3-updateinfo70.json --confirm-live\` is deliberately explicit and will refuse if the server is not armed or its session changes. No command is sent by running \`check\`.

Do not put tokens or screenshots into public CI/artifacts. Keep a redacted JSONL audit file under a chosen local private directory. This client never claims it can observe a phone-side ACK without lower-layer instrumentation.

## Acceptance blockers

- Do **not** add this branch as a push trigger for existing ChairPlay Windows packaging workflows.
- Do **not** merge into the UI-v5 branch during active acceptance.
- Verify the exact \`AirPlaySession\` / DiPlay sender API, CSeq/reply callbacks and snapshot provenance before implementing S2.
- Confirm that \`displayPanels\` in actual /info does not make \`UpdateInfoScaleBuilder\` reject a legitimate baseline; never circumvent the guard by dropping legitimate descriptors without an independent schema audit.
- Manual sign-off: full-session fallback, 100% restoration, no persistent token leakage, screenshots before/after, no Type110 interruption.

Research links: [P1–P4 audit](https://github.com/CaneTLOTW/M.I.B._Research/blob/861507d96614ad59cbbe342c929ae89684d1e9f8/projects/chairplay-skoda-vc-eval/analysis/IOS27_2_P1_P4_SOFT_RECONNECT_REVIEW_2026-11-07.md), [Research Issue #129](https://github.com/CaneTLOTW/M.I.B._Research/issues/129).
