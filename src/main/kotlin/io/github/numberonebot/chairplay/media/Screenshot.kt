package io.github.numberonebot.chairplay.media

import java.awt.image.BufferedImage
import java.nio.ByteBuffer
import java.nio.file.Files
import java.nio.file.Path
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import javax.imageio.ImageIO
import io.github.numberonebot.chairplay.config.ClusterProfiles
import io.github.numberonebot.chairplay.ui.Json
import java.security.MessageDigest
import java.time.OffsetDateTime
import java.util.Locale
import java.util.Properties
import java.nio.file.StandardCopyOption

/** RGBA pixels as glReadPixels returns them, bottom row first, as an upright RGB picture. */
internal fun screenshotImage(width: Int, height: Int, rgba: ByteBuffer): BufferedImage {
    val image = BufferedImage(width, height, BufferedImage.TYPE_INT_RGB)
    for (row in 0 until height) {
        val y = height - 1 - row
        for (x in 0 until width) {
            val at = (row * width + x) * 4
            val r = rgba.get(at).toInt() and 0xFF
            val g = rgba.get(at + 1).toInt() and 0xFF
            val b = rgba.get(at + 2).toInt() and 0xFF
            image.setRGB(x, y, (r shl 16) or (g shl 8) or b)
        }
    }
    return image
}

/** screenshots/<screen>-<date>-<time>.png in the app folder [dir]; [screen] is carplay or altscreen. */
internal fun screenshotFile(dir: Path, now: LocalDateTime, screen: String = "carplay"): Path =
    dir.resolve("screenshots").resolve("$screen-${now.format(FILE_TIME)}.png")

/** Writes [image] next to the app's other files and logs where, or why not. */
internal fun saveScreenshot(image: BufferedImage, dir: Path, log: (String) -> Unit, screen: String = "carplay") {
    val file = screenshotFile(dir, LocalDateTime.now(), screen)
    try {
        Files.createDirectories(file.parent)
        ImageIO.write(image, "png", file.toFile())
        log("screenshot ${image.width}x${image.height}: $file")
    } catch (error: Exception) {
        log("screenshot not saved: $error")
    }
}

/**
 * One persistent six-digit counter for screenshot actions. A paired F12 capture deliberately uses
 * the same sequence for Main and AltScreen, making the two pictures an analyzable pair.
 * A restart scans the existing screenshot filenames, so an older run is never silently overwritten.
 */
internal class ScreenshotSequence(private val dir: Path) {
    private var last: Int? = null

    @Synchronized
    fun next(): String {
        val folder = dir.resolve("screenshots")
        Files.createDirectories(folder)
        val current = last ?: Files.list(folder).use { paths ->
            paths.iterator().asSequence().mapNotNull { path ->
                Regex("^([0-9]{6})(?:-|\\.json$)").find(path.fileName.toString())?.groupValues?.get(1)?.toIntOrNull()
            }.maxOrNull() ?: 0
        }
        require(current < 999999) { "Screenshot sequence exhausted (999999); archive old screenshots" }
        val number = current + 1
        last = number
        return number.toString().padStart(6, '0')
    }

