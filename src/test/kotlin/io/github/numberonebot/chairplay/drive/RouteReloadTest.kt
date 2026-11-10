package io.github.numberonebot.chairplay.drive

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test
import java.nio.file.NoSuchFileException

/** gps.route whose file went missing (a deploy wiped it) and was chosen again under the same path. */
class RouteReloadTest {
    private val gpx = """<gpx><trk><trkseg><trkpt lat="52" lon="21"/><trkpt lat="52.001" lon="21"/></trkseg></trk></gpx>"""

    @Test
    fun `a file kept again under the path gps route names is read again`() {
        var file: String? = null
        val settings = GpsSettings(true, start = GeoPoint(52.0, 21.0), route = "routes/a.gpx")
        val driving = Driving(settings, gamepad = { null }, nanoTime = { 0L }, routeText = { file ?: throw NoSuchFileException(it) })
        assertNull(driving.state()["route"])
        assertEquals("routes/a.gpx not found. Choose the GPX file again", driving.routeError)
        // Missing, Play says why rather than nothing.
        assertNotNull(driving.route("play"))

        file = gpx
        driving.routeFileSaved("routes/other.gpx")
        assertNull(driving.state()["route"])
        driving.routeFileSaved("routes/a.gpx")
        assertNotNull(driving.state()["route"])
        assertNull(driving.routeError)
        assertNull(driving.route("play"))
    }
}
