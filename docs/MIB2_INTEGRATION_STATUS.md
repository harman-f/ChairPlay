# MIB2 Skoda ChairPlay integration tracker

**2026-11-09 status: INCOMPLETE / NOT RELEASED / LIVE_UNVERIFIED**

The fork's `main` currently contains the upstream ChairPlay base, fork README, Luna automation runner/offline tests/API notes, and a **staged** geometry patch script. It **does not yet contain** the complete combined ChairPlay v4/v5/P6 application source or a validated native fork build. Do not infer functionality of the successful separate research CI artifact from the source on this branch.

## Source lineage

- Original project: https://github.com/NumberOneBot/ChairPlay
- Intermediate Skoda fork: https://github.com/zakklmv/ChairPlay (development research based on `feature/skoda_790`)
- Research PR #177 base head: `382750222986fd56694442910cfb0c553feca4a1` (https://github.com/CaneTLOTW/M.I.B._Research/pull/177)
- Research PR #184 head: `117a2e2f51a7511dd994e829962f9aa5f38e29db` (https://github.com/CaneTLOTW/M.I.B._Research/pull/184)
- Research Windows overlay CI passed: https://github.com/CaneTLOTW/M.I.B._Research/actions/runs/42532826506 ; manual Build-44/JAR patch only

## Porting backlog

- [ ] Verify the pinned Skoda source base versus this fork's `main`.
- [ ] Port the complete ordered patch layers to native Kotlin, UI and test sources: v4/v5 consolidated UI, editable Vehicle Views and profiles, Display Geometry preset regression fix, Scaling/Safe Area, P6 ViewAreas and runtime negotiation/race guards.
- [ ] Integrate guarded and **disabled-by-default** Live Lab diagnostics; verify token-free screenshot route policy before production.
- [ ] Use the imported standard API Luna runner with verified authentication and local-only endpoint; do not conflate API response with iOS confirmation.
- [ ] Build and test the resulting fork source in its **own** CI; avoid substituting previous research-pipeline results.
- [ ] Validate Windows UI and iPhone end-to-end (profile 1010×376, fallback 1440×540, 0→1→2→0, two PNGs/view, stable hashes/manifest, Stream111 correlation).
- [ ] Add real UI screenshots to README after operator capture.
- [ ] Review prior to any upstream PR/release; preserve GPL-3.0, credits and source notices.

GitHub Issues are currently disabled for this fork; this in-repository tracker records the outstanding work.
