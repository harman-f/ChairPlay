package io.github.numberonebot.chairplay.config

import com.shilapi.xcertplay.airplay.AirPlayInfoPlist
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.file.Files

/** altscreen.profile: the AltScreen declared as a car's head unit declares its cluster, from profiles\<id>.json. */
class ClusterProfileTest {
    @After
    fun forget() {
        ClusterProfile.active = null
    }

    private val builtIn get() = ClusterProfile.parse("mu1440-790", ClusterProfiles.builtIn("mu1440-790")!!)

    // The MU1440's core.so (create_alt_display, Auto): one 1010x376 frame, seven areas of the whole frame, each with its
    // own safe area; the VC's views 0, 1 and 2 are areas 4, 5 and 6, views 3 and 4 have no map.
    @Test
    fun `the built-in mu1440 profile declares the cluster as the car does`() {
        val entry = builtIn.displayEntry()
        assertEquals(AirPlayInfoPlist.ALT_UUID, entry["uuid"])
        assertEquals(111, entry["type"])
        assertEquals(listOf(40, 1010, 376, 300, 112, 10, 3, 4), listOf("maxFPS", "widthPixels", "heightPixels",
            "widthPhysical", "heightPhysical", "features", "primaryInputDevice", "initialViewArea").map(entry::get))
        assertEquals("maps:/car/instrumentcluster/map", entry["initialURL"])
        val areas = entry["viewAreas"] as List<*>
        assertEquals(7, areas.size)
        val safe = areas.map { area ->
            area as Map<*, *>
            assertEquals(listOf(1010, 376, 0, 0), listOf("widthPixels", "heightPixels", "originXPixels", "originYPixels").map(area::get))
            val rect = area["safeArea"] as Map<*, *>
            listOf("originXPixels", "originYPixels", "widthPixels", "heightPixels").map(rect::get)
        }
        assertEquals(listOf(listOf(364, 110, 280, 205), listOf(100, 56, 800, 245), listOf(205, 90, 610, 220)), safe.subList(4, 7))
        assertEquals(listOf(0, 1, 2, 3, 5, 6), (areas[4] as Map<*, *>)["adjacentViewAreas"])
        assertTrue(areas.none { "drawUIOutsideSafeArea" in ((it as Map<*, *>)["safeArea"] as Map<*, *>) })
        assertEquals(listOf(4, 5, 6, null, null), builtIn.views.map { it.area })
        assertEquals("maps:/car/instrumentcluster", builtIn.views[1].url)
    }

    // A view without the map shows the last one's before it; the URL takes the options set, in their order.
    @Test
    fun `views without the map keep the last one, and options make the url`() {
        assertEquals(builtIn.views[2], builtIn.mapViewAt(4))
        val card = ClusterView("v", 0, "instrumentcluster", linkedMapOf("showETA" to "no", "showSpeedLimit" to "", "maneuverLayout" to "leftAligned"))
        assertEquals("maps:/car/instrumentcluster?showETA=no&maneuverLayout=leftAligned", card.url)
        assertEquals("maps:/car/instrumentcluster/map?showSpeedLimit=yes", ClusterView("v", 0, options = mapOf("showSpeedLimit" to "yes")).url)
        // In the same order whatever the JSON's, the compass among them.
        val compass = ClusterView("v", 0, options = linkedMapOf("maneuverLayout" to "topAligned", "showCompass" to "no", "showETA" to "yes"))
        assertEquals("maps:/car/instrumentcluster/map?showETA=yes&showCompass=no&maneuverLayout=topAligned", compass.url)
    }

    // A connection with the profile set takes its frame and areas; the profile comes from the app folder's profiles.
    @Test
    fun `the setting reads the profile from the profiles folder`() {
        val config = configWith("altscreen.enabled=true", "altscreen.profile=mu1440-790", "altscreen.width=1920")
        assertEquals(WindowSize(1010, 376), config.altscreen!!.size)
        assertEquals(7, config.altscreenAreaCount)
        assertEquals(1010, config.airPlay.cluster!!.widthPixels)
        assertNull(configWith("altscreen.enabled=true").clusterProfile)
        assertThrows(IllegalArgumentException::class.java) { configWith("altscreen.enabled=true", "altscreen.profile=nope") }
    }

    // A profile saved must read as one; under a new id it joins the list; a built-in one deleted comes back.
    @Test
    fun `profiles are kept, refused, copied and put back`() {
        val profiles = ClusterProfiles(Files.createTempDirectory("profiles"))
        assertEquals(listOf("mu1440-790"), profiles.ids())
        assertNotNull(profiles.save("broken", "{"))
        val bad = profiles.text("mu1440-790").replace("\"area\": 6", "\"area\": 9")
        assertTrue(profiles.save("mu1440-790", bad)!!.contains("area 9"))
        assertNull(profiles.save("my-car", profiles.text("mu1440-790").replace("Skoda 790", "My car")))
        assertEquals(listOf("mu1440-790", "my-car"), profiles.ids())
        assertTrue(profiles.load("my-car").name.startsWith("My car"))
        assertNotNull(profiles.save("../x", "{}"))
        assertNull(profiles.delete("mu1440-790"))
        assertEquals(listOf("mu1440-790", "my-car"), profiles.ids())
    }

