import { describe, expect, it } from 'vitest'
import { addView, removeView, setDisplay, setOption, setSafeArea, setViewMap, setZoomFactor, viewUrl, type Profile } from './profileEdits'

const profile: Profile = {
  display: { width: 1000, height: 400, widthMm: 300, heightMm: 120 },
  areas: [[10, 20, 300, 200]],
  views: [{ name: 'A', area: 0, scene: 'map' }, { name: 'B', cover: true }],
}

describe('car profile edits', () => {
  // The URL takes the options set, in their order, as the app builds it.
  it('builds the cluster URL from the scene and the options', () => {
    expect(viewUrl(profile.views[0])).toBe('maps:/car/instrumentcluster/map')
    const card = setOption(setOption(profile, 0, 'maneuverLayout', 'leftAligned'), 0, 'showETA', 'no')
    expect(viewUrl({ ...card.views[0], scene: 'instrumentcluster' })).toBe('maps:/car/instrumentcluster?showETA=no&maneuverLayout=leftAligned')
    expect(setOption(card, 0, 'showETA', '').views[0].options).toEqual({ maneuverLayout: 'leftAligned' })
    const compass = setOption(card, 0, 'showCompass', 'yes')
    expect(viewUrl(compass.views[0])).toBe('maps:/car/instrumentcluster/map?showETA=no&showCompass=yes&maneuverLayout=leftAligned')
  })

  // A view given the map gets an area of its own; taken away and given back, it keeps it.
  it('gives a view the map with an area of its own', () => {
    const on = setViewMap(profile, 1, true)
    expect(on.views[1].area).toBe(1)
    expect(on.areas[1]).toEqual([100, 40, 800, 320])
    const back = setViewMap(setViewMap(on, 1, false), 1, true)
    expect(back.views[1].area).toBe(1)
    expect(back.areas).toHaveLength(2)
    expect(setSafeArea(on, 1, [1, 2, 3, 4]).areas[1]).toEqual([1, 2, 3, 4])
  })

  // The physical size keeps the frame's shape in pixels, or iOS takes the pixels for oblong and squeezes the picture.
  it('keeps the physical size in the shape of the frame', () => {
    const mu = { ...profile, display: { width: 1010, height: 376, widthMm: 300, heightMm: 112 } }
    expect(setDisplay(mu, 'widthMm', 340).display).toMatchObject({ widthMm: 340, heightMm: 127 })
    expect(setDisplay(mu, 'heightMm', 134).display).toMatchObject({ widthMm: 360, heightMm: 134 })
    expect(setDisplay(mu, 'width', 1280).display).toMatchObject({ width: 1280, widthMm: 300, heightMm: 88 })
    expect(setDisplay(mu, 'height', 480).display).toMatchObject({ height: 480, widthMm: 300, heightMm: 143 })
  })

  // A zoom factor is a number in the display; Auto takes the key out.
  it('sets and clears the zoom factor', () => {
    const zoomed = setZoomFactor(profile, '125')
    expect(zoomed.display.zoomFactor).toBe(125)
    expect('zoomFactor' in setZoomFactor(zoomed, '').display).toBe(false)
  })

  // Views come and go, but the last one with the map stays.
  it('adds and removes views, keeping one with the map', () => {
    expect(addView(profile).views).toHaveLength(3)
    expect(removeView(profile, 1)!.views).toHaveLength(1)
    expect(removeView(profile, 0)).toBeNull()
  })
})
