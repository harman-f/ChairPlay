#!/usr/bin/env python3
"""ChairPlay UI audit v4. Runs after the pinned live, manual, consolidated and smart patches.
Every edit is exact and refuses drift, rather than silently building a previous UI.
"""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
modified = {}

def edit(path, old, new, n=1):
    text = modified.get(path, (root/path).read_text(encoding="utf-8"))
    count = text.count(old)
    if count != n:
        raise RuntimeError(f"V4_EXACT_MISMATCH {path}: expected {n}, got {count}: {old[:115]!r}")
    modified[path] = text.replace(old, new)

def splice(path, begin, end, replacement):
    text = modified.get(path, (root/path).read_text(encoding="utf-8"))
    assert text.count(begin) == 1 and text.count(end) == 1, f"V4_BOUNDARY_MISSING {path} {begin[:50]}"
    a = text.index(begin)
    b = text.index(end, a)
    modified[path] = text[:a] + replacement + text[b:]

P = "webui/src/pages/CarProfile.tsx"
A = "webui/src/pages/AltScreenPage.tsx"
E = "webui/src/pages/profileEdits.ts"

# Display: an independent fallback Custom resolution (never edits the vehicle JSON).
# There are six 2x3 choices: five common resolutions, plus Custom.
edit(P, "const FRAME_PRESETS = [[1280, 480], [1440, 540], [1600, 600], [1920, 720]] as const",
     "const FRAME_PRESETS = [[1010, 376], [1280, 480], [1440, 540], [1600, 600], [1920, 720]] as const")
edit(P, "  const profileSizeSettings: Settings = {", "  const UNUSED_PROFILE_SIZE_SETTINGS: Settings = {")
# Avoid carrying the old wrapper that silently overwrote profile size when Custom was edited.
s = modified[P]
start = s.index("  const UNUSED_PROFILE_SIZE_SETTINGS: Settings = {")
end = s.index("  const physicalZoom =", start)
modified[P] = s[:start] + s[end:]
edit(P, '<Group title="Manual setup" note="The selected profile controls the iPhone\'s cluster display" />',
     '<Group title="Display Geometry" note="Vehicle geometry is authoritative; Custom settings are a separate fallback" />\n'
     '                  <Row label="Vehicle Profile"><span>{display.width} × {display.height} px · {display.widthMm} × {display.heightMm} mm (active on iPhone reconnect)</span></Row>\n'
     '                  <Row><small>The Custom size below is independently saved in settings.properties. It never rewrites this vehicle profile and applies only when Vehicle Profile is None.</small></Row>')
edit(P, '<SizeRows settings={profileSizeSettings} prefix="altscreen" presets={FRAME_PRESETS}\n                    fallback={{ width: 1010, height: 376 }} showCustom after={<ActualSize sizes={altScreenWindow} window="altscreen" backend={backend} />} />',
     '<SizeRows settings={settings} prefix="altscreen" presets={FRAME_PRESETS} columns={3}\n'
     '                    fallback={{ width: 1440, height: 540 }} showCustom after={<ActualSize sizes={altScreenWindow} window="altscreen" backend={backend} />} />')
# The visual Vehicle Profile is the canonical source; physical reference mm always lives in the profile.
edit(P, '<Row label="Vehicle name">\n                <Field label="Name" value={draft.name ?? \'\'} onCommit={(t) => change({ ...draft, name: t.trim() }, \'descriptor\')} />\n              </Row>',
     '<Row label="Vehicle name"><span>{draft.name ?? editing ?? "Unnamed vehicle"}</span></Row>')
# Normal screen has no HUD/Output mode switch. Legacy HUD remains available internally to the non-profile path.
edit(P, '              <Group title="Output mode" note="HUD or vehicle display; independent of the chosen Controller View" />\n              {liveContent}\n', '')
# Move Scaling BELOW all Vehicle Views; geometry stays directly above Vehicle Views.
s = modified[P]
start = s.index('                  <Group title="Scaling" note="Both scaling methods may be combined" />')
end = s.index('                </>\n              )}', start)
scale = s[start:end]
assert scale.count('<Group title="Scaling"') == 1 and 'Reconnect CarPlay' in scale
s = s[:start] + s[end:]
target = '              <Group title="CarPlay · selected View"'
assert s.count(target) == 1
s = s.replace(target, '              {editing === chosen && Boolean(chosen) && (\n                <>\n'+scale+'                </>\n              )}\n'+target)
modified[P] = s
edit(P, '<Group title="CarPlay · selected View" note="Settings below belong to the View selected above, not to another menu selector" />',
     '<Group title="CarPlay Setup" note="Settings of the vehicle View selected above" />')
