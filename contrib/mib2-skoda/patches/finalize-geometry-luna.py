#!/usr/bin/env python3
"""Fail-closed profile-geometry correction after UI v5; no AirPlay protocol changes."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: finalize-geometry-luna.py <pinned-chairplay-checkout>")

root = Path(sys.argv[1]).resolve()
page = root / "webui/src/pages/CarProfile.tsx"
tests = root / "webui/src/pages/CarProfile.test.tsx"

def replace_once(text: str, old: str, new: str, name: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"GEOMETRY_DRIFT {name}: expected 1 anchor, found {count}")
    return text.replace(old, new)

src = page.read_text(encoding="utf-8")
# In v5 the SizeRows below is bound to independent settings.properties, not draft.display.
# Reuse the existing validated profile edit path and keep the no-profile fallback untouched.
old = """<SizeRows settings={settings} prefix="altscreen" presets={FRAME_PRESETS} columns={3}
                    fallback={{ width: 1440, height: 540 }} showCustom after={<ActualSize sizes={altScreenWindow} window="altscreen" backend={backend} />} />"""
new = """<Row label="Size">
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
                    Profile is None and is never overwritten here. Reconnect to renegotiate display geometry.</small></Row>"""
src = replace_once(src, old, new, "v5 independent fallback SizeRows")
# TypeScript noUnusedLocals is enabled. The profile editor no longer needs SizeRows.
src = replace_once(src, "import { ActualSize, SizeRows } from './parts'",
                   "import { ActualSize } from './parts'", "remove unused SizeRows import")
src = replace_once(
    src,
    '<Group title="Display Geometry" note="Vehicle Profile is authoritative on reconnect; Size presets and Custom edit only the independent fallback" />',
    '<Group title="Display Geometry" note="The edited vehicle profile owns Size and Custom dimensions; changes need a reconnect" />',
    "v5 misleading group note"
)
if "change(setDisplay(setDisplay(draft, 'width', width), 'height', height), 'descriptor')" not in src:
    raise RuntimeError("GEOMETRY_DESCRIPTOR_SAVE_MISSING")
if old in src:
    raise RuntimeError("GEOMETRY_FALLBACK_LEAK")
# The AltScreenPage (not patched here) retains its independent fallback SizeRows.

test_src = tests.read_text(encoding="utf-8")
anchor = "  // Saved, the editor stays on the view being edited rather than going back to the first."
test_add = """  it('shows the effective vehicle geometry rather than stored fallback and saves preset to JSON', async () => {
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

"""
test_src = replace_once(test_src, anchor, test_add + anchor, "v5 test insertion")
# Write only after all guards and test anchors succeeded.
page.write_text(src, encoding="utf-8", newline="\n")
tests.write_text(test_src, encoding="utf-8", newline="\n")
print("GEOMETRY_PROFILE=PASS")
print("GEOMETRY_FALLBACK_PRESERVED=PASS")
print("GEOMETRY_TESTS_INJECTED=PASS")
