import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { FakeBackend } from '../fakeBackend'
import { Shell } from '../shell/Shell'
import { appState } from '../testing'

afterEach(cleanup)

const text = JSON.stringify({
  name: 'Car',
  display: { width: 1010, height: 376, widthMm: 300, heightMm: 112 },
  areas: [[364, 56, 280, 255]],
  views: [{ name: 'View 0', area: 0, scene: 'map' }, { name: 'View 1', cover: true }],
})

async function altscreenPage() {
  const backend = new FakeBackend()
  backend.data = { ...backend.data, values: { ...backend.data.values, 'altscreen.enabled': 'true', 'altscreen.profile': 'car' } }
  backend.profiles = { profiles: [{ id: 'car', text, builtIn: false }, { id: 'other', text, builtIn: false }], active: 'car' }
  render(<Shell state={appState({ phase: 'active', canShowCarPlay: true })} backend={backend} />)
  await screen.findByRole('textbox', { name: 'Network' })
  fireEvent.click(screen.getByRole('tab', { name: 'AltScreen' }))
  await screen.findByText('Vehicle Views')
  return backend
}

describe('AltScreen page, car profiles', () => {
  // A safe area changed and saved goes to the app as the profile's JSON, the rest kept.
  it('saves a view edited in the form', async () => {
    const backend = await altscreenPage()
    const y = screen.getByRole('textbox', { name: 'Safe area y' })
    fireEvent.change(y, { target: { value: '100' } })
    fireEvent.blur(y)
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'ETA' })).getByRole('radio', { name: 'Hide' }))
    fireEvent.click(screen.getByText('Profile JSON'))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(backend.profileSaves).toHaveLength(3))
    const saved = JSON.parse(backend.profileSaves[2].text!)
    expect(backend.profileSaves[2].id).toBe('car')
    expect(saved.areas[0]).toEqual([364, 100, 280, 255])
    expect(saved.views[0].options).toEqual({ showETA: 'no' })
    expect(saved.views[1]).toEqual({ name: 'View 1', cover: true })
  })

  it('applies navigation URL controls immediately for the active profile, not for other profiles', async () => {
    const backend = await altscreenPage()
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Compass' })).getByRole('radio', { name: 'Show' }))

    await waitFor(() => expect(backend.profileSaves).toHaveLength(1))
    const applied = JSON.parse(backend.profileSaves[0].text!)
    expect(applied.views[0].options.showCompass).toBe('yes')

    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Profile' })).getByRole('radio', { name: 'other' }))
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'ETA' })).getByRole('radio', { name: 'Hide' }))
    expect(backend.profileSaves).toHaveLength(1)
  })

  it('combines iOS zoomFactor and physical zoom and reconnects through the original backend', async () => {
    const backend = await altscreenPage()
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Physical zoom' })).getByRole('radio', { name: '125 %' }))
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Zoom factor' })).getByRole('radio', { name: '85 %' }))
    await waitFor(() => expect(backend.profileSaves).toHaveLength(2))
    const saved = JSON.parse(backend.profileSaves[1].text!)
    expect(saved.display.physicalZoom).toBe(125)
    expect(saved.display.zoomFactor).toBe(85)
    expect(screen.getByText('240 × 90 mm (reported to iOS)')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Reconnect CarPlay' }))
    await waitFor(() => expect(backend.reconnects).toBe(1))
  })

  it('shows consolidated CarPlay settings and an always-visible profile editor', async () => {
    await altscreenPage()
    expect(screen.getByText('CarPlay Setup')).toBeTruthy()
    expect(screen.queryByRole('radiogroup', { name: 'View' })).toBeNull()
    expect(screen.getByRole('textbox', { name: 'Frames per Second (FPS)' })).toBeTruthy()
    expect(within(screen.getByRole('radiogroup', { name: 'Physical zoom' })).getAllByRole('radio')).toHaveLength(6)
    expect(within(screen.getByRole('radiogroup', { name: 'Physical zoom' })).getByRole('radio', { name: '50 %' })).toBeTruthy()
    expect(screen.getByRole('textbox', { name: 'Safe area x' })).toBeTruthy()
    expect(screen.getByText('Profile JSON')).toBeTruthy()
    expect(screen.getByText('Profile JSON').closest('details')).toBeNull()
    expect(screen.getByRole('textbox', { name: 'Profile JSON' })).toBeTruthy()
  })

  it('follows Controller views 1 and 2 for live edits and maps overlay-only View 3 to View 2', async () => {
    const backend = new FakeBackend()
    backend.data = { ...backend.data, values: {
      ...backend.data.values, 'altscreen.enabled': 'true', 'altscreen.profile': 'car',
    } }
    const profile = JSON.stringify({
      name: 'Skoda test', display: { width: 1010, height: 376, widthMm: 202, heightMm: 75 },
      areas: [[372, 58, 266, 249], [40, 58, 930, 216], [290, 61, 430, 245]],
      views: [
        { name: 'View 0', area: 0, scene: 'map' },
        { name: 'View 1', area: 1, scene: 'map' },
        { name: 'View 2', area: 2, scene: 'map' },
        { name: 'View 3', cover: true },
        { name: 'View 4', cover: true },
      ],
    })
    backend.profiles = { profiles: [{ id: 'car', text: profile, builtIn: false }], active: 'car' }
    const state = appState({ phase: 'active', canShowCarPlay: true })
    const withView = (carView: number) => ({ ...state, controls: { ...state.controls!, carView } })
    const page = render(<Shell state={withView(0)} backend={backend} />)
    await screen.findByRole('textbox', { name: 'Network' })
    fireEvent.click(screen.getByRole('tab', { name: 'AltScreen' }))
    await screen.findByText('Vehicle Views')

    page.rerender(<Shell state={withView(1)} backend={backend} />)
    await waitFor(() => expect(within(screen.getByRole('radiogroup', { name: 'Car view' }))
      .getByRole('radio', { name: 'View 1' }).getAttribute('aria-checked')).toBe('true'))
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'ETA' })).getByRole('radio', { name: 'Hide' }))
    await waitFor(() => expect(backend.profileSaves).toHaveLength(1))
    const first = JSON.parse(backend.profileSaves[0].text!)
    expect(first.views[1].options.showETA).toBe('no')
    expect(first.views[0].options).toBeUndefined()

    const areas = () => screen.getByRole('img', { name: /All declared safe areas/ })
    expect(areas().querySelectorAll('rect')).toHaveLength(4)
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Safe-area preview' }))
      .getByRole('radio', { name: 'Selected area' }))
    expect(areas().querySelectorAll('rect')).toHaveLength(2)

    page.rerender(<Shell state={withView(2)} backend={backend} />)
    await waitFor(() => expect(within(screen.getByRole('radiogroup', { name: 'Car view' }))
      .getByRole('radio', { name: 'View 2' }).getAttribute('aria-checked')).toBe('true'))
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Compass' })).getByRole('radio', { name: 'Show' }))
    await waitFor(() => expect(backend.profileSaves).toHaveLength(2))
    const second = JSON.parse(backend.profileSaves[1].text!)
    expect(second.views[2].options.showCompass).toBe('yes')
    expect(second.views[1].options.showETA).toBe('no')
    expect(areas().querySelectorAll('rect')).toHaveLength(2)

    page.rerender(<Shell state={withView(3)} backend={backend} />)
    await waitFor(() => expect(screen.getByText(/map settings from View 2/)).toBeTruthy())
    expect(within(screen.getByRole('radiogroup', { name: 'Car view' }))
      .getByRole('radio', { name: 'View 3' }).getAttribute('aria-checked')).toBe('true')
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Safe-area preview' }))
      .getByRole('radio', { name: 'All areas' }))
    expect(areas().querySelectorAll('rect')).toHaveLength(4)
  })

  it('creates a blank vehicle and configures its PNG overlay rather than exporting legacy JSON', async () => {
    const backend = await altscreenPage()
    fireEvent.click(screen.getByRole('button', { name: 'New blank vehicle' }))
    expect(screen.getByRole('button', { name: 'Edit name' })).toBeTruthy()
    expect(screen.getByText(/1 Controller views/)).toBeTruthy()
    const png = screen.getByRole('textbox', { name: 'PNG filename' })
    fireEvent.change(png, { target: { value: 'new-cluster.png' } })
    fireEvent.blur(png)
    fireEvent.click(screen.getByRole('button', { name: 'Use PNG' }))
    const raw = document.querySelector('textarea[aria-label="Profile JSON"]') as HTMLTextAreaElement
    expect(raw).not.toBeNull()
    expect(JSON.parse(raw.value).views[0].overlayImage).toBe('new-cluster.png')
    expect(backend.overlaySaves).toHaveLength(0)
  })

  it('audits v4 section order, controls and profile-independent geometry', async () => {
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

  it('edits and saves the vehicle view name at the view selector', async () => {
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

  it('shows the effective vehicle geometry rather than stored fallback and saves preset to JSON', async () => {
    const backend = await altscreenPage()
    expect(backend.data.values['altscreen.width']).toBe('1440')
    expect(backend.data.values['altscreen.height']).toBe('540')
    const size = within(screen.getByRole('radiogroup', { name: 'Size' }))
    expect(size.getByRole('radio', { name: 'Custom' }).getAttribute('aria-checked')).toBe('true')
    expect((screen.getByRole('textbox', { name: 'Custom width' }) as HTMLInputElement).value).toBe('1010')
    expect((screen.getByRole('textbox', { name: 'Custom height' }) as HTMLInputElement).value).toBe('376')
    fireEvent.click(size.getByRole('radio', { name: '1280×480' }))
    await waitFor(() => expect(backend.profileSaves.length).toBeGreaterThan(0))
    const saved = JSON.parse(backend.profileSaves[backend.profileSaves.length - 1].text!)
    expect(saved.display.width).toBe(1280)
    expect(saved.display.height).toBe(480)
    expect(backend.saved).toEqual([])
    expect(backend.data.values['altscreen.width']).toBe('1440')
    expect(backend.data.values['altscreen.height']).toBe('540')
  })

  it('does not modify the fallback when selecting no vehicle profile', async () => {
    const backend = await altscreenPage()
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Profile' }))
      .getByRole('radio', { name: 'None' }))
    await waitFor(() => expect(backend.saved).toEqual([{ 'altscreen.profile': '' }]))
    expect(backend.data.values['altscreen.width']).toBe('1440')
    expect(backend.data.values['altscreen.height']).toBe('540')
  })

  // Saved, the editor stays on the view being edited rather than going back to the first.
  it('stays on the view being edited after a save', async () => {
    const backend = await altscreenPage()
    const views = () => screen.getByRole('radiogroup', { name: 'Car view' })
    fireEvent.click(within(views()).getByRole('radio', { name: 'View 1' }))
    fireEvent.click(screen.getByText('Profile JSON'))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(backend.profileSaves).toHaveLength(1))
    await waitFor(() => expect(within(views()).getByRole('radio', { name: 'View 1' }).getAttribute('aria-checked')).toBe('true'))
    expect(screen.getByRole('button', { name: 'Edit name' })).toBeTruthy()
  })

  // Choosing a profile saves altscreen.profile; the one in use cannot be deleted, another can.
  it('requires confirmation before deleting a vehicle profile', async () => {
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
  })
})
