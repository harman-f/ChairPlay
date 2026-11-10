import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import type { Backend, ClusterProfilesData } from '../api'
import { Group, Row, Segmented, Switch, type Choice } from '../shell/controls'
import { Field } from '../shell/fields'
import { ActualSize } from './parts'
import type { Settings } from '../shell/useSettings'
import { addSafeArea, addView, cloneViewArea, compactAreas, deleteSafeArea, mapViewIndex, newBlankProfile, removeView, setDisplay, setInlineOverlayEnabled, setOverlayPng, setViewArea, setViewField, setZoomFactor, type Profile } from './profileEdits'
import { ProfileViewForm, ProfileSafeAreaForm } from './ProfileViewForm'

/** The zoom factors mhi2_altscreen_carplay offers, in percent; Auto leaves the key out. */
const ZOOM: readonly Choice[] = [
  ['', 'Auto'],
  ['70', '70 %'],
  ['85', '85 %'],
  ['100', '100 %'],
  ['125', '125 %'],
  ['150', '150 %'],
]

const PHYSICAL_ZOOMS: readonly Choice[] = [
  ['50', '50 %'], ['70', '70 %'], ['85', '85 %'], ['100', '100 %'], ['125', '125 %'], ['150', '150 %'],
]
const FRAME_PRESETS = [[800, 480], [1280, 480], [1440, 540], [1600, 600], [1920, 720]] as const

/** The profile's text read, or why not. */
function parse(text: string): { profile?: Profile; error?: string } {
  try {
    const profile = JSON.parse(text) as Profile
    if (!profile || !Array.isArray(profile.views) || !Array.isArray(profile.areas) || !profile.display) {
      return { error: 'A profile needs display, areas and views' }
    }
    return { profile }
  } catch (e) {
    return { error: `Not JSON: ${(e as Error).message}` }
  }
}

/**
 * The cars' cluster profiles (profiles\<id>.json): which one the AltScreen copies (altscreen.profile, at the next
 * connection), and an editor for one of them: its name and frame, each car view, the View button's views added or
 * removed, and its whole JSON, the schematic's shapes among it. Save keeps it; the one in use takes its schematic and
 * URLs at once, its frame and areas at the next connection. Save as copies it under a new name.
 */
