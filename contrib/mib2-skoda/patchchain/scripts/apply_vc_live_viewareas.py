#!/usr/bin/env python3
"""Fail-closed post-v5/Live-Lab patch for the existing Type111 ViewArea sender."""
from pathlib import Path
import subprocess
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_vc_live_viewareas.py <checkout>")
root = Path(sys.argv[1]).resolve()
project = Path(__file__).resolve().parents[1]
pin = (project / "UPSTREAM_REVISION.txt").read_text().strip()
head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
if pin != "fd7a22fa1f503695309ec9efad0e48b2d900349f" or head != pin:
    raise RuntimeError("VC_PIN_MISMATCH " + head)
changes = {}

def edit(path, old, new):
    f = root / path
    if not f.is_file():
        raise RuntimeError("VC_MISSING " + path)
    source = changes.get(path, f.read_text(encoding="utf-8"))
    n = source.count(old)
    if n != 1:
        raise RuntimeError("VC_ANCHOR_DRIFT " + path + " " + repr(old[:70]) + " count=" + str(n))
    changes[path] = source.replace(old, new)

C = "src/main/kotlin/io/github/numberonebot/chairplay/"
D = "upstream/shared/src/main/java/com/shilapi/xcertplay/airplay/"
T = "src/test/kotlin/io/github/numberonebot/chairplay/config/"

# Actual /info is generated in DiPlay, not in ClusterProfile.displayEntry.
edit(D + "AirPlayInfoPlist.kt",
     '        entry["viewAreas"] = areas?.map { areaDict(display, it, disableSafeArea) } ?: listOf(areaDict(display, null, disableSafeArea))\n',
     '''        entry["viewAreas"] = areas?.mapIndexed { index, area ->
            areaDict(display, area, disableSafeArea).toMutableMap().apply {
                if (uuid == ALT_UUID && areas.size > 1) {
                    put("adjacentViewAreas", areas.indices.filter { it != index })
                }
            }
        } ?: listOf(areaDict(display, null, disableSafeArea))
''')

# Keep the profile-only descriptor consistent with actual /info.
edit(C + "config/ClusterProfile.kt",
     '    ).apply { zoomFactor?.let { put("zoomFactor", it) } }\n',
     '''    ).apply {
        if (safeAreas.size > 1) put("viewAreaTransitionControl", true)
        zoomFactor?.let { put("zoomFactor", it) }
    }
''')

# Negative or out-of-range indices must never reach AirPlaySession.sendCommand.
edit(C + "config/AltscreenAreas.kt",
     '''    operator fun invoke(index: Int): Boolean {
        if (!send(altscreenViewAreaCommand(index, count()))) return false
        showView()
        return true
    }
''',
     '''    operator fun invoke(index: Int): Boolean {
        val n = count()
        if (n <= 1 || index !in 0 until n) return false
        if (!send(altscreenViewAreaCommand(index, n))) return false
        showView()
        return true
    }
''')

edit(C + "config/AltscreenAreas.kt",
     '/**\n * updateViewArea for the AltScreen: DiPlay',
     '''/** The iPhone still has the last negotiated geometry after a local profile edit. */
fun clusterGeometryMatchesNegotiated(negotiated: ClusterProfile?, live: ClusterProfile?): Boolean =
    when {
        negotiated == null -> live == null
        live == null -> false
        else -> negotiated.size == live.size && negotiated.safeAreas == live.safeAreas
    }

/** The stream begins at the connection's initial area, not a later profile edit. */
fun negotiatedInitialArea(negotiated: ClusterProfile?): Int = negotiated?.initialArea ?: 0

/** Deterministic control-plane plan shared by AltscreenView.show and JVM regression tests. */
enum class ClusterAreaDecision { SHOW, MOVE, WAIT, RECONNECT }

fun clusterAreaDecision(
    session: Boolean, seen: Boolean, requested: Int, current: Int,
    geometryMatches: Boolean, settling: Boolean,
): ClusterAreaDecision = when {
    !session || !seen -> ClusterAreaDecision.SHOW
    requested != current && !geometryMatches -> ClusterAreaDecision.RECONNECT
    requested != current -> ClusterAreaDecision.MOVE
    settling -> ClusterAreaDecision.WAIT
    else -> ClusterAreaDecision.SHOW
}

/** A settle completion and its actual showUI decision share the invalidation lock. */
class AreaMoveSettleGate {
    private var revision = 0L
    private var pending = false
    private var askRevision = 0L

    @Synchronized fun start(): Long { pending = true; ++askRevision; return ++revision }
    @Synchronized fun invalidate() { ++revision; ++askRevision; pending = false }
    @Synchronized fun invalidateAsk() { ++askRevision }
    @Synchronized fun nextAsk(): Long = ++askRevision
    /** VideoWindow.onBlack runs on its own view-ask thread, after show() returns. */
    @Synchronized fun dispatchAsk(ticket: Long, action: () -> Boolean): Boolean =
        if (ticket != askRevision) false else action()
    @Synchronized fun isPending(): Boolean = pending
    @Synchronized fun completeIfCurrent(ticket: Long, action: () -> Unit): Boolean {
        if (!pending || revision != ticket) return false
        pending = false
        action()
        return true
    }
}

/**
 * updateViewArea for the AltScreen: DiPlay''')

