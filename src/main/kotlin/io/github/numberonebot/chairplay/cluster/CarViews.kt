package io.github.numberonebot.chairplay.cluster

import io.github.numberonebot.chairplay.config.ClusterProfile
import io.github.numberonebot.chairplay.media.WindowOverlay

/**
 * The car's View button on an AltScreen with a car's [profile] (altscreen.profile): the car view the cluster shows,
 * which View steps through as the car's does, the view area and URL the iPhone is asked for there, and its schematic
 * drawn over the iPhone's picture. A car view with the map moves the iPhone to that view's area and URL; one without
 * keeps the last, as the car's core.so does. [repaint] draws the window again for a new view's schematic.
 */
class CarViews(private val repaint: () -> Unit = {}) {
    /** The profile in force: the connection's, or the one the AltScreen page saved since; null without one. */
    @Volatile
    var profile: ClusterProfile? = null
        set(value) {
            field = value
            repaint()
        }

    /** The car view the cluster shows. */
    @Volatile
    var index = 0
        private set

    /** The car view, null without a car's profile. */
    val current: Int? get() = profile?.let { index.coerceIn(it.views.indices) }

    /** View pressed: the next car view; false without a profile. */
    fun next(): Boolean {
        val profile = profile ?: return false
        index = (current!! + 1) % profile.views.size
        repaint()
        return true
    }

    /** A connection with [now]'s profile starts on its first view with the map. */
    fun connected(now: ClusterProfile?) {
        index = now?.startView ?: 0
        profile = now
    }

    /**
     * The view area and URL the iPhone is asked for in the car view now, the area one of the [count] the connection
     * declared; null without a profile.
     */
    fun target(count: Int): Pair<Int, String>? = profile?.let { profile ->
        val view = profile.mapViewAt(index)
        (view.area!!.takeIf { it < count } ?: profile.initialArea.coerceAtMost(count - 1)) to view.url
    }

    /** The window title's part for the car view: profile, view and area. */
    fun title(): String? = profile?.let { p ->
        val view = p.views[current!!]
        "${p.id} ${view.name}" + (view.area?.let { ", area $it" } ?: ", no map")
    }

    /** [under] with the car view's schematic over it, drawn only with a car's profile. */
    fun over(under: WindowOverlay): WindowOverlay = Layers(listOf(ShapePainter(::schematic), under))

    /** The car view for the schematic; null without a profile. */
    fun schematic(): SchematicView? = profile?.let { SchematicView(current!!, it) }
}

/** What the schematic draws: car view [index] of [profile]. */
data class SchematicView(val index: Int, val profile: ClusterProfile)

/** [layers] drawn in their order, the last on top. */
private class Layers(private val layers: List<WindowOverlay>) : WindowOverlay {
    override fun open() = layers.forEach { it.open() }

    override fun paint(width: Int, height: Int) = layers.forEach { it.paint(width, height) }

    override fun close() = layers.forEach { runCatching { it.close() } }

    override val animating: Boolean get() = layers.any { it.animating }
}
