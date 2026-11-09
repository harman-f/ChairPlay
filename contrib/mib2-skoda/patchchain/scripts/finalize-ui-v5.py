#!/usr/bin/env python3
"""Guarded v5 UX delta on top of the pinned UI v4 ChairPlay patch."""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
out = {}

def replace(path, before, after, count=1):
    s = out.get(path, (root / path).read_text(encoding='utf-8'))
    if s.count(before) != count:
        raise RuntimeError(f'V5_DRIFT {path}: expected {count} occurrences of {before[:75]!r}, got {s.count(before)}')
    out[path] = s.replace(before, after)

def once_regex(path, pattern, after):
    s = out.get(path, (root / path).read_text(encoding='utf-8'))
    new, n = re.subn(pattern, lambda _: after, s, count=1, flags=re.S)
    if n != 1: raise RuntimeError(f'V5_REGEX_DRIFT {path}: {pattern[:75]}')
    out[path] = new

P='webui/src/pages/CarProfile.tsx'
F='webui/src/pages/ProfileViewForm.tsx'
T='webui/src/pages/CarProfile.test.tsx'

# R1. Two directional switches, with queued native down/up controller pulses.
replace(P, "  const [followController, setFollowController] = useState(true)",
"""  const [followController, setFollowController] = useState(true)
  const [coupleController, setCoupleController] = useState(false)
  const [pendingControllerView, setPendingControllerView] = useState<number | null>(null)
  const [editingViewName, setEditingViewName] = useState(false)
  const [viewNameDraft, setViewNameDraft] = useState('')
  const controllerQueue = useRef<Promise<void>>(Promise.resolve())
  const requestedControllerView = useRef<number | null>(null)""")
replace(P,
"""  const editingView = followController && editing === chosen && liveCarView !== null && liveCarView >= 0
    && liveCarView < (draft?.views.length ?? 0) ? liveCarView : view""",
"""  const controllerSlot = pendingControllerView ?? liveCarView
  const editingView = followController && editing === chosen && controllerSlot !== null && controllerSlot >= 0
    && controllerSlot < (draft?.views.length ?? 0) ? controllerSlot : view""")
replace(P,
"""  const previewArea = draft?.views[editingView]?.area
    ?? (draft && draft.views.length > 0
      ? draft.views[mapViewIndex(draft, editingView)]?.area : undefined)""",
"""  // Highlight the single selected area, without silently assigning it.
  const previewArea = Math.min(managedArea, Math.max(0, (draft?.areas.length ?? 1) - 1))""")
needle="  /** Opens profile [id] in the editor"
s=out[P]
if s.count(needle)!=1: raise RuntimeError('V5_OPEN_ANCHOR')
out[P]=s.replace(needle,"""  useEffect(() => {
    if (pendingControllerView !== null && liveCarView === pendingControllerView) {
      setPendingControllerView(null)
      requestedControllerView.current = null
    }
  }, [liveCarView, pendingControllerView])

  useEffect(() => {
    const bound = draft?.views[editingView]?.area
    if (bound !== undefined) setManagedArea(bound)
  }, [editing, editingView, draft?.views[editingView]?.area])

  useEffect(() => {
    // Do not apply a stale rename to a different View when Follow changes it.
    setEditingViewName(false)
  }, [editing, editingView])

  /** Native Controller View button pulses are serialized, including rapid UI selections. */
  function requestControllerView(target: number) {
    if (!draft || !chosen || editing !== chosen || liveCarView === null ||
        target < 0 || target >= draft.views.length) {
      setProblem('The active vehicle profile and a connected Controller are required')
      return
    }
    const count = draft.views.length
    const start = requestedControllerView.current ?? liveCarView
    const steps = (target - start + count) % count
    requestedControllerView.current = target
    setPendingControllerView(target)
    controllerQueue.current = controllerQueue.current.catch(() => {}).then(async () => {
      for (let i = 0; i < steps; i++) {
        await backend.control('altscreen.view', true)
        await backend.control('altscreen.view', false)
      }
    }).catch((error) => {
      setProblem('Controller view switching failed: ' + String(error))
      setPendingControllerView(null)
      requestedControllerView.current = null
    })
  }

"""+needle)
replace(P,
"""                <Segmented label="Car view" value={String(editingView)} options={views}
                  onChange={(v) => { setFollowController(false); setView(Number(v)) }} />
                <Switch label="Follow Controller" checked={followController}
                  onChange={(checked) => {
                    if (!checked) setView(editingView)
                    setFollowController(checked)
                  }} />""",
"""                <Segmented label="Car view" value={String(editingView)} options={views}
                  onChange={(v) => {
                    const target = Number(v)
                    setView(target)
                    setEditingViewName(false)
                    if (coupleController) requestControllerView(target)
                    else setFollowController(false)
                  }} />
                <Switch label="Follow Controller" checked={followController}
                  onChange={(checked) => {
                    if (!checked) setView(editingView)
                    setFollowController(checked)
                  }} />
                <Switch label="Couple Controller" checked={coupleController}
                  onChange={setCoupleController} />""")
