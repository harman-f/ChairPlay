package io.github.numberonebot.chairplay.cluster

import io.github.numberonebot.chairplay.config.Shape
import io.github.numberonebot.chairplay.drive.NanoPen
import io.github.numberonebot.chairplay.media.WindowOverlay
import org.lwjgl.nanovg.NanoVG.*
import org.lwjgl.nanovg.NanoVGGL3.NVG_ANTIALIAS
import org.lwjgl.nanovg.NanoVGGL3.NVG_STENCIL_STROKES
import org.lwjgl.nanovg.NanoVGGL3.nvgCreate
import org.lwjgl.nanovg.NanoVGGL3.nvgDelete
import java.nio.ByteBuffer
import java.io.File
import kotlin.math.PI

/**
 * A car's cluster drawn over the AltScreen from its profile (ClusterProfile.shapes): a view that covers the map first
 * gets the cluster's background, then the shapes of every view, then the view's own, in the profile's frame scaled to
 * the window; the safe area the iPhone was given for the view as a thin green frame, and the view's name. The kinds
 * are in [shape]. Nothing is drawn while [view] is null, without a car's profile.
 */
class ShapePainter(private val view: () -> SchematicView?) : WindowOverlay {
    private var pen: NanoPen? = null
    private var failed = false
    private val fontData = mutableListOf<ByteBuffer>()
    /** PNG textures are owned by this GL context and refreshed when a file is replaced. */
    private val pngImages = mutableMapOf<String, Pair<Long, Int>>()

    override fun open() = Unit

    private fun create(): NanoPen? {
        pen?.let { return it }
        if (failed) return null
        val vg = nvgCreate(NVG_ANTIALIAS or NVG_STENCIL_STROKES)
        if (vg == 0L) {
            failed = true
            return null
        }
        fun font(name: String, file: String): Boolean {
            val bytes = ShapePainter::class.java.getResourceAsStream("/fonts/$file")?.use { it.readBytes() } ?: return false
            val buffer = ByteBuffer.allocateDirect(bytes.size).put(bytes).flip()
            fontData += buffer
            return nvgCreateFontMem(vg, name, buffer, false) >= 0
        }
        return NanoPen(vg).also {
            it.fonts = font(REGULAR, "RobotoFlexWide-Regular.ttf") && font(BOLD, "RobotoFlexWide-ExtraBoldItalic.ttf")
            pen = it
        }
    }

    override fun close() {
        pen?.let { current ->
            pngImages.values.forEach { (_, texture) -> if (texture > 0) nvgDeleteImage(current.vg, texture) }
            nvgDelete(current.vg)
        }
        pen = null
        pngImages.clear()
        fontData.clear()
    }

    override fun paint(width: Int, height: Int) {
        val now = view() ?: return
        if (width == 0 || height == 0) return
        val pen = create() ?: return
        val profile = now.profile
        val car = profile.views[now.index]
        val (w, h) = profile.size.width.toFloat() to profile.size.height.toFloat()
        val vg = pen.vg
        nvgBeginFrame(vg, width.toFloat(), height.toFloat(), 1f)
        nvgScale(vg, width / w, height / h)
        if (car.covers) cover(pen, w, h)
        val guidance = Guidance(pen, REGULAR)
        (profile.shapes + car.shapes).forEach { runCatching { shape(pen, guidance, it) } }
        car.area?.let { profile.safeAreas[it] }?.let { safe ->
            nvgBeginPath(vg)
            nvgRect(vg, safe.x.toFloat(), safe.y.toFloat(), safe.width.toFloat(), safe.height.toFloat())
            nvgStrokeWidth(vg, 1.5f)
            pen.stroke(SAFE)
        }
        pen.text(car.name, 6f, 10f, 11f, colour("dim"), REGULAR, NVG_ALIGN_LEFT)
        nvgEndFrame(vg)
    }

