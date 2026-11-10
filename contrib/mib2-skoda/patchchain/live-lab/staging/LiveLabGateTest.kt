package io.github.numberonebot.chairplay.livelab

/** Run standalone with kotlinc, no application/DiPlay dependency. */
fun main() {
    var time = 0L
    val gate = LiveLabGate(monotonicMs = { time })
    fun checkRejected(reason: String, f: () -> LiveLabGate.Decision) {
        val decision = f()
        check(!decision.allowed && decision.reason == reason) { "Expected $reason; got $decision" }
    }

    checkRejected("NOT_ARMED") { gate.permit("s1", "s1", "showUI") }
    checkRejected("LOCAL_CONFIRM_REQUIRED") { gate.arm("s1", false) }
    checkRejected("NO_ACTIVE_SESSION") { gate.arm(null, true) }
    check(gate.arm("s1", true).allowed)

    checkRejected("EXPECTED_GENERATION_MISMATCH") { gate.permit("old", "s1", "showUI") }
    checkRejected("TYPE111_ONLY") { gate.permit("s1", "s1", "showUI", targetType = 110) }
    checkRejected("COMMAND_NOT_ALLOWED") { gate.permit("s1", "s1", "socketKill") }
    checkRejected("UNEXPECTED_ZOOM") { gate.permit("s1", "s1", "stopUI", zoomPercent = 70) }
    checkRejected("ZOOM_NOT_ALLOWED") { gate.permit("s1", "s1", "updateInfo", zoomPercent = 85) }
    checkRejected("NEGOTIATED_INFO_NOT_VERIFIED") { gate.permit("s1", "s1", "updateInfo", zoomPercent = 70) }
    checkRejected("DDP_CONFLICT") {
        gate.permit("s1", "s1", "updateInfo", zoomPercent = 70, completeInfoVerified = true, hasDisplayPanels = true)
    }
    check(gate.remaining("s1") == 12)
    check(gate.permit("s1", "s1", "updateInfo", 70, completeInfoVerified = true).allowed)
    check(gate.remaining("s1") == 11)
    repeat(11) { check(gate.permit("s1", "s1", "showUI").allowed) }
    checkRejected("COMMAND_BUDGET_EXHAUSTED") { gate.permit("s1", "s1", "showUI") }
    checkRejected("NOT_ARMED") { gate.permit("s1", "s1", "stopUI") }

    check(gate.arm("s2", true).allowed)
    checkRejected("NOT_ARMED") { gate.permit("s2", "s3", "showUI") }
    check(gate.arm("s4", true).allowed)
    time = 600_001L
    checkRejected("NOT_ARMED") { gate.permit("s4", "s4", "showUI") }
    check(gate.arm("s5", true).allowed)
    check(gate.disarm().allowed)
    checkRejected("NOT_ARMED") { gate.permit("s5", "s5", "showUI") }
    println("PASS LiveLabGate: fail-closed, consent, Type111, exact generation, TTL, budget, DDP, restore scale")
}