replace(P,
"""onClick={() => {
                    if (liveCarView === null || !draft) return
                    const steps = (editingView - liveCarView + draft.views.length) % draft.views.length
                    void (async () => {
                      for (let i = 0; i < steps; i++) {
                        await backend.control('altscreen.view', true)
                        await backend.control('altscreen.view', false)
                      }
                    })()
                  }}>Show editing view on AltScreen</button>""",
"""onClick={() => requestControllerView(editingView)}>Show editing view on AltScreen</button>""")

# R2. Editor is colocated with Vehicle Views, not CarPlay Setup.
replace(P,"setDisplay, setInlineOverlayEnabled, setOverlayPng, setZoomFactor",
          "setDisplay, setInlineOverlayEnabled, setOverlayPng, setViewArea, setViewField, setZoomFactor")
replace(P,'              <Row label="Active view">',
"""              <Row label="View name">
                {editingViewName ? (
                  <>
                    <Field label="View name" value={viewNameDraft}
                      onCommit={(name) => setViewNameDraft(name)} />
                    <button type="button" className="btn small" onClick={() => {
                      const name = viewNameDraft.trim()
                      if (!name || name.length > 64) {
                        setProblem('View name must be 1 to 64 characters long')
                        return
                      }
                      const next = setViewField(draft, editingView, 'name', name)
                      change(next, 'local')
                      if (editing && editing !== chosen) void save(editing, JSON.stringify(next, null, 2))
                      setEditingViewName(false)
                    }}>Save name</button>
                    <button type="button" className="btn small"
                      onClick={() => setEditingViewName(false)}>Cancel</button>
                  </>
                ) : (
                  <>
                    <span>{editingView}: {draft.views[editingView]?.name || 'View ' + editingView}</span>
                    <button type="button" className="btn small" onClick={() => {
                      setViewNameDraft(draft.views[editingView]?.name || 'View ' + editingView)
                      setEditingViewName(true)
                    }}>Edit name</button>
                  </>
                )}
              </Row>
              <Row label="Active view">""")
replace(F,
"""      <Row label="View name">
        <Field label="View name" value={view.name ?? ''} onCommit={(text) => change(setViewField(profile, index, 'name', text.trim()))} />
      </Row>
""","")

# Map/cover remains per-view JSON; never convert inherited overlay-only Views 3/4.
replace(F,
"""      <Row title="The iPhone's map shows in this view; without it the cluster covers the map and the iPhone keeps the last view's">
        <Switch label="Map" checked={area !== null} onChange={(on) => change(setViewMap(profile, index, on))} />
      </Row>
""","")
replace(F,"import { Row, Segmented, Switch, type Choice } from '../shell/controls'",
          "import { Row, Segmented, type Choice } from '../shell/controls'")
replace(F,"setOption, setSafeArea, setViewArea, setViewField, setViewMap, viewUrl",
          "setOption, setSafeArea, setViewField, viewUrl")
