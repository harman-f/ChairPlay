import { Row, Segmented, type Choice } from '../shell/controls'
import { Field } from '../shell/fields'
import { setOption, setSafeArea, setViewField, viewUrl, type Profile } from './profileEdits'

/** The cluster URL's options: blank leaves each to the navigation app. */
const SHOW: readonly Choice[] = [
  ['', 'Default'],
  ['yes', 'Show'],
  ['no', 'Hide'],
]
const CARD: readonly Choice[] = [
  ['', 'Default'],
  ['leftAligned', 'Left'],
  ['rightAligned', 'Right'],
  ['topAligned', 'Top'],
  ['no', 'None'],
]
const SCENES: readonly Choice[] = [
  ['map', 'Map', 'maps:/car/instrumentcluster/map'],
  ['instrumentcluster', 'Map + card', 'maps:/car/instrumentcluster'],
]

/** A whole number from [text], or null. */
function whole(text: string): number | null {
  const n = Number(text.trim())
  return Number.isInteger(n) ? n : null
}

/**
 * One car view of a profile: its name, whether it shows the map, and with it the cluster URL (scene, ETA, speed limit,
 * turn card) and the safe area the iPhone lays the map out in.
 */
export function ProfileViewForm({ profile, index, liveChange }: { profile: Profile; index: number; change: (p: Profile) => void; liveChange: (p: Profile) => void }) {
  const view = profile.views[index]
  const area = view.area === undefined ? null : profile.areas[view.area]
  const option = (key: string, label: string, choices: readonly Choice[], title: string) => (
    <Row label={label} title={title}>
      <Segmented label={label} value={view.options?.[key] ?? ''} options={choices} onChange={(v) => liveChange(setOption(profile, index, key, v))} />
    </Row>
  )
  return (
    <>
      {area && (
        <>
          <Row label="Scene" title="The bare map, or the map with the navigation app's own turn card">
            <Segmented label="Scene" value={view.scene ?? 'map'} options={SCENES} onChange={(v) => liveChange(setViewField(profile, index, 'scene', v))} />
          </Row>
          {option('showETA', 'ETA', SHOW, "The navigation app's arrival time on the map (showETA)")}
          {option('showSpeedLimit', 'Speed limit', SHOW, "The navigation app's speed limit sign (showSpeedLimit)")}
          {option('showCompass', 'Compass', SHOW, "The navigation app's compass on the map (showCompass)")}
          {option('maneuverLayout', 'Turn card', CARD, "Where the navigation app's turn card goes (maneuverLayout)")}
          <Row label="URL">
            <code className="route-file">{viewUrl(view)}</code>
          </Row>
        </>
      )}
    </>
  )
}

/** Profile-specific rectangle, kept with the selected car view instead of the navigation URL controls. */
export function ProfileSafeAreaForm({ profile, index, change }: { profile: Profile; index: number; change: (p: Profile) => void }) {
  const view = profile.views[index]
  if (view.area === undefined) {
    return <Row><small>This view covers the map with its overlay. It retains the preceding map view's area.</small></Row>
  }
  const area = profile.areas[view.area]
  if (!area) return <Row><small>Invalid area reference: {view.area}</small></Row>
  const edge = (i: number, label: string) => (
    <>
      <Field label={`Safe area ${label}`} className="n" value={String(area[i])} onCommit={(value) => {
        const number = whole(value)
        if (number === null || number < 0) return 'A whole number of 0 or more'
        const updated = [...area]
        updated[i] = number
        const [x, y, width, height] = updated
        if (width <= 0 || height <= 0 || x + width > profile.display.width || y + height > profile.display.height)
          return 'The rectangle must fit inside the display'
        change(setSafeArea(profile, index, updated))
      }} />
      <span className="unit">{label}</span>
    </>
  )
  const [x, y, width, height] = area
  return (
    <>
      <Row label="Bound area"><span>Area {view.area} (View {index})</span></Row>
      <Row label="Safe area" title="Map rectangle in the display's pixel coordinates">
        {edge(0, 'x')}{edge(1, 'y')}
      </Row>
      <Row label="Safe size">
        {edge(2, 'width')}{edge(3, 'height')}
      </Row>
      <Row label="Computed insets">
        <span>Left {x} · Top {y} · Right {profile.display.width - x - width} · Bottom {profile.display.height - y - height} px</span>
      </Row>
      <Row className="hint-row"><small>View geometry is negotiated on CarPlay reconnect. Views sharing an area index share this rectangle.</small></Row>
    </>
  )
}