edit(C + "AltscreenView.kt",
     'import io.github.numberonebot.chairplay.config.altscreenTitle\n',
     'import io.github.numberonebot.chairplay.config.altscreenTitle\n'
     'import io.github.numberonebot.chairplay.config.clusterGeometryMatchesNegotiated\n'
     'import io.github.numberonebot.chairplay.config.negotiatedInitialArea\n'
     'import io.github.numberonebot.chairplay.config.AreaMoveSettleGate\n'
     'import io.github.numberonebot.chairplay.config.ClusterAreaDecision\n'
     'import io.github.numberonebot.chairplay.config.clusterAreaDecision\n')

edit(C + "AltscreenView.kt",
     'import java.util.concurrent.atomic.AtomicInteger\n',
     'import java.util.concurrent.atomic.AtomicInteger\n'
     'import java.util.concurrent.atomic.AtomicLong\n')

edit(C + "AltscreenView.kt",
     '    private val currentArea = AtomicInteger(0)\n',
     '    private val currentArea = AtomicInteger(0)\n'
     '    private val areaSettleGate = AreaMoveSettleGate()\n'
     '    private val streamGeneration = AtomicLong(0)\n'
     '    @Volatile private var streamResetPending = false\n')

# Every show request retires any earlier VideoWindow.onBlack callback, even
# if the new request is a blocked move or still settling.
edit(C + "AltscreenView.kt",
     '        val cards = cards\n',
     '        val cards = cards\n'
     '        if (streamResetPending && session != null) return\n'
     '        areaSettleGate.invalidateAsk()\n')

edit(C + "AltscreenView.kt",
     '''        if (session != null && seen && area != currentArea.get()) {
            val moved = AltscreenAreaMove(
''',
     '''        // HUD/hidden transitions must send stopUI promptly, never behind a stale settle.
        if (hud || !seen) areaSettleGate.invalidate()
        val geometryPendingReconnect = session != null &&
            !clusterGeometryMatchesNegotiated(declared.get().clusterProfile, carViews.profile)
        val decision = clusterAreaDecision(session != null, seen, area, currentArea.get(),
            !geometryPendingReconnect, areaSettleGate.isPending())
        when (decision) {
            ClusterAreaDecision.WAIT -> {
                window.setTitle(altscreenTitle(alt.size, content, cards, carViews.title()) + " (area settling)")
                changed()
                return
            }
            ClusterAreaDecision.RECONNECT -> {
                areaSettleGate.invalidate()
                log("altscreen Type111 geometry was not negotiated; reconnect required")
                window.setTitle(altscreenTitle(alt.size, content, cards, carViews.title()) +
                    " (area not applied; reconnect required)")
                changed()
                return
            }
            else -> Unit
        }
        if (decision == ClusterAreaDecision.MOVE && session != null) {
            val moved = AltscreenAreaMove(
''')

edit(C + "AltscreenView.kt",
     '''                if (window.hud && !hud) window.showView(false, seen)
                return
            }
        }
        // Going to or from the HUD''',
     '''                if (window.hud && !hud) window.showView(false, seen)
                return
            }
            // A refused request cannot claim the new view or send showUI.
            areaSettleGate.invalidate()
            log("altscreen Type111 area change refused or not sent; keeping area " + currentArea.get())
            window.setTitle(altscreenTitle(alt.size, content, cards, carViews.title()) +
                " (area not sent)")
            changed()
            return
        }
        // Going to or from the HUD''')

# Even when the requested area index is unchanged, an edited SafeArea remains
# unnegotiated. Keep URL/name edits working, but mark the pending geometry.
edit(C + "AltscreenView.kt",
     '            window.setTitle(altscreenTitle(alt.size, content, cards, carViews.title()) + if (sent == false) " (not sent)" else "")\n',
     '            window.setTitle(altscreenTitle(alt.size, content, cards, carViews.title()) +\n'
     '                when {\n'
     '                    sent == false -> " (not sent)"\n'
     '                    geometryPendingReconnect -> " (geometry pending reconnect)"\n'
     '                    else -> ""\n'
     '                })\n')