replace(F,
"export function ProfileViewForm({ profile, index, change, liveChange }: { profile: Profile; index: number; change: (p: Profile) => void; liveChange: (p: Profile) => void }) {",
"export function ProfileViewForm({ profile, index, liveChange }: { profile: Profile; index: number; change: (p: Profile) => void; liveChange: (p: Profile) => void }) {")

# R3. The Skoda 1010x376 geometry is Custom, not a generic preset. 5 + Custom = 2x3.
replace(P,
"const FRAME_PRESETS = [[1010, 376], [1280, 480], [1440, 540], [1600, 600], [1920, 720]] as const",
"const FRAME_PRESETS = [[800, 480], [1280, 480], [1440, 540], [1600, 600], [1920, 720]] as const")
replace(P,
'<Group title="Display Geometry" note="Vehicle geometry is authoritative; Custom settings are a separate fallback" />',
'<Group title="Display Geometry" note="Vehicle Profile is authoritative on reconnect; Size presets and Custom edit only the independent fallback" />')

# R4. Exactly one area selector; assign is explicit, never implicit.
once_regex(F,
r'      <Row label="Area assignment" title="Select the declared rectangle used by this vehicle view">.*?      </Row>',
'      <Row label="Bound area"><span>Area {view.area} (View {index})</span></Row>')
replace(P,
'                <Segmented label="Area to manage" value={String(Math.min(managedArea, draft.areas.length - 1))}',
'                <Segmented label="Area" value={String(Math.min(managedArea, draft.areas.length - 1))}')
replace(P,
'                  onChange={(id) => setManagedArea(Number(id))} />',
"""                  onChange={(id) => setManagedArea(Number(id))} />
                <button type="button" className="btn small"
                  disabled={draft.views[editingView]?.area === undefined ||
                    draft.views[editingView]?.area === managedArea}
                  onClick={() => change(setViewArea(draft, editingView, managedArea), 'descriptor')}>
                  Assign to View
                </button>""")
replace(P, '>Keep mapped areas only</button>', '>Remove unused Safe Areas</button>')

replace(P,
'<Row><small>The selected area follows the edited View; overlay-only Views inherit the safe area of their map source. Editing a View does not silently activate it on the Controller.</small></Row>',
'<Row><small>The Area selector previews the chosen rectangle. Only Assign to View changes its binding. Overlay-only Views retain their inherited map area.</small></Row>')

# R5. True standalone Group and always-visible JSON editor (no details disclosure).
replace(P,
'<details className="profile-json-editor"><summary>Profile JSON</summary><Row><small>Direct JSON edits require explicit Save. All regular UI edits auto-save.</small></Row>',
'<Group title="Profile JSON" note="Entire vehicle profile · always visible" />\n              <div className="profile-json-editor"><Row><small>Direct JSON edits require explicit Save. All regular UI edits auto-save.</small></Row>')
replace(P,'</details>','</div>')

# Adapt tests that assumed a permanent input under CarPlay Setup.
s=(root/T).read_text(encoding='utf-8')
old="await screen.findByRole('textbox', { name: 'View name' })"
if s.count(old)<1: raise RuntimeError('V5_TEST_EDITOR_SETUP_DRIFT')
s=s.replace(old,"await screen.findByText('Vehicle Views')")
s=s.replace("it('shows consolidated CarPlay settings and a collapsible profile editor'",
            "it('shows consolidated CarPlay settings and an always-visible profile editor'")
s=s.replace("""    const summary = screen.getByText('Profile JSON')
    const details = summary.closest('details')
    expect(details).not.toBeNull()
    expect(details?.open).toBe(false)
    fireEvent.click(summary)
    expect(details?.open).toBe(true)
    expect(screen.getByRole('textbox', { name: 'Profile JSON' })).toBeTruthy()""",
            """    expect(screen.getByText('Profile JSON')).toBeTruthy()
    expect(screen.getByText('Profile JSON').closest('details')).toBeNull()
    expect(screen.getByRole('textbox', { name: 'Profile JSON' })).toBeTruthy()""")

