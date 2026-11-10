# MIB2 Skoda ChairPlay – native integration status

**2026-11-10: NATIVE SOURCE INTEGRATED / CI PASS / LIVE_UNVERIFIED / NOT RELEASED**

## Confirmed result

The combined P6 / Skoda Virtual Cockpit / UI v4-v5 baseline is committed as **native application code** on [`harman-f/ChairPlay:main`](https://github.com/harman-f/ChairPlay), not merely a build-time transformation of a separate checkout.

- [Native consolidation run #42906968812](https://github.com/harman-f/ChairPlay/actions/runs/42906968812): **success**. Pinned combined P6 patchchain PASS, tests and compiled UI/runtime guard markers PASS, materialization of native source PASS, **standalone Gradle `test jar` from the fork checkout PASS**, and fast-forward commit to `main` PASS.
- [Native source commit `6e5dc81382fc1d414303fb688b4c20367ab79ae1`](https://github.com/harman-f/ChairPlay/commit/6e5dc81382fc1d414303fb688b4c20367ab79ae1): combined Kotlin/WebUI/VC code, tests and native build, plus tracked DiPlay core.
- The prior DiPlay `upstream` gitlink was removed. `upstream` is now an ordinary tracked directory; `AirPlaySession.kt`, `AirPlayInfoPlist.kt` and required shared sources are present. See [vendored provenance](../upstream/VENDOR_PROVENANCE.md). Third-party licensing and upstream credits remain important.
- The older [Research PR #184](https://github.com/CaneTLOTW/M.I.B._Research/pull/184) pinned source patchchain and previous [successful Build-44 overlay CI](https://github.com/CaneTLOTW/M.I.B._Research/actions/runs/42532826506) remain as evidence and replay material, **not the canonical build path**.

## Original sources and attribution

- Original ChairPlay: https://github.com/NumberOneBot/ChairPlay — Alex Strelets / NumberOneBot
- Intermediate Škoda fork: https://github.com/zakklmv/ChairPlay — zakklmv
- Pinned Škoda ChairPlay base `fd7a22fa1f503695309ec9efad0e48b2d900349f`
- DiPlay core `28d6002ba00320f0ba745212160b08759e4f60b9` (2026-10-28), tracked as source, not an unmodified submodule.

## What CI does and does not establish

The successful native Windows CI establishes that source, Kotlin tests, Gradle packaging and selected generated UI/P6 guard checks pass. It **does not** establish live iPhone session behavior, real Type 111 setup/teardown renegotiation, on-car fidelity, or safe release status.

- [x] Consolidate P6, UI v4-v5, profiles, display geometry, safe areas and VC ViewArea runtime changes into source.
- [x] Integrate DiPlay shared core so the native ChairPlay build does not require a modified external submodule.
- [x] Successfully build and test native checkout, and push after successful checks.
- [x] Preserve Luna screenshot automation, API notes and historic source patchchain.
- [ ] Manual Windows UI acceptance for profiles/geometry, including 1010×376 versus 1440×540 fallback.
- [ ] Luna end-to-end capture `0 → 1 → 2 → 0` with two fresh stable PNGs per view and manifest validation on an actual iPhone session.
- [ ] Verify Stream 111 / VC behavior and correlate with live iOS/device evidence.
- [ ] Review local experimental Live-Lab/screenshot-route authentication before release.
- [ ] Add real UI screenshots from the Windows test environment.
- [ ] Separate experimental P8 `updateDisplayPanels` remove/re-add experiment **after** native baseline acceptance; it is **not** part of the consolidated P6 source.
- [ ] Issue a separately approved preview/release only after relevant checks.

## CI workflows

- [`chairplay-native-consolidate.yml`](../.github/workflows/chairplay-native-consolidate.yml) records the one-shot migration and successful test-before-commit process. Normal development should now use the native checked-in source and its regular Gradle build; do not rerun one-shot migration against an already consolidated `main` without deliberate review.
- [`mib2-skoda-combined.yml`](../.github/workflows/mib2-skoda-combined.yml) is retained as a pinned research patchchain reproduction workflow, not a prerequisite for the native build.
