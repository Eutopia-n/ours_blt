"""Import the UI glyph subset from Fusion Pixel Font's 12px zh_Hans BDF."""
from pathlib import Path
import argparse
import re

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--bdf', required=True, type=Path, help='Fusion Pixel 12px zh_Hans BDF file')
args = parser.parse_args()


def parse_bdf(path, wanted):
    lines = path.read_text(encoding='ascii').splitlines()
    ascent = next(int(line.split()[1]) for line in lines if line.startswith('FONT_ASCENT '))
    glyphs = {}
    index = 0
    while index < len(lines):
        if not lines[index].startswith('STARTCHAR '):
            index += 1
            continue
        index += 1
        codepoint = None
        advance = 0
        box = None
        bitmap = []
        while index < len(lines) and lines[index] != 'ENDCHAR':
            line = lines[index]
            if line.startswith('ENCODING '):
                values = line.split()
                codepoint = int(values[-1])
            elif line.startswith('DWIDTH '):
                advance = int(line.split()[1])
            elif line.startswith('BBX '):
                box = tuple(map(int, line.split()[1:]))
            elif line == 'BITMAP':
                index += 1
                if box is None:
                    raise SystemExit('BDF BITMAP appears before BBX')
                bitmap = lines[index:index + box[1]]
                index += box[1] - 1
            index += 1
        if codepoint in wanted and box is not None:
            width, height, x_offset, y_offset = box
            if len(bitmap) != height:
                raise SystemExit(f'Invalid bitmap row count for U+{codepoint:04X}')
            rows = [0] * 14
            x_origin = 1 + (12 - advance) // 2 + x_offset
            y_origin = 1 + ascent - (y_offset + height)
            bytes_per_row = (width + 7) // 8
            for y, encoded in enumerate(bitmap):
                bits = int(encoded, 16) if encoded else 0
                bits >>= bytes_per_row * 8 - width
                for x in range(width):
                    if bits & (1 << (width - 1 - x)):
                        px, py = x_origin + x, y_origin + y
                        if not (0 <= px < 14 and 0 <= py < 14):
                            raise SystemExit(f'Glyph U+{codepoint:04X} exceeds 12px cell')
                        rows[py] |= 1 << px
            glyphs[codepoint] = rows
        index += 1
    return glyphs


sources = [ROOT / 'software/main.c', ROOT / 'software/game_view.h',
           ROOT / 'software/survivor_game.c']
needed = set()
for path in sources:
    source = path.read_text(encoding='utf-8')
    for literal in re.findall(r'"((?:[^"\\]|\\.)*)"', source):
        needed.update(ord(char) for char in literal if ord(char) > 127)

font = parse_bdf(args.bdf, needed)
missing = sorted(needed - font.keys())
if missing:
    labels = ', '.join(f'U+{codepoint:04X}' for codepoint in missing)
    raise SystemExit(f'Fusion Pixel font is missing required glyphs: {labels}')

header = [
    '#ifndef FONT_CN_H', '#define FONT_CN_H', '#include <stdint.h>',
    'typedef struct { uint32_t codepoint; uint16_t rows[14]; } FontCnGlyph;',
    'static uint32_t font_cn_utf8_next(const char **text) {',
    '    const uint8_t *p=(const uint8_t *)(*text); uint32_t c=p[0];',
    '    if(!c) return 0;',
    '    if(c<0x80u) { *text=(const char *)(p+1); return c; }',
    '    if((c&0xe0u)==0xc0u && (p[1]&0xc0u)==0x80u) { *text=(const char *)(p+2); return ((c&31u)<<6)|(p[1]&63u); }',
    '    if((c&0xf0u)==0xe0u && (p[1]&0xc0u)==0x80u && (p[2]&0xc0u)==0x80u) { *text=(const char *)(p+3); return ((c&15u)<<12)|((p[1]&63u)<<6)|(p[2]&63u); }',
    '    *text=(const char *)(p+1); return 0xfffdu;',
    '}',
    '/* Fusion Pixel 12px zh_Hans bitmaps centered in the existing 14x14 cells. */',
    'static const FontCnGlyph font_cn_glyphs[] = {'
]
for codepoint in sorted(needed):
    rows = ','.join(f'0x{value:04x}' for value in font[codepoint])
    header.append(f'    {{0x{codepoint:x},{{{rows}}}}}, // {chr(codepoint)}')
header.extend([
    '};',
    'static const uint16_t *font_cn_find(uint32_t codepoint) {',
    '    for(uint32_t i=0;i<sizeof(font_cn_glyphs)/sizeof(font_cn_glyphs[0]);++i)',
    '        if(font_cn_glyphs[i].codepoint==codepoint) return font_cn_glyphs[i].rows;',
    '    return 0;',
    '}',
    '#endif',
    ''
])
(ROOT / 'software/font_cn.h').write_text('\n'.join(header), encoding='utf-8', newline='\n')
print(f'Imported {len(needed)} Fusion Pixel zh_Hans glyphs into software/font_cn.h')
