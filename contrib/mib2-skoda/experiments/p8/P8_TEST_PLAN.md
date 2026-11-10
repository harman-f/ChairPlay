# P8 Test Plan: updateDisplayPanels variant B (remove + re-add secondary panel 111)

Status: **DRAFT, NOT EXECUTED, no device touched, nothing built.** Results go to `harman-f/mhi2_altscreen_carplay#159` (posted by the owner).

## Source provenance
- Fork (read-only clone): `https://github.com/harman-f/ChairPlay`, branch `main`, **base SHA `f6b122855ffd833d0dfe079493ce40383205a7c0`**.
- Patch: `patches/p8/0001-p8-panel-readd-probe.patch` (`git apply` on that base; adds `contrib/mib2-skoda/patchchain/panel-p8/{PanelReaddProbe.kt,apply_p8.py}`).
- Important: the fork `main` holds only the patchchain (Live-Lab staging, P6 ViewAreas), not native source. The variant-A probe (`PanelUpdateProbe.kt`, `updateDisplayPanels` with one panel) lives in Research branch `work/chairplay-update-display-panels-poc-20261106` (`patches/panel-poc/`). P7 = `scripts/apply_p7_area_zoom_probe.py` (Research branch `work/chairplay-p7-per-area-zoom-spike-20261108`). Live-Lab `updateInfo/showUI/stopUI` = `live-lab/staging/*` on the fork.
- `apply_p8.py <checkout>` edits `PanelUpdateProbe.kt` (3 unique anchors, fail-closed: stores the full DDP panel list, dispatches `p8*` modes) and adds `PanelReaddProbe.kt`. Offline check: applied to the panel-poc `PanelUpdateProbe.kt`, anchors unique. **Not compiled** (no JDK/Gradle); a Kotlin compile + unit test of `PanelReaddProbe.build` is still required.
- Build: workflow `.github/workflows/mib2-skoda-combined.yml` (fork; workflow_dispatch/push on contrib/**). Do NOT trigger without owner OK; it does not yet include panel-poc or P8, so a combined build must first apply panel-poc then `apply_p8.py` (not yet scripted).

## Prerequisites
1. Build with panel-poc + P8 applied; record JAR SHA-256 and source SHAs. Keep known-good JAR for rollback.
2. Launch with `CHAIRPLAY_P8=1` (optional `CHAIRPLAY_P8_DELAY_MS`, default 500, 100..5000; `CHAIRPLAY_P8_ZOOM` 70|100, default = opposite of advertised).
3. PanelUpdateProbe enabled, then one full CarPlay reconnect so `/info` contains `displayPanels` (110 + 111). Baseline `zoomFactor` 100. DDP conflicts with the Live-Lab `updateInfo` path: do not mix in one session.
4. Type111 map view visible and stream 111 active (`stream111Active=true`). Screen/video recording of main display and cluster; baseline screenshot at zoom 100.
5. Log capture on, ChairPlay log plus (if available) pcap/AirPlay trace without body hex.

## Triggers (explicit, per session max 6 writes, serialized on touchSender)
| mode | action |
|---|---|
| `p8status` | no write; generation, write budget |
| `p8a` | updateDisplayPanels: only 110 entry (unchanged geometry, non-empty `videoStreams`); 111 removed |
| `p8b` | list 110 + 111, SAME UUID, non-empty `videoStreams`, new `zoomFactor` (70 vs 100) |
| `p8run` | a, delay (default 500 ms), b: the P8 experiment |
| `p8c` | like p8run but NEW random 111 UUID (uid and stream uuid); H2 isolate, only after p8run result |
| `p8abort` | resend original full list (110 + 111, original zoom); always allowed |

## Steps
1. `p8status`, record baseline: stream111SetupCount (expected 1), main frame ticking, screenshot.
2. `p8run`. Observe 10 s. Log lines `P8 t=... step=begin|sent-a|pre-readd|sent-b|post+2s` with `stream111SetupCount`, `stream111Active`, `mainFrameRendered`, `ack=NOT_OBSERVED`.
3. Screenshot of cluster + main; compare zoom 70 vs 100 against baseline.
4. `p8abort`, confirm original state or full reconnect (positive control).
5. Only if run 2 shows no re-setup: optionally `p8c` after fresh reconnect.

## Pass / fail
- PASS (hypothesis confirmed): TEARDOWN of stream 111 and SETUP of 111 observed (ChairPlay/AirPlay log type lists), stream111SetupCount 1 -> 2, stream 110 uninterrupted (no tearDown/setUp for 110, video continues, no frame gap beyond normal), visible zoom 70 vs 100 with before/after screenshot.
- PARTIAL: ACK-only or count unchanged with no visual change = LIVE_UNVERIFIED, not "ignored".
- FAIL: phone drops session, 110 interrupted, or new setup arrives for 110.
- Negative outcomes to record separately: no tearDown on removal (iOS ignores shorter list), tearDown but no re-setup on re-add (then try p8c), setup with stale zoom.

## What to log
UTC timestamps, session generation, local-write result, stream111SetupCount before/after, setup/teardown stream type lists, `/info` requests, main frame state, JAR/source SHAs. Known gaps: **CSeq/ACK correlation (P5 D4 design) is not implemented**, so ACK is always NOT_OBSERVED; the 110 frame count is only the boolean `mainFrameRendered`: continuity must be judged from the recording. Teardown/setup type-list logging depends on existing session logging; if absent, add a hook (not verified, submodule source not in fork).

## Abort criteria
Any unexpected disconnect, 110 freeze > 2 s, write failure, budget exhausted, or no visible recovery after `p8abort` -> full reconnect to known-good profile/JAR. No automatic retries.

## Approval
Owner authorization is required for build trigger, install, profile selection, reconnect and any phone-facing step.
