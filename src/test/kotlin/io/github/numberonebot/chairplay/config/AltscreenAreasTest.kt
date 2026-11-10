package io.github.numberonebot.chairplay.config

import com.shilapi.xcertplay.airplay.AirPlayInfoPlist
import com.shilapi.xcertplay.airplay.AirPlayViewArea
import org.junit.Assert.assertEquals
import org.junit.Test

class AltscreenAreasTest {
    // The parts a view can show in, for an 8:3 cluster: the whole frame; five eighths at the left, the middle or the
    // right; four eighths, a half, at the left, the middle or the right; three eighths at the left, the middle or the
    // right, between dials or in a side panel. All of the full height.
    @Test
    fun `the parts are the whole frame and parts of its eighths`() {
        assertEquals(
            listOf(
                AirPlayViewArea(1920, 720),
                AirPlayViewArea(1200, 720), AirPlayViewArea(1200, 720, originX = 360), AirPlayViewArea(1200, 720, originX = 720),
                AirPlayViewArea(960, 720), AirPlayViewArea(960, 720, originX = 480), AirPlayViewArea(960, 720, originX = 960),
                AirPlayViewArea(720, 720), AirPlayViewArea(720, 720, originX = 600), AirPlayViewArea(720, 720, originX = 1200),
            ),
            AreaPreset.entries.map { it.area(1920, 720) },
        )
        // A width keeps to a multiple of 8, as DiPlay's streams do, and the middle ones to an even origin.
        assertEquals(
            listOf(
                AirPlayViewArea(1440, 540),
                AirPlayViewArea(896, 540), AirPlayViewArea(896, 540, originX = 272), AirPlayViewArea(896, 540, originX = 544),
                AirPlayViewArea(720, 540), AirPlayViewArea(720, 540, originX = 360), AirPlayViewArea(720, 540, originX = 720),
                AirPlayViewArea(536, 540), AirPlayViewArea(536, 540, originX = 452), AirPlayViewArea(536, 540, originX = 904),
            ),
            AreaPreset.entries.map { it.area(1440, 540) },
        )
    }

    // Seen on an iPhone 15 Pro Max (AirPlay 870.14): after updateViewArea the AltScreen's view stays blurred, mid-way,
    // until it is asked for again with showUI; then it is drawn in the new area. So a move sends the area, then the view.
    @Test
    fun `a move sends the area, then asks for the view again`() {
        val sent = mutableListOf<String>()
        val move = AltscreenAreaMove(count = { 3 }, send = { sent += "area ${(it["params"] as Map<*, *>)["viewAreaIndex"]}"; true },
            showView = { sent += "view" })

        assertEquals(true, move(2))
        assertEquals(listOf("area 2", "view"), sent)
    }

    @Test
    fun `a move the iPhone did not get asks for no view`() {
        val sent = mutableListOf<String>()
        val move = AltscreenAreaMove(count = { 3 }, send = { false }, showView = { sent += "view" })

        assertEquals(false, move(1))
        assertEquals(emptyList<String>(), sent)
    }

    @Test
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
        val geometryEdit = ClusterProfile.parse("edit", source.replace("\"width\": 1010", "\"width\": 1012"))
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
        val live = ClusterProfile.parse("edited", source.replace("\"initialView\": 0", "\"initialView\": 1"))
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
    @Test
    fun `the AltScreen is moved to an area as DiPlay moves the main screen`() {
        val command = altscreenViewAreaCommand(1, 6)

        assertEquals("updateViewArea", command["type"])
        assertEquals(
            mapOf("uuid" to AirPlayInfoPlist.ALT_UUID, "viewAreaIndex" to 1, "animationDurationMillis" to 300, "adjacentViewAreas" to listOf(0, 2, 3, 4, 5)),
            command["params"],
        )
    }
}