    /**
     * One shape: rect (x, y, w, h, fill), poly (points, fill, the edges outlined by the index of the point they start
     * from), line (points, color, width), circle (x, y, r, fill, color), dial (x, y, r, face, value, unit), text (x, y,
     * text, size, bold, dim), compass (x, y, text), and the cluster's own guidance as zones: zone (x, y, w, h, text),
     * lanes (x, y, count, cell), turn (x, y, lanesY, distanceY, text) and eta (x, x2, y, from, to). Colours are named
     * (bar, panel, face, ring, edge, line, text, dim) or written #AARRGGBB.
     */
    private fun shape(pen: NanoPen, guidance: Guidance, s: Shape) {
        val vg = pen.vg
        fun f(key: String, default: Float = 0f) = (s[key] as? Number)?.toFloat() ?: default
        fun points() = (s["points"] as? List<*>).orEmpty().mapNotNull { p ->
            (p as? List<*>)?.let { (it.getOrNull(0) as? Number)?.toFloat() to (it.getOrNull(1) as? Number)?.toFloat() }
                ?.takeIf { it.first != null && it.second != null }?.let { it.first!! to it.second!! }
        }
        fun path(points: List<Pair<Float, Float>>) = points.forEachIndexed { i, (x, y) -> if (i == 0) nvgMoveTo(vg, x, y) else nvgLineTo(vg, x, y) }
        when (s["kind"]) {
            "png" -> {
                val path = s["path"] as? String ?: return
                val stamp = File(path).lastModified()
                if (stamp <= 0L) return
                val previous = pngImages[path]
                val texture = if (previous?.first == stamp) previous.second else {
                    if (previous != null && previous.second > 0) nvgDeleteImage(vg, previous.second)
                    nvgCreateImage(vg, path, 0).also { pngImages[path] = stamp to it }
                }
                if (texture <= 0) return
                nvgBeginPath(vg)
                nvgRect(vg, f("x"), f("y"), f("w"), f("h"))
                nvgFillPaint(vg, nvgImagePattern(vg, f("x"), f("y"), f("w"), f("h"), 0f, texture, 1f, pen.paint))
                nvgFill(vg)
            }
            "rect" -> {
                nvgBeginPath(vg)
                nvgRect(vg, f("x"), f("y"), f("w"), f("h"))
                pen.fill(colour(s["fill"], "bar"))
            }
            "poly" -> {
                val points = points()
                nvgBeginPath(vg)
                path(points)
                nvgClosePath(vg)
                pen.fill(colour(s["fill"], "panel"))
                val edges = (s["edges"] as? List<*>).orEmpty().mapNotNull { (it as? Number)?.toInt() }.filter { it in points.indices }
                if (edges.isNotEmpty()) {
                    nvgBeginPath(vg)
                    edges.forEach { i -> path(listOf(points[i], points[(i + 1) % points.size])) }
                    nvgStrokeWidth(vg, 4f)
                    pen.stroke(colour("edge"))
                }
            }
            "line" -> {
                nvgBeginPath(vg)
                path(points())
                nvgStrokeWidth(vg, f("width", 2f))
                pen.stroke(colour(s["color"], "line"))
            }
            "circle" -> {
                nvgBeginPath(vg)
                nvgCircle(vg, f("x"), f("y"), f("r"))
                s["fill"]?.let { pen.fill(colour(it)) }
                s["color"]?.let { nvgStrokeWidth(vg, f("width", 2f)); pen.stroke(colour(it)) }
            }
            "dial" -> dial(pen, f("x"), f("y"), f("r"), f("face"), s["value"] as? String, s["unit"] as? String)
            "text" -> pen.text(s["text"] as? String ?: "", f("x"), f("y"), f("size", 14f),
                colour(if (s["dim"] == true) "dim" else s["color"] ?: "text"), if (s["bold"] == true) BOLD else REGULAR)
            "compass" -> {
                val (x, y) = f("x") to f("y")
                nvgBeginPath(vg)
                nvgMoveTo(vg, x, y - 7f)
                nvgLineTo(vg, x + 5f, y + 6f)
                nvgLineTo(vg, x - 5f, y + 6f)
                nvgClosePath(vg)
                pen.fill(colour("text"))
                pen.text(s["text"] as? String ?: "N", x + 15f, y, f("size", 15f), colour("text"), REGULAR)
            }
            "zone" -> guidance.zone(f("x"), f("y"), f("x") + f("w"), f("y") + f("h"), s["text"] as? String)
            "lanes" -> guidance.lanes(f("x"), f("y"), f("count", 4f).toInt(), f("cell", 32f))
            "turn" -> guidance.turn(f("x"), f("lanesY"), f("y"), f("distanceY"), s["text"] as? String ?: "")
            "eta" -> guidance.eta(f("x"), f("x2"), f("y"), f("from"), f("to"))
        }
    }

    /** The cluster's own background where it covers the map. */
    private fun cover(pen: NanoPen, w: Float, h: Float) {
        nvgBeginPath(pen.vg)
        nvgRect(pen.vg, 0f, 0f, w, h)
        nvgFillPaint(pen.vg, nvgLinearGradient(pen.vg, 0f, 0f, 0f, h, pen.rgba(0xFF4A3F9E.toInt(), pen.inner),
            pen.rgba(0xFF1F2B66.toInt(), pen.outer), pen.paint))
        nvgFill(pen.vg)
    }

    /** A round dial: its face and scale ring, ticks on the scale, an inner ring and [value] over [unit] in the middle. */
    private fun dial(pen: NanoPen, cx: Float, cy: Float, r: Float, face: Float, value: String?, unit: String?) {
        val vg = pen.vg
        nvgBeginPath(vg)
        nvgCircle(vg, cx, cy, r)
        pen.fill(colour("panel"))
        nvgStrokeWidth(vg, 3f)
        pen.stroke(colour("ring"))
        nvgBeginPath(vg)
        for (i in 0..12) pen.ray(cx, cy, 0.75 * PI + i * 1.5 * PI / 12, r * 0.80f, r * 0.92f)
        nvgStrokeWidth(vg, 2f)
        pen.stroke(colour("ring"))
        nvgBeginPath(vg)
        nvgCircle(vg, cx, cy, face)
        pen.fill(colour("face"))
        nvgStrokeWidth(vg, 5f)
        pen.stroke(colour("edge"))
        value?.let { pen.text(it, cx, cy, face * 0.75f, colour("text"), BOLD) }
        unit?.let { pen.text(it, cx, cy + face * 0.5f, 13f, colour("dim"), REGULAR) }
    }

    private companion object {
        const val REGULAR = "vc-regular"
        const val BOLD = "vc-bold"
        const val SAFE = 0xCC32D74B.toInt()
        val NAMED = mapOf(
            "text" to 0xFFFFFFFF.toInt(), "dim" to 0xB3FFFFFF.toInt(), "bar" to 0x99000000.toInt(),
            "line" to 0xE6FFFFFF.toInt(), "panel" to 0xF2232A38.toInt(), "edge" to 0xFFC8CDD5.toInt(),
            "face" to 0xFF20242C.toInt(), "ring" to 0xFF6B7280.toInt(),
        )

        /** A named colour, or one written #AARRGGBB or #RRGGBB; [default] for none or a mistake. */
        fun colour(value: Any?, default: String = "text"): Int {
            val text = value as? String ?: return NAMED.getValue(default)
            NAMED[text]?.let { return it }
            val hex = text.removePrefix("#").toLongOrNull(16) ?: return NAMED.getValue(default)
            return if (text.length == 7) (0xFF000000 or hex).toInt() else hex.toInt()
        }
    }
}
