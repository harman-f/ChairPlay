package io.github.numberonebot.chairplay

import io.github.numberonebot.chairplay.config.ClusterProfiles
import io.github.numberonebot.chairplay.config.DesktopConfig
import io.github.numberonebot.chairplay.ui.UiProfiles
import java.nio.file.Path

/**
 * The AltScreen page's car profiles in [dir]'s profiles folder. The one altscreen.profile names, saved, is in force at
 * once for the schematic, the views' URLs and the View button ([altView]); its size and view areas reach the iPhone
 * with the next connection, which [config]'s reading of the settings declares. It cannot be deleted while in use.
 */
internal fun uiProfiles(dir: Path, config: DesktopConfig, altView: AltscreenView, log: (String) -> Unit) = object : UiProfiles {
    private val store = ClusterProfiles(dir)

    private fun activeId(): String? = runCatching { config.now().clusterProfile?.id }.getOrNull()

    override fun list(): Map<String, Any?> = mapOf(
        "profiles" to store.ids().map { id ->
            mapOf("id" to id, "text" to runCatching { store.text(id) }.getOrDefault(""), "builtIn" to (id in ClusterProfiles.BUILT_IN))
        },
        "active" to activeId(),
        "overlays" to store.overlayIds().map { overlay ->
            mapOf("id" to overlay, "text" to runCatching { store.overlayText(overlay) }.getOrDefault(""))
        },
    )

    override fun saveOverlay(id: String, text: String): String? {
        val error = store.saveOverlay(id, text)
        if (error == null) {
            log("cockpit overlay $id saved")
            activeId()?.let { active ->
                runCatching { store.load(active) }.onSuccess { altView.carViews.profile = it }
                    .onFailure { log("overlay refresh failed: $it") }
            }
        }
        return error
    }

    override fun save(id: String, text: String?): String? {
        val active = activeId()
        if (text == null && id == active) return "Choose another profile before deleting $id"
        val error = if (text == null) store.delete(id) else store.save(id, text)
        if (error != null) return error
        log("car profile $id ${if (text == null) "deleted" else "saved"}")
        if (text != null && id == active) {
            runCatching { store.load(id) }.getOrNull()?.let(altView::profileSaved)
        }
        return null
    }
}
