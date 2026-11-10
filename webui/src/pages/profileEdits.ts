// A car profile's JSON (ClusterProfile.kt reads it) and the AltScreen page's edits of it, each a new profile.

export interface ProfileView {
  name?: string
  /** The view area the map shows in; none for a view whose cluster covers the map. */
  area?: number
  /** 'map' for the bare map, 'instrumentcluster' for the map with the navigation app's card. */
  scene?: string
  /** showETA, showSpeedLimit, showCompass and maneuverLayout, as the cluster URL takes them. */
  options?: Record<string, string>
  cover?: boolean
  shapes?: unknown[]
  /** Optional reusable drawing in overlays/<id>.json. Inline shapes remain as a fallback. */
  overlay?: string
  overlayEnabled?: boolean
  overlayImage?: string
}

export interface Profile {
  name?: string
  display: { width: number; height: number; widthMm: number; heightMm: number; fps?: number; features?: number; primaryInputDevice?: number; zoomFactor?: number; physicalZoom?: number }
  /** Each view area's safe area: x, y, width, height. */
  areas: number[][]
  initialView?: number
  shapes?: unknown[]
  views: ProfileView[]
}

/** The cluster URL a view with the map asks for, as ClusterView.url makes it. */
export function viewUrl(view: ProfileView): string {
  const query = ['showETA', 'showSpeedLimit', 'showCompass', 'maneuverLayout']
    .filter((key) => view.options?.[key])
    .map((key) => `${key}=${view.options![key]}`)
    .join('&')
  return `maps:/car/instrumentcluster${(view.scene ?? 'map') === 'map' ? '/map' : ''}${query ? `?${query}` : ''}`
}

function withView(profile: Profile, index: number, change: (view: ProfileView) => ProfileView): Profile {
  return { ...profile, views: profile.views.map((view, i) => (i === index ? change(view) : view)) }
}

/**
 * The view with the map or without: a view given the map gets an area of its own, a safe area with a tenth of the frame
 * at each edge, which it keeps when the map goes again; without, the cluster covers the map.
 */
export function setViewMap(profile: Profile, index: number, on: boolean): Profile {
  const view = profile.views[index]
  if (!on) return withView(profile, index, ({ area: _, ...rest }) => ({ ...rest, cover: true, kept: view.area }) as ProfileView)
  const kept = (view as { kept?: number }).kept
  if (kept !== undefined && kept < profile.areas.length) {
    return withView(profile, index, ({ cover: _, kept: __, ...rest }: ProfileView & { kept?: number }) => ({ ...rest, area: kept }))
  }
  const { width, height } = profile.display
  const margin = [Math.round(width / 10), Math.round(height / 10)]
  const areas = [...profile.areas, [margin[0], margin[1], width - 2 * margin[0], height - 2 * margin[1]]]
  return withView({ ...profile, areas }, index, ({ cover: _, ...rest }) => ({ scene: 'map', ...rest, area: areas.length - 1 }))
}

/**
 * One side of the frame in pixels or of its physical size in mm. The physical size keeps the frame's shape: iOS takes
 * the ratio of the mm for the shape of a pixel, so another ratio than the pixels' squeezes the picture. A width in mm
 * sets the height to match, a height the width, and a new frame size the height in mm under the same width.
 */
export function setDisplay(profile: Profile, key: 'width' | 'height' | 'widthMm' | 'heightMm', value: number): Profile {
  const d = { ...profile.display, [key]: value }
  if (key === 'heightMm') d.widthMm = Math.round((value * d.width) / d.height)
  else d.heightMm = Math.round((d.widthMm * d.height) / d.width)
  return { ...profile, display: d }
}

/** The iPhone's display scale in percent (zoomFactor); blank leaves the key out, as Auto. */
export function setZoomFactor(profile: Profile, value: string): Profile {
  const { zoomFactor: _, ...display } = profile.display
  return { ...profile, display: value ? { ...display, zoomFactor: Number(value) } : display }
}

/** Resolve the map view that provides the URL and safe area for a Controller view.
 * Overlay-only views inherit the last preceding view with a map, as the backend does.
 */
