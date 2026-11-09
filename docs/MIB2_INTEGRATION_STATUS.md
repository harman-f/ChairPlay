# MIB2 Skoda ChairPlay integration tracker

**2026-11-09 status: INCOMPLETE / NOT RELEASED / LIVE_UNVERIFIED**

The fork's `main` currently contains the upstream ChairPlay base, fork README, Luna automation runner/offline tests/API notes, a **staged** geometry patch script, and the complete 20-file pinned source patchchain from research PR #184 (verified on `main`). A dedicated [Windows CI reproduction workflow](../.github/workflows/mib2-skoda-combined.yml) has also been committed. Its successful execution in this fork has **not yet been verified**. It **does not yet contain** the complete combined ChairPlay v4/v5/P6 application source or a validated native fork build. Do not infer functionality of the successful separate research CI artifact from the source on this branch.

## Source lineage

- Original project: https://github.com/NumberOneBot/ChairPlay
- Intermediate Skoda fork: https://github.com/zakklmv/ChairPlay (development research based on `feature/skoda_790`)
- Research PR #177 base head: `382750222986fd56694442910cfb0c553feca4a1` (https://github.com/CaneTLOTW/M.I.B._Research/pull/177)
- Research PR #184 head: `117a2e2f51a7511dd994e829962f9aa5f38e29db` (https://github.com/CaneTLOTW/M.I.B._Research/pull/184)
- Research Windows overlay CI passed: https://github.com/CaneTLOTW/M.I.B._Research/actions/runs/42532826506 ; manual Build-44/JAR patch only

## Porting backlog

- [x] Verify source distinction: pinned Skoda source is `fd7a22fa1f503695309ec9efad0e48b2d900349f`, while this fork's default `main` is a different, diverged branch.
- [x] Preserve the 20-file research source patchchain in `contrib/mib2-skoda/patchchain/`, plus the separate last geometry patch under `contrib/mib2-skoda/patches/`.
- [x] Add `.github/workflows/mib2-skoda-combined.yml` to reproduce the ordered patches and run tests on the pinned Skoda source.
- [ ] Port the complete ordered patch layers to native Kotlin, UI and test sources: v4/v5 consolidated UI, editable Vehicle Views and profiles, Display Geometry preset regression fix, Scaling/Safe Area, P6 ViewAreas and runtime negotiation/race guards.
- [ ] Integrate guarded and **disabled-by-default** Live Lab diagnostics; verify token-free screenshot route policy before production.
- [ ] Use the imported standard API Luna runner with verified authentication and local-only endpoint; do not conflate API response with iOS confirmation.
- [ ] Obtain a successful run of `.github/workflows/mib2-skoda-combined.yml` in THIS fork. The workflow currently compiles a pinned clone with the locally versioned patchchain; it does **not** yet compile the native code from this fork's `main` without patch steps.
- [ ] Resolve the DiPlay `upstream` Git submodule changes from the P6 patchchain: changed files inside `upstream/shared` cannot simply be committed to the ChairPlay parent without an appropriate submodule revision/fork or a consciously reviewed vendored overlay.
- [ ] Once native source and submodule changes are integrated, build and test this fork's own checkout without source rewriting; avoid substituting the previous research-pipeline result.
- [ ] Validate Windows UI and iPhone end-to-end (profile 1010×376, fallback 1440×540, 0→1→2→0, two PNGs/view, stable hashes/manifest, Stream111 correlation).
- [ ] Add real UI screenshots to README after operator capture.
- [ ] Review prior to any upstream PR/release; preserve GPL-3.0, credits and source notices.

GitHub Issues are currently disabled for this fork; this in-repository tracker records the outstanding work.

## CI source-patch reproduction

[Workflow](../.github/workflows/mib2-skoda-combined.yml) is triggered by updates to its own file, patchchain or automation on `main` and supports manual dispatch. It checks out the fork for patch inputs, clones the **exact pinned** `zakklmv/ChairPlay` `feature/skoda_790` source, applies the same ordered patch layers and runs offline Luna, Live-Lab, Gradle/Kotlin/Vitest and compiled-marker checks. A successful run would produce a combined JAR artifact and source diff/status artifact; it is **not** native fork-main integration and **not** live iPhone acceptance. GitHub Actions execution/permissions for the new fork require verification.