s=s.replace("expect((screen.getByRole('textbox', { name: 'View name' }) as HTMLInputElement).value).toBe('View 0')",
            "expect(screen.getByRole('button', { name: 'Edit name' })).toBeTruthy()")
s=s.replace("expect((screen.getByRole('textbox', { name: 'View name' }) as HTMLInputElement).value).toBe('View 1')",
            "expect(screen.getByRole('button', { name: 'Edit name' })).toBeTruthy()")
out[T]=s
anchor='  // Saved, the editor stays on the view being edited rather than going back to the first.'
addition="""  it('edits and saves the vehicle view name at the view selector', async () => {
    const backend = await altscreenPage()
    fireEvent.click(screen.getByRole('button', { name: 'Edit name' }))
    const name = screen.getByRole('textbox', { name: 'View name' })
    fireEvent.change(name, { target: { value: 'Center' } })
    fireEvent.blur(name)
    fireEvent.click(screen.getByRole('button', { name: 'Save name' }))
    await waitFor(() => expect(backend.profileSaves.length).toBeGreaterThan(0))
    expect(JSON.parse(backend.profileSaves[backend.profileSaves.length - 1].text!).views[0].name).toBe('Center')
    expect(screen.queryByRole('textbox', { name: 'View name' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Edit name' })).toBeTruthy()
  })

  it('couples a view selection to the native Controller View button', async () => {
    const backend = new FakeBackend()
    backend.data = { ...backend.data, values: {
      ...backend.data.values, 'altscreen.enabled': 'true', 'altscreen.profile': 'car',
    } }
    backend.profiles = { profiles: [{ id: 'car', text, builtIn: false }], active: 'car' }
    const state = appState({ phase: 'active', canShowCarPlay: true })
    render(<Shell state={{ ...state, controls: { ...state.controls!, carView: 0 } }} backend={backend} />)
    await screen.findByRole('textbox', { name: 'Network' })
    fireEvent.click(screen.getByRole('tab', { name: 'AltScreen' }))
    await screen.findByText('Vehicle Views')
    fireEvent.click(screen.getByRole('switch', { name: 'Couple Controller' }))
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Car view' }))
      .getByRole('radio', { name: 'View 1' }))
    await waitFor(() => expect(backend.controls).toEqual(['altscreen.view down', 'altscreen.view up']))
    expect(within(screen.getByRole('radiogroup', { name: 'Car view' }))
      .getByRole('radio', { name: 'View 1' }).getAttribute('aria-checked')).toBe('true')
  })

  it('keeps Map as profile data but exposes Couple and a single safe-area selector', async () => {
    await altscreenPage()
    expect(screen.getByRole('switch', { name: 'Follow Controller' })).toBeTruthy()
    expect(screen.getByRole('switch', { name: 'Couple Controller' })).toBeTruthy()
    expect(screen.queryByRole('switch', { name: 'Map' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Assign to View' })).toBeTruthy()
    expect(screen.queryByRole('radiogroup', { name: 'Area assignment' })).toBeNull()
    expect(screen.getByText('Profile JSON')).toBeTruthy()
    expect(screen.queryByText('JSON Editor · advanced profile management')).toBeNull()
  })

"""
if out[T].count(anchor)!=1: raise RuntimeError('V5_TEST_ANCHOR_DRIFT')
out[T]=out[T].replace(anchor,addition+anchor)

for token in ['Couple Controller','Save name','Assign to View','Remove unused Safe Areas',
              '<Group title="Profile JSON"','[[800, 480]']:
    if token not in out[P]: raise RuntimeError('V5_MISSING '+token)
for token in ['<details className="profile-json-editor">','Area to manage']:
    if token in out[P]: raise RuntimeError('V5_STALE '+token)
for token in ['<Switch label="Map"','<Row label="View name">','<Segmented label="Area assignment"']:
    if token in out[F]: raise RuntimeError('V5_STALE '+token)
for path,s in out.items():
    (root/path).write_text(s, encoding='utf-8', newline='\n')
    print('V5_PATCH_OK',path)
print('V5_UI_AUDIT=PASS')
