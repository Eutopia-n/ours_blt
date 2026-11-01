"""Keep public Sapphire OCR wiring, decoder and software at 128 KiB.

Only the public on-chip RAM path changes; the encrypted CPU is preserved.
Run after importing board sources, before building firmware or simulation.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OCR_BYTES = 128 * 1024
STACK_BYTES = 4096
ADDRESS_BITS = OCR_BYTES.bit_length() - 1
RAM_PATTERN = r'module BmbOnChipRam(?:_\w+)?\b[^;]*;.*?endmodule'
MARKER = f'// Project OCR extension: {OCR_BYTES // 1024} KiB (tools/expand_soc_ram.py).\n'

def ram_module(source):
    matches = list(re.finditer(RAM_PATTERN, source, re.S))
    assert len(matches) == 1, 'Expected one public OCR module'
    return matches[0]


def expand(source):
    match = ram_module(source)
    ram = match.group()
    port = re.search(r'input\s+wire\s+\[(\d+):0\]\s+io_bus_cmd_payload_fragment_address\b', ram)
    assert port, 'Missing OCR address port'
    old_bits = int(port[1]) + 1
    assert old_bits in (12, 14, 16, ADDRESS_BITS), f'Unexpected OCR width: {old_bits}'
    old_address, new_address = f'[{old_bits-1}:0]', f'[{ADDRESS_BITS-1}:0]'
    old_word, new_word = f'[{old_bits-3}:0]', f'[{ADDRESS_BITS-3}:0]'
    old_depth, new_depth = f'[0:{(1 << (old_bits-2))-1}]', f'[0:{OCR_BYTES//4-1}]'
    assert ram.count(old_address) == 1 and ram.count(old_word) == 1 and ram.count(old_depth) == 4
    ram = ram.replace(old_address, new_address).replace(old_word, new_word).replace(old_depth, new_depth)
    source = source[:match.start()] + ram + source[match.end():]
    lines = source.splitlines(keepends=True)
    changes = 0
    for n, line in enumerate(lines):
        if 'system_ramA_' in line and 'fragment_address' in line and old_address in line:
            lines[n] = line.replace(old_address, new_address)
            changes += 1
    assert changes == 4, f'Unexpected OCR wiring: {changes}'
    source = ''.join(lines)
    old_mask, new_mask = f'{(1 << old_bits)-1:08x}', f'{OCR_BYTES-1:08x}'
    old = f"((io_input_cmd_payload_fragment_address & (~ 32'h{old_mask})) == 32'hf9000000)"
    assert source.count(old) == 1, 'Unexpected OCR decoder'
    source = source.replace(old, old.replace(old_mask, new_mask))
    source = re.sub(r'^// Project OCR extension: \d+ KiB \(tools/expand_soc_ram.py\)\.\n', '', source)
    return MARKER + source


def verify_project():
    for name in ('soc.v', 'EfxSapphireSoc_modelsim.v'):
        source = (ROOT/'vendor/soc'/name).read_text(encoding='utf-8')
        assert expand(source) == source, f'{name}: run tools/expand_soc_ram.py first'
    header = (ROOT/'software/soc.h').read_text(encoding='utf-8')
    assert re.search(rf'^#define SYSTEM_RAM_A_SIZE {OCR_BYTES}$', header, re.M)
    assert re.search(rf'^#define SYSTEM_RAM_A_CTRL_SIZE 0x{OCR_BYTES:x}$', header, re.M)
    linker = (ROOT/'software/link.ld').read_text(encoding='utf-8')
    assert re.search(rf'ORIGIN = 0xf9000000, LENGTH = {OCR_BYTES//1024}K', linker)
    assert f'_stack_top - {STACK_BYTES}' in linker


def write_source(path, source):
    # Preserve imported sources' line endings so expansion remains a small diff.
    newline = b'\r\n' if b'\r\n' in path.read_bytes() else b'\n'
    path.write_bytes(source.replace('\r\n', '\n').encode('utf-8').replace(b'\n', newline))

def main():
    # Validate both layouts before writing either model.
    models = [ROOT/'vendor/soc'/name for name in ('soc.v', 'EfxSapphireSoc_modelsim.v')]
    outputs = [(path, expand(path.read_text(encoding='utf-8'))) for path in models]
    header_path, linker_path = ROOT/'software/soc.h', ROOT/'software/link.ld'
    header = header_path.read_text(encoding='utf-8')
    header, count = re.subn(r'^#define SYSTEM_RAM_A_SIZE \d+$', f'#define SYSTEM_RAM_A_SIZE {OCR_BYTES}', header, flags=re.M)
    assert count == 1
    header, count = re.subn(r'^#define SYSTEM_RAM_A_CTRL_SIZE 0x[0-9a-fA-F]+$', f'#define SYSTEM_RAM_A_CTRL_SIZE 0x{OCR_BYTES:x}', header, flags=re.M)
    assert count == 1
    linker, count = re.subn(r'ORIGIN = 0xf9000000, LENGTH = \d+K', f'ORIGIN = 0xf9000000, LENGTH = {OCR_BYTES//1024}K', linker_path.read_text(encoding='utf-8'))
    assert count == 1
    for path, source in [*outputs, (header_path, header), (linker_path, linker)]:
        write_source(path, source)
    verify_project()
    print(f'OCR: {OCR_BYTES//1024} KiB, identical synthesis/simulation ranges; {STACK_BYTES} byte stack reserve.')

if __name__ == '__main__':
    main()
