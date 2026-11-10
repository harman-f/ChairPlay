package io.github.numberonebot.chairplay.config

import java.nio.file.Files
import java.nio.file.Path
import io.github.numberonebot.chairplay.ui.Json
import kotlin.io.path.extension
import kotlin.io.path.listDirectoryEntries
import kotlin.io.path.nameWithoutExtension

/**
 * The cars' cluster profiles, profiles\<id>.json in the app folder: the ones the app comes with ([BUILT_IN]) are
 * written there when missing, so each can be edited, copied under another id, or deleted and so put back as it came.
 */
class ClusterProfiles(dir: Path) {
    val folder: Path = dir.resolve("profiles")
    val overlaysFolder: Path = dir.resolve("overlays")

    /** Reusable cockpit drawings, independent of firmware/profile; JSON {name, shapes:[...]}. */
    fun overlayIds(): List<String> = if (Files.isDirectory(overlaysFolder))
        overlaysFolder.listDirectoryEntries("*.json").map { it.nameWithoutExtension }.sorted()
    else emptyList()

    fun overlayText(id: String): String {
        require(ID.matches(id)) { "Invalid overlay id: $id" }
        return Files.readString(overlaysFolder.resolve("$id.json"))
    }

    private fun overlayShapes(id: String): List<Map<*, *>> {
        val root = Json.parse(overlayText(id)) as? Map<*, *>
            ?: throw IllegalArgumentException("Overlay $id must be a JSON object")
        return (root["shapes"] as? List<*>)?.map {
            it as? Map<*, *> ?: throw IllegalArgumentException("Overlay $id contains a non-object shape")
        } ?: throw IllegalArgumentException("Overlay $id requires a shapes array")
    }

    /** Invalid references refuse a save; the original profile and its inline overlays are left intact. */
    private fun effective(id: String, text: String): ClusterProfile {
        val root = Json.parse(text) as? Map<*, *>
            ?: throw IllegalArgumentException("$id must be a JSON object")
        val items = root["views"] as? List<*> ?: emptyList<Any>()
        val resolved = items.map { item ->
            val view = item as? Map<*, *> ?: throw IllegalArgumentException("$id contains a bad view")
            val ref = view["overlay"] as? String
            val enabled = view["overlayEnabled"] != false
            val imageName = view["overlayImage"] as? String
            if (!enabled) {
                LinkedHashMap(view).apply { put("shapes", emptyList<Any>()) }
            } else if (!imageName.isNullOrBlank()) {
                require(Regex("[A-Za-z0-9._-]{1,64}\\.png", RegexOption.IGNORE_CASE).matches(imageName)) {
                    "Invalid PNG overlay filename: $imageName"
                }
                val file = overlaysFolder.resolve(imageName)
                require(Files.isRegularFile(file) && Files.size(file) in 8..10_485_760) {
                    "PNG overlay must exist in overlays/ and be at most 10 MiB: $imageName"
                }
                val header = Files.newInputStream(file).use { it.readNBytes(8) }
                require(header.contentEquals(byteArrayOf(137.toByte(), 80, 78, 71, 13, 10, 26, 10))) {
                    "PNG overlay has an invalid header: $imageName"
                }
                val d = root["display"] as? Map<*, *> ?: error("Missing display")
                val w = d["width"] as? Number ?: error("Missing display width")
                val h = d["height"] as? Number ?: error("Missing display height")
                val pngShape = mapOf("kind" to "png", "path" to file.toAbsolutePath().normalize().toString(),
                    "x" to 0, "y" to 0, "w" to w.toInt(), "h" to h.toInt())
                LinkedHashMap(view).apply { put("shapes", listOf(pngShape)) }
            } else if (ref.isNullOrBlank()) view else {
                require(ID.matches(ref)) { "Invalid overlay reference: $ref" }
                LinkedHashMap(view).apply { put("shapes", overlayShapes(ref)) }
            }
        }
        return ClusterProfile.parse(id, Json.write(LinkedHashMap(root).apply { put("views", resolved) }))
    }

    fun saveOverlay(id: String, text: String): String? {
        if (!ID.matches(id)) return "Overlay ID allows only letters, digits, dots, hyphens and underscores (up to 64)"
        if (text.toByteArray(Charsets.UTF_8).size > 1_048_576) return "Overlay JSON must be at most 1 MiB"
        runCatching {
            val root = Json.parse(text) as? Map<*, *> ?: error("Overlay must be an object")
            val shapes = root["shapes"] as? List<*> ?: error("Overlay requires shapes array")
            require(shapes.size <= 1500 && shapes.all { it is Map<*, *> }) { "Overlay has invalid shapes" }
        }.onFailure { return it.message ?: "Invalid overlay JSON" }
        Files.createDirectories(overlaysFolder)
        Files.writeString(overlaysFolder.resolve("$id.json"), text)
        return null
    }

    /** The profiles' ids, the built-in ones among them. */
    fun ids(): List<String> {
        writeBuiltIns()
        return folder.listDirectoryEntries().filter { it.extension == "json" }.map { it.nameWithoutExtension }.sorted()
    }

    /** Profile [id]'s JSON text. */
    fun text(id: String): String {
        writeBuiltIns()
        val file = file(id)
        require(Files.exists(file)) { "No car profile $id in ${folder.fileName}" }
        return Files.readString(file)
    }

    /** Profile [id], read from its file; refused with what is wrong. */
    fun load(id: String): ClusterProfile = effective(id, text(id))

    /** Keeps [text] as profile [id] once it reads as one; the reason it does not, else null. */
    fun save(id: String, text: String): String? {
        if (!ID.matches(id)) return "A profile's name takes letters, digits, '.', '-' and '_', not $id"
        runCatching { effective(id, text) }.onFailure { return it.message }
        Files.createDirectories(folder)
        Files.writeString(file(id), text)
        return null
    }

    /** Deletes profile [id]; a built-in one comes back as it came the next time the profiles are read. */
    fun delete(id: String): String? {
        if (!ID.matches(id)) return "No car profile $id"
        Files.deleteIfExists(file(id))
        return null
    }

    private fun file(id: String): Path = folder.resolve("$id.json")

    private fun writeBuiltIns() {
        Files.createDirectories(folder)
        for (id in BUILT_IN) {
            val file = file(id)
            if (!Files.exists(file)) builtIn(id)?.let { Files.writeString(file, it) }
        }
    }

    companion object {
        val BUILT_IN = listOf("mu1440-790")
        private val ID = Regex("[A-Za-z0-9._-]{1,64}")

        /** Built-in profile [id]'s JSON as the app carries it. */
        fun builtIn(id: String): String? =
            ClusterProfiles::class.java.getResourceAsStream("/profiles/$id.json")?.use { String(it.readBytes(), Charsets.UTF_8) }
    }
}
