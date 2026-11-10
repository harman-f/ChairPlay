package io.github.numberonebot.chairplay

import com.shilapi.xcertplay.airplay.AirPlaySession
import io.github.numberonebot.chairplay.config.ClusterProfile
import java.util.concurrent.Callable
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit

/**
 * Explicitly opt-in DDP/displayPanels experiment. This is not the normal ChairPlay scaling path.
 * /info is built from the existing screen descriptors, without changing the legacy displays list.
 * Only one stable type-111 panel is ever targeted at runtime. An event write is NOT an iOS ACK.
 */
internal object PanelUpdateProbe {
    private val lock = Any()
    @Volatile private var enabled = false
    private var cluster: Map<String, Any?>? = null
    private var advertisedCount = 0
    private var baselineSession: AirPlaySession? = null
    /** Last command outcome survives status polling; cleared on enable/reconnect. */
    private var lastResult: Map<String, Any?> = emptyMap()

    fun setEnabled(on: Boolean): Map<String, Any?> = synchronized(lock) {
        enabled = on
        cluster = null
        advertisedCount = 0
        baselineSession = null
        lastResult = emptyMap()
        statusLocked() + mapOf("detail" to "Reconnect CarPlay once to negotiate the changed /info descriptor.")
    }

    /** Called before the next AirPlay listener is created; never alter the currently active stream. */
    fun beginConnection() = synchronized(lock) {
        cluster = null
        advertisedCount = 0
        baselineSession = null
        lastResult = emptyMap()
    }

    fun status(): Map<String, Any?> = synchronized(lock) { statusLocked() }

    private fun statusLocked(): Map<String, Any?> = mapOf(
        "enabled" to enabled,
        "advertised" to (cluster != null),
        "advertisedCount" to advertisedCount,
        "baselineSent" to (baselineSession != null),
        "state" to if (!enabled) "OFF" else if (cluster != null) "DESCRIPTOR_OFFERED" else "RECONNECT_REQUIRED",
        "ack" to "NOT_OBSERVED",
        "visualEffect" to "UNKNOWN",
    ) + lastResult

    private fun rejected(mode: String, detail: String): Map<String, Any?> = synchronized(lock) {
        lastResult = mapOf("state" to "REJECTED", "mode" to mode, "detail" to detail)
        statusLocked()
    }

    /**
     * Invoked from the final /info assembly, AFTER ClusterProfile.advertise. A failed conversion
     * leaves the stock /info unchanged. This is deliberately opt-in because DDP may affect SETUP.
     */
    fun advertise(info: MutableMap<String, Any?>) {
        if (!enabled) return
        val displays = info["displays"] as? List<*> ?: return
        if (displays.size < 2) return
        val seen = HashSet<String>()
        val panels = ArrayList<Map<String, Any?>>()
        for (entry in displays) {
            val original = entry as? Map<*, *> ?: return
            val uuid = original["uuid"] as? String ?: return
            val type = (original["type"] as? Number)?.toInt() ?: return
            if (uuid.isBlank() || !seen.add(uuid) || type !in setOf(110, 111)) return
            for (field in listOf("widthPixels", "heightPixels", "widthPhysical", "heightPhysical")) {
                if (((original[field] as? Number)?.toInt() ?: 0) <= 0) return
            }
            val panel = linkedMapOf<String, Any?>()
            for ((key, value) in original) {
                if (key !is String) return
                panel[key] = value
            }
            // A logical display has uuid. The modern physical display is identified by uid;
            // each stream itself still carries its own uuid. Preserve both, never invent main IDs.
            panel["uid"] = uuid
            panel["initialVideoStreams"] = listOf(
                linkedMapOf("uuid" to uuid, "originXPixels" to 0, "originYPixels" to 0, "zIndex" to 0),
            )
            panel["properties"] = if (type == 111) listOf("Instrument Cluster") else emptyList<String>()
            panels += panel
        }
        val target = panels.singleOrNull { (it["type"] as? Number)?.toInt() == 111 } ?: return
        synchronized(lock) {
            if (!enabled) return
            info["displayPanels"] = panels
            cluster = target
            advertisedCount++
        }
    }

