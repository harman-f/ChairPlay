#!/usr/bin/env python3
"""Fail-closed, isolated ChairPlay Live Lab patch. Apply after accepted UI v5 source patch.

Refuses missing, duplicated, or changed anchor text before writing any source file.
Does not touch the accepted build workflow, release branch, or user's Windows install.
"""
from pathlib import Path
import subprocess
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: integrate_live_lab.py <pinned-chairplay-checkout>")
root = Path(sys.argv[1]).resolve()
project = Path(__file__).resolve().parent
revision = (project.parent / "UPSTREAM_REVISION.txt").read_text(encoding="utf-8").strip()
actual = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
if actual != revision:
    raise RuntimeError("LIVE_LAB_PIN_MISMATCH: checkout " + actual + " expected " + revision)
if revision != "fd7a22fa1f503695309ec9efad0e48b2d900349f":
    raise RuntimeError("LIVE_LAB_NEW_UPSTREAM_REVIEW_REQUIRED: " + revision)

changed = {}


def edit(path, before, after):
    full = root / path
    if not full.is_file():
        raise RuntimeError("LIVE_LAB_MISSING_SOURCE " + path)
    text = changed.get(path, full.read_text(encoding="utf-8"))
    found = text.count(before)
    if found != 1:
        raise RuntimeError("LIVE_LAB_ANCHOR_DRIFT " + path + " count=" + str(found) + " marker=" + repr(before[:90]))
    changed[path] = text.replace(before, after)


def add(path, source):
    target = root / path
    if target.exists():
        raise RuntimeError("LIVE_LAB_TARGET_ALREADY_EXISTS " + path)
    src = project / "staging" / source
    if not src.is_file():
        raise RuntimeError("LIVE_LAB_MISSING_STAGED_SOURCE " + source)
    changed[path] = src.read_text(encoding="utf-8")


U = "src/main/kotlin/io/github/numberonebot/chairplay/ui/"
C = "src/main/kotlin/io/github/numberonebot/chairplay/"
D = "upstream/shared/src/main/java/com/shilapi/xcertplay/airplay/AirPlaySession.kt"

edit(U + "UiApi.kt",
     "interface UiApi {\n",
     'interface UiApi {\n    /** Local-only experimental lab (never connected unless explicitly armed). */\n'
     '    fun liveLab(body: Map<*, *>): Map<String, Any?> = mapOf("state" to "NOT_SUPPORTED")\n')

edit(U + "AppUiApi.kt",
     "    private val driving: () -> UiDriving?,\n",
     "    private val labProvider: () -> UiLiveLab? = { null },\n"
     "    private val driving: () -> UiDriving?,\n")
edit(U + "AppUiApi.kt",
     "    override fun gpsDrive(throttle: Double, brake: Double, steer: Double) =\n",
     "    override fun liveLab(body: Map<*, *>): Map<String, Any?> =\n"
     '        labProvider()?.request(body) ?: mapOf("state" to "NOT_SUPPORTED")\n\n'
     "    override fun gpsDrive(throttle: Double, brake: Double, steer: Double) =\n")

edit(U + "ChairPlayUi.kt",
     "    private val separateSettings: Boolean = false,\n",
     "    private val separateSettings: Boolean = false,\n"
     "    private val liveLab: UiLiveLab? = null,\n")
edit(U + "ChairPlayUi.kt",
     "    private val api = AppUiApi(controller, { profiles }) { driving }\n",
     "    private val api = AppUiApi(controller, { profiles }, { liveLab }) { driving }\n")

# Keep the general ChairPlay UI authenticated, but allow the experimental *loopback-only*
# lab and its screenshot helper to be called directly. UiServer.handle still rejects nonlocal Hosts
# and binds exclusively to InetAddress.getLoopbackAddress().
edit(U + "UiServer.kt",
     "        if (!authorized(exchange)) {\n",
     '        if (route !in setOf("live-lab", "screenshot") && !authorized(exchange)) {\n')
edit(U + "UiServer.kt",
     '"gps-route", "cluster-profile")',
     '"gps-route", "cluster-profile", "live-lab")')