export function CarProfile({ backend, settings, canReconnect, altScreenWindow, windowControls, nativeInsets, liveCarView }: {
  backend: Backend; settings: Settings; canReconnect: boolean;
  altScreenWindow: Parameters<typeof ActualSize>[0]['sizes'];
  windowControls: ReactNode; nativeInsets: ReactNode; liveCarView: number | null
}) {
  const [data, setData] = useState<ClusterProfilesData | null>(null)
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState<Profile | null>(null)
  const [text, setText] = useState('')
  const [view, setView] = useState(0)
  const [followController, setFollowController] = useState(true)
  const [coupleController, setCoupleController] = useState(false)
  const [pendingControllerView, setPendingControllerView] = useState<number | null>(null)
  const [editingViewName, setEditingViewName] = useState(false)
  const [viewNameDraft, setViewNameDraft] = useState('')
  const controllerQueue = useRef<Promise<void>>(Promise.resolve())
  const requestedControllerView = useRef<number | null>(null)
  const [safeAreaPreview, setSafeAreaPreview] = useState<'all' | 'active'>('all')
  const [problem, setProblem] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const [copyName, setCopyName] = useState('')
  const [managedArea, setManagedArea] = useState(0)
  const [pngName, setPngName] = useState('')
  const pendingLive = useRef<Promise<void>>(Promise.resolve())
  const chosen = settings.value('altscreen.profile')
  // Never confuse the selected editor view with the map view actually controlling the URL.
  // Views without a map use the last preceding map view (3/4 inherit 2 in the Skoda profile).
  const activeMapIndex = draft && editing === chosen && Boolean(chosen) && liveCarView !== null
    ? mapViewIndex(draft, liveCarView) : -1
  // Follow the actual Controller slot, not its inherited map URL; overlay-only slots stay editable.
  const controllerSlot = pendingControllerView ?? liveCarView
  const editingView = followController && editing === chosen && controllerSlot !== null && controllerSlot >= 0
    && controllerSlot < (draft?.views.length ?? 0) ? controllerSlot : view
  // Preview follows the edited View, not a different live Controller view; overlay-only
  // Views make their inherited map rectangle explicit without pretending to own an iOS view area.
  // Highlight the single selected area, without silently assigning it.
  const previewArea = Math.min(managedArea, Math.max(0, (draft?.areas.length ?? 1) - 1))

  useEffect(() => {
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

  /** Opens profile [id] in the editor on view [at], the first for another profile, the last if it has fewer views. */
  const open = useCallback((list: ClusterProfilesData, id: string | null, at = 0) => {
    const file = list.profiles.find((p) => p.id === id) ?? list.profiles[0]
    setEditing(file?.id ?? null)
    const read = file ? parse(file.text) : {}
    setDraft(read.profile ?? null)
    setText(file?.text ?? '')
    setProblem(read.error ?? null)
    setView(Math.max(0, Math.min(at, (read.profile?.views.length ?? 1) - 1)))
    setFollowController(true)
  }, [])

  const reload = useCallback(
    async (id: string | null, at = 0) => {
      const list = await backend.clusterProfiles()
      setData(list)
      open(list, id, at)
    },
    [backend, open],
  )

  useEffect(() => {
    void reload(chosen || null)
    // Read once as the page opens; Reload reads again.
  }, [reload])

  function change(next: Profile, mode: 'url' | 'descriptor' | 'local' | null = null) {
    setDraft(next)
    const nextText = JSON.stringify(next, null, 2)
    setText(nextText)
    setDone(null)
    // URL-only view options apply immediately for the selected active profile.
    // Serialize writes so two rapid switches cannot land out of order.
    if (mode && editing && editing === chosen) {
      const id = editing
      pendingLive.current = pendingLive.current.catch(() => {}).then(async () => {
        try {
          const error = await backend.saveClusterProfile(id, nextText)
          if (error) setProblem(error)
          else {
            setProblem(null)
            setDone(mode === 'url' ? 'Saved: live CarPlay URL requested'
              : mode === 'local' ? 'Saved: local cockpit overlay updated'
              : 'Saved: display changes require CarPlay reconnect')
          }
        } catch (error) {
          setProblem(`Live profile update failed: ${String(error)}`)
        }
      })
    }
  }

  async function save(id: string, saved: string | null) {
    await pendingLive.current
    setDone(null)
    const error = await backend.saveClusterProfile(id, saved)
    setProblem(error)
    if (error) return
    setDone(saved === null ? `Deleted ${id}` : `Saved ${id}`)
    // Saved, the editor stays on the view it was on; a deleted profile's place takes another, from its first view.
    await reload(saved === null ? chosen || null : id, saved === null || id !== editing ? 0 : editingView)
    if (saved !== null) setDone(`Saved ${id}`)
  }

  const ids: readonly Choice[] = (data?.profiles ?? []).map((p) => [p.id, p.id] as const)
  const views: readonly Choice[] = (draft?.views ?? []).map((v, i) => [String(i), v.name || `View ${i}`] as const)
  const display = draft?.display
  const editDisplay = (key: 'width' | 'height' | 'widthMm' | 'heightMm' | 'fps', value: string) => {
    const n = Number(value.trim())
    if (!draft || !Number.isInteger(n)) return 'Enter a whole number'
    if (key === 'fps') {
      if (n < 1 || n > 120) return 'FPS must be between 1 and 120'
      change({ ...draft, display: { ...draft.display, fps: n } }, 'descriptor')
    } else if (n > 0) change(setDisplay(draft, key, n), 'descriptor')
    else return 'Enter a positive number'
  }
  const physicalZoom = display?.physicalZoom ?? 100
  const effectiveWidth = display ? Math.max(1, Math.round(display.widthMm * 100 / physicalZoom)) : 0
  const effectiveHeight = display ? Math.max(1, Math.round(display.heightMm * 100 / physicalZoom)) : 0

  return (
    <>
      <Group title="Vehicle Profile" note="UI v4 · one vehicle contains its display, Views, Areas and Overlays" />
      <Row label="Active vehicle" title="The vehicle profile the iPhone negotiates on reconnect">
        <Segmented
          label="Profile"
          value={chosen}
          options={[['', 'None'], ...ids]}
          onChange={(id) => {
            void settings.save({ 'altscreen.profile': id })
            if (id && data) open(data, id)
          }}
        />
      </Row>
      <Row>
        <button type="button" className="btn small" onClick={() => void reload(editing, editingView)}>
          Reload
        </button>
        <button type="button" className="btn small" onClick={() => void backend.open('profiles')}>
          Open profiles folder
        </button>
        <button type="button" className="btn small" onClick={() => {
          const profile = newBlankProfile()
          setDraft(profile)
          setText(JSON.stringify(profile, null, 2))
          setEditing(null)
          setFollowController(false)
          setView(0)
          setCopyName('')
          setDone('New blank vehicle profile: enter an ID under Save as, then Save copy')
          setProblem(null)
        }}>New blank vehicle</button>
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
        }}>{data?.profiles.find((p) => p.id === editing)?.builtIn ? 'Reset built-in' : 'Delete vehicle'}</button>}
      </Row>
      <Row label="New profile ID" title="The filename under profiles/, independent of the read-only vehicle name">
        <Field label="New profile ID" value={copyName} placeholder="my-car" onCommit={(value) => setCopyName(value.trim())} />
        <button type="button" className="btn small"
          disabled={!draft || !/^[A-Za-z0-9._-]{1,64}$/.test(copyName) || data?.profiles.some((p) => p.id === copyName)}
          onClick={() => void save(copyName, text)}>Save new / copy</button>
      </Row>
      {data && data.profiles.length > 0 && (
        <>
          {done && <Row><small>{done}</small></Row>}
          {problem && (
            <Row>
              <span className="errtext">{problem}</span>
            </Row>
          )}
          {draft && display && (
            <>
              <Row label="Vehicle name"><span>{draft.name ?? editing ?? "Unnamed vehicle"}</span></Row>
              <Row><small>Profile ID: {editing ?? 'new / unsaved'} · {draft.views.length} Controller views · {draft.areas.length} declared areas</small></Row>
              {editing === chosen && Boolean(chosen) && (
                <>
                  <Group title="Display Geometry" note="The edited vehicle profile owns Size and Custom dimensions; changes need a reconnect" />
                  <Row label="Vehicle Profile"><span>{display.width} × {display.height} px · {display.widthMm} × {display.heightMm} mm (active on iPhone reconnect)</span></Row>
                  <Row><small>The Custom size below is independently saved in settings.properties. It never rewrites this vehicle profile and applies only when Vehicle Profile is None.</small></Row>
                  <Row label="Size">
                    <Segmented label="Size"
                      value={FRAME_PRESETS.some(([w, h]) => w === display.width && h === display.height)
                        ? String(display.width) + 'x' + String(display.height) : 'custom'}
                      options={[...FRAME_PRESETS.map(([w, h]) => [String(w) + 'x' + String(h), String(w) + '×' + String(h)] as const),
                        ['custom', 'Custom'] as const]}
                      onChange={(size) => {
                        if (size === 'custom') return
                        const [width, height] = size.split('x').map(Number)
                        if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) return
                        change(setDisplay(setDisplay(draft, 'width', width), 'height', height), 'descriptor')
                      }} />
                  </Row>
                  <Row>
                    <Field label="Custom width" value={String(display.width)} className="short c"
                      onCommit={(text) => editDisplay('width', text)} />
                    <span className="x times">×</span>
                    <Field label="Custom height" value={String(display.height)} className="short c"
                      onCommit={(text) => editDisplay('height', text)} />
                    <span className="unit">px</span>
                    <ActualSize sizes={altScreenWindow} window="altscreen" backend={backend} />
                  </Row>
                  <Row><small>Size and Custom dimensions above edit this vehicle profile. The separate
                    no-profile fallback (altscreen.width/height) is configured under AltScreen when
                    Profile is None and is never overwritten here. Reconnect to renegotiate display geometry.</small></Row>
                  <Row label="Physical size" title="Calibrated physical reference size; scaling below does not alter this baseline">
                    <Field label="Physical width" className="n" value={String(display.widthMm)} onCommit={(t) => editDisplay('widthMm', t)} />
                    <span className="unit">×</span>
                    <Field label="Physical height" className="n" value={String(display.heightMm)} onCommit={(t) => editDisplay('heightMm', t)} />
                    <span className="unit">mm</span>
                  </Row>
                  <Row label="Frames per Second" title="Maximum cluster frame rate requested from the iPhone">
                    <Field label="Frames per Second (FPS)" className="n" value={String(display.fps ?? 30)}
                      onCommit={(t) => editDisplay('fps', t)} />
                    <span className="unit">FPS</span>
                  </Row>
                </>
              )}
              <Group title="Vehicle Views" note="One view selector controls CarPlay, Safe Area and Overlay sections below" />
              <Row label="Editing view" title="Follow Controller selects the active map view automatically; manual selection edits without switching the Controller">
                <Segmented label="Car view" value={String(editingView)} options={views}
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
                  onChange={setCoupleController} />
              </Row>
              <Row label="View name">
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
              <Row label="Active view">
                <span>{liveCarView === null ? 'Not connected'
                  : `${liveCarView}: ${draft.views[liveCarView]?.name ?? 'Vehicle view'}${activeMapIndex >= 0 && activeMapIndex !== liveCarView ? ` · map settings from View ${activeMapIndex}` : ''}`}</span>
                <button type="button" className="btn small" disabled={liveCarView === null || !chosen || !draft}
                  onClick={() => requestControllerView(editingView)}>Show editing view on AltScreen</button>
                <button type="button" className="btn small" disabled={liveCarView === null}
                  onClick={() => { void backend.control('altscreen.view', true).then(() => backend.control('altscreen.view', false)) }}>
                  Next Controller View
                </button>
              </Row>
              <Row>
                <button type="button" className="btn small" onClick={() => change(addView(draft), 'descriptor')}>
                  Add view
                </button>
                <button
                  type="button"
                  className="btn small"
                  title="Remove this view; a profile keeps one view with the map"
                  onClick={() => {
                    const next = removeView(draft, editingView)
                    if (next) {
                      change(next, 'descriptor')
                      setFollowController(false)
                      setView(Math.max(0, editingView - 1))
                    } else setProblem('A profile keeps one view with the map')
                  }}
                >
                  Remove view
                </button>
              </Row>
              {editing === chosen && Boolean(chosen) && (
                <>
                  <Group title="Scaling" note="Both scaling methods may be combined" />
                  <Row label="Zoom factor" title="iOS Smart Display zoomFactor. Auto omits this property.">
                    <Segmented label="Zoom factor" value={display.zoomFactor === undefined ? '' : String(display.zoomFactor)}
                      options={ZOOM} onChange={(v) => change(setZoomFactor(draft, v), 'descriptor')} />
                  </Row>
                  <Row label="Physical zoom" title="Adjusts the physical millimetres advertised to iOS; 100% preserves the reference size">
                    <Segmented label="Physical zoom" columns={3} value={String(physicalZoom)} options={PHYSICAL_ZOOMS}
                      onChange={(v) => change({ ...draft, display: { ...display, physicalZoom: Number(v) } }, 'descriptor')} />
                  </Row>
                  <Row label="Effective size">
                    <span>{effectiveWidth} × {effectiveHeight} mm (reported to iOS)</span>
                  </Row>
                  <Row>
                    <span className="hint">Resolution, physical size and both zoom settings apply after CarPlay reconnect.</span>
                    <button type="button" className="btn small" disabled={!canReconnect}
                      title="End this CarPlay session and renegotiate the updated cluster display"
                      onClick={() => void pendingLive.current.then(() => backend.reconnect())}>
                      Reconnect CarPlay
                    </button>
                  </Row>
                </>
              )}
              <Group title="CarPlay Setup" note="Settings of the vehicle View selected above" />
              {draft.views[editingView] && (
                <>
                  {draft.views[editingView].area === undefined && (
                    <Row label="Inherited map source">
                      <span>View {mapViewIndex(draft, editingView)} · its CarPlay URL and safe area remain active under this overlay</span>
                      <button type="button" className="btn small"
                        onClick={() => {
                          setFollowController(false)
                          setView(mapViewIndex(draft, editingView))
                        }}>Edit map source</button>
                    </Row>
                  )}
                  <ProfileViewForm profile={draft} index={editingView} change={change} liveChange={(next) => change(next, 'url')} />
                  <Row>
                    <small>{editing === chosen && liveCarView === editingView
                      ? (draft.views[editingView]?.area === undefined
                        ? 'This Controller View is active. Its custom overlay is independent; the inherited map URL comes from the source View shown above.'
                        : 'This is the active Controller View: changes to its CarPlay options request a live URL.')
                      : 'Editing an inactive View: its changes apply when that View becomes active.'}
                      {' '}Navigation apps may ignore unsupported requests. Frame, safe area and native scale still require reconnect.</small>
                  </Row>
                </>
              )}
              {windowControls}
              <Group title="Safe Area Setup" note="Add, assign, clone and remove safe areas in the selected vehicle" />
              <Row label="Manage areas">
                <Segmented label="Area" value={String(Math.min(managedArea, draft.areas.length - 1))}
                  options={draft.areas.map((_, i) => [String(i), `Area ${i}`] as const)}
                  onChange={(id) => setManagedArea(Number(id))} />
                <button type="button" className="btn small"
                  disabled={draft.views[editingView]?.area === undefined ||
                    draft.views[editingView]?.area === managedArea}
                  onClick={() => change(setViewArea(draft, editingView, managedArea), 'descriptor')}>
                  Assign to View
                </button>
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
              <Row label="Declared areas">
                <span>{draft.areas.length} defined · {new Set(draft.views.map((v) => v.area).filter((a) => a !== undefined)).size} in use</span>
                <button type="button" className="btn small" disabled={draft.areas.length <= new Set(draft.views.map((v) => v.area).filter((a) => a !== undefined)).size}
                  onClick={() => change(compactAreas(draft), 'descriptor')}>Remove unused Safe Areas</button>
              </Row>
              <Row label="Safe-area preview">
                <Segmented label="Safe-area preview" value={safeAreaPreview}
                  options={[[ 'all', 'All areas' ], [ 'active', 'Selected area' ]]}
                  onChange={(next) => setSafeAreaPreview(next as 'all' | 'active')} />
              </Row>
              <Row label="All safe areas">
                <svg viewBox={`0 0 ${display.width} ${display.height}`} role="img"
                  aria-label="All declared safe areas; highlighted rectangle belongs to editing view"
                  style={{ width: '100%', maxWidth: 580, background: '#101924', border: '1px solid #64748b' }}>
                  <rect x={0} y={0} width={display.width} height={display.height} fill="none" stroke="#94a3b8" strokeWidth={2} />
                  {draft.areas.map(([x, y, width, height], i) =>
                    safeAreaPreview === 'active' && i !== previewArea ? null : (
                    <g key={i}>
                      <rect x={x} y={y} width={width} height={height}
                        fill={i === previewArea ? '#149c8b55' : '#60a5fa14'}
                        stroke={i === previewArea ? '#4ade80' : '#60a5fa'}
                        strokeWidth={i === previewArea ? 3 : 1} />
                      <text x={x + 6} y={y + 18} fill="#ffffff" fontSize={16}>Area {i}</text>
                    </g>
                  ))}
                </svg>
              </Row>
              <Row><small>The Area selector previews the chosen rectangle. Only Assign to View changes its binding. Overlay-only Views retain their inherited map area.</small></Row>
              {draft.views[editingView] && (
                <>
                  {draft.views[editingView].area !== undefined &&
                    draft.views.filter((v) => v.area === draft.views[editingView].area).length > 1 && (
                    <Row label="Shared safe area">
                      <span>Also used by Views {draft.views.map((v, i) => v.area === draft.views[editingView].area && i !== editingView ? i : null).filter((i) => i !== null).join(', ')}</span>
                      <button type="button" className="btn small" onClick={() => change(cloneViewArea(draft, editingView), 'descriptor')}>
                        Make independent copy
                      </button>
                    </Row>
                  )}
                  <ProfileSafeAreaForm profile={draft} index={editingView} change={(next) => change(next, 'descriptor')} />
                </>
              )}
              {!chosen && nativeInsets}
              <Row className="hint-row"><small>Changes to the green AltScreen safe-area frame preview immediately. iOS must reconnect to negotiate changed rectangles.</small></Row>
              <Group title="Cockpit Overlay Setup" note="Keep the embedded Shapes or use a transparent PNG" />
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
                      disabled={!/^[A-Za-z0-9._-]{1,64}\.png$/i.test(pngName)}
                      onClick={() => {
                        change(setOverlayPng(draft, editingView, pngName), 'local')
                        setProblem(null)
                      }}>Use PNG</button>
                    <button type="button" className="btn small" onClick={() => void backend.open('overlays')}>Open overlays folder</button>
                  </Row>
                  <Row><small>PNG: transparent, full AltScreen frame size ({display.width}×{display.height} px), placed under overlays/. Embedded Shapes are preserved and can be re-enabled at any time.</small></Row>
                </>
              )}
              <Group title="Profile JSON" note="Entire vehicle profile · always visible" />
              <div className="profile-json-editor"><Row><small>Direct JSON edits require explicit Save. All regular UI edits auto-save.</small></Row>
          <Row><small>Editing the entire vehicle profile: {editing ?? 'new / unsaved'}</small></Row>
          <Row label="JSON" title="The whole profile, the schematic's shapes among it; leave the field to apply it">
            <textarea
              aria-label="Profile JSON"
              className="profile-json"
              rows={22}
              spellCheck={false}
              value={text}
              onChange={(event) => setText(event.target.value)}
              onBlur={() => {
                const read = parse(text)
                setProblem(read.error ?? null)
                if (read.profile) setDraft(read.profile)
              }}
            />
          </Row>
          <Row>
            <button type="button" className="btn small" onClick={() => {
              const result = parse(text)
              setProblem(result.error ?? null)
              if (result.profile) {
                setDraft(result.profile)
                setText(JSON.stringify(result.profile, null, 2))
              }
            }}>Format JSON</button>
            <button type="button" className="btn small" disabled={!editing} onClick={() => editing && void save(editing, text)}>
              Save
            </button>
            <button type="button" className="btn small" onClick={() => data && open(data, editing, view)}>
              Revert
            </button>
          </Row>

              </div>
            </>
          )}
        </>
      )}
    </>
  )
}
