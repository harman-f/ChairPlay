import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { GpsState } from '../api'
import { FakeBackend } from '../fakeBackend'
import { Shell } from '../shell/Shell'
import { appState } from '../testing'

afterEach(cleanup)

const car: GpsState = {
  position: [52.2297, 21.0122],
  heading: 0,
  speed: 0,
  rpm: 0,
  gear: 'P',
  throttle: 0,
  brake: 0,
  keyboard: false,
  gamepad: false,
  listening: true,
  sentences: ['GGA', 'RMC'],
  sent: 3,
}

async function gpsPage(gps: GpsState, on = true) {
  const backend = new FakeBackend()
  backend.data = { ...backend.data, values: { ...backend.data.values, 'gps.enabled': String(on), 'gps.route': '' } }
  render(<Shell state={{ ...appState({ phase: 'active', canShowCarPlay: true }), gps }} backend={backend} />)
  await screen.findByRole('textbox', { name: 'Network' })
  fireEvent.click(screen.getByRole('tab', { name: 'GPS' }))
  return backend
}

describe('GPS page, route', () => {
  // A chosen file goes to the app, which keeps it and answers its path; the page saves that as gps.route.
  it('keeps a chosen GPX file and saves its path', async () => {
    const backend = await gpsPage(car)
    backend.routeAnswer = { path: 'routes/loop.gpx' }
    const file = new File(['<gpx/>'], 'loop.gpx', { type: 'application/gpx+xml' })

    fireEvent.change(screen.getByLabelText('GPX file'), { target: { files: [file] } })

    await waitFor(() => expect(backend.saved).toEqual([{ 'gps.route': 'routes/loop.gpx' }]))
    expect(backend.routeActions).toEqual(['load loop.gpx'])
  })

  // A file the app refuses says why and saves nothing.
  it('says why a file is refused', async () => {
    const backend = await gpsPage(car)
    backend.routeAnswer = { error: 'loop.gpx has fewer than two points' }

    fireEvent.change(screen.getByLabelText('GPX file'), { target: { files: [new File(['x'], 'loop.gpx')] } })

    expect(await screen.findByText('loop.gpx has fewer than two points')).toBeTruthy()
    expect(backend.saved).toEqual([])
  })

  // Play while stopped, Pause while playing; neither without a route.
  it('plays and pauses a route, and waits for one', async () => {
    const backend = await gpsPage({ ...car, route: { name: 'routes/loop.gpx', km: 3.2, at: 0, playing: false } })
    fireEvent.click(screen.getByRole('button', { name: 'Play' }))
    await waitFor(() => expect(backend.routeActions).toEqual(['play']))
    cleanup()

    const playing = await gpsPage({ ...car, route: { name: 'routes/loop.gpx', km: 3.2, at: 1.1, playing: true } })
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
    await waitFor(() => expect(playing.routeActions).toEqual(['pause']))
    cleanup()

    await gpsPage(car)
    expect((screen.getByRole('button', { name: 'Play' }) as HTMLButtonElement).disabled).toBe(true)
  })
})
