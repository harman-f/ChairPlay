package io.github.numberonebot.chairplay

import io.github.numberonebot.chairplay.drive.CarInput
import io.github.numberonebot.chairplay.drive.DriveControl
import io.github.numberonebot.chairplay.drive.Driving
import io.github.numberonebot.chairplay.drive.GlfwGamepad
import io.github.numberonebot.chairplay.drive.GpxRoute
import io.github.numberonebot.chairplay.input.GamepadControls
import io.github.numberonebot.chairplay.media.VideoWindow
import io.github.numberonebot.chairplay.ui.RouteAnswer
import io.github.numberonebot.chairplay.ui.UiDriving
import java.nio.file.Files
import java.nio.file.Path

/**
 * The GPS car as the GPS page and its experiments reach it: drive mode, the car driven by a script, and the CarPlay
 * screens saved. Each change goes in on the next pass of the window loop, which [window]'s repaint wakes.
 */
internal fun uiDriving(driving: Driving, window: VideoWindow, screenshots: () -> Unit, log: (String) -> Unit, dir: Path,
    targetedScreenshots: (String) -> Boolean = { if (it == "both") { screenshots(); true } else false },
) = object : UiDriving {
    /**
     * The GPS page's route: "load" keeps [gpx] as routes\[name] in the app folder once it reads as a route and answers
     * the path for gps.route, which the page saves; the rest play, pause, toggle or restart it.
     */
    override fun gpsRoute(action: String, name: String?, gpx: String?): RouteAnswer {
        if (action != "load") return RouteAnswer(error = driving.route(action)).also { window.repaint() }
        val file = name?.let { Path.of(it).fileName?.toString() }?.replace(Regex("[^A-Za-z0-9._ -]"), "_")?.ifBlank { null }
            ?: return RouteAnswer(error = "Name the GPX file")
        if (gpx == null) return RouteAnswer(error = "The GPX file is empty")
        runCatching { GpxRoute.parse(file, gpx) }.onFailure { return RouteAnswer(error = it.message) }
        val path = "routes/" + if (file.endsWith(".gpx", ignoreCase = true)) file else "$file.gpx"
        Files.createDirectories(dir.resolve("routes"))
        Files.writeString(dir.resolve(path), gpx)
        log("GPS route file saved as $path")
        driving.routeFileSaved(path)
        return RouteAnswer(path = path)
    }

    override fun driveMode(on: Boolean): Boolean {
        val done = driving.driveMode(on)
        if (done) log("drive mode ${if (on) "on" else "off"} from the GPS page")
        window.repaint()
        return done
    }

    override fun gpsDrive(throttle: Double, brake: Double, steer: Double): Boolean {
        driving.control.scripted = CarInput(throttle, brake, steer)
        window.repaint()
        return driving.settings.enabled
    }

    override fun screenshot(): Boolean = true.also { screenshots() }
    override fun screenshotTarget(target: String): Boolean = targetedScreenshots(target)
}

/**
 * The window loop's pass, on the main thread: the GPS car's, then a gamepad's buttons as the knob and the AltScreen's
 * zoom ([GamepadControls]) sent to [controls], the GPS on or off; a gamepad there is looked at now and then.
 */
internal fun windowPass(driving: Driving, controls: AppControls, buttons: GamepadControls = GamepadControls()): () -> Double? = {
    val globalDue = controls.global.pass()
    val due = driving.pass()
    val pad = GlfwGamepad.buttons()
    buttons.pass(pad).forEach(controls::send)
    listOfNotNull(due, globalDue, controls.volumeTitlePass(), pad?.let { DriveControl.GAMEPAD_POLL_SECONDS }).minOrNull()
}
