package io.github.numberonebot.chairplay.config

import com.shilapi.xcertplay.airplay.AirPlayDisplayConfig
import com.shilapi.xcertplay.airplay.AirPlayInfoPlist
import com.shilapi.xcertplay.airplay.AirPlayInsets
import com.shilapi.xcertplay.airplay.AirPlayViewArea
import io.github.numberonebot.chairplay.ui.Json

/** A drawing of the schematic, as its profile's JSON has it: "kind" and the kind's own fields (cluster/ShapePainter). */
typealias Shape = Map<String, Any?>

/**
 * One of a car's cluster views, which its View button steps through: with the map, the view area it shows in ([area])
 * and the cluster URL the car asks for there, its [scene] with [options] (showETA, showSpeedLimit, showCompass, maneuverLayout);
 * without, the car's own content [covers] the map and the iPhone stays on the last view with one. [shapes] draw it.
 */
data class ClusterView(
    val name: String,
    val area: Int?,
    val scene: String = MAP_SCENE,
    val options: Map<String, String> = emptyMap(),
    val covers: Boolean = false,
    val shapes: List<Shape> = emptyList(),
) {
    val hasMap: Boolean get() = area != null

    /** maps:/car/instrumentcluster, /map for the bare map, and the options set, in the order of [OPTIONS]. */
    val url: String
        get() = "maps:/car/instrumentcluster" + (if (scene == MAP_SCENE) "/map" else "") +
            options.filterValues { it.isNotBlank() }.entries.sortedBy { OPTIONS.indexOf(it.key).let { i -> if (i < 0) OPTIONS.size else i } }
                .joinToString("&") { "${it.key}=${it.value}" }.let { if (it.isEmpty()) "" else "?$it" }

    companion object {
        const val MAP_SCENE = "map"
        val SCENES = listOf(MAP_SCENE, "instrumentcluster")
        val OPTIONS = listOf("showETA", "showSpeedLimit", "showCompass", "maneuverLayout")
    }
}

/**
 * A car's cluster as its head unit declares it to the iPhone (altscreen.profile, profiles\<id>.json): the frame, its
 * physical size, which sizes the iPhone's cluster UI, view areas that each cover the whole frame with a safe area of
 * their own, the car's views, and the schematic of the cluster drawn over the AltScreen ([shapes] in every view).
 */
