package io.github.numberonebot.chairplay.cluster

import io.github.numberonebot.chairplay.config.ClusterProfile
import io.github.numberonebot.chairplay.config.ClusterProfiles
import io.github.numberonebot.chairplay.input.Control
import io.github.numberonebot.chairplay.input.ControlAction
import io.github.numberonebot.chairplay.input.ControlPad
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Test

/** The car's View button on the AltScreen: the VC's five views, the first three with the map. */
class CarViewsTest {
    private val mu1440 = ClusterProfile.parse("mu1440-790", ClusterProfiles.builtIn("mu1440-790")!!)

    // View steps 0, 1, 2, 3, 4 and round again; views 3 and 4 have no map, so the iPhone keeps view 2's area and URL.
    @Test
    fun `view steps through the car's views as the VC does`() {
        val views = CarViews().apply { connected(mu1440) }
        val map = "maps:/car/instrumentcluster/map"
        val view2 = "$map?showSpeedLimit=yes&maneuverLayout=topAligned"
        assertEquals(4 to map, views.target(7))
        val shown = (1..6).map { views.next(); views.index to views.target(7) }
        assertEquals(listOf(1 to (5 to "maps:/car/instrumentcluster"), 2 to (6 to view2), 3 to (6 to view2), 4 to (6 to view2),
            0 to (4 to map), 1 to (5 to "maps:/car/instrumentcluster")), shown)
    }

    // An area the connection did not declare (a profile saved since with more) falls back to its first.
    @Test
    fun `an area beyond those declared falls back`() {
        val views = CarViews().apply { connected(mu1440) }
        views.next()
        assertEquals(4, views.target(5)!!.first)
    }

    // Without a car's profile View does nothing and the AltScreen has no car view.
    @Test
    fun `without a profile there are no car views`() {
        val views = CarViews().apply { connected(null) }
        assertFalse(views.next())
        assertNull(views.current)
        assertNull(views.target(7))
    }

    @Test
    fun `the view button and key press view`() {
        assertEquals(Control.CarView, ControlPad().press(ControlAction.ALTSCREEN_VIEW))
    }
}
