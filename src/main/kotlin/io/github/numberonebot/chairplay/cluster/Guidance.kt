package io.github.numberonebot.chairplay.cluster

import io.github.numberonebot.chairplay.drive.NanoPen
import org.lwjgl.nanovg.NanoVG.*

/**
 * The cluster's own route guidance and ETA in a schematic (ShapePainter's zone, lanes, turn and eta shapes): what lies
 * over the map as amber zones with stand-in contents, so what they cover of the iPhone's map, and of its safe area,
 * shows; the turn, in a dial or a panel, without one.
 */
internal class Guidance(private val pen: NanoPen, private val font: String) {
    private val vg = pen.vg

    /** A zone from [x0], [y0] to [x1], [y1], with [text] in its middle. */
    fun zone(x0: Float, y0: Float, x1: Float, y1: Float, text: String?) {
        nvgBeginPath(vg)
        nvgRoundedRect(vg, x0, y0, x1 - x0, y1 - y0, 4f)
        pen.fill(FILL)
        nvgStrokeWidth(vg, 1.2f)
        pen.stroke(EDGE)
        text?.let { pen.text(it, (x0 + x1) / 2, (y0 + y1) / 2, 15f, TEXT, font) }
    }

    /** [count] lane cells round [x], the second one recommended (straight on), the rest crossed out. */
    fun lanes(x: Float, y: Float, count: Int, cell: Float) {
        val left = x - cell * count / 2
        nvgBeginPath(vg)
        for (i in 0..count) {
            nvgMoveTo(vg, left + i * cell, y - cell * 0.35f)
            nvgLineTo(vg, left + i * cell, y + cell * 0.35f)
        }
        for (i in 0 until count) {
            val cx = left + (i + 0.5f) * cell
            val s = cell * 0.18f
            if (i == 1) {
                nvgMoveTo(vg, cx, y + s * 1.6f)
                nvgLineTo(vg, cx, y - s * 1.6f)
                nvgMoveTo(vg, cx - s, y - s * 0.6f)
                nvgLineTo(vg, cx, y - s * 1.6f)
                nvgLineTo(vg, cx + s, y - s * 0.6f)
            } else {
                nvgMoveTo(vg, cx - s, y - s)
                nvgLineTo(vg, cx + s, y + s)
                nvgMoveTo(vg, cx + s, y - s)
                nvgLineTo(vg, cx - s, y + s)
            }
        }
        nvgStrokeWidth(vg, 1.5f)
        pen.stroke(TEXT)
    }

    /** The lanes at [lanesY], a right turn's arrow at [arrow] and its [text] distance at [distance], round [x]. */
    fun turn(x: Float, lanesY: Float, arrow: Float, distance: Float, text: String) {
        lanes(x, lanesY, 4, 22f)
        nvgBeginPath(vg)
        nvgMoveTo(vg, x - 8f, arrow + 18f)
        nvgLineTo(vg, x - 8f, arrow - 6f)
        nvgLineTo(vg, x + 10f, arrow - 6f)
        nvgStrokeWidth(vg, 9f)
        pen.stroke(TEXT)
        nvgBeginPath(vg)
        nvgMoveTo(vg, x + 10f, arrow - 18f)
        nvgLineTo(vg, x + 24f, arrow - 6f)
        nvgLineTo(vg, x + 10f, arrow + 6f)
        nvgClosePath(vg)
        pen.fill(TEXT)
        pen.text(text, x, distance, 17f, TEXT, font)
    }

    /** The distance at [distanceX] and the time at [timeX] left to the destination on line [y], in a zone [from] to [to]. */
    fun eta(distanceX: Float, timeX: Float, y: Float, from: Float, to: Float) {
        zone(from, y - 12f, to, y + 12f, null)
        val icon = distanceX - 36f
        nvgBeginPath(vg)
        nvgCircle(vg, icon, y, 6f)
        for (k in 0..3) pen.ray(icon, y, k * Math.PI / 2, 0f, 9f)
        nvgStrokeWidth(vg, 1.5f)
        pen.stroke(TEXT)
        pen.text("1.2 km", distanceX + 4f, y, 14f, TEXT, font)
        nvgBeginPath(vg)
        nvgCircle(vg, timeX + 28f, y, 6f)
        pen.ray(timeX + 28f, y, -Math.PI / 2, 0f, 5f)
        pen.ray(timeX + 28f, y, 0.0, 0f, 4f)
        nvgStrokeWidth(vg, 1.5f)
        pen.stroke(TEXT)
        pen.text("0:03", timeX - 6f, y, 14f, TEXT, font)
    }

    private companion object {
        const val TEXT = 0xFFFFFFFF.toInt()
        const val FILL = 0x59B07A10
        const val EDGE = 0xE6FFB020.toInt()
    }
}
