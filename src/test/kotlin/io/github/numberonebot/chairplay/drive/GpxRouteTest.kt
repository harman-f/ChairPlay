package io.github.numberonebot.chairplay.drive

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/** gps.route: a GPX track the GPS car follows, at gps.route.speed, slowing for its sharp corners. */
class GpxRouteTest {
    // 0.001° of latitude is 111.2 m north; then as far east.
    private val gpx = """<?xml version="1.0"?>
        <gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>Test</name><trkseg>
        <trkpt lat="52.000" lon="21.000"><ele>100</ele></trkpt>
        <trkpt lat="52.000" lon="21.000"/>
        <trkpt lat="52.001" lon="21.000"/>
        <trkpt lat="52.001" lon="21.00162"/>
        </trkseg></trk></gpx>"""

    @Test
    fun `a track's points make the route, repeats dropped`() {
        val route = GpxRoute.parse("test.gpx", gpx)
        assertEquals(3, route.points.size)
        assertEquals(222.0, route.length, 2.0)
        val start = route.at(0.0)
        assertEquals(0.0, start.headingDegrees, 0.5)
        val turned = route.at(150.0)
        assertEquals(90.0, turned.headingDegrees, 0.5)
        assertEquals(52.001, turned.position.latitude, 1e-5)
    }

    // Route points (rtept) do as well; a file without two points is refused, saying why.
    @Test
    fun `route points do, and too few are refused`() {
        val rte = """<gpx><rte><rtept lat="1" lon="2"/><rtept lat="1.001" lon="2"/></rte></gpx>"""
        assertEquals(2, GpxRoute.parse("r.gpx", rte).points.size)
        assertThrows(IllegalArgumentException::class.java) { GpxRoute.parse("x.gpx", "<gpx><trk/></gpx>") }
        assertThrows(IllegalArgumentException::class.java) { GpxRoute.parse("x.gpx", "not xml") }
    }

    // At its cruise between corners, slower near the right angle, and stopped at the end.
    @Test
    fun `the player slows for corners and stops at the end`() {
        val route = GpxRoute.parse("test.gpx", gpx)
        assertEquals(50.0, route.speedLimitKmh(10.0, 50.0), 0.01)
        assertTrue(route.speedLimitKmh(111.0, 50.0) < 30.0)
        val player = RoutePlayer(route, 50.0)
        player.playing = true
        repeat(60 * 60) { player.step(1.0 / 60) }
        assertTrue(player.finished)
        assertFalse(player.playing)
        assertEquals(0.0, player.speed, 1e-9)
        assertEquals(route.length, player.distance, 1e-6)
        player.restart()
        assertEquals(0.0, player.distance, 1e-9)
    }
}
