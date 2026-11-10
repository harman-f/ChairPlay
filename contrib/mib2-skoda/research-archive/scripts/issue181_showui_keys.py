#!/usr/bin/env python3
"""Resolve directly referenced CFStrings in pinned 27.2 showUI and ViewArea code."""
import hashlib
from pathlib import Path
import struct
import sys
import lief

if len(sys.argv) != 2:
    raise SystemExit('usage: python issue181_showui_keys.py <local CarKit Mach-O>')
path = Path(sys.argv[1])
digest = hashlib.sha256(path.read_bytes()).hexdigest()
if digest != 'a45a2e9f4745fefa5e64e036915311d53649c7d95edf886a2c3f571c9f32bd69':
    raise SystemExit('CarKit SHA-256 mismatch')
lief.logging.disable()
image = lief.parse(str(path))
print(f'CarKit sha256={digest}; lief={lief.__version__}')
for address, expected in ((0x1e6c573a0, 'uuid'), (0x1e6c580e0, 'url'),
                          (0x1e6c586e0, 'viewAreaSupportsFocusTransfer'),
                          (0x1e6c58700, 'drawUIOutsideSafeArea')):
    if not any(s.name == '__cfstring' and s.virtual_address <= address and
               address + 32 <= s.virtual_address + s.size for s in image.sections):
        raise SystemExit(f'CFString out of range: {address:#x}')
    isa, flags, pointer, length = struct.unpack('<QQQQ', bytes(image.get_content_from_virtual_address(address, 32)))
    if flags != 0x7c8 or length > 128:
        raise SystemExit('unexpected CFString encoding')
    literal = bytes(image.get_content_from_virtual_address(pointer, length)).decode('ascii')
    if literal != expected:
        raise SystemExit(f'unexpected literal at {address:#x}')
    print(f'{address:#x} -> {literal}; data={pointer:#x}; length={length}')
