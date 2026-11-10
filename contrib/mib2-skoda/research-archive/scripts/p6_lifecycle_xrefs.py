#!/usr/bin/env python3
"""Read-only direct branch index for named P6 functions in the pinned Mach-O.

Usage: python p6_lifecycle_xrefs.py AIRPLAYSENDER. Does not resolve indirect
calls, selector dispatch, callbacks, dynamically loaded code or tail dataflow.
"""
import argparse
import bisect
import hashlib
from pathlib import Path
import capstone
import lief

EXPECTED = 'ef5daa0e0e0058448e83642a3fecfaa1746877f203b5b04fca95153416406e8d'
SELECTED = {'_carEndpoint_setupScreenStreams', '_apsession_TeardownStreams',
            '_endpoint_setupAuxiliaryScreenStream', '_endpoint_setSecondDisplayMode',
            '_carEndpoint_updateViewArea', '_carEndpoint_requestUI'}
parser = argparse.ArgumentParser()
parser.add_argument('binary', type=Path)
args = parser.parse_args()
digest = hashlib.sha256(args.binary.read_bytes()).hexdigest()
if digest != EXPECTED:
    raise SystemExit('Refused: input SHA-256 mismatch')
lief.logging.disable()
image = lief.parse(str(args.binary))
section = next(s for s in image.sections if s.name == '__text')
symbols = sorted((s.value, s.name) for s in image.symbols if s.value and s.name
                 and section.virtual_address <= s.value < section.virtual_address + section.size)
addresses = [s[0] for s in symbols]
targets = {address: name for address, name in symbols if name in SELECTED}
if set(targets.values()) != SELECTED:
    raise SystemExit('Refused: expected target symbols not found')
print(f'sha256={digest} lief={lief.__version__} capstone={capstone.__version__}')
for address, name in sorted(targets.items()):
    print(f'target {address:#x} {name}')
decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
for inst in decoder.disasm(bytes(section.content), section.virtual_address):
    if inst.mnemonic not in ('bl', 'b') or not inst.op_str.startswith('#0x'):
        continue
    try:
        target = int(inst.op_str[1:], 16)
    except ValueError:
        continue
    if target not in targets:
        continue
    i = bisect.bisect_right(addresses, inst.address) - 1
    caller = symbols[i][1] if i >= 0 else 'UNKNOWN'
    print(f'{inst.address:#x} {inst.mnemonic} {targets[target]} <- {caller}')
