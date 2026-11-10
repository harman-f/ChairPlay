# P6 — ChairPlay Stream111: guarded live VC ViewAreas

**Status:** implementation candidate on a Draft PR, not a live iPhone validation. Based on pinned ChairPlay `fd7a22fa1f503695309ec9efad0e48b2d900349f`, DiPlay `28d6002ba00320f0ba745212160b08759e4f60b9`, Research UI v5 and token-free Live Lab.

## Actual baseline and delta

A source audit found that ChairPlay **already** sends `updateViewArea` with `AirPlayInfoPlist.ALT_UUID` through `AltscreenAreaMove`. More importantly, ChairPlay's `gradle/upstream.gradle.kts` *patches the compiled DiPlay serializer* to call `ClusterProfile.advertise(info)` when the profile is active. Thus the **active-profile** `/info` already carries each area's `adjacentViewAreas` from `ClusterProfile.displayEntry()`; the missing capability in that replacement dictionary was top-level `viewAreaTransitionControl=true`. The **generic/no-profile** DiPlay serializer, on the other hand, lacked the cluster adjacency list. This patch aligns both paths. The tests explicitly exercise both actual entry points rather than mistaking the generic pre-override dictionary for the live profile descriptor.

This patch closes that discrepancy without implementing a second sender:

1. In pinned DiPlay `AirPlayInfoPlist.displayEntry`, add `adjacentViewAreas` to **each generic** cluster (ALT_UUID) area, with the exact complementary indices; **main (Type110) areas are unchanged**.
2. Add the **missing** top-level `viewAreaTransitionControl=true` to the profile-specific replacement descriptor when multiple VC areas exist. Its per-area adjacency list was already present. No changes to zoomFactor, mm or pixel dimensions.
3. Guard `AltscreenAreaMove`: refuse missing/single-area capability, negative/out-of-range indices, and skip `showUI` on refused/sent-failed moves.
4. When an active local profile edit changes the VC frame or SafeArea set relative to the connection-time configuration, do **not** send a move until reconnect; a view-label or URL-only edit can continue to apply live.
5. A delayed, post-animation `showUI` callback is allowed only for the **same active AirPlaySession**, never a retired session.
6. Kotlin regression tests inspect **both** `AirPlayInfoPlist.build` with `ClusterProfile.active=null` (generic) **and** with the active MU1440 profile (post-override), plus Type110 isolation, seven neighbor sets, runtime guards and compatibility.

## Target scope and mappings

For built-in `mu1440-790` the negotiated 1010×376 VC display has seven named areas. Map-bearing CarViews **0, 1, 2 select indices 4, 5, 6** respectively; overlay-only Views 3/4 inherit the previous map area. The View button and the existing `Couple Controller` UI continue to drive the same `AltscreenView.show()` path. `zoomFactor` and physical-mm adjustments **still require an ordinary CarPlay reconnect**.

## CI and rollout

New isolated workflow: `.github/workflows/chairplay-vc-live-viewareas-windows.yml`. It composes the pinned baseline in order (live profile, manual scaling, UI consolidation, smart update, UI v4, UI v5, token-free Live Lab), **then** applies the VC patch. It runs `gradlew.bat test jar`, verifies markers, and packages **only** `app/chairplay.jar` as a manual optional patch relative to successful Build #44. No source-control merge or local installation is implied.

**Manual acceptance on Windows/iPhone:** record original JAR SHA and settings; verify `mu1440-790` active with a full connection; View0→1→2→0 and back; expect Type111 `updateViewArea` indices 4→5→6→4 with the cluster UUID, and Map/Map+Card visual geometry transitions. Verify Type110 continues, session generation stable, no new 111 SETUP, and restore after changing the active profile SafeArea only on a full reconnect. A `LOCAL_SENT` log is not an iOS ACK or visible PASS. Keep screenshots and raw logs locally, not in GitHub artifacts.

**Limits:** No live iPhone test performed. No native 70% DPI, no new receiver-triggered Stream111 SETUP, no dynamic modification of arbitrary ViewArea rectangles, no unauthorized socket close. CI PASS would establish source/tests/build only.