    @Test
    fun `external overlay files map to views without modifying inline profile JSON`() {
        val dir = Files.createTempDirectory("chairplay-overlays")
        val store = ClusterProfiles(dir)
        val base = store.text("mu1440-790")
        val linked = base.replace("\"name\": \"View 0\"", "\"name\": \"View 0\", \"overlay\": \"custom-dials\"")
        assertTrue(store.save("linked", linked)?.contains("custom-dials") == true)
        assertNull(store.saveOverlay("custom-dials",
            """{"name":"Custom dials","shapes":[{"kind":"line","x":4,"y":5}]}"""))
        assertNull(store.save("linked", linked))
        assertEquals(1, store.load("linked").views[0].shapes.size)
        assertEquals(4L, store.load("linked").views[0].shapes[0]["x"])
        assertTrue(store.text("linked").contains("\"overlay\": \"custom-dials\""))
        assertNotNull(store.saveOverlay("../escape", """{"shapes":[]}"""))
        assertNotNull(store.saveOverlay("invalid", """{"shapes":[42]}"""))
    }

    // display.zoomFactor goes to /info as zoomFactor when set (the car's build has 85), left out when not; out of range is refused.
    @Test
    fun `the zoom factor goes to the display only when set`() {
        val text = ClusterProfiles.builtIn("mu1440-790")!!
        assertEquals(85, builtIn.displayEntry()["zoomFactor"])
        assertTrue("zoomFactor" !in ClusterProfile.parse("z", text.replace(", \"zoomFactor\": 85", "")).displayEntry())
        val zoomed = ClusterProfile.parse("z", text.replace("\"zoomFactor\": 85", "\"zoomFactor\": 125"))
        assertEquals(125, zoomed.displayEntry()["zoomFactor"])
        assertEquals(125, zoomed.display().zoomFactor)
        val config = configWith("altscreen.enabled=true", "altscreen.profile=mu1440-790")
        val info = AirPlayInfoPlist.build(config.airPlay)
        val alt = (info["displays"] as List<*>)[1] as Map<*, *>
        assertEquals(85, alt["zoomFactor"])
        assertThrows(IllegalArgumentException::class.java) {
            ClusterProfile.parse("z", text.replace("\"zoomFactor\": 85", "\"zoomFactor\": 5"))
        }
    }

    // The two scaling methods must compose: the iOS zoomFactor is sent unchanged while effective mm change.
    @Test
    fun `physical zoom changes the advertised millimetres without overriding iOS zoomFactor`() {
        val source = ClusterProfiles.builtIn("mu1440-790")!!
        val scaled = ClusterProfile.parse("scaled", source.replace("\"zoomFactor\": 85", "\"zoomFactor\": 125, \"physicalZoom\": 125"))
        val entry = scaled.displayEntry()
        assertEquals(125, entry["zoomFactor"])
        assertEquals(240, entry["widthPhysical"])
        assertEquals(90, entry["heightPhysical"])
        assertEquals(240, scaled.display().widthPhysicalMm)
        assertEquals(90, scaled.display().heightPhysicalMm)
        assertEquals(300, builtIn.displayEntry()["widthPhysical"])
        assertThrows(IllegalArgumentException::class.java) {
            ClusterProfile.parse("wrong", source.replace("\"zoomFactor\": 85", "\"zoomFactor\": 85, \"physicalZoom\": 0"))
        }
    }

    @Test
    fun negotiatedInfoHasClusterNeighborIndicesAndTransitionControl() {
        val cfg = configWith("altscreen.enabled=true", "altscreen.profile=mu1440-790")
        // ChairPlay's Gradle copy additionally applies ClusterProfile.advertise.
        // Test both the generic serializer AND the actual active-profile override.
        ClusterProfile.active = null
        val generic = AirPlayInfoPlist.build(cfg.airPlay)["displays"] as List<*>
        val genericAreas = (generic[1] as Map<*, *>)["viewAreas"] as List<*>
        assertEquals(listOf(0, 1, 2, 3, 5, 6),
            (genericAreas[4] as Map<*, *>)["adjacentViewAreas"])
        ClusterProfile.active = cfg.clusterProfile
        val displays = AirPlayInfoPlist.build(cfg.airPlay)["displays"] as List<*>
        val main = displays[0] as Map<*, *>
        val vc = displays[1] as Map<*, *>
        assertEquals(110, main["type"])
        assertEquals(111, vc["type"])
        assertEquals(AirPlayInfoPlist.ALT_UUID, vc["uuid"])
        assertEquals(true, vc["viewAreaTransitionControl"])
        val areas = vc["viewAreas"] as List<*>
        assertEquals(7, areas.size)
        areas.forEachIndexed { index, area ->
            area as Map<*, *>
            assertEquals(areas.indices.filter { it != index }, area["adjacentViewAreas"])
            assertEquals(1010, area["widthPixels"])
            assertEquals(376, area["heightPixels"])
            assertTrue("safeArea" in area)
        }
        assertTrue((main["viewAreas"] as List<*>).all { "adjacentViewAreas" !in (it as Map<*, *>) })
        assertEquals(true, builtIn.displayEntry()["viewAreaTransitionControl"])
        assertEquals(85, vc["zoomFactor"])
    }

    // /info's cluster display is the profile's, the main screen untouched; without a profile nothing changes.
    @Test
    fun `advertise replaces the cluster display only`() {
        val main = mapOf("uuid" to AirPlayInfoPlist.MAIN_UUID, "widthPixels" to 1280)
        val info = mutableMapOf<String, Any?>("displays" to listOf(main, mapOf("uuid" to AirPlayInfoPlist.ALT_UUID, "widthPixels" to 1440)))
        ClusterProfile.advertise(info, null)
        assertEquals(1440, ((info["displays"] as List<*>)[1] as Map<*, *>)["widthPixels"])
        ClusterProfile.advertise(info, builtIn)
        val displays = info["displays"] as List<*>
        assertEquals(main, displays[0])
        assertEquals(1010, (displays[1] as Map<*, *>)["widthPixels"])
    }
}
