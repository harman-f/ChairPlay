#!/usr/bin/env python3
"""Reproduce selected 27.2 ViewArea branches and CFString values; no device IO.

Usage: python p6_viewarea_payload_probe.py AIRPLAYSENDER CARKIT
Only the selected functions/branches are covered; indirect recipients are not.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import capstone
import lief

SENDER_SHA = 'ef5daa0e0e0058448e83642a3fecfaa1746877f203b5b04fca95153416406e8d'
CARKIT_SHA = 'a45a2e9f4745fefa5e64e036915311d53649c7d95edf886a2c3f571c9f32bd69'
CASES = [
    ('AirPlaySender', 0x26e264a30, 'uuid'),
    ('AirPlaySender', 0x26e26d8f0, 'viewAreaIndex'),
    ('AirPlaySender', 0x26e266bb0, 'adjacentViewAreas'),
    ('AirPlaySender', 0x26e26d910, 'animationDurationMillis'),
    ('CarKit', 0x1e6c573a0, 'uuid'),
    ('CarKit', 0x1e6c57fa0, 'viewAreaIndex'),
    ('CarKit', 0x1e6c57ba0, 'viewArea'),
    ('CarKit', 0x1e6c57fc0, 'animationDurationMillis'),
    ('CarKit', 0x1e6c57fe0, 'adjacentViewAreas'),
]
RANGES = [
    ('AirPlaySender', 0x255289e34, 0x255289eb4),
    ('AirPlaySender', 0x255289f18, 0x255289fb4),
    ('AirPlaySender', 0x25528af68, 0x25528b010),
    ('AirPlaySender', 0x2551535b4, 0x255153620),
    ('AirPlaySender', 0x2552e3950, 0x2552e39a4),
    ('AirPlaySender', 0x2552e38e0, 0x2552e3918),
    ('CarKit', 0x1c395a990, 0x1c395aa30),
    ('CarKit', 0x1c393fa10, 0x1c393faa0),
]
p = argparse.ArgumentParser()
p.add_argument('sender', type=Path)
p.add_argument('carkit', type=Path)
a = p.parse_args()
for path, expected in ((a.sender, SENDER_SHA), (a.carkit, CARKIT_SHA)):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit('Refused: input SHA-256 mismatch')
lief.logging.disable()
images = {'AirPlaySender': lief.parse(str(a.sender)), 'CarKit': lief.parse(str(a.carkit))}
print(f'lief={lief.__version__} capstone={capstone.__version__}')
print(f'AirPlaySender sha256={SENDER_SHA}')
print(f'CarKit sha256={CARKIT_SHA}')
for name, address, expected in CASES:
    image = images[name]
    cf = next((s for s in image.sections if s.name == '__cfstring'
               and s.virtual_address <= address and address + 32 <= s.virtual_address + s.size), None)
    if cf is None:
        raise SystemExit(f'Refused: {name} CFString is out of bounds')
    raw = bytes(image.get_content_from_virtual_address(address, 32))
    isa, flags, string_address, length = struct.unpack('<QQQQ', raw)
    if flags != 0x7c8 or length > 128:
        raise SystemExit(f'Refused: unexpected CFString encoding at {address:#x}')
    data = bytes(image.get_content_from_virtual_address(string_address, length))
    if data.decode('ascii') != expected:
        raise SystemExit(f'Refused: unexpected literal at {address:#x}')
    print(f'{name} CFString {address:#x} data={string_address:#x} len={length}: {expected}')
decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
for name, start, end in RANGES:
    image = images[name]
    raw = bytes(image.get_content_from_virtual_address(start, end - start))
    if len(raw) != end - start:
        raise SystemExit(f'Refused: truncated instruction range {start:#x}')
    print(f'\n{name} {start:#x}..{end:#x}:')
    for i in decoder.disasm(raw, start):
        print(f'{i.address:#x} {i.mnemonic} {i.op_str}'.rstrip())
print('\nOnly listed keys and ranges are resolved; no exhaustive observer coverage is implied.')