    /**
     * Build the exact outbound /command payload. Unlike profile editing this does not persist
     * settings, switch ViewAreas, change stream UUIDs, or alter the framebuffer dimensions.
     */
    fun command(mode: String, value: Int? = null, profile: ClusterProfile? = null): Map<String, Any?>? = synchronized(lock) {
        if (!enabled) return null
        val original = cluster ?: return null
        if (mode !in setOf("baseline", "zoom", "physical", "apply")) return null
        if (mode == "apply" && (profile == null || baselineSession == null)) return null
        if (mode in setOf("zoom", "physical") && value !in setOf(70, 85, 100, 125, 150)) return null
        val uid = original["uid"] as? String ?: return null
        val streams = original["initialVideoStreams"] as? List<*> ?: return null
        if (streams.size != 1) return null
        val out = linkedMapOf<String, Any?>(
            "uid" to uid, "videoStreams" to streams,
        )
        for (name in listOf("widthPixels", "heightPixels", "widthPhysical", "heightPhysical")) {
            out[name] = original[name] as? Number ?: return null
        }
        val initialZoom = original["zoomFactor"] as? Number
        if (initialZoom != null) out["zoomFactor"] = initialZoom
        when (mode) {
            "apply" -> {
                // Scale from the actually saved active profile. Do not change the negotiated
                // frame, UUID or stream layout, even if the user edited other settings.
                val desired = profile!!.displayEntry()
                if (desired["uuid"] != uid) return null
                for (name in listOf("widthPixels", "heightPixels")) {
                    if ((desired[name] as? Number)?.toInt() != (out[name] as Number).toInt()) return null
                }
                val zoom = (desired["zoomFactor"] as? Number)?.toInt()
                if (zoom != null) {
                    if (zoom !in 25..400) return null
                    out["zoomFactor"] = zoom
                } else {
                    // With Auto, leave the zoom factor out as in /info. No promise
                    // that an iPhone will revert a previously set native zoom.
                    out.remove("zoomFactor")
                }
                for (name in listOf("widthPhysical", "heightPhysical")) {
                    out[name] = desired[name] as? Number ?: return null
                }
            }
            "zoom" -> out["zoomFactor"] = value!!
            "physical" -> {
                val scale = value!!
                out["widthPhysical"] = ((out["widthPhysical"] as Number).toInt() * 100.0 / scale).let { kotlin.math.round(it).toInt().coerceAtLeast(1) }
                out["heightPhysical"] = ((out["heightPhysical"] as Number).toInt() * 100.0 / scale).let { kotlin.math.round(it).toInt().coerceAtLeast(1) }
            }
        }
        mapOf("type" to "updateDisplayPanels", "params" to mapOf("displayPanels" to listOf(out)))
    }

    fun perform(
        mode: String, value: Int?, active: () -> AirPlaySession?,
        sender: ExecutorService, log: (String) -> Unit,
        profile: () -> ClusterProfile? = { null },
    ): Map<String, Any?> {
        if (mode == "status") return status()
        if (mode == "enable") return setEnabled(true)
        if (mode == "disable") return setEnabled(false)
        val session = active()
            ?: return rejected(mode, "No active CarPlay session.")
        val payload = command(mode, value, if (mode == "apply") profile() else null)
            ?: return rejected(mode, "No negotiated panel or baseline, incompatible frame, Auto zoom or disabled probe.")
        if (mode == "apply" && synchronized(lock) { baselineSession !== session }) {
            return rejected(mode, "New session requires a fresh baseline first.")
        }
        if (session.clusterUrl() == null) {
            return rejected(mode, "No running Type-111 cluster UI; show a map view first.")
        }
        val future = sender.submit(Callable {
            if (active() !== session || session.clusterUrl() == null) false
            else session.sendCommand(payload)
        })
        val sent = try {
            future.get(3, TimeUnit.SECONDS)
        } catch (error: Exception) {
            future.cancel(true)
            log("panel POC timed out or failed: " + error.javaClass.simpleName)
            return rejected(mode, "Local send failed or timed out.")
        }
        val result = synchronized(lock) {
            if (sent && mode == "baseline") baselineSession = session
            lastResult = mapOf(
                "state" to if (sent) "LOCAL_SENT" else "REJECTED",
                "mode" to mode, "value" to value,
                "detail" to if (sent) "Encrypted AirPlay event written. No iOS acknowledgement or visual effect proven."
                    else "AirPlay event socket refused the write.",
            )
            statusLocked()
        }
        val details = ((payload["params"] as Map<*, *>)["displayPanels"] as List<*>).single() as Map<*, *>
        log("panel POC mode=$mode value=$value local_sent=$sent uid=${details["uid"]} " +
            "pixels=${details["widthPixels"]}x${details["heightPixels"]} " +
            "physical=${details["widthPhysical"]}x${details["heightPhysical"]}mm " +
            "zoomFactor=${details["zoomFactor"] ?: "AUTO"} ack=NOT_OBSERVED visual=UNKNOWN")
        return result
    }
}