    /** Safe filenames carry the requested screen, actual Controller view, mapped area, and content at capture time. */
    fun file(number: String, screen: String, profile: String?, view: Int?, viewName: String?, area: Int?, content: String?): Path {
        fun label(value: String?): String = value.orEmpty().lowercase()
            .replace(Regex("[^a-z0-9_-]+"), "-").trim('-').take(36).ifBlank { "unknown" }
        val viewPart = if (view == null) "view-none" else "view-${view.toString().padStart(2, '0')}-${label(viewName)}-active"
        val areaPart = if (area == null) "area-none" else "area-${area.toString().padStart(2, '0')}"
        val name = listOf(number, label(screen), "profile-${label(profile)}", viewPart, areaPart, "mode-${label(content)}",
            LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss"))).joinToString("-")
        return dir.resolve("screenshots").resolve("$name.png")
    }
}

/** Writes an explicitly named screenshot (sequence and active View captured before the asynchronous GL read). */
internal fun saveCapturedScreenshot(image: BufferedImage, file: Path, log: (String) -> Unit) {
    try {
        Files.createDirectories(file.parent)
        check(ImageIO.write(image, "png", file.toFile())) { "No PNG writer" }
        log("screenshot ${image.width}x${image.height}: $file")
    } catch (error: Exception) {
        log("screenshot not saved: $error")
    }
}

private val FILE_TIME = DateTimeFormatter.ofPattern("yyyy-MM-dd-HHmmss")

/**
 * Screenshot configuration code K1. All variable-length data (shapes, coordinates, options,
 * and every view block) is held losslessly in the same numbered JSON sidecar, not in the name.
 *
 * Flags, least significant bit first:
 * 0..1 ETA, 2..3 speed limit, 4..5 compass: 0 default, 1 yes, 2 no, 3 custom.
 * 6..8 maneuver: 0 default, 1 left, 2 right, 3 top, 4 none, 7 custom.
 * 9..10 scene: 0 map, 1 instrumentcluster, 2 overlay-only, 3 custom.
 * 11..12 content: 0 HUD, 1 map, 2 map-card, 3 other.
 * 13 overlay cover, 14 active view has its own map, 15 phone connected.
 *
 * Z contains four big-endian base36 pairs, in this exact order:
 * main zoomFactor (00=Auto), main physicalZoom, cluster zoomFactor, cluster physicalZoom.
 * An explicit K1 marker in every filename makes future layouts backward-compatible.
 */
internal class ScreenshotRecord private constructor(
    private val dir: Path,
    private val number: String,
    private val profileId: String?,
    private val viewIndex: Int?,
    private val areaIndex: Int?,
    private val activeMode: String,
    private val flags: String,
    private val zoom: String,
    private val fingerprint: String,
    private val snapshot: Map<String, Any?>,
) {
    fun file(screen: String): Path {
        require(screen == "main" || screen == "altscreen") { "Unknown capture screen $screen" }
        val tag = if (screen == "main") "M" else "A"
        val profileTag = profileId.orEmpty().lowercase(Locale.ROOT)
            .replace(Regex("[^a-z0-9_-]"), "-").take(16).ifBlank { "none" }
        val viewTag = viewIndex?.toString()?.padStart(2, '0') ?: "xx"
        val areaTag = areaIndex?.toString()?.padStart(2, '0') ?: "xx"
        val filename = "$number-$tag-v$viewTag-a$areaTag-p$profileTag-k1-$flags-z$zoom-h$fingerprint.png"
        require(filename.length <= 112) { "Screenshot filename exceeds 112 characters" }
        return dir.resolve("screenshots").resolve(filename)
    }

    fun saveMetadata(screens: List<String>) {
        val folder = dir.resolve("screenshots")
        val images = screens.associateWith { file(it).fileName.toString() }
        val details = linkedMapOf<String, Any?>(
            "schema" to "chairplay-screenshot-k1",
            "sequence" to number,
            "capturedAt" to OffsetDateTime.now().toString(),
            "images" to images,
            "state" to snapshot,
            "encoding" to mapOf(
                "version" to "k1",
                "flagsHex" to flags,
                "zoomBase36" to zoom,
                "fingerprintSha256_12" to fingerprint,
                "flagLayout" to mapOf(
                    "bits0to1" to "ETA: default=0 yes=1 no=2 custom=3",
                    "bits2to3" to "speedLimit: default=0 yes=1 no=2 custom=3",
                    "bits4to5" to "compass: default=0 yes=1 no=2 custom=3",
                    "bits6to8" to "maneuver: default=0 left=1 right=2 top=3 none=4 custom=7",
                    "bits9to10" to "scene: map=0 instrumentcluster=1 overlayOnly=2 custom=3",
                    "bits11to12" to "content: HUD=0 map=1 mapCard=2 other=3",
                    "bit13" to "active controller view covers the map",
                    "bit14" to "active controller view owns a map area",
                    "bit15" to "iPhone connected",
                ),
                "zoomOrder" to listOf("main.zoomFactor", "main.physicalZoom",
                    "cluster.zoomFactor", "cluster.physicalZoom"),
                "zoomNote" to "Each 2-character base36 pair is a decimal percentage; zoomFactor 00 means Auto",
            ),
        )
        Files.createDirectories(folder)
        val destination = folder.resolve("$number.json")
        val temporary = folder.resolve("$number.json.tmp")
        try {
            Files.writeString(temporary, Json.write(details))
            Files.move(temporary, destination, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE)
        } finally {
            Files.deleteIfExists(temporary)
        }
    }

    companion object {
        private fun valueCode(value: String?) = when (value) {
            null, "" -> 0
            "yes" -> 1
            "no" -> 2
            else -> 3
        }
        private fun maneuverCode(value: String?) = when (value) {
            null, "" -> 0
            "leftAligned" -> 1
            "rightAligned" -> 2
            "topAligned" -> 3
            "no" -> 4
            else -> 7
        }
        private fun percent(value: Int): String {
            require(value in 0..1295) { "Percentage outside K1 representation: $value" }
            return value.toString(36).uppercase(Locale.ROOT).padStart(2, '0')
        }
        private fun asInt(value: Any?): Int? = (value as? Number)?.toInt()
        private fun map(value: Any?): Map<*, *>? = value as? Map<*, *>

        fun create(dir: Path, number: String, profileId: String?, viewIndex: Int?,
            mode: String, connected: Boolean): ScreenshotRecord {
            // Do not export network, phone, pairing or other unrelated settings.
            val settings = runCatching {
                val properties = Properties()
                Files.newBufferedReader(dir.resolve("settings.properties")).use { reader -> properties.load(reader) }
                properties.stringPropertyNames().filter {
                    it.startsWith("display.") || it.startsWith("altscreen.")
                }.sorted().associateWith(properties::getProperty)
            }.getOrDefault(emptyMap())
            val profile = profileId?.let { id ->
                runCatching { Json.parse(ClusterProfiles(dir).text(id)) as? Map<*, *> }.getOrNull()
            }
            val views = (profile?.get("views") as? List<*>).orEmpty()
            val overlayFiles = views.mapNotNull { (it as? Map<*, *>)?.get("overlay") as? String }
                .distinct().sorted().associateWith { overlay ->
                    runCatching { Json.parse(ClusterProfiles(dir).overlayText(overlay)) }
                        .getOrElse { mapOf("unavailable" to (it.message ?: "not found")) }
                }
            val actual = viewIndex?.takeIf { it in views.indices }
            val hasArea: (Int) -> Boolean = { i -> asInt(map(views[i])?.get("area")) != null }
            val mapIndex = actual?.let { index ->
                (index downTo 0).firstOrNull(hasArea) ?: views.indices.firstOrNull(hasArea)
            }
            val selected = actual?.let { map(views[it]) }
            val source = mapIndex?.let { map(views[it]) }
            val options = map(source?.get("options"))
            val area = asInt(source?.get("area"))
            val scene = when {
                actual != null && source == null -> "overlay"
                actual != null && !hasArea(actual) -> "overlay"
                else -> source?.get("scene") as? String ?: "map"
            }
            val sceneCode = when (scene) {
                "map" -> 0
                "instrumentcluster" -> 1
                "overlay" -> 2
                else -> 3
            }
            val modeCode = when (mode) {
                "hud" -> 0
                "map" -> 1
                "map-card" -> 2
                else -> 3
            }
            val packed = valueCode(options?.get("showETA") as? String) or
                (valueCode(options?.get("showSpeedLimit") as? String) shl 2) or
                (valueCode(options?.get("showCompass") as? String) shl 4) or
                (maneuverCode(options?.get("maneuverLayout") as? String) shl 6) or
                (sceneCode shl 9) or (modeCode shl 11) or
                (if (selected?.get("cover") == true) (1 shl 13) else 0) or
                (if (actual != null && hasArea(actual)) (1 shl 14) else 0) or
                (if (connected) (1 shl 15) else 0)
            val flags = "%04X".format(Locale.ROOT, packed)
            val clusterDisplay = map(profile?.get("display"))
            val mainZoom = settings["display.zoom.factor"]?.toIntOrNull() ?: 0
            val mainPhysical = settings["display.physical.zoom"]?.toIntOrNull() ?: 100
            val clusterZoom = asInt(clusterDisplay?.get("zoomFactor")) ?: 0
            val clusterPhysical = asInt(clusterDisplay?.get("physicalZoom")) ?: 100
            val zoom = listOf(mainZoom, mainPhysical, clusterZoom, clusterPhysical)
                .joinToString("") { percent(it) }
            val activeState = linkedMapOf<String, Any?>(
                "profileId" to profileId,
                "controllerView" to viewIndex,
                "controllerViewName" to selected?.get("name"),
                "controllerOverlayFile" to selected?.get("overlay"),
                "controllerInlineShapes" to selected?.get("shapes"),
                "mapView" to mapIndex,
                "mapArea" to area,
                "mode" to mode,
                "connected" to connected,
                "effectiveMapScene" to source?.get("scene"),
                "effectiveMapOptions" to options,
            )
            val mainPixelsWidth = settings["display.width"]?.toIntOrNull() ?: 1280
            val mainPixelsHeight = settings["display.height"]?.toIntOrNull() ?: 720
            val mainPpi = settings["display.ppi"]?.toIntOrNull()?.takeIf { it > 0 }
            val mainSetWidth = settings["display.physical.width.mm"]?.toIntOrNull()
            val mainMmWidth = mainSetWidth
                ?: mainPpi?.let { Math.round(mainPixelsWidth * 25.4 / it).toInt() } ?: 200
            val mainMmHeight = settings["display.physical.height.mm"]?.toIntOrNull()
                ?: (if (mainSetWidth == null) mainPpi?.let { Math.round(mainPixelsHeight * 25.4 / it).toInt() }
                else null)
                ?: Math.round(mainMmWidth.toDouble() * mainPixelsHeight / mainPixelsWidth).toInt()
            val mainDisplay = linkedMapOf<String, Any?>(
                "widthPixels" to mainPixelsWidth, "heightPixels" to mainPixelsHeight,
                "widthPhysicalMm" to mainMmWidth, "heightPhysicalMm" to mainMmHeight,
                "maxFPS" to (settings["display.fps"]?.toIntOrNull() ?: 60),
                "zoomFactor" to mainZoom.takeIf { it > 0 }, "physicalZoom" to mainPhysical,
                "effectiveWidthMm" to Math.round(mainMmWidth.toDouble() * 100 / mainPhysical).toInt(),
                "effectiveHeightMm" to Math.round(mainMmHeight.toDouble() * 100 / mainPhysical).toInt(),
            )
            val clusterDisplayInfo = clusterDisplay?.let {
                val wm = asInt(it["widthMm"]) ?: 0
                val hm = asInt(it["heightMm"]) ?: 0
                linkedMapOf<String, Any?>(
                    "widthPixels" to asInt(it["width"]), "heightPixels" to asInt(it["height"]),
                    "widthPhysicalMm" to wm, "heightPhysicalMm" to hm,
                    "maxFPS" to asInt(it["fps"]), "zoomFactor" to clusterZoom.takeIf { it > 0 },
                    "physicalZoom" to clusterPhysical,
                    "effectiveWidthMm" to Math.round(wm.toDouble() * 100 / clusterPhysical).toInt(),
                    "effectiveHeightMm" to Math.round(hm.toDouble() * 100 / clusterPhysical).toInt(),
                )
            }
            val snapshot = linkedMapOf<String, Any?>(
                "active" to activeState,
                "mainDisplay" to mainDisplay,
                "clusterDisplay" to clusterDisplayInfo,
                "visualSettingsFromDisk" to settings,
                "profileFullJson" to profile,
                "overlayFiles" to overlayFiles,
                "note" to "Saved configuration at capture request; iPhone may still use earlier descriptor until reconnect",
            )
            val canonical = Json.write(mapOf("state" to snapshot, "k1" to flags, "zoom" to zoom))
            val hash = MessageDigest.getInstance("SHA-256").digest(canonical.toByteArray(Charsets.UTF_8))
                .take(6).joinToString("") { "%02X".format(Locale.ROOT, it.toInt() and 255) }
            return ScreenshotRecord(dir, number, profileId, viewIndex, area, mode, flags, zoom, hash, snapshot)
        }
    }
}

