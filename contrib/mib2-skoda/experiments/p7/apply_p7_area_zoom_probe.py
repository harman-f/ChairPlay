#!/usr/bin/env python3
"""Apply the opt-in P7 /info probe to the exact post-P6 checkout; never touch profiles."""
from pathlib import Path
import subprocess
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply_p7_area_zoom_probe.py <post-P6 ChairPlay checkout>')
root = Path(sys.argv[1]).resolve()
head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
if head != 'fd7a22fa1f503695309ec9efad0e48b2d900349f':
    raise RuntimeError('P7_PIN_MISMATCH')
changes = {}

def edit(path, before, after):
    file = root / path
    source = changes.get(path, file.read_text(encoding='utf-8'))
    if source.count(before) != 1:
        raise RuntimeError(f'P7_ANCHOR_DRIFT {path}: {before[:80]!r}')
    changes[path] = source.replace(before, after)

profile = 'src/main/kotlin/io/github/numberonebot/chairplay/config/ClusterProfile.kt'
generic = 'upstream/shared/src/main/java/com/shilapi/xcertplay/airplay/AirPlayInfoPlist.kt'
test = 'src/test/kotlin/io/github/numberonebot/chairplay/config/ClusterProfileTest.kt'
# Explicit A/B startup opt-in, no profile schema changes. System property also allows isolated tests.
probe = 'System.getProperty("chairplay.p7.probe", System.getenv("CHAIRPLAY_P7_PROBE") ?: "")'
edit(profile,
     '                "adjacentViewAreas" to safeAreas.indices.filter { it != index },\n            )\n',
     '''                "adjacentViewAreas" to safeAreas.indices.filter { it != index },
            ).apply {
                if (P7_MODE in setOf("A", "B")) when (index) {
                    4 -> put("zoomFactor", 100)
                    5 -> put("zoomFactor", 85)
                    6 -> put("zoomFactor", 70)
                }
            }
'''.replace('P7_MODE', probe))
edit(profile, '        zoomFactor?.let { put("zoomFactor", it) }\n',
     f'        if ({probe} != "B") zoomFactor?.let {{ put("zoomFactor", it) }}\n')
edit(generic,
     '                    put("adjacentViewAreas", areas.indices.filter { it != index })\n',
     '''                    put("adjacentViewAreas", areas.indices.filter { it != index })
                    if (P7_MODE in setOf("A", "B")) when (index) {
                        4 -> put("zoomFactor", 100)
                        5 -> put("zoomFactor", 85)
                        6 -> put("zoomFactor", 70)
                    }
'''.replace('P7_MODE', probe))
edit(generic, '        display.zoomFactor?.let { entry["zoomFactor"] = it }\n',
     f'        if (uuid != ALT_UUID || {probe} != "B") display.zoomFactor?.let {{ entry["zoomFactor"] = it }}\n')
edit(test, '    // /info\'s cluster display is the profile\'s, the main screen untouched; without a profile nothing changes.\n',
     '''    @Test
    fun p7ProbeChangesOnlyRequestedClusterAreaFieldsInBothRealDescriptorPaths() {
        val oldProperty = System.getProperty("chairplay.p7.probe")
        val oldProfile = ClusterProfile.active
        try {
            val cfg = configWith("altscreen.enabled=true", "altscreen.profile=mu1440-790")
            for (profileActive in listOf(false, true)) {
                ClusterProfile.active = if (profileActive) cfg.clusterProfile else null
                fun build(mode: String): List<*> {
                    System.setProperty("chairplay.p7.probe", mode)
                    return AirPlayInfoPlist.build(cfg.airPlay)["displays"] as List<*>
                }
                val off = build("")
                val offAgain = build("OFF")
                assertEquals(off, offAgain)
                for (mode in listOf("A", "B")) {
                    val on = build(mode)
                    assertEquals(off[0], on[0]) // Type110 unchanged
                    val original = off[1] as Map<*, *>
                    val experimental = on[1] as Map<*, *>
                    assertEquals(AirPlayInfoPlist.ALT_UUID, experimental["uuid"])
                    val beforeAreas = original["viewAreas"] as List<*>
                    val afterAreas = experimental["viewAreas"] as List<*>
                    assertEquals(7, afterAreas.size)
                    afterAreas.forEachIndexed { index, item ->
                        val area = item as Map<*, *>
                        assertEquals(mapOf(4 to 100, 5 to 85, 6 to 70)[index], area["zoomFactor"])
                        assertEquals(beforeAreas[index], area.filterKeys { it != "zoomFactor" })
                    }
                    val beforeOther = original.filterKeys { it != "viewAreas" && (mode != "B" || it != "zoomFactor") }
                    val afterOther = experimental.filterKeys { it != "viewAreas" }
                    assertEquals(beforeOther, afterOther)
                    if (mode == "B") assertTrue("zoomFactor" !in experimental)
                }
            }
        } finally {
            if (oldProperty == null) System.clearProperty("chairplay.p7.probe")
            else System.setProperty("chairplay.p7.probe", oldProperty)
            ClusterProfile.active = oldProfile
        }
    }

    // /info's cluster display is the profile's, the main screen untouched; without a profile nothing changes.
''')
for path, source in changes.items():
    (root / path).write_text(source, encoding='utf-8', newline='\n')
print('P7_PATCH_APPLIED: experimental area field; default OFF')
