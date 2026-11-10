package io.github.numberonebot.chairplay

import org.junit.Assert.*
import org.junit.Test

class PanelUpdateProbeTest {
    private fun display(type: Int, id: String): Map<String, Any?> = linkedMapOf(
        "uuid" to id, "type" to type,
        "widthPixels" to 1000, "heightPixels" to 400,
        "widthPhysical" to 250, "heightPhysical" to 100,
        "zoomFactor" to 85,
    )

    @Suppress("UNCHECKED_CAST")
    @Test fun originalDescriptorAndStreamIdentitySurviveTheNoOp() {
        PanelUpdateProbe.setEnabled(true)
        try {
            val info = linkedMapOf<String, Any?>("displays" to listOf(display(110, "main"), display(111, "cluster")))
            val legacy = info["displays"]
            PanelUpdateProbe.advertise(info)
            assertSame(legacy, info["displays"])
            val panels = info["displayPanels"] as List<Map<String, Any?>>
            assertEquals(2, panels.size)
            assertEquals("cluster", panels[1]["uid"])
            val baseline = PanelUpdateProbe.command("baseline")!!
            val actual = ((baseline["params"] as Map<*, *>)["displayPanels"] as List<Map<String, Any?>>).single()
            assertEquals(panels[1]["initialVideoStreams"], actual["videoStreams"])
            assertEquals(85, actual["zoomFactor"])
            assertEquals(250, actual["widthPhysical"])
            assertEquals(1000, actual["widthPixels"])
        } finally { PanelUpdateProbe.setEnabled(false) }
    }

    @Suppress("UNCHECKED_CAST")
    @Test fun scaleProbesChangeOnlyTheRequestedFields() {
        PanelUpdateProbe.setEnabled(true)
        try {
            val info = linkedMapOf<String, Any?>("displays" to listOf(display(110, "main"), display(111, "cluster")))
            PanelUpdateProbe.advertise(info)
            fun panel(mode: String, value: Int): Map<String, Any?> {
                val command = PanelUpdateProbe.command(mode, value)!!
                return ((command["params"] as Map<*, *>)["displayPanels"] as List<Map<String, Any?>>).single()
            }
            val zoom = panel("zoom", 150)
            assertEquals(150, zoom["zoomFactor"])
            assertEquals(250, zoom["widthPhysical"])
            val physical = panel("physical", 125)
            assertEquals(200, physical["widthPhysical"])
            assertEquals(80, physical["heightPhysical"])
            assertEquals(85, physical["zoomFactor"])
            assertEquals(1000, physical["widthPixels"])
            assertNull(PanelUpdateProbe.command("zoom", 42))
            assertNull(PanelUpdateProbe.command("anything", 100))
        } finally { PanelUpdateProbe.setEnabled(false) }
    }

    @Test fun optInAndIncompleteDescriptorsFailClosed() {
        PanelUpdateProbe.setEnabled(false)
        val info = linkedMapOf<String, Any?>("displays" to listOf(display(111, "cluster")))
        PanelUpdateProbe.advertise(info)
        assertFalse(info.containsKey("displayPanels"))
        PanelUpdateProbe.setEnabled(true)
        try {
            PanelUpdateProbe.advertise(info)
            assertFalse(info.containsKey("displayPanels"))
            assertNull(PanelUpdateProbe.command("baseline"))
        } finally { PanelUpdateProbe.setEnabled(false) }
    }
}
