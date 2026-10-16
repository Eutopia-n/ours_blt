"""Extend only the public Sapphire OCR datapath/decoder to 64 KiB.

The vendor CPU implementation is unchanged. Apply identically to synthesis and
ModelSim netlists after importing the board files; reject unexpected layouts.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OCR_BYTES = 65536

def expand(source):
    marker = '// Project OCR extension: 64 KiB (tools/expand_soc_ram.py).\n'
    if marker in source:
        return source
    source = source.replace('// Project OCR extension: 16 KiB (tools/expand_soc_ram.py).\n', '')
    old_bits = 14 if "32'h00003fff" in source else 12
    old_address = f'[{old_bits-1}:0]'
    old_word = f'[{old_bits-3}:0]'
    old_depth = f'[0:{(1 << (old_bits-2))-1}]'
    lines = source.splitlines(keepends=True)
    changes = 0
    for n, line in enumerate(lines):
        if 'system_ramA_' in line and 'fragment_address' in line and old_address in line:
            lines[n] = line.replace(old_address, '[15:0]')
            changes += 1
    assert changes == 4, f'Unexpected OCR wiring: {changes}'
    source = ''.join(lines)
    pattern = r'module BmbOnChipRam\b[^;]*;.*?endmodule|module BmbOnChipRam_\w+\b[^;]*;.*?endmodule'
    matches = list(re.finditer(pattern, source, re.S))
    assert len(matches) == 1, 'Expected one OCR module'
    match = matches[0]
    ram = match.group()
    assert ram.count(old_address) == 1 and ram.count(old_word) == 1 and ram.count(old_depth) == 4
    ram = ram.replace(old_address, '[15:0]').replace(old_word, '[13:0]').replace(old_depth, '[0:16383]')
    source = source[:match.start()] + ram + source[match.end():]
    old_mask = '00003fff' if old_bits == 14 else '00000fff'
    old = f"((io_input_cmd_payload_fragment_address & (~ 32'h{old_mask})) == 32'hf9000000)"
    assert source.count(old) == 1, 'Unexpected OCR decoder'
    return marker + source.replace(old, old.replace(old_mask, '0000ffff'))

def main():
    for name in ['soc.v', 'EfxSapphireSoc_modelsim.v']:
        path = ROOT/'vendor/soc'/name
        path.write_text(expand(path.read_text(encoding='utf-8')), encoding='utf-8')
    path = ROOT/'software/soc.h'
    source = re.sub(r'#define SYSTEM_RAM_A_SIZE \d+', f'#define SYSTEM_RAM_A_SIZE {OCR_BYTES}', path.read_text())
    source = re.sub(r'#define SYSTEM_RAM_A_CTRL_SIZE 0x[0-9a-fA-F]+', '#define SYSTEM_RAM_A_CTRL_SIZE 0x10000', source)
    path.write_text(source)
    print('OCR: 64 KiB, identical synthesis and simulation address ranges.')

if __name__ == '__main__':
    main()
