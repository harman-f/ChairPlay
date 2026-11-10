package io.github.numberonebot.chairplay.drive

import org.w3c.dom.Element
import java.io.StringReader
import javax.xml.XMLConstants
import javax.xml.parsers.DocumentBuilderFactory
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.min
import org.xml.sax.InputSource

/** Where a route puts the car: its place and the way the road goes there (0 north, 90 east). */
data class RoutePlace(val position: GeoPoint, val headingDegrees: Double)

/**
 * A GPX file's track or route (gps.route) as a line the GPS car follows: its points in order, repeats dropped, measured
 * in straight local steps as [GeoPoint.moved] takes them, which is right for the few hundred metres between two points.
 */
class GpxRoute(val name: String, val points: List<GeoPoint>) {
    // Metres from the start to each point, and the turn at each point in degrees (0 at the ends).
    private val along: DoubleArray
    private val turns: DoubleArray

    init {
        require(points.size >= 2) { "$name has fewer than two points" }
        along = DoubleArray(points.size)
        for (i in 1 until points.size) along[i] = along[i - 1] + distance(points[i - 1], points[i])
        turns = DoubleArray(points.size) { i ->
            if (i == 0 || i == points.lastIndex) 0.0
            else abs(angleBetween(bearing(points[i - 1], points[i]), bearing(points[i], points[i + 1])))
        }
    }

    /** The route's length in metres. */
    val length: Double get() = along.last()

    /** The place [meters] along the route, the start before it and the end past it. */
    fun at(meters: Double): RoutePlace {
        val d = meters.coerceIn(0.0, length)
        val i = segment(d)
        val from = points[i]
        val to = points[i + 1]
        val heading = bearing(from, to)
        return RoutePlace(from.moved(heading, d - along[i]), heading)
    }

    /**
     * How fast the car goes [meters] along at a [cruiseKmh]: as fast, but slower within [CORNER_METERS] of a corner, down
     * to [CORNER_KMH] for a right angle or sharper, as a driver slows to turn.
     */
    fun speedLimitKmh(meters: Double, cruiseKmh: Double): Double {
        var limit = cruiseKmh
        for (i in 1 until points.lastIndex) {
            val turn = turns[i]
            if (turn < GENTLE_DEGREES) continue
            val near = abs(along[i] - meters)
            if (near >= CORNER_METERS) continue
            val slow = cruiseKmh - (cruiseKmh - CORNER_KMH) * min(1.0, (turn - GENTLE_DEGREES) / (90.0 - GENTLE_DEGREES))
            limit = min(limit, slow + (cruiseKmh - slow) * near / CORNER_METERS)
        }
        return limit
    }

    private fun segment(meters: Double): Int {
        var low = 0
        var high = points.lastIndex - 1
        while (low < high) {
            val mid = (low + high + 1) / 2
            if (along[mid] <= meters) low = mid else high = mid - 1
        }
        return low
    }

    companion object {
        private const val GENTLE_DEGREES = 25.0
        private const val CORNER_METERS = 40.0
        private const val CORNER_KMH = 20.0

        /** The route in GPX [text] named [name]: its track points, else its route points; refused with the reason. */
        fun parse(name: String, text: String): GpxRoute {
            val factory = DocumentBuilderFactory.newInstance().apply {
                isNamespaceAware = false
                setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true)
                setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
            }
            val document = runCatching { factory.newDocumentBuilder().parse(InputSource(StringReader(text))) }
                .getOrElse { throw IllegalArgumentException("$name is not a GPX file: ${it.message}") }
            fun points(tag: String) = document.getElementsByTagName(tag).let { nodes ->
                (0 until nodes.length).mapNotNull { i ->
                    val node = nodes.item(i) as Element
                    val lat = node.getAttribute("lat").toDoubleOrNull()
                    val lon = node.getAttribute("lon").toDoubleOrNull()
                    if (lat == null || lon == null || lat !in -90.0..90.0 || lon !in -180.0..180.0) null else GeoPoint(lat, lon)
                }
            }
            val found = points("trkpt").ifEmpty { points("rtept") }
            val distinct = found.filterIndexed { i, point -> i == 0 || distance(found[i - 1], point) > 0.5 }
            return GpxRoute(name, distinct)
        }

        internal fun distance(a: GeoPoint, b: GeoPoint): Double {
            val north = (b.latitude - a.latitude) * GeoPoint.METERS_PER_DEGREE
            val east = (b.longitude - a.longitude) * GeoPoint.METERS_PER_DEGREE * cos(Math.toRadians(a.latitude))
            return hypot(north, east)
        }

        internal fun bearing(a: GeoPoint, b: GeoPoint): Double {
            val north = b.latitude - a.latitude
            val east = (b.longitude - a.longitude) * cos(Math.toRadians(a.latitude))
            return (Math.toDegrees(atan2(east, north)) + 360.0) % 360.0
        }

        /** The turn from [from] to [to], -180 to 180 degrees, right positive. */
        private fun angleBetween(from: Double, to: Double): Double = ((to - from + 540.0) % 360.0) - 180.0
    }
}

/**
 * The GPS car playing a [route] at [cruiseKmh] (gps.route.speed): [step] moves it on along the road while [playing],
 * speeding up and slowing down at [ACCEL] toward the speed the road allows there; paused, it rolls to a stop on the
 * road, and at the end it stops and the play ends.
 */
class RoutePlayer(val route: GpxRoute, @Volatile var cruiseKmh: Double) {
    @Volatile var playing = false
    @Volatile var distance = 0.0
        private set
    /** Metres a second. */
    @Volatile var speed = 0.0
        private set

    val finished: Boolean get() = distance >= route.length

    /** Whether the route moves the car: playing, or rolling to a stop. */
    val moving: Boolean get() = playing || speed > 0.0

    /** Moves on by [seconds]; where the car is then. */
    fun step(seconds: Double): RoutePlace {
        val aim = if (playing && !finished) route.speedLimitKmh(distance, cruiseKmh) / 3.6 else 0.0
        val change = ACCEL * seconds
        speed = (speed + (aim - speed).coerceIn(-change, change)).coerceAtLeast(0.0)
        distance = min(route.length, distance + speed * seconds)
        if (finished) {
            playing = false
            speed = 0.0
        }
        return route.at(distance)
    }

    /** Back to the start, stopped. */
    fun restart() {
        playing = false
        speed = 0.0
        distance = 0.0
    }

    private companion object {
        /** Metres a second each second, a calm car's pull and braking. */
        const val ACCEL = 2.5
    }
}
