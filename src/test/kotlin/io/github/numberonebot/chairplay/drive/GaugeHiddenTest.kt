package io.github.numberonebot.chairplay.drive

import io.github.numberonebot.chairplay.config.configWith
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** gps.gauges=hidden: drive mode without the wells, the speed alone in a line at the bottom. */
class GaugeHiddenTest {
    @Test
    fun `hidden is a gauge size the settings take`() {
        assertEquals(GaugeSize.HIDDEN, configWith("gps.gauges=hidden").gps.gauges)
    }

    // Shift+F10 steps large, small, hidden and round again.
    @Test
    fun `shift f10 steps through the three`() {
        assertEquals(listOf(GaugeSize.SMALL, GaugeSize.HIDDEN, GaugeSize.LARGE), GaugeSize.entries.map { it.other() })
    }

    // Hidden wells are gone for the motion, so the HUD makes no room for them.
    @Test
    fun `hidden gauges leave no wells`() {
        val motion = GaugeMotion { 0L }
        assertNull(motion.frame(wellsOf(view(GaugeSize.HIDDEN))))
        assertEquals(0f, motion.there)
    }

    private fun view(size: GaugeSize) = GaugeView(0.0, 0.0, "P", 0.0, 0.0, 0.0,
        GaugeScale.speedometer(), GaugeScale.tachometer(CarSpec()), size = size)
}