edit(P, '<Group title="Safe area · selected View" note="All areas belong to the vehicle; the selected View explicitly binds one map rectangle" />',
     '<Group title="Safe Area Setup" note="Add, assign, clone and remove safe areas in the selected vehicle" />')
# Add/delete safe areas without corrupting view references.
edit(E, '/** Assign an external overlay file to this view, without changing its existing inline shapes. */',
'''/** Add a new default area and assign it to the edited map-bearing View if applicable. */
export function addSafeArea(profile: Profile, viewIndex: number): Profile {
  const { width, height } = profile.display
  const x = Math.max(0, Math.round(width / 10))
  const y = Math.max(0, Math.round(height / 10))
  const areas = [...profile.areas, [x, y, width - 2 * x, height - 2 * y]]
  return { ...profile, areas, views: profile.views.map((view, i) =>
    i === viewIndex && view.area !== undefined ? { ...view, area: areas.length - 1 } : view) }
}

/** Refuse to remove used areas; renumber only higher indices when an unused one is deleted. */
export function deleteSafeArea(profile: Profile, index: number): Profile | null {
  if (index < 0 || index >= profile.areas.length ||
      profile.views.some((view) => view.area === index) || profile.areas.length < 2) return null
  return { ...profile,
    areas: profile.areas.filter((_, i) => i !== index),
    views: profile.views.map((view) => view.area !== undefined && view.area > index
      ? { ...view, area: view.area - 1 } : view),
  }
}

/** Enable/disable a View's embedded drawing without discarding its Shapes. */
export function setInlineOverlayEnabled(profile: Profile, index: number, enabled: boolean): Profile {
  return { ...profile, views: profile.views.map((view, i) => i !== index ? view :
    { ...view, overlayEnabled: enabled }) }
}

/** Assign a transparent PNG stored in overlays/ to a View without losing embedded Shapes. */
export function setOverlayPng(profile: Profile, index: number, name: string): Profile {
  return { ...profile, views: profile.views.map((view, i) => i !== index ? view :
    { ...view, overlayImage: name || undefined, overlayEnabled: true }) }
}

/** Assign an external overlay file to this view, without changing its existing inline shapes. */''')
edit(E, '  overlay?: string\n}', '  overlay?: string\n  overlayEnabled?: boolean\n  overlayImage?: string\n}')
edit(P, 'addView, cloneViewArea, compactAreas, mapViewIndex, newBlankProfile, removeView, setDisplay, setViewOverlay, setZoomFactor',
     'addSafeArea, addView, cloneViewArea, compactAreas, deleteSafeArea, mapViewIndex, newBlankProfile, removeView, setDisplay, setInlineOverlayEnabled, setOverlayPng, setZoomFactor')
edit(P, "  const [overlayName, setOverlayName] = useState('')",
     "  const [managedArea, setManagedArea] = useState(0)\n  const [pngName, setPngName] = useState('')")
# Profile management at top: copy/create and confirmed deletion, no filename editing.
needle = '        }}>New blank vehicle</button>'
edit(P, needle, needle + '''
        {editing && <button type="button" className="btn small" onClick={() => {
          const builtIn = data?.profiles.find((p) => p.id === editing)?.builtIn
          if (!window.confirm(builtIn
            ? `Reset built-in vehicle ${editing} to its bundled defaults?`
            : `Delete vehicle profile ${editing}.json permanently?`)) return
          void (async () => {
            if (editing === chosen) {
              const ok = await settings.save({ 'altscreen.profile': '' })
              if (!ok) { setProblem('Deselect the active vehicle before deleting it'); return }
            }
            await save(editing, null)
          })()
        }}>{data?.profiles.find((p) => p.id === editing)?.builtIn ? 'Reset built-in' : 'Delete vehicle'}</button>}''')
