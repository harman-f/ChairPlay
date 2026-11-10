package io.github.numberonebot.chairplay.livelab

/**
 * Staging only: independent, deterministic policy for a future in-process ChairPlay Live Lab.
 * No socket/API reference, no change to the currently accepted ChairPlay artifact.
 *
 * SECURITY: Call permit() again on the serialized sender thread immediately before every write.
 * Every command must use the current AirPlaySession identity/generation, not a cached pointer.
 */
internal class LiveLabGate(
    private val monotonicMs: () -> Long,
    private val ttlMs: Long = 10 * 60 * 1000L,
    private val maxWrites: Int = 12,
) {
    internal data class Decision(
        val allowed: Boolean,
        val state: String,
        val reason: String,
        val remaining: Int,
    )

    private var armedFor: String? = null
    private var expiresAt = 0L
    private var writes = 0

    @Synchronized
    fun arm(currentGeneration: String?, operatorConfirmed: Boolean): Decision {
        if (!operatorConfirmed) return refuse("LOCAL_CONFIRM_REQUIRED")
        if (currentGeneration.isNullOrBlank()) return refuse("NO_ACTIVE_SESSION")
        armedFor = currentGeneration
        expiresAt = monotonicMs() + ttlMs
        writes = 0
        return allow("ARMED")
    }

    @Synchronized
    fun disarm(): Decision {
        armedFor = null
        expiresAt = 0L
        writes = 0
        return allow("DISARMED")
    }

    @Synchronized
    fun status(currentGeneration: String?): Decision {
        expireIfChanged(currentGeneration)
        return if (armedFor != null) allow("ARMED") else refuse("NOT_ARMED")
    }

    /**
     * Has to be invoked on the sender thread, not just when parsing the HTTP request.
     * Caller-provided UUID, plist payloads, URL, stream data or custom commands are not accepted.
     *
     * updateInfo can only pass if a separate immutable live descriptor validation succeeded;
     * the gate alone cannot establish a valid AirPlay wire command or an iOS acknowledgement.
     */
    @Synchronized
    fun permit(
        expectedGeneration: String?,
        currentGeneration: String?,
        command: String,
        zoomPercent: Int? = null,
        targetType: Int = 111,
        completeInfoVerified: Boolean = false,
        hasDisplayPanels: Boolean = false,
    ): Decision {
        expireIfChanged(currentGeneration)
        if (armedFor == null) return refuse("NOT_ARMED")
        if (expectedGeneration.isNullOrBlank() || expectedGeneration != armedFor)
            return refuse("EXPECTED_GENERATION_MISMATCH")
        if (targetType != 111) return refuse("TYPE111_ONLY")
        if (writes >= maxWrites) {
            disarm()
            return refuse("COMMAND_BUDGET_EXHAUSTED")
        }
        when (command) {
            "stopUI", "showUI" -> if (zoomPercent != null) return refuse("UNEXPECTED_ZOOM")
            "updateInfo" -> {
                if (zoomPercent !in setOf(70, 100)) return refuse("ZOOM_NOT_ALLOWED")
                if (!completeInfoVerified) return refuse("NEGOTIATED_INFO_NOT_VERIFIED")
                if (hasDisplayPanels) return refuse("DDP_CONFLICT")
            }
            else -> return refuse("COMMAND_NOT_ALLOWED")
        }
        writes++
        return allow("PERMITTED")
    }

    @Synchronized
    fun remaining(currentGeneration: String?): Int {
        expireIfChanged(currentGeneration)
        return if (armedFor == null) 0 else (maxWrites - writes).coerceAtLeast(0)
    }

    private fun expireIfChanged(currentGeneration: String?) {
        if (armedFor != null &&
            (currentGeneration != armedFor || monotonicMs() >= expiresAt)
        ) disarm()
    }

    private fun allow(state: String) = Decision(true, state, "NONE", (maxWrites - writes).coerceAtLeast(0))
    private fun refuse(reason: String) = Decision(false, "REJECTED", reason, (maxWrites - writes).coerceAtLeast(0))
}
