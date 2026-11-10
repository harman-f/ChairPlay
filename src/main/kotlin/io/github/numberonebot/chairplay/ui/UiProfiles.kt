package io.github.numberonebot.chairplay.ui

/** The AltScreen page's car profiles (profiles\<id>.json): see [UiApi.clusterProfiles] and [UiApi.saveClusterProfile]. */
interface UiProfiles {
    fun list(): Map<String, Any?>

    fun save(id: String, text: String?): String?
    /** Save reusable, separately referenced cockpit overlay JSON. */
    fun saveOverlay(id: String, text: String): String? = "Overlay files are not supported"
}