# Give new blank vehicle and Save Copy their own top-level workflow, not inside the JSON editor.
needle = '      {data && data.profiles.length > 0 && ('
edit(P, needle, '''      <Row label="New profile ID" title="The filename under profiles/, independent of the read-only vehicle name">
        <Field label="New profile ID" value={copyName} placeholder="my-car" onCommit={(value) => setCopyName(value.trim())} />
        <button type="button" className="btn small"
          disabled={!draft || !/^[A-Za-z0-9._-]{1,64}$/.test(copyName) || data?.profiles.some((p) => p.id === copyName)}
          onClick={() => void save(copyName, text)}>Save new / copy</button>
      </Row>
''' + needle)
# Area editing controls: New area is default rectangle, Copy shared remains, Delete refuses a live reference.
needle = '              <Row label="Declared areas">'
edit(P, needle, '''              <Row label="Manage areas">
                <Segmented label="Area to manage" value={String(Math.min(managedArea, draft.areas.length - 1))}
                  options={draft.areas.map((_, i) => [String(i), `Area ${i}`] as const)}
                  onChange={(id) => setManagedArea(Number(id))} />
                <button type="button" className="btn small" onClick={() => {
                  const previous = draft.areas.length
                  change(addSafeArea(draft, editingView), 'descriptor')
                  setManagedArea(previous)
                }}>New Safe Area</button>
                <button type="button" className="btn small"
                  disabled={draft.areas.length < 2 || draft.views.some((v) => v.area === Math.min(managedArea, draft.areas.length - 1))}
                  onClick={() => {
                    const index = Math.min(managedArea, draft.areas.length - 1)
                    if (!window.confirm(`Delete unused Safe Area ${index}? Higher area IDs will be renumbered.`)) return
                    const next = deleteSafeArea(draft, index)
                    if (!next) { setProblem('This Safe Area is still referenced by a View'); return }
                    change(next, 'descriptor')
                    setManagedArea(Math.max(0, index - 1))
                  }}>Delete Safe Area</button>
              </Row>
''' + needle)
# No duplicated editable Native Insets in an active vehicle; keep the computed px values and reconnect hint.
edit(P, '              {nativeInsets}\n', '              {!chosen && nativeInsets}\n')
# Keep the legacy JSON overlay-file resolution in the backend; reduce the normal menu to three sources.
splice(P, '              <Group title="Cockpit overlay · selected View"', '              <Group title="Advanced profile"',
'''              <Group title="Cockpit Overlay Setup" note="Keep the embedded Shapes or use a transparent PNG" />
              {draft.views[editingView] && (
                <>
                  <Row label="Overlay mode">
                    <Segmented label="Overlay mode"
                      value={draft.views[editingView].overlayImage ? 'png' : draft.views[editingView].overlayEnabled === false ? 'off' : 'inline'}
                      options={[[ 'off', 'Off' ], [ 'inline', 'Vehicle Profile' ], [ 'png', 'PNG image' ]]}
                      onChange={(mode) => {
                        if (mode === 'png') {
                          if (!draft.views[editingView].overlayImage) {
                            setProblem('First enter the PNG filename below; copy the file into the overlays folder.')
                            return
                          }
                          change(setOverlayPng(draft, editingView, draft.views[editingView].overlayImage!), 'local')
                        } else {
                          const next = setOverlayPng(draft, editingView, '')
                          change(setInlineOverlayEnabled(next, editingView, mode === 'inline'), 'local')
                        }
                      }} />
                  </Row>
                  <Row label="Embedded drawing"><span>{draft.views[editingView].shapes?.length ?? 0} Shapes are stored directly in the vehicle profile JSON.</span></Row>
                  <Row label="PNG file">
                    <Field label="PNG filename" value={pngName || draft.views[editingView].overlayImage || ''}
                      placeholder="cluster-overlay.png" onCommit={(value) => setPngName(value.trim())} />
                    <button type="button" className="btn small"
                      disabled={!/^[A-Za-z0-9._-]{1,64}\\.png$/i.test(pngName)}
                      onClick={() => {
                        change(setOverlayPng(draft, editingView, pngName), 'local')
                        setProblem(null)
                      }}>Use PNG</button>
                    <button type="button" className="btn small" onClick={() => void backend.open('overlays')}>Open overlays folder</button>
                  </Row>
                  <Row><small>PNG: transparent, full AltScreen frame size ({display.width}×{display.height} px), placed under overlays/. Embedded Shapes are preserved and can be re-enabled at any time.</small></Row>
                </>
              )}
''')
# The whole JSON is an advanced, collapsible editor of the chosen vehicle only.
s = modified[P]
start = s.index('              <Group title="Advanced profile"')
tail = s[start:]
tail = tail.replace('<Group title="Advanced profile" note="One JSON document for the entire vehicle, including View bindings" />',
  '<details className="profile-json-editor"><summary>Profile JSON</summary><Row><small>Direct JSON edits require explicit Save. All regular UI edits auto-save.</small></Row>',1)