# VideoWindow.showView defers onBlack to a separate "view-ask" thread:
# validation at the timer stage alone does NOT protect the actual showUI.
# Give each published callback a generation and gate the eventual send.
edit(C + "AltscreenView.kt",
     '        window.showView(hud, seen) {\n            val sent = session?.let { ui.tell(AltscreenUi.of(it), url, seen, key = it) }\n',
     '''        val askTicket = areaSettleGate.nextAsk()
        val streamAtAsk = streamGeneration.get()
        window.showView(hud, seen) {
            areaSettleGate.dispatchAsk(askTicket) {
                if (streamGeneration.get() != streamAtAsk || active() !== session ||
                    (streamResetPending && session != null)) return@dispatchAsk false
                val sent = session?.let { ui.tell(AltscreenUi.of(it), url, seen, key = it) }
''')

edit(C + "AltscreenView.kt",
     '''            (seen && drawing == url).also { drawing = url.takeIf { seen } }
        }
        changed()
''',
     '''                (seen && drawing == url).also { drawing = url.takeIf { seen } }
            }
        }
        changed()
''')

edit(C + "AltscreenView.kt",
     '                showView = {\n                    areaTimer.schedule({ runCatching { touchSender.execute { show(session) } } }, AREA_MOVE_SETTLE_MILLIS, TimeUnit.MILLISECONDS)\n                },\n',
     '''                showView = {
                    val ticket = areaSettleGate.start()
                    val streamAtSend = streamGeneration.get()
                    areaTimer.schedule({
                        runCatching {
                            touchSender.execute {
                                if (active() === session && streamGeneration.get() == streamAtSend) {
                                    areaSettleGate.completeIfCurrent(ticket) {
                                        if (active() === session && streamGeneration.get() == streamAtSend) show(session)
                                    }
                                }
                            }
                        }
                    }, AREA_MOVE_SETTLE_MILLIS, TimeUnit.MILLISECONDS)
                },
''')

edit(C + "AltscreenView.kt",
     '''        ui.newStream()
        runCatching {
            touchSender.execute {
                // It starts in the first view area again, as on the initial view; the view goes back to its own.
                currentArea.set(carViews.profile?.initialArea ?: 0)
''',
     '''        val streamAtEvent = synchronized(areaSettleGate) {
            areaSettleGate.invalidate()
            streamResetPending = true
            streamGeneration.incrementAndGet()
        }
        ui.newStream()
        runCatching {
            touchSender.execute {
                if (streamGeneration.get() != streamAtEvent) return@execute
                streamResetPending = false
                // The phone starts from the descriptor negotiated for this connection.
                currentArea.set(negotiatedInitialArea(declared.get().clusterProfile))
''')

edit(C + "AltscreenView.kt",
     '    fun connected(now: DesktopConfig) {\n        areaCount.set(now.altscreenAreaCount)\n',
     '    fun connected(now: DesktopConfig) {\n        synchronized(areaSettleGate) {\n            areaSettleGate.invalidate()\n            streamResetPending = false\n            streamGeneration.incrementAndGet()\n        }\n        areaCount.set(now.altscreenAreaCount)\n')

edit(C + "AltscreenView.kt",
     '    fun sessionGone() {\n        runCatching { touchSender.execute { show(null) } }\n',
     '    fun sessionGone() {\n        synchronized(areaSettleGate) {\n            areaSettleGate.invalidate()\n            streamResetPending = false\n            streamGeneration.incrementAndGet()\n        }\n        runCatching { touchSender.execute { show(null) } }\n')

