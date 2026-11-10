# ChairPlay · Skoda MU1440 / AID10.5 · upstream-first Windows build

**Status 2026-11-04:** Rebased build on pristine `zakklmv/ChairPlay` `feature/skoda_790`, pinned to [`fd7a22fa1f50`](https://github.com/zakklmv/ChairPlay/commit/fd7a22fa1f503695309ec9efad0e48b2d900349f). Source code is not copied into this Research repository. Our two separately named MU1440 safe-area profiles remain included.

## Why the build changed

The upstream commits of 2026-11-03/04 added native cluster profiles, the Skoda VC schematic, View button / key V, GPX route playback, native `display.zoomFactor`, and `showCompass`. The Research build used 21 file overrides against an earlier feature-branch snapshot. Four of their original upstream blobs have since changed, so blindly applying the old overrides would discard upstream changes or fail their SHA guards.

The former source overrides, patch and apply-overrides script were **retired** rather than rebased. They remain recoverable in Git history at [`16592433f0e8`](https://github.com/CaneTLOTW/M.I.B._Research/commit/16592433f0e8c8af01797791abf93cb7f8261b4b). **Do not apply them to this upstream version.** This clean build is an intentional replacement, not a claim that every prior experimental feature reached upstream.

## Scope and behavior

- Exact upstream revision: `UPSTREAM_REVISION.txt`.
- No user credentials, MFi files, pairing data, custom APK certificates, or firmware go into Git/CI artifacts.
- Source-controlled experimental profiles: `profiles/mu1440-790-safeareas.json` and `profiles/mu1440-790-map-only.json`, preserving Type-111, 1010 x 376, 40 fps, 202 x 75 mm.
- Areas 4/5/6 remain **research candidate** safe rectangles, not proven pixel-perfect by iPhone testing: `[372,58,266,249]`, `[40,58,930,216]`, `[290,61,430,245]`. Upstream built-in `mu1440-790` uses its own **300 x 112 mm** physical size, **zoomFactor 85**, and as of `fd7a22fa` its own modified 4/5/6 areas `[364,110,280,205]`, `[100,56,800,245]`, `[205,90,610,220]`. Our separate `*-safeareas` / `*-map-only` profiles are intentionally left unchanged for A/B geometry comparison.
- Upstream understands `display.zoomFactor` as a **number** between 25 and 400; omit it to leave zoomFactor out of the iOS descriptor. Our two profiles omit both the legacy `"AUTO"` string and Research-only `physicalPreset` metadata to be fully compatible with upstream.
- Upstream's `View` button and `V` key, cluster editor, `showCompass`, and `zoomFactor` are retained exactly as upstream implemented them.
- **No longer in active build:** Research-specific F6 OEM-guidance toggle and UI button, bespoke BASE/P20/P30/P50 physical presets, research-only reconnect button, explicit negotiated-area guard, and oversized Controls window. Upstream has its own reconnect (`Ctrl+R`), view navigation and editing features. Reintroduce any missing functionality as small audited changes **after** live iPhone acceptance, rather than overwriting entire upstream files.

## Build and use

The GitHub Actions job checks out upstream at the pinned SHA, applies a **test-harness-only Vitest timeout of 15 seconds** via `scripts/prepare-webui-tests.ps1` (no production code changes), runs upstream JVM and Web UI tests, builds `ChairPlay.exe` on `windows-latest`, and adds the two separate test profiles into a downloadable ZIP.

On Windows with Git and JDK 17, run `scripts\build-on-windows.cmd` from this Research project. It fetches upstream, **force-checks out the exact pinned SHA only inside this project's dedicated `local\ChairPlay` directory**, builds and launches it. Previously modified **tracked source files in that dedicated checkout are overwritten**. The script deliberately does not run `git clean` or erase untracked local MFi/pairings/settings, and it does not change another clone in Visual Studio / VS Code or an installation elsewhere on the PC.

To update an existing independent IDE checkout, the user must run a separate Git action on their own PC. Our GitHub CI runner's clone and Research source-only patch set were never a remotely controlled clone in the user's Windows Visual Studio.

After opening, select the MU1440 profile on the AltScreen settings page, connect the iPhone, then test views 0/1/2 with Apple Maps, Google Maps and Waze. Descriptor changes (areas, scale and physical mm) require reconnect (`Ctrl+R`). Physical iPhone tests, UI fidelity and iOS `zoomFactor` acceptance are not yet proven.

Further geometry notes: [analysis/CALIBRATION.md](analysis/CALIBRATION.md); latest handoff: [Issue #163](https://github.com/CaneTLOTW/M.I.B._Research/issues/163).

## Upstream refresh 2026-11-04 evening

Pinned to `fd7a22fa` after upstream commits `3317a8d` (standalone Settings window) and `fd7a22fa` (built-in MU1440 profile: zoomFactor 85, revised safe-area rectangles, View 2 speed limit and top-aligned maneuvers). The separate Research geometry profiles are kept intact for comparison; Windows CI always checks out and builds the full pinned upstream including these commits. No Research source overrides.

## Live navigation controls patch (2026-11-04)

The unmodified upstream `fd7a22fa` had a concrete control-plane gap: clicking Scene / ETA / Speed limit / Compass / Turn card only changed editor state until Save, and even saving the active profile updated `CarViews.profile` without calling `AltscreenView.show(active())` to deliver `setClusterUrl` to the connected iPhone. The SHA-guarded `scripts/apply-live-profile-patch.ps1` now applies a small, reviewable runtime patch to **six** transient checkout files (Kotlin source + dedicated regression, TS UI source + dedicated regression), before tests/build. This is not the old monolithic overwrite approach: fail closed on upstream drift.

For the selected **active** profile, the five URL options now immediately save (serialized so quick successive clicks preserve order) and request the updated URL on the current CarPlay session, without a physical reconnection. For another edited profile, modifications remain staged until Save. Changes to safe area, native scale and physical mm still require reconnect; an iOS navigation app can ignore an option even when ChairPlay successfully sends the URL. The editor's `Car view` selects the view **being edited**, not the current simulated VC view. Choose the matching actual VC view using `V` / View to see its changed URL.

## Iteration 1: Manual setup and combined Scaling (2026-11-04)

- Research-only incremental patch: `scripts/patches/manual-scaling-v1.patch`, applied **after** the existing live-URL fix; original upstream source remains pinned to `fd7a22fa`. No older monolithic source overrides are reintroduced.
- With an **active, matching car profile**, the old separate Frame/Physical Size/Zoom controls are relocated into the original Size-selector style under **Manual setup** plus **Scaling**. The profile's JSON is the source of truth and settings persist automatically.
- `Physical size` is an unscaled reference. `Physical zoom` of 70/85/100/125/150% computes `effective mm = round(reference mm × 100 / physical zoom)`, independently of `display.zoomFactor` (Auto or numeric).
- Both effective mm and `zoomFactor` are advertised to iOS on the next CarPlay connection. A new **Reconnect CarPlay** button calls the same backend method as the main Toolbar and waits for pending profile saves.
- Without a profile, the original native Manual Setup remains and gains an explicit Custom size choice; this first iteration does **not** yet add physical-size/zoomFactor overrides in generic no-profile mode.
- Safe areas, Appearance, MFi/pairings and built-in presets are not changed. New tests cover the combined descriptor and the mirrored reconnect action.
- Manual test still required: verify iOS picks up the changed `widthPhysical`, `heightPhysical`, and `zoomFactor`; a successful build alone does not prove an app's visual response.
