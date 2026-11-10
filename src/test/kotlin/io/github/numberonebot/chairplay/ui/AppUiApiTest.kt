package io.github.numberonebot.chairplay.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.file.Files

class AppUiApiTest : UiControllerFixture() {
    // The wrapper once lacked the forwarding method and answered the default, an empty map.
    @Test
    fun `the folder sizes come through the app's API from the real folders`() {
        Files.createDirectories(dir.resolve("logs"))
        Files.write(dir.resolve("logs").resolve("chairplay.log"), ByteArray(1500))

        assertEquals(1500L, AppUiApi(controller()) { null }.folderSizes()["logs"])
    }

    @Test
    fun `every call of the UI API is forwarded, not left to its default body`() {
        val missing = UiApi::class.java.methods.filter { !it.isSynthetic && !java.lang.reflect.Modifier.isStatic(it.modifiers) }.filter { method ->
            runCatching { AppUiApi::class.java.getDeclaredMethod(method.name, *method.parameterTypes) }.isFailure
        }

        assertTrue("AppUiApi does not forward: ${missing.joinToString { it.name }}", missing.isEmpty())
    }

    @Test
    fun `the car's calls go to the driving that is there when they are made, and are refused without one`() {
        var driving: UiDriving? = null
        val api = AppUiApi(controller()) { driving }

        assertFalse(api.driveMode(true))
        assertFalse(api.gpsDrive(1.0, 0.0, 0.0))
        assertFalse(api.screenshot())
        assertFalse(api.screenshotTarget("main"))

        val calls = mutableListOf<String>()
        driving = object : UiDriving {
            override fun driveMode(on: Boolean) = true.also { calls += "mode $on" }
            override fun gpsDrive(throttle: Double, brake: Double, steer: Double) = true.also { calls += "drive $throttle" }
            override fun screenshot() = true.also { calls += "shot" }
            override fun screenshotTarget(target: String) = true.also { calls += "shot $target" }
        }

        assertTrue(api.driveMode(true) && api.gpsDrive(1.0, 0.0, 0.0) && api.screenshot())
        assertTrue(api.screenshotTarget("altscreen"))
        assertEquals(listOf("mode true", "drive 1.0", "shot", "shot altscreen"), calls)
    }
}
