import { useRef, useState, type ReactNode } from 'react'
import type { Backend, GpsState, RouteAction } from '../api'
import { keyLabel } from '../ControlsScreen'
import { Group, Row } from '../shell/controls'
import type { Settings } from '../shell/useSettings'

/**
 * gps.route: a GPX file the car follows. Choose GPX reads a file and hands it to the app, which keeps a copy in its
 * routes folder and answers the path, saved as gps.route; Play, Pause and Restart drive the car along it, as F5 does.
 * The speed field is the page's own, for gps.route.speed.
 */
export function RouteGroup(props: {
  backend: Backend
  settings: Settings
  car: GpsState | null
  /** The key that plays and pauses the route, as controls.properties names it. */
  routeKey?: string | null
  /** The GPS is off: the route does not play. */
  off: boolean
  speedField: ReactNode
}) {
  const { backend, settings, car, off } = props
  const input = useRef<HTMLInputElement>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const route = car?.route ?? null
  const file = settings.value('gps.route')

  async function choose(chosen: File | undefined) {
    if (!chosen) return
    setProblem(null)
    const answer = await backend.gpsRoute('load', chosen.name, await chosen.text())
    if (answer.error) setProblem(answer.error)
    else if (answer.path) void settings.save({ 'gps.route': answer.path })
    if (input.current) input.current.value = ''
  }

  async function act(action: RouteAction) {
    setProblem(null)
    const answer = await backend.gpsRoute(action)
    if (answer.error) setProblem(answer.error)
  }

  const key = props.routeKey ? ` (${keyLabel(props.routeKey)})` : ''
  const blocked = off ? 'Turn on the GPS first' : !route ? 'Choose a GPX route first' : null
  const shown = problem ?? car?.routeError ?? null
  return (
    <>
      <Group title="Route" note={route ? `${route.at.toFixed(2)} of ${route.km.toFixed(2)} km` : undefined} />
      <Row label="Route (GPX)" title="A GPX track or route the car follows when played; the app keeps a copy in its routes folder">
        <input
          ref={input}
          type="file"
          accept=".gpx"
          hidden
          aria-label="GPX file"
          onChange={(event) => void choose(event.target.files?.[0])}
        />
        <button type="button" className="btn small" onClick={() => input.current?.click()}>
          Choose GPX…
        </button>
        <span className="route-file">{file || 'None'}</span>
      </Row>
      {shown && (
        <Row>
          <span className="errtext">{shown}</span>
        </Row>
      )}
      <Row label="Route speed" title="How fast the car goes along the route between the corners; it slows for the sharp ones">
        {props.speedField}
        <span className="unit">km/h</span>
      </Row>
      <Row>
        <button
          type="button"
          className="btn small"
          disabled={blocked !== null}
          title={blocked ?? `${route?.playing ? 'Stop' : 'Drive'} the car along the route${key}`}
          onClick={() => void act(route?.playing ? 'pause' : 'play')}
        >
          {route?.playing ? 'Pause' : 'Play'}
        </button>
        <button
          type="button"
          className="btn small"
          disabled={blocked !== null}
          title={blocked ?? 'Put the car back at the start of the route'}
          onClick={() => void act('restart')}
        >
          Restart
        </button>
      </Row>
    </>
  )
}