edit(T + "ClusterProfileTest.kt",
     '    // /info\'s cluster display is the profile\'s, the main screen untouched; without a profile nothing changes.\n',
     '''    @Test
    fun negotiatedInfoHasClusterNeighborIndicesAndTransitionControl() {
        val cfg = configWith("altscreen.enabled=true", "altscreen.profile=mu1440-790")
        // ChairPlay's Gradle copy additionally applies ClusterProfile.advertise.
        // Test both the generic serializer AND the actual active-profile override.
        ClusterProfile.active = null
        val generic = AirPlayInfoPlist.build(cfg.airPlay)["displays"] as List<*>
        val genericAreas = (generic[1] as Map<*, *>)["viewAreas"] as List<*>
        assertEquals(listOf(0, 1, 2, 3, 5, 6),
            (genericAreas[4] as Map<*, *>)["adjacentViewAreas"])
        ClusterProfile.active = cfg.clusterProfile
        val displays = AirPlayInfoPlist.build(cfg.airPlay)["displays"] as List<*>
        val main = displays[0] as Map<*, *>
        val vc = displays[1] as Map<*, *>
        assertEquals(110, main["type"])
        assertEquals(111, vc["type"])
        assertEquals(AirPlayInfoPlist.ALT_UUID, vc["uuid"])
        assertEquals(true, vc["viewAreaTransitionControl"])
        val areas = vc["viewAreas"] as List<*>
        assertEquals(7, areas.size)
        areas.forEachIndexed { index, area ->
            area as Map<*, *>
            assertEquals(areas.indices.filter { it != index }, area["adjacentViewAreas"])
            assertEquals(1010, area["widthPixels"])
            assertEquals(376, area["heightPixels"])
            assertTrue("safeArea" in area)
        }
        assertTrue((main["viewAreas"] as List<*>).all { "adjacentViewAreas" !in (it as Map<*, *>) })
        assertEquals(true, builtIn.displayEntry()["viewAreaTransitionControl"])
        assertEquals(85, vc["zoomFactor"])
    }

    // /info's cluster display is the profile's, the main screen untouched; without a profile nothing changes.
''')

