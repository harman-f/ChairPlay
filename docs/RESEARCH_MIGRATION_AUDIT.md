# ChairPlay Research migration audit

**Updated 2026-11-10. Scope:** the ChairPlay-specific material from 16 `work/chairplay-*` research branches in the private `CaneTLOTW/M.I.B._Research` repository. This does **not** mean the whole M.I.B. research repository is copied into ChairPlay.

## Canonical native source

**MIGRATED / BUILD PASS.** The combined approved P6 / UI v4-v5 / Luna geometry baseline, including the native Kotlin code, WebUI, tests and DiPlay shared core (formerly a Git submodule), is tracked directly on the fork's `main`. [Native CI #42906968812](https://github.com/harman-f/ChairPlay/actions/runs/42906968812) passed `gradlew test jar` against the native checkout and pushed [commit `6e5dc813`](https://github.com/harman-f/ChairPlay/commit/6e5dc81382fc1d414303fb688b4c20367ab79ae1). Native source now builds without the Research patchchain. See [DiPlay provenance](../upstream/VENDOR_PROVENANCE.md).

## Research material preserved in the fork

| Track | Destination | Status |
| --- | --- | --- |
| P0/P1, P6 development, calibration and guarded ViewAreas | [Research notes](research/), native `src/`, `webui/`, `upstream/shared/` | Code integrated; offline CI passed; live iOS causality not fully proven |
| P6 complete historical patchchain | [`contrib/mib2-skoda/patchchain/`](../contrib/mib2-skoda/patchchain/) | Archived for reproducibility; not needed for normal native build |
| Luna screenshot client and tests | [`automation/`](../automation/), [API document](CHAIRPLAY_LOCAL_AUTOMATION_API.md) | Source imported; device automation acceptance outstanding |
| Vehicle/cluster map-only and safe-area profiles | [fixtures](../contrib/mib2-skoda/fixtures/profiles/) | Imported as fixtures, not silently installed |
| Live Lab source and safety review | Native code, [historical source](../contrib/mib2-skoda/patchchain/live-lab/), [research notes](research/) | Native P6 included; security/release review remains open |
| **P7** hypothetical zoom per area | [P7](../contrib/mib2-skoda/experiments/p7/) | Patch script + isolated profile + original workflow + analysis archived; **not active in native app** |
| **P8** Type111 panel remove/re-add | [P8](../contrib/mib2-skoda/experiments/p8/) | Unit-side patch and test plan archived; not compiled or device-tested |
| P8 prerequisite `updateDisplayPanels` POC | [panel-poc](../contrib/mib2-skoda/experiments/panel-poc/) | Original variant and later UI-v4 variant/tests/manifests archived; not active in native app |
| Early Windows build script, branch workflows and analysis utilities | [research archive](../contrib/mib2-skoda/research-archive/) | Inactive archive, not executable CI under `.github/workflows/` |
| Protocol observations and historical acceptance | [protocol research summary](research/PROTOCOL_RESEARCH_INDEX.md) | Public-safe summary with precise private source references |

### P7: exact disposition

Research [PR #180](https://github.com/CaneTLOTW/M.I.B._Research/pull/180) remains **open and unmerged**. [Windows CI #42426831167](https://github.com/CaneTLOTW/M.I.B._Research/actions/runs/42426831167) passed. `CHAIRPLAY_P7_PROBE=A` adds hypothetical per-area Type111 `zoomFactor` values for view-area indices 4/5/6 (100/85/70), retaining display-level zoom. `B` uses the same per-area values while omitting global Type111 zoom. Both modes are startup-only, require separate CarPlay connections, and have no live validation. They were **not** included in the consolidated P6 native source.

Research Issue #181's iOS 27.2 analysis found no proven consumer of per-area zoom in the examined paths, but incomplete indirect/observer coverage means **UNKNOWN_DUE_TO_SOURCE_GAP**, not evidence of impossibility. P7 is therefore **LIVE_UNVERIFIED / DEFERRED**, rather than a confirmed solution or failure.

The archived P7 script still targets the **old pinned source commit** `fd7a22fa1f503695309ec9efad0e48b2d900349f`, with fail-closed anchors. It is **not directly executable on the current native fork `main`** without adapting source pinning and anchors. The separately archived P7 workflow likewise refers to private Research paths and is not an active fork CI workflow.

### P8: exact disposition

P8's later `work/chairplay-p8-panel-readd-20261110` branch carries the Unit-side patch for `p8a`, `p8b`, `p8run`, `p8c`, `p8abort`, and `p8status`. It needs `CHAIRPLAY_P8=1`, panel-POC advertisement, and an explicit command. No Kotlin compile, phone-facing test, or selective 111 SETUP/TEARDOWN effect has been established. Archived **does not mean integrated or approved for execution**. The native P6 app is deliberately unchanged.

## Intentionally retained only in private Research

Not copied into this public repository: personal/location-bearing iPhone/Windows screenshots, runtime logs or pairing/MFi material; third-party Apple iOS binary images and raw disassembly excerpts; private-device identifiers; ephemeral GitHub Actions binaries/ZIPs. They are not required for the fork's native application build. Keep the provenance links in the private Research repository instead of redistributing sensitive or third-party artifacts.

Research-only protocol observations and the operator's P6 acceptance findings are summarized [here](research/PROTOCOL_RESEARCH_INDEX.md). That summary does not imply a new experiment or independent verification.

## Remaining gates

- [x] Current native P6 build reproducible in the fork, with DiPlay source tracked.
- [x] P7, P8, and early panel POC preserved in separate version-controlled experimental directories.
- [x] Original profile fixtures, Live-Lab test and historical workflows archived.
- [ ] Adapt and independently test P7 against native `main` **only if explicitly reactivated**; currently deferred by evidence.
- [ ] Evaluate P8 independently after baseline UI and native test acceptance; no automatic enablement.
- [ ] Manual screenshot/geometry acceptance on the user's Windows/iPhone test system.
- [ ] Protocol response correlation, Type111 causality and security review before a public preview.