export function mapViewIndex(profile: Profile, controllerIndex: number): number {
  if (profile.views.length === 0) return -1
  const index = Math.max(0, Math.min(Math.trunc(controllerIndex), profile.views.length - 1))
  for (let i = index; i >= 0; i--) if (profile.views[i].area !== undefined) return i
  return profile.views.findIndex((v) => v.area !== undefined)
}

/** Add a new default area and assign it to the edited map-bearing View if applicable. */
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

/** Assign an external overlay file to this view, without changing its existing inline shapes. */
export function setViewOverlay(profile: Profile, index: number, file: string): Profile {
  return withView(profile, index, (view) => {
    const { overlay: _, ...rest } = view
    return file ? { ...rest, overlay: file } : rest
  })
}

/** Copy a shared or inherited rectangle into an independently editable area. */
export function cloneViewArea(profile: Profile, index: number): Profile {
  const view = profile.views[index]
  if (view.area === undefined || !profile.areas[view.area]) return profile
  const areas = [...profile.areas, [...profile.areas[view.area]]]
  return { ...profile, areas,
    views: profile.views.map((v, i) => i === index ? { ...v, area: areas.length - 1 } : v) }
}

/** New vehicle can begin with just one map view; no decorative overlay is required. */
export function newBlankProfile(): Profile {
  return {
    name: 'New vehicle',
    display: { width: 1280, height: 480, widthMm: 240, heightMm: 90, fps: 40, features: 10, primaryInputDevice: 3 },
    areas: [[128, 48, 1024, 384]],
    initialView: 0,
    views: [{ name: 'View 0', area: 0, scene: 'map', options: {}, shapes: [] }],
  }
}

/** Drop unused legacy areas and remap the actual mapped vehicle views to dense 0..N-1 area indices. */
export function compactAreas(profile: Profile): Profile {
  const used = [...new Set(profile.views.map((v) => v.area).filter((a): a is number => a !== undefined))]
  if (!used.length || used.some((i) => i < 0 || i >= profile.areas.length)) return profile
  const mapping = new Map(used.map((old, now) => [old, now] as const))
  return {
    ...profile,
    areas: used.map((i) => [...profile.areas[i]]),
    views: profile.views.map((v) => v.area === undefined ? v : { ...v, area: mapping.get(v.area) }),
  }
}

/** Assign a pre-existing declared safe area to a view, without modifying other views. */
export function setViewArea(profile: Profile, index: number, area: number): Profile {
  if (!profile.areas[area] || profile.views[index].area === undefined) return profile
  return withView(profile, index, (v) => ({ ...v, area }))
}

/** View [index]'s safe area, in its area. */
export function setSafeArea(profile: Profile, index: number, rect: number[]): Profile {
  const area = profile.views[index].area
  if (area === undefined) return profile
  return { ...profile, areas: profile.areas.map((r, i) => (i === area ? rect : r)) }
}

/** A cluster URL option of view [index]; blank leaves it to the app. */
export function setOption(profile: Profile, index: number, key: string, value: string): Profile {
  return withView(profile, index, (view) => {
    const options = { ...(view.options ?? {}) }
    if (value) options[key] = value
    else delete options[key]
    return { ...view, options }
  })
}

export function setViewField(profile: Profile, index: number, field: 'name' | 'scene', value: string): Profile {
  return withView(profile, index, (view) => ({ ...view, [field]: value }))
}

/** A new view after the last, without the map until given it. */
export function addView(profile: Profile): Profile {
  return { ...profile, views: [...profile.views, { name: `View ${profile.views.length}`, cover: true, shapes: [] }] }
}

/** View [index] gone; a profile keeps one view at least, and one with the map. */
export function removeView(profile: Profile, index: number): Profile | null {
  const views = profile.views.filter((_, i) => i !== index)
  if (!views.some((view) => view.area !== undefined)) return null
  const initialView = Math.min(profile.initialView ?? 0, views.length - 1)
  return { ...profile, views, initialView }
}
