"""Export the firmware's compact Chinese font to the SoC pixel-model test."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'software/font_cn.h').read_text(encoding='utf-8')
glyphs = []
for match in re.finditer(r'\{0x([0-9a-fA-F]+),\{([^}]+)\}\}', source):
    codepoint = int(match.group(1), 16)
    rows = [int(value, 16) for value in re.findall(r'0x([0-9a-fA-F]+)', match.group(2))]
    if len(rows) != 14:
        raise SystemExit(f'Expected 14 rows for U+{codepoint:04X}, found {len(rows)}')
    glyphs.append([codepoint, *rows])
if not glyphs:
    raise SystemExit('No Chinese font glyphs found')
out = ROOT / 'sim/font_cn.hex'
out.write_text(f'{len(glyphs):08x}\n' + ''.join(f'{value:08x}\n' for glyph in glyphs for value in glyph), encoding='ascii')
print(f'Exported {len(glyphs)} Chinese glyphs to {out.relative_to(ROOT)}')
