package io.github.numberonebot.chairplay.media

import org.junit.Assert.assertEquals
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.file.Path
import java.nio.file.Files
import org.junit.Assert.assertTrue
import io.github.numberonebot.chairplay.ui.Json
import java.time.LocalDateTime

class ScreenshotTest {
    // glReadPixels returns the bottom row first; the PNG starts at the top.
    @Test
    fun `read pixels become an upright picture without alpha`() {
        val rgba = ByteBuffer.allocateDirect(2 * 2 * 4)
        // Bottom row: red, green. Top row: blue, white.
        for (pixel in listOf(0xFF0000, 0x00FF00, 0x0000FF, 0xFFFFFF)) {
            rgba.put((pixel shr 16).toByte()).put((pixel shr 8).toByte()).put(pixel.toByte()).put(0x7F)
        }
        rgba.flip()

        val image = screenshotImage(2, 2, rgba)

        assertEquals(0x0000FF, image.getRGB(0, 0) and 0xFFFFFF)
        assertEquals(0xFFFFFF, image.getRGB(1, 0) and 0xFFFFFF)
        assertEquals(0xFF0000, image.getRGB(0, 1) and 0xFFFFFF)
        assertEquals(0x00FF00, image.getRGB(1, 1) and 0xFFFFFF)
    }

    @Test
    fun `six-digit capture sequences survive restart and pair main with AltScreen`() {
        val dir = Files.createTempDirectory("chairplay-shots")
        val first = ScreenshotSequence(dir)
        assertEquals("000001", first.next())
        val main = first.file("000001", "main", "mu1440-790", 2, "Map + dials", 6, "map")
        val alt = first.file("000001", "altscreen", "mu1440-790", 2, "Map + dials", 6, "map")
        assertTrue(main.fileName.toString().startsWith("000001-main-profile-mu1440-790-view-02-map-dials-active-area-06-mode-map-"))
        assertTrue(alt.fileName.toString().startsWith("000001-altscreen-profile-mu1440-790-view-02-map-dials-active-area-06-mode-map-"))
        Files.createDirectories(main.parent)
        Files.write(main, byteArrayOf(1))
        Files.write(alt, byteArrayOf(2))
        assertEquals("000002", ScreenshotSequence(dir).next())
        assertEquals("000002", first.next())
    }

    @Test
    fun `K1 filename uses bounded bitfields and JSON sidecar captures all view and display data`() {
        val dir = Files.createTempDirectory("chairplay-k1")
        val profileDir = Files.createDirectories(dir.resolve("profiles"))
        Files.writeString(profileDir.resolve("demo.json"), """
            {
              "name": "Demo", "display": {
                "width":1010, "height":376, "widthMm":202, "heightMm":75,
                "fps":40, "zoomFactor":85, "physicalZoom":125
              },
              "areas":[[372,58,266,249],[40,58,930,216]],
              "shapes":[{"kind":"text","value":"overlay"}],
              "views":[
                {"name":"Map + dials","area":0},
                {"name":"Wide map","area":1,"scene":"map",
                 "options":{"showETA":"yes","showSpeedLimit":"no","showCompass":"yes",
                 "maneuverLayout":"rightAligned"},"shapes":[{"kind":"line","x":5}]},
                {"name":"Cover","cover":true}
              ]
            }
        """.trimIndent())
        Files.writeString(dir.resolve("settings.properties"),
            "display.zoom.factor=125\ndisplay.physical.zoom=100\ndisplay.width=1280\ndisplay.height=720\nwifi.passphrase=DO_NOT_EXPORT\n")
        val record = ScreenshotRecord.create(dir, "000123", "demo", 1, "map", true)
        val main = record.file("main")
        val alt = record.file("altscreen")
        assertEquals("000123-M-v01-a01-pdemo-k1-C899-z3H2S2D3H", main.fileName.toString().substringBefore("-h"))
        assertTrue(alt.fileName.toString().startsWith("000123-A-v01-a01-pdemo-k1-C899-z3H2S2D3H-h"))
        assertTrue(main.fileName.toString().length < 100)
        record.saveMetadata(listOf("main", "altscreen"))
        val json = Json.parse(Files.readString(dir.resolve("screenshots/000123.json"))) as Map<*, *>
        assertEquals("chairplay-screenshot-k1", json["schema"])
        val images = json["images"] as Map<*, *>
        assertEquals(main.fileName.toString(), images["main"])
        assertEquals(alt.fileName.toString(), images["altscreen"])
        val snapshot = json["state"] as Map<*, *>
        val settings = snapshot["visualSettingsFromDisk"] as Map<*, *>
        assertEquals("125", settings["display.zoom.factor"])
        assertTrue(!settings.containsKey("wifi.passphrase"))
        val full = snapshot["profileFullJson"] as Map<*, *>
        assertEquals(3, (full["views"] as List<*>).size)
        assertEquals(2, (full["areas"] as List<*>).size)
        assertEquals(1, (full["shapes"] as List<*>).size)
        val active = snapshot["active"] as Map<*, *>
        assertEquals(1L, active["controllerView"]?.let { (it as Number).toLong() })
        assertEquals("no", (active["effectiveMapOptions"] as Map<*, *>)["showSpeedLimit"])
        assertEquals("000124", ScreenshotSequence(dir).next())
        val overlay = ScreenshotRecord.create(dir, "000124", "demo", 2, "map", true)
        assertTrue(overlay.file("altscreen").fileName.toString().contains("-v02-a01-"))
    }

    @Test
    fun `screenshots go to their own folder, named by the time they were taken`() {
        val file = screenshotFile(Path.of("app"), LocalDateTime.of(2026, 10, 21, 22, 30, 5))

        assertEquals(Path.of("app", "screenshots", "carplay-2026-10-21-223005.png"), file)
        assertEquals(
            Path.of("app", "screenshots", "altscreen-2026-10-21-223005.png"),
            screenshotFile(Path.of("app"), LocalDateTime.of(2026, 10, 21, 22, 30, 5), "altscreen"),
        )
    }
}