# Constant lab port: Codex can use http://127.0.0.1:18765 without finding a secret or log line.
# CHAIRPLAY_UI_PORT remains a supported explicit override in case that port is occupied.
edit(U + "ChairPlayUi.kt",
     'System.getenv("CHAIRPLAY_UI_PORT")?.toIntOrNull() ?: 0, log = log)',
     'System.getenv("CHAIRPLAY_UI_PORT")?.toIntOrNull() ?: 18765, log = log)')

edit(U + "UiPosts.kt",
     '        "volume" -> {\n',
     '        "live-lab" -> {\n'
     '            val result = api.liveLab(body)\n'
     '            json(if (result["state"] == "REJECTED") 409 else 200, result)\n'
     '        }\n'
     '        "volume" -> {\n')

edit(C + "Main.kt",
     "import com.shilapi.xcertplay.airplay.AirPlaySession\n",
     "import com.shilapi.xcertplay.airplay.AirPlaySession\n"
     "import io.github.numberonebot.chairplay.livelab.LiveLabController\n")
edit(C + "Main.kt",
     "    val altView = AltscreenView(dir, config, altscreen, touchSender, active::get) { controlsChanged.get()() }\n",
     "    val altView = AltscreenView(dir, config, altscreen, touchSender, active::get) { controlsChanged.get()() }\n"
     "    val liveLab = LiveLabController(active::get, touchSender, ::log)\n")
edit(C + "Main.kt",
     "separateSettings = windows.settings != null)\n",
     "separateSettings = windows.settings != null, liveLab = liveLab)\n")

edit(D, "    private var clusterStreamSetups = 0\n",
     "    @Volatile private var clusterStreamSetups = 0\n")
edit(D, "    private var eventCseq = 0\n",
     "    private var eventCseq = 0\n"
     "    /** The exact bytes encoded for /info on this AirPlay control session, not current profile settings. */\n"
     "    @Volatile private var liveLabInfoBytes: ByteArray? = null\n")
edit(D,
     "    fun sendCommand(command: Map<String, Any?>): Boolean = synchronized(eventWriteLock) {\n",
     (project / "staging" / "AirPlaySessionLabMethods.txt").read_text(encoding="utf-8")
     + "    fun sendCommand(command: Map<String, Any?>): Boolean = synchronized(eventWriteLock) {\n")
edit(D,
     '                    body = BplistCodec.encode(info),\n',
     '                    body = BplistCodec.encode(info).also { liveLabInfoBytes = it.copyOf() },\n')

# Regression: no token for only the two lab actions; normal UI still rejects unauthenticated traffic.
edit("src/test/kotlin/io/github/numberonebot/chairplay/ui/UiServerTest.kt",
     "    @Test\n    fun `the API needs the token`() {",
     """    @Test
    fun `the experimental localhost lab and screenshot work without a token`() {
        fun noTokenPost(route: String): HttpResponse<String> {
            val request = HttpRequest.newBuilder(URI("$base/api/$route"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(if (route == "live-lab") "{\\"op\\":\\"status\\"}" else "{}"))
                .build()
            return client.send(request, HttpResponse.BodyHandlers.ofString())
        }
        assertEquals(200, noTokenPost("live-lab").statusCode())
        assertEquals(200, noTokenPost("screenshot").statusCode())
        assertEquals(401, get("/api/state", token = null).statusCode())
        assertEquals(401, get("/api/settings", token = null).statusCode())
    }

    @Test
    fun `the API needs the token`() {""")
 
add(U + "UiLiveLab.kt", "UiLiveLab.kt")
add(C + "livelab/LiveLabGate.kt", "LiveLabGate.kt")
add(C + "livelab/LiveLabController.kt", "LiveLabController.kt")

# No partial writes. Every existing anchor, source and target is already verified.
for path, content in changed.items():
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    print("LIVE_LAB_PATCH_OK " + path)
print("LIVE_LAB_PATCH=PASS files=" + str(len(changed)))
