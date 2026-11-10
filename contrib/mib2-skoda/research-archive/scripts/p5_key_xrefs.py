#!/usr/bin/env python3
"""Find bounded ADRP references in pinned AirPlaySender; usage: script BINARY.

Heuristic only: register clobbers, computed/indirect references are not resolved.
"""
import argparse
import bisect
import hashlib
from pathlib import Path
import re
import capstone
import lief

EXPECTED = 'ef5daa0e0e0058448e83642a3fecfaa1746877f203b5b04fca95153416406e8d'
TARGETS = {0x269486888, 0x26812d908}
p = argparse.ArgumentParser()
p.add_argument('binary', type=Path)
args = p.parse_args()
digest = hashlib.sha256(args.binary.read_bytes()).hexdigest()
if digest != EXPECTED:
    raise SystemExit('Refused: wrong input SHA-256')
lief.logging.disable()
image = lief.parse(str(args.binary))
section = next(s for s in image.sections if s.name == '__text')
decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
instructions = list(decoder.disasm(bytes(section.content), section.virtual_address))
symbols = sorted((s.value, s.name) for s in image.symbols if s.value and s.name
                 and section.virtual_address <= s.value < section.virtual_address + section.size)
addresses = [s[0] for s in symbols]
print(f'sha256={digest} lief={lief.__version__} capstone={capstone.__version__}')
for i, inst in enumerate(instructions):
    if inst.mnemonic != 'adrp':
        continue
    match = re.fullmatch(r'(x\d+), #0x([0-9a-f]+)', inst.op_str)
    if not match:
        continue
    register, page = match.group(1), int(match.group(2), 16)
    if page not in {target & ~0xfff for target in TARGETS}:
        continue
    for candidate in instructions[i + 1:i + 7]:
        use = (re.search(r'\[' + register + r', #(0x[0-9a-f]+|\d+)\]', candidate.op_str)
               or re.fullmatch(r'x\d+, ' + register + r', #(0x[0-9a-f]+|\d+)', candidate.op_str))
        if use and page + int(use.group(1), 0) in TARGETS:
            index = bisect.bisect_right(addresses, inst.address) - 1
            symbol = symbols[index][1] if index >= 0 else 'UNKNOWN'
            print(f'{page + int(use.group(1), 0):#x} {inst.address:#x} {symbol} ; '
                  f'{candidate.mnemonic} {candidate.op_str}')
