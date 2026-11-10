import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { FakeBackend } from '../fakeBackend'
import { appState } from '../testing'
import { Shell } from './Shell'

afterEach(cleanup)

// The settings window's page (/settings): it never gives way to CarPlay, which shows in its own window.
describe('settings in a window of their own', () => {
  it('stays on the settings while CarPlay shows, and offers no CarPlay button', async () => {
    const state = { ...appState({ phase: 'active', canShowCarPlay: true }), screen: 'carplay' as const, embedded: true }
    const { container } = render(<Shell state={state} backend={new FakeBackend()} standalone />)
    await screen.findByRole('textbox', { name: 'Network' })
    expect(container.querySelector('.shell.away')).toBeNull()
    expect(screen.queryByRole('button', { name: 'CarPlay' })).toBeNull()
  })

  it('shows the settings, not the wait, while the app connects on its own', async () => {
    const state = { ...appState({ phase: 'calling', canShowCarPlay: false }), waiting: true }
    render(<Shell state={state} backend={new FakeBackend()} standalone />)
    expect(await screen.findByRole('textbox', { name: 'Network' })).toBeTruthy()
  })

  // Over CarPlay in its window, as before: the page fades away while CarPlay shows.
  it('still gives way to CarPlay in the main window', () => {
    const state = { ...appState({ phase: 'active', canShowCarPlay: true }), screen: 'carplay' as const, embedded: true }
    const { container } = render(<Shell state={state} backend={new FakeBackend()} />)
    expect(container.querySelector('.shell.away')).not.toBeNull()
  })
})
