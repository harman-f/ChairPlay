package io.github.numberonebot.chairplay.ui

/**
 * The controller's API, with the GPS car's calls, which only the app's windows and car can answer, and the cars'
 * cluster profiles. A named class, not an anonymous object in [ChairPlayUi]: a changed [UiApi] then recompiles it, and
 * its test lists every call it forwards.
 */
internal class AppUiApi(
    private val controller: UiController,
    private val profiles: () -> UiProfiles? = { null },
    private val labProvider: () -> UiLiveLab? = { null },
    private val driving: () -> UiDriving?,
) : UiApi by controller {
    override fun liveLab(body: Map<*, *>): Map<String, Any?> =
        labProvider()?.request(body) ?: mapOf("state" to "NOT_SUPPORTED")

    override fun gpsDrive(throttle: Double, brake: Double, steer: Double) =
        driving()?.gpsDrive(throttle, brake, steer) ?: false

    override fun screenshot() = driving()?.screenshot() ?: false
    override fun screenshotTarget(target: String) = driving()?.screenshotTarget(target) ?: false

    override fun driveMode(on: Boolean) = driving()?.driveMode(on) ?: false

    override fun gpsRoute(action: String, name: String?, gpx: String?) =
        driving()?.gpsRoute(action, name, gpx) ?: RouteAnswer(error = "No GPS car")

    override fun clusterProfiles() = profiles()?.list() ?: mapOf("profiles" to emptyList<Any>())

    // A save's null is its success: only a missing set of profiles answers the refusal.
    override fun saveClusterProfile(id: String, text: String?): String? = profiles().let { it?.save(id, text) ?: if (it == null) "No car profiles here" else null }
    override fun saveClusterOverlay(id: String, text: String): String? =
        profiles().let { it?.saveOverlay(id, text) ?: "No car overlays here" }
}