class ClusterProfile(
    val id: String,
    val name: String,
    val size: WindowSize,
    private val physicalMm: WindowSize,
    private val fps: Int,
    private val features: Int,
    private val primaryInputDevice: Int,
    /** Each view area's safe area; every area is the whole frame. */
    val safeAreas: List<AreaRect>,
    val views: List<ClusterView>,
    private val initialView: Int = 0,
    val shapes: List<Shape> = emptyList(),
    /** The iPhone's display scale (iOS 26 Smart Display Zoom) in percent, as zoomFactor; null leaves the key out. */
    val zoomFactor: Int? = null,
    /** Independent physical-mm zoom percent; 100 keeps the original calibrated dimensions. */
    val physicalZoom: Int = 100,
) {
    private val effectivePhysicalMm: WindowSize get() = WindowSize(
        Math.round(physicalMm.width * 100.0 / physicalZoom).toInt().coerceAtLeast(1),
        Math.round(physicalMm.height * 100.0 / physicalZoom).toInt().coerceAtLeast(1),
    )

    init {
        require(views.isNotEmpty()) { "$id has no views" }
        require(views.any { it.hasMap }) { "$id has no view with the map" }
        zoomFactor?.let { require(it in 25..400) { "$id: zoomFactor must be a percentage from 25 to 400, not $it" } }
        require(physicalZoom in 25..400) { "$id: physicalZoom must be a percentage from 25 to 400, not $physicalZoom" }
        views.forEach { view ->
            view.area?.let { require(it in safeAreas.indices) { "$id: ${view.name} shows in area $it, which is not there" } }
            require(view.scene in ClusterView.SCENES) { "$id: ${view.name}'s scene must be ${ClusterView.SCENES.joinToString(" or ")}" }
        }
        safeAreas.forEachIndexed { i, safe ->
            require(safe.width > 0 && safe.height > 0 && safe.fitsInto(size.width, size.height)) {
                "$id: area $i's safe area ($safe) must lie inside ${size.width}x${size.height}"
            }
        }
    }

    /** The view the AltScreen starts on: [initialView] if it has the map, else the first that has. */
    private val firstMapView: ClusterView get() = views.getOrNull(initialView)?.takeIf { it.hasMap } ?: views.first { it.hasMap }

    /** The car view the AltScreen starts on. */
    val startView: Int get() = views.indexOf(firstMapView)

    /** The area a new AltScreen stream starts in (initialViewArea). */
    val initialArea: Int get() = firstMapView.area!!

    /** The view the map shows as car view [index]: its own, or for one without the map the last one before it with. */
    fun mapViewAt(index: Int): ClusterView {
        val i = index.coerceIn(views.indices)
        return (i downTo 0).map(views::get).firstOrNull { it.hasMap } ?: firstMapView
    }

    /** The view areas as ChairPlay's own config holds them, for the count and the window's frame. */
    val areas: List<AirPlayViewArea>
        get() = safeAreas.map { safe ->
            AirPlayViewArea(size.width, size.height, safeArea = AirPlayInsets(top = safe.y, left = safe.x,
                bottom = size.height - safe.y - safe.height, right = size.width - safe.x - safe.width))
        }

    /** The cluster display as ChairPlay's config holds it; [displayEntry] replaces what /info makes of it. */
    fun display(): AirPlayDisplayConfig = AirPlayDisplayConfig(
        widthPixels = size.width, heightPixels = size.height, widthPhysicalMm = effectivePhysicalMm.width,
        heightPhysicalMm = effectivePhysicalMm.height, fps = fps, primaryInputDevice = primaryInputDevice, features = features,
        initialUrl = firstMapView.url, viewAreas = areas, initialViewArea = initialArea,
        zoomFactor = zoomFactor,
    )

    /**
     * The display's /info entry, key for key as the car's head unit sends it: no appearance or transition keys; the
     * zoomFactor only when the profile sets one (mhi2_altscreen_carplay writes it under this lowercase key).
     */
    fun displayEntry(): Map<String, Any?> = linkedMapOf<String, Any?>(
        "uuid" to AirPlayInfoPlist.ALT_UUID,
        "type" to CLUSTER_TYPE,
        "maxFPS" to fps,
        "widthPixels" to size.width,
        "heightPixels" to size.height,
        "widthPhysical" to effectivePhysicalMm.width,
        "heightPhysical" to effectivePhysicalMm.height,
        "features" to features,
        "primaryInputDevice" to primaryInputDevice,
        "initialViewArea" to initialArea,
        "initialURL" to firstMapView.url,
        "viewAreas" to safeAreas.mapIndexed { index, safe ->
            linkedMapOf(
                "widthPixels" to size.width, "heightPixels" to size.height, "originXPixels" to 0, "originYPixels" to 0,
                "safeArea" to linkedMapOf("widthPixels" to safe.width, "heightPixels" to safe.height,
                    "originXPixels" to safe.x, "originYPixels" to safe.y),
                "adjacentViewAreas" to safeAreas.indices.filter { it != index },
            )
        },
    ).apply {
        if (safeAreas.size > 1) put("viewAreaTransitionControl", true)
        zoomFactor?.let { put("zoomFactor", it) }
    }

    companion object {
        private const val CLUSTER_TYPE = 111

        /** The profile [id] in its JSON [text]; refused with what is wrong. */
        fun parse(id: String, text: String): ClusterProfile {
            val root = runCatching { Json.parse(text) }.getOrElse { throw IllegalArgumentException("$id is not JSON: ${it.message}") }
                as? Map<*, *> ?: throw IllegalArgumentException("$id must be a JSON object")
            val display = root["display"] as? Map<*, *> ?: throw IllegalArgumentException("$id has no display")
            fun Map<*, *>.int(key: String, default: Int? = null): Int =
                (this[key] as? Number)?.toInt() ?: default ?: throw IllegalArgumentException("$id: $key must be a number")
            @Suppress("UNCHECKED_CAST")
            fun shapes(of: Map<*, *>) = (of["shapes"] as? List<*>).orEmpty().filterIsInstance<Map<*, *>>().map { it as Shape }
            val areas = (root["areas"] as? List<*>).orEmpty().mapIndexed { i, item ->
                val n = (item as? List<*>)?.map { (it as? Number)?.toInt() }
                require(n != null && n.size == 4 && n.all { it != null }) { "$id: area $i must be [x, y, width, height]" }
                AreaRect(n[0]!!, n[1]!!, n[2]!!, n[3]!!)
            }
            val views = (root["views"] as? List<*>).orEmpty().mapIndexed { i, item ->
                val view = item as? Map<*, *> ?: throw IllegalArgumentException("$id: view $i must be an object")
                ClusterView(
                    name = view["name"] as? String ?: "View $i",
                    area = (view["area"] as? Number)?.toInt(),
                    scene = view["scene"] as? String ?: ClusterView.MAP_SCENE,
                    options = (view["options"] as? Map<*, *>).orEmpty().entries
                        .mapNotNull { (k, v) -> (k as? String)?.let { key -> (v as? String)?.let { key to it } } }.toMap(),
                    covers = view["cover"] == true,
                    shapes = shapes(view),
                )
            }
            return ClusterProfile(
                id, root["name"] as? String ?: id, WindowSize(display.int("width"), display.int("height")),
                WindowSize(display.int("widthMm"), display.int("heightMm")), display.int("fps", 30), display.int("features", 10),
                display.int("primaryInputDevice", 3), areas, views, root.int("initialView", 0), shapes(root),
                (display["zoomFactor"] as? Number)?.toInt(),
                display.int("physicalZoom", 100),
            )
        }

        /** The profile the session being set up declares, set as it starts; null declares DiPlay's cluster. */
        @Volatile
        var active: ClusterProfile? = null

        /** Puts [profile]'s cluster display in /info's [info] in place of DiPlay's. */
        fun advertise(info: MutableMap<String, Any?>, profile: ClusterProfile? = active) {
            if (profile == null) return
            info["displays"] = (info["displays"] as? List<*>)?.map { item ->
                if ((item as? Map<*, *>)?.get("uuid") == AirPlayInfoPlist.ALT_UUID) profile.displayEntry() else item
            }
        }
    }
}
