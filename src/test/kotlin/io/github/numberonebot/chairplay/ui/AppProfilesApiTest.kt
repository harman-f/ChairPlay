package io.github.numberonebot.chairplay.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** The AltScreen page's car profiles through the app's API. */
class AppProfilesApiTest : UiControllerFixture() {
    // A save's null is its success, not a missing set of profiles (it once came back as "No car profiles here").
    @Test
    fun `a save that went through answers nothing, and without profiles says so`() {
        val saved = mutableListOf<Pair<String, String?>>()
        val profiles = object : UiProfiles {
            override fun list() = mapOf("profiles" to listOf(mapOf("id" to "car")))
            override fun save(id: String, text: String?): String? = if (id == "bad") "refused" else null.also { saved += id to text }
        }
        val api = AppUiApi(controller(), { profiles }) { null }

        assertNull(api.saveClusterProfile("car", "{}"))
        assertEquals("refused", api.saveClusterProfile("bad", "{}"))
        assertEquals(listOf("car" to "{}"), saved)
        assertEquals(listOf(mapOf("id" to "car")), api.clusterProfiles()["profiles"])
        assertEquals("No car profiles here", AppUiApi(controller()) { null }.saveClusterProfile("car", "{}"))
    }
}
