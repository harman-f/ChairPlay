package io.github.numberonebot.chairplay.config

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** window.settings.separate: the settings over CarPlay unless asked for in a window of their own. */
class SettingsWindowTest {
    @Test
    fun `the settings show over carplay unless set apart`() {
        assertFalse(configWith().windowOnTop.separateSettings)
        assertTrue(configWith("window.settings.separate=true").windowOnTop.separateSettings)
    }
}