tail = tail.replace('              <div className="profile-json-editor">\n                <Group title="JSON Editor · advanced profile management" />\n','',1)
tail = tail.replace('              </div>','              </details>',1)
# Remove destructive/copy actions from the raw JSON editor. They live in Vehicle Profile above.
a = tail.index('            <button\n              type="button"\n              className="btn small"\n              disabled={!editing || editing === chosen}')
b = tail.index('          </Row>\n          <Row label="Save as"', a)
tail = tail[:a] + tail[b:]
a = tail.index('          <Row label="Save as"')
b = tail.index('          </Row>', a)+len('          </Row>')
tail = tail[:a] + tail[b:]
modified[P] = s[:start] + tail
# Move Always on Top under Display > Enabled and remove redundant Window header.
edit(A, '      {/* Off, the AltScreen has nothing to set: the rest waits for it. */}',
     '''      <Row><Switch label="Always on top" checked={settings.value('altscreen.always.on.top') === 'true'}
        onChange={(on) => void settings.save({ 'altscreen.always.on.top': String(on) })} /></Row>
      {/* Off, the AltScreen has nothing to set: the rest waits for it. */}''')
edit(A, '  const windowControls = (\n    <>\n      <AlwaysOnTop settings={settings} setting="altscreen.always.on.top" />\n    </>\n  )',
     '  const windowControls = null')
edit(A, "import { AlwaysOnTop } from './AlwaysOnTop'\n", "")
# The fallback geometry selector stays available only without an active vehicle.
edit(A, '<Group title="Manual setup" note={settings.value(\'altscreen.profile\') ? \'A car profile sets the size and areas\' : undefined} />',
     '<Group title="Display Geometry" note="Independent custom fallback: never overwrites a vehicle profile" />')
edit(A, '          presets={PRESETS}\n', '          presets={PRESETS}\n          columns={3}\n')
edit(A, 'const PRESETS = [\n  [1280, 480],\n  [1440, 540],\n  [1600, 600],\n  [1920, 720],\n]',
     'const PRESETS = [\n  [1010, 376],\n  [1280, 480],\n  [1440, 540],\n  [1600, 600],\n  [1920, 720],\n]')
# Never offer HUD as the default when vehicle profile is active, but do not change raw system controls.
edit(A, '          liveContent={liveContent} windowControls={windowControls} nativeInsets={nativeInsets}',
     '          windowControls={windowControls} nativeInsets={nativeInsets}')
edit(P, 'altScreenWindow, liveContent, windowControls, nativeInsets, liveCarView', 'altScreenWindow, windowControls, nativeInsets, liveCarView')
edit(P, '  liveContent: ReactNode; windowControls: ReactNode; nativeInsets: ReactNode; liveCarView: number | null',
     '  windowControls: ReactNode; nativeInsets: ReactNode; liveCarView: number | null')
# Old AlwaysOnTop remains in the no-profile legacy fallback only; normal screen uses Display row above.

# PNG files remain opt-in and are never copied into profiles/ JSON. Local files are validated
# before a profile links them; the internal renderer receives only an allowlisted file path.
C = "src/main/kotlin/io/github/numberonebot/chairplay/config/ClusterProfiles.kt"
edit(C, '''            if (ref.isNullOrBlank()) view else {
                require(ID.matches(ref)) { "Invalid overlay reference: $ref" }
                LinkedHashMap(view).apply { put("shapes", overlayShapes(ref)) }
            }''',
'''            val enabled = view["overlayEnabled"] != false
            val imageName = view["overlayImage"] as? String
            if (!enabled) {
                LinkedHashMap(view).apply { put("shapes", emptyList<Any>()) }
            } else if (!imageName.isNullOrBlank()) {
                require(Regex("[A-Za-z0-9._-]{1,64}\\\\.png", RegexOption.IGNORE_CASE).matches(imageName)) {
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
            }''')
S = "src/main/kotlin/io/github/numberonebot/chairplay/cluster/ShapePainter.kt"
edit(S, "import java.nio.ByteBuffer", "import java.nio.ByteBuffer\nimport java.io.File")
edit(S, "    private val fontData = mutableListOf<ByteBuffer>()",
'''    private val fontData = mutableListOf<ByteBuffer>()
    /** PNG textures are owned by this GL context and refreshed when a file is replaced. */
    private val pngImages = mutableMapOf<String, Pair<Long, Int>>()''')
