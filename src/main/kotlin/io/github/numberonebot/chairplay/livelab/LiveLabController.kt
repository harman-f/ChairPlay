package io.github.numberonebot.chairplay.livelab

import com.shilapi.xcertplay.airplay.AirPlaySession
import io.github.numberonebot.chairplay.ui.UiLiveLab
import java.util.UUID
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit

/**
 * Ephemeral local-only experiment controller. A caller can choose only known actions.
 * All outgoing commands are serialized on ChairPlay's existing touch-sender executor.
 * No arbitrary plist/UUID, no transport reset, no persistence.
 */
internal class LiveLabController(
    private val active: () -> AirPlaySession?,
    private val sender: ExecutorService,
    private val log: (String) -> Unit,
) : UiLiveLab {
    private val gate = LiveLabGate(monotonicMs = { TimeUnit.NANOSECONDS.toMillis(System.nanoTime()) })
    private val lock = Any()
    private val prefix = UUID.randomUUID().toString().substring(0, 8)
    private var last: AirPlaySession? = null
    private var sessionNumber = 0L
    private val history = ArrayDeque<Map<String, Any?>>()
    private val zooms = setOf(70, 100)

    /** Synchronized on our controller; session identity changes disarm the gate. */
    private fun current(): Pair<AirPlaySession?, String?> = synchronized(lock) {
        val session = active()
        if (session !== last) {
            last = session
            sessionNumber++
            gate.disarm()
            history.clear()
        }
        session to session?.let { prefix + "-" + sessionNumber }
    }

    private fun refused(reason: String): Map<String, Any?> =
        mapOf("state" to "REJECTED", "reason" to reason, "ack" to "NOT_OBSERVED",
            "visualEffect" to "UNKNOWN")

    override fun request(body: Map<*, *>): Map<String, Any?> {
        if (body.keys.any { it !is String }) return refused("INVALID_REQUEST")
        val op = body["op"] as? String ?: return refused("MISSING_OPERATION")
        val allowed = when (op) {
            "status", "events", "disarm" -> setOf("op")
            "arm" -> setOf("op", "confirm")
            "command" -> setOf("op", "command", "zoomPercent", "expectedGeneration")
            else -> return refused("UNKNOWN_OPERATION")
        }
        if (body.keys.any { it !in allowed }) return refused("UNEXPECTED_PROPERTY")
        val (session, generation) = current()
        when (op) {
            "status" -> {
                val state = gate.status(generation)
                val descriptor = session?.liveLabInfoStatus() ?: mapOf(
                    "descriptorReady" to false, "descriptorReason" to "NO_ACTIVE_SESSION")
                return linkedMapOf<String, Any?>(
                    "state" to if (state.allowed) "ARMED" else "NOT_ARMED",
                    "sessionActive" to (session != null),
                    "generation" to generation,
                    "armed" to state.allowed,
                    "remaining" to gate.remaining(generation),
                    "capabilities" to listOf("updateInfo", "showUI", "stopUI"),
                    "ack" to "NOT_OBSERVED",
                    "visualEffect" to "UNKNOWN",
                ).apply { putAll(descriptor) }
            }
            "events" -> return synchronized(lock) {
                mapOf("state" to "OK", "generation" to generation, "history" to history.toList())
            }
            "arm" -> {
                if (body["confirm"] != "LIVE_LAB_LOCAL") return refused("LOCAL_CONFIRM_REQUIRED")
                val decision = gate.arm(generation, operatorConfirmed = session != null)
                return if (decision.allowed) request(mapOf("op" to "status"))
                    else refused(decision.reason)
            }
            "disarm" -> {
                gate.disarm()
                return mapOf("state" to "NOT_ARMED", "armed" to false)
            }
        }

        // Command: the HTTP thread never holds or directly writes a session socket.
        val expected = body["expectedGeneration"] as? String ?: return refused("EXPECTED_GENERATION_REQUIRED")
        val command = body["command"] as? String ?: return refused("MISSING_COMMAND")
        if (command !in setOf("updateInfo", "showUI", "stopUI")) return refused("COMMAND_NOT_ALLOWED")
        val zoom = body["zoomPercent"]
        if (command == "updateInfo") {
            if (zoom !is Number || zoom.toInt() !in zooms || zoom.toDouble() != zoom.toInt().toDouble())
                return refused("ZOOM_NOT_ALLOWED")
        } else if ("zoomPercent" in body) return refused("UNEXPECTED_ZOOM")
        if (expected != generation || session == null) return refused("EXPECTED_GENERATION_MISMATCH")
        val task = sender.submit<Map<String, Any?>> {
            val (now, nowGeneration) = current()
            if (now !== session || nowGeneration != expected) return@submit refused("SESSION_CHANGED")
            val info = now.liveLabInfoStatus()
            val decision = gate.permit(
                expectedGeneration = expected,
                currentGeneration = nowGeneration,
                command = command,
                zoomPercent = if (command == "updateInfo") (zoom as Number).toInt() else null,
                targetType = 111,
                completeInfoVerified = info["descriptorReady"] == true,
                hasDisplayPanels = info["descriptorReason"] == "DDP_CONFLICT",
            )
            if (!decision.allowed) return@submit refused(decision.reason)
            val result = when (command) {
                "updateInfo" -> now.liveLabSendUpdateInfo((zoom as Number).toInt())
                "showUI" -> {
                    val sent = now.setClusterUiShown(true)
                    mapOf("state" to if (sent) "LOCAL_SENT" else "REJECTED",
                        "reason" to if (sent) "NONE" else "LOCAL_WRITE_FAILED",
                        "localSent" to sent)
                }
                else -> {
                    val sent = now.setClusterUiShown(false)
                    mapOf("state" to if (sent) "LOCAL_SENT" else "REJECTED",
                        "reason" to if (sent) "NONE" else "LOCAL_WRITE_FAILED",
                        "localSent" to sent)
                }
            }
            val entry = linkedMapOf<String, Any?>(
                "command" to command, "state" to result["state"],
                "generation" to nowGeneration, "zoomPercent" to
                    (if (command == "updateInfo") (zoom as Number).toInt() else null),
                "ack" to "NOT_OBSERVED", "visualEffect" to "UNKNOWN",
                "eventCSeq" to result["eventCSeq"],
                "stream111SetupCount" to info["stream111SetupCount"],
            )
            synchronized(lock) {
                if (history.size >= 60) history.removeFirst()
                history.addLast(entry)
            }
            log("live-lab command=" + command + " result=" + result["state"] +
                " generation=" + nowGeneration + " cseq=" + (result["eventCSeq"] ?: "-"))
            linkedMapOf<String, Any?>(
                "state" to result["state"], "command" to command,
                "generation" to nowGeneration, "localSent" to result["localSent"],
                "reason" to result["reason"], "eventCSeq" to result["eventCSeq"],
                "stream111SetupCount" to info["stream111SetupCount"],
                "ack" to "NOT_OBSERVED", "visualEffect" to "UNKNOWN",
            )
        }
        return try {
            task.get(6, TimeUnit.SECONDS)
        } catch (error: Exception) {
            task.cancel(true)
            log("live-lab command=" + command + " cancelled_or_unknown; never retry automatically")
            refused("EXECUTION_TIMEOUT_OR_FAILURE")
        }
    }
}