edit(T + "AltscreenAreasTest.kt",
     '''    // DiPlay's updateViewArea, which it sends for the main screen alone, addressed to the AltScreen.
''',
     '''    @Test
    fun invalidAreasNeverSendACommand() {
        val sent = mutableListOf<Map<String, Any?>>()
        val zero = AltscreenAreaMove({ 0 }, { sent.add(it); true }, {})
        val one = AltscreenAreaMove({ 1 }, { sent.add(it); true }, {})
        val three = AltscreenAreaMove({ 3 }, { sent.add(it); true }, {})
        assertEquals(false, zero(0))
        assertEquals(false, one(0))
        assertEquals(false, three(-1))
        assertEquals(false, three(3))
        assertEquals(emptyList<Map<String, Any?>>(), sent)
    }

    @Test
    fun unnegotiatedProfileGeometryNeedsReconnect() {
        val source = ClusterProfiles.builtIn("mu1440-790")!!
        val negotiated = ClusterProfile.parse("base", source)
        val labelEdit = ClusterProfile.parse("edit", source.replace("View 0", "Full"))
        val geometryEdit = ClusterProfile.parse("edit", source.replace("\\"width\\": 1010", "\\"width\\": 1012"))
        assertEquals(true, clusterGeometryMatchesNegotiated(negotiated, labelEdit))
        assertEquals(false, clusterGeometryMatchesNegotiated(negotiated, geometryEdit))
        assertEquals(false, clusterGeometryMatchesNegotiated(negotiated, null))
        assertEquals(false, clusterGeometryMatchesNegotiated(null, labelEdit))
        assertEquals(true, clusterGeometryMatchesNegotiated(null, null))
    }

    @Test
    fun streamStartsAtNegotiatedAreaEvenIfLiveProfileInitialViewChanges() {
        val source = ClusterProfiles.builtIn("mu1440-790")!!
        val negotiated = ClusterProfile.parse("base", source)
        val live = ClusterProfile.parse("edited", source.replace("\\"initialView\\": 0", "\\"initialView\\": 1"))
        assertEquals(4, negotiatedInitialArea(negotiated))
        assertEquals(5, live.initialArea)
        assertEquals(true, clusterGeometryMatchesNegotiated(negotiated, live))
        assertEquals(0, negotiatedInitialArea(null))
    }

    @Test
    fun onlyLatestMoveCallbackMayFinishAndStreamChangesInvalidateIt() {
        val gate = AreaMoveSettleGate()
        val first = gate.start()
        val second = gate.start()
        assertEquals(true, gate.isPending())
        val shown = mutableListOf<String>()
        assertEquals(false, gate.completeIfCurrent(first) { shown += "stale" })
        assertEquals(true, gate.isPending())
        assertEquals(true, gate.completeIfCurrent(second) { shown += "latest" })
        assertEquals(listOf("latest"), shown)
        assertEquals(false, gate.isPending())
        assertEquals(false, gate.completeIfCurrent(second) { shown += "duplicate" })
        val stale = gate.start()
        gate.invalidate()
        assertEquals(false, gate.completeIfCurrent(stale) { shown += "disconnected" })
        assertEquals(listOf("latest"), shown)
        assertEquals(false, gate.isPending())
    }

    @Test
    fun rapidAreaChangesRejectOldSettlesAndNeverShowFailedOrUnnegotiatedTarget() {
        val gate = AreaMoveSettleGate()
        val sends = mutableListOf<Int>()
        val shows = mutableListOf<Int>()
        var current = 4
        fun choose(requested: Int, accepted: Boolean): Long? {
            val action = clusterAreaDecision(true, true, requested, current, true, gate.isPending())
            if (action == ClusterAreaDecision.WAIT) return null
            if (action == ClusterAreaDecision.SHOW) { shows += requested; return null }
            assertEquals(ClusterAreaDecision.MOVE, action)
            var ticket: Long? = null
            val moved = AltscreenAreaMove(
                count = { 7 },
                send = {
                    sends += (it["params"] as Map<*, *>)["viewAreaIndex"] as Int
                    accepted
                },
                showView = { ticket = gate.start() },
            )(requested)
            if (moved) current = requested else gate.invalidate()
            return ticket
        }
        val b = choose(5, true)!!
        assertEquals(ClusterAreaDecision.WAIT,
            clusterAreaDecision(true, true, 5, current, true, gate.isPending()))
        val c = choose(6, true)!!
        assertEquals(false, gate.completeIfCurrent(b) { shows += 5 })
        assertEquals(6, current)
        assertEquals(true, gate.completeIfCurrent(c) { shows += 6 })
        assertEquals(listOf(5, 6), sends)
        assertEquals(listOf(6), shows)
        assertEquals(null, choose(4, false))
        assertEquals(6, current)
        assertEquals(listOf(6), shows)
        assertEquals(listOf(5, 6, 4), sends)
        assertEquals(ClusterAreaDecision.RECONNECT,
            clusterAreaDecision(true, true, 4, current, false, false))
        assertEquals(ClusterAreaDecision.SHOW,
            clusterAreaDecision(true, true, 6, current, false, false))
    }

    @Test
    fun hudAndNewStreamCancelOutstandingSettleWithoutNewShow() {
        val gate = AreaMoveSettleGate()
        val shown = mutableListOf<Int>()
        val a = gate.start()
        // The hidden/HUD path must process its stopUI instead of blocking on WAIT.
        assertEquals(ClusterAreaDecision.SHOW,
            clusterAreaDecision(true, false, 5, 5, true, gate.isPending()))
        gate.invalidate() // HUD transition
        assertEquals(false, gate.completeIfCurrent(a) { shown += 5 })
        val b = gate.start()
        gate.invalidate() // same-session new 111 stream
        assertEquals(false, gate.completeIfCurrent(b) { shown += 6 })
        val c = gate.start()
        gate.invalidate() // disconnect/connected
        assertEquals(false, gate.completeIfCurrent(c) { shown += 4 })
        assertEquals(emptyList<Int>(), shown)
    }

    @Test
    fun videoWindowBlackCallbacksCheckActualSendGeneration() {
        val gate = AreaMoveSettleGate()
        val sent = mutableListOf<String>()
        val old = gate.nextAsk()
        val newer = gate.nextAsk() // fast View A -> View B
        assertEquals(false, gate.dispatchAsk(old) { sent += "stale A"; true })
        assertEquals(true, gate.dispatchAsk(newer) { sent += "B"; true })
        assertEquals(listOf("B"), sent)
        val beforeMove = gate.nextAsk()
        gate.start() // an area move retires any callback waiting for the old window
        assertEquals(false, gate.dispatchAsk(beforeMove) { sent += "old view"; true })
        val afterMove = gate.nextAsk()
        gate.invalidate() // new 111 stream, disconnect, or HUD transition
        assertEquals(false, gate.dispatchAsk(afterMove) { sent += "old stream"; true })
        val fresh = gate.nextAsk()
        gate.invalidateAsk() // next requested view (even while WAIT)
        assertEquals(false, gate.dispatchAsk(fresh) { sent += "superseded"; true })
        assertEquals(listOf("B"), sent)
    }

    // DiPlay's updateViewArea, which it sends for the main screen alone, addressed to the AltScreen.
''')

for path, required in {
    C + "config/AltscreenAreas.kt": ['"uuid" to AirPlayInfoPlist.ALT_UUID', '"viewAreaIndex" to index'],
    D + "AirPlayInfoPlist.kt": ['if (areas != null && areas.size > 1) entry["viewAreaTransitionControl"] = true'],
}.items():
    data = changes.get(path, (root / path).read_text(encoding="utf-8"))
    for marker in required:
        if marker not in data:
            raise RuntimeError("VC_REQUIRED_MISSING " + path + " " + marker)

for path, data in changes.items():
    (root / path).write_text(data, encoding="utf-8", newline="\n")
    print("VC_PATCH_OK " + path)
print("VC_PATCH_PASS " + str(len(changes)))