edit(S, "        fontData.clear()", '''        pngImages.values.forEach { (_, texture) -> if (texture > 0) nvgDeleteImage(pen?.vg ?: return@forEach, texture) }
        pngImages.clear()
        fontData.clear()''')
# Close cleanup must happen BEFORE the NanoVG context is deleted; avoid use of the already-cleared pen.
edit(S, '''        pen?.let { nvgDelete(it.vg) }
        pen = null
        pngImages.values.forEach { (_, texture) -> if (texture > 0) nvgDeleteImage(pen?.vg ?: return@forEach, texture) }
        pngImages.clear()''',
'''        pen?.let { current ->
            pngImages.values.forEach { (_, texture) -> if (texture > 0) nvgDeleteImage(current.vg, texture) }
            nvgDelete(current.vg)
        }
        pen = null
        pngImages.clear()''')
edit(S, '''        when (s["kind"]) {
            "rect" -> {''', '''        when (s["kind"]) {
            "png" -> {
                val path = s["path"] as? String ?: return
                val stamp = File(path).lastModified()
                if (stamp <= 0L) return
                val previous = pngImages[path]
                val texture = if (previous?.first == stamp) previous.second else {
                    if (previous != null && previous.second > 0) nvgDeleteImage(vg, previous.second)
                    nvgCreateImage(vg, path, 0).also { pngImages[path] = stamp to it }
                }
                if (texture <= 0) return
                nvgBeginPath(vg)
                nvgRect(vg, f("x"), f("y"), f("w"), f("h"))
                nvgFillPaint(vg, nvgImagePattern(vg, f("x"), f("y"), f("w"), f("h"), 0f, texture, 1f, pen.paint))
                nvgFill(vg)
            }
            "rect" -> {''')
# A visible indication that the stored UI really came from this v4 build.
edit(P, '<Group title="Vehicle Profile" note="One vehicle contains its display settings, named Controller views, safe areas and overlays" />',
     '<Group title="Vehicle Profile" note="UI v4 · one vehicle contains its display, Views, Areas and Overlays" />')

T = "webui/src/pages/CarProfile.test.tsx"
edit(T, '  // Saved, the editor stays on the view being edited rather than going back to the first.',
'''  it('audits v4 section order, controls and profile-independent geometry', async () => {
    await altscreenPage()
    const names = ['Vehicle Profile', 'Display Geometry', 'Vehicle Views', 'Scaling',
      'CarPlay Setup', 'Safe Area Setup', 'Cockpit Overlay Setup', 'Profile JSON']
    const html = document.body.textContent ?? ''
    let prev = -1
    for (const name of names) {
      const at = html.indexOf(name)
      expect(at).toBeGreaterThan(prev)
      prev = at
    }
    expect(screen.queryByText('Output mode')).toBeNull()
    expect(screen.queryByText('JSON Editor · advanced profile management')).toBeNull()
    expect(screen.getByRole('button', { name: 'New Safe Area' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Delete Safe Area' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Save new / copy' })).toBeTruthy()
    expect(screen.getByText('UI v4', { exact: false })).toBeTruthy()
    expect(screen.queryByRole('textbox', { name: 'Overlay JSON' })).toBeNull()
  })

  // Saved, the editor stays on the view being edited rather than going back to the first.''',n=1)

# Bring legacy upstream interaction tests into line with the v4 menu without hiding them.
# This only changes test selectors, not production behavior; the tests must still pass.
test = modified[T]
old_summary = "screen.getByText('JSON Editor · advanced profile management')"
if test.count(old_summary) != 4:
    raise RuntimeError(f"V4_TEST_DRIFT: expected 4 legacy summary selectors, got {test.count(old_summary)}")
test = test.replace(old_summary, "screen.getByText('Profile JSON')")
# The old heading was deleted by design, but the new section is still required.
test = test.replace("screen.getByText('CarPlay · selected View')", "screen.getByText('CarPlay Setup')")
# The PNG overlay editor replaces the raw overlay filename field.
test = test.replace("name: 'Overlay filename'", "name: 'PNG filename'")
modified[T] = test

# Replace three tests still targeting controls intentionally removed in UI v4.
# Keep meaningful coverage for the replacement behavior and refuse unexpected upstream drift.
def v4_replace_test(source, title, body):
    pattern = r"  it\('" + re.escape(title) + r"', async \(\) => \{[\s\S]*?\n  \}\)"
    source, count = re.subn(pattern, lambda _: body, source, count=1)
    if count != 1:
        raise RuntimeError(f"V4_TEST_CASE_DRIFT {title}: {count}")
    return source

test = modified[T]
test = v4_replace_test(test, 'retains the native live Content control and exposes custom FPS and six physical zoom choices', """  it('shows consolidated CarPlay settings and a collapsible profile editor', async () => {
    await altscreenPage()
    expect(screen.getByText('CarPlay Setup')).toBeTruthy()
    expect(screen.queryByRole('radiogroup', { name: 'View' })).toBeNull()
    expect(screen.getByRole('textbox', { name: 'Frames per Second (FPS)' })).toBeTruthy()
    expect(within(screen.getByRole('radiogroup', { name: 'Physical zoom' })).getAllByRole('radio')).toHaveLength(6)
    expect(within(screen.getByRole('radiogroup', { name: 'Physical zoom' })).getByRole('radio', { name: '50 %' })).toBeTruthy()
    expect(screen.getByRole('textbox', { name: 'Safe area x' })).toBeTruthy()
    const summary = screen.getByText('Profile JSON')
    const details = summary.closest('details')
    expect(details).not.toBeNull()
    expect(details?.open).toBe(false)
    fireEvent.click(summary)
    expect(details?.open).toBe(true)
    expect(screen.getByRole('textbox', { name: 'Profile JSON' })).toBeTruthy()
  })""")
test = v4_replace_test(test, 'creates a blank one-view vehicle, maps a reusable overlay file, and switches Controller with the same button', """  it('creates a blank vehicle and configures its PNG overlay rather than exporting legacy JSON', async () => {
    const backend = await altscreenPage()
    fireEvent.click(screen.getByRole('button', { name: 'New blank vehicle' }))
    expect((screen.getByRole('textbox', { name: 'View name' }) as HTMLInputElement).value).toBe('View 0')
    expect(screen.getByText(/1 Controller views/)).toBeTruthy()
    const png = screen.getByRole('textbox', { name: 'PNG filename' })
    fireEvent.change(png, { target: { value: 'new-cluster.png' } })
    fireEvent.blur(png)
    fireEvent.click(screen.getByRole('button', { name: 'Use PNG' }))
    const raw = document.querySelector('textarea[aria-label="Profile JSON"]') as HTMLTextAreaElement
    expect(raw).not.toBeNull()
    expect(JSON.parse(raw.value).views[0].overlayImage).toBe('new-cluster.png')
    expect(backend.overlaySaves).toHaveLength(0)
  })""")
test = v4_replace_test(test, 'chooses a profile and deletes only one not in use', """  it('requires confirmation before deleting a vehicle profile', async () => {
    const backend = await altscreenPage()
    const originalConfirm = window.confirm
    window.confirm = () => false
    try {
      fireEvent.click(screen.getByRole('button', { name: 'Delete vehicle' }))
      expect(backend.profileSaves).toHaveLength(0)
      fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Profile' })).getByRole('radio', { name: 'None' }))
      await waitFor(() => expect(backend.saved).toEqual([{ 'altscreen.profile': '' }]))
      window.confirm = () => true
      fireEvent.click(screen.getByRole('button', { name: 'Delete vehicle' }))
      await waitFor(() => expect(backend.profileSaves).toEqual([{ id: 'car', text: null }]))
    } finally {
      window.confirm = originalConfirm
    }
  })""")
modified[T] = test

# Verify final required screen sections are present and old duplicated sections are gone.
must = ['Vehicle Profile', 'Display Geometry', 'Vehicle Views', 'Scaling',
        'CarPlay Setup', 'Safe Area Setup', 'Cockpit Overlay Setup', 'Profile JSON',
        'New Safe Area', 'Delete Safe Area', 'Save new / copy']
for label in must:
    if label not in modified[P]:
        raise RuntimeError(f"V4_AUDIT_MISSING {label}")
for label in ['Cockpit overlay · selected View', '<Group title="Output mode"', 'Save drawing as file',
              'JSON Editor · advanced profile management']:
    if label in modified[P]:
        raise RuntimeError(f"V4_AUDIT_STALE {label}")
order = [modified[P].index(label) for label in must[:8]]
if order != sorted(order):
    raise RuntimeError(f"V4_AUDIT_ORDER {dict(zip(must,order))}")
for path, text in modified.items():
    (root/path).write_text(text, encoding="utf-8", newline="\n")
    print("V4_PATCH_OK", path)
print("V4_UI_AUDIT=PASS", "files="+str(len(modified)), "sections="+",".join(must[:8]))
