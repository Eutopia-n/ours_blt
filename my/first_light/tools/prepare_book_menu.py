"""Export compact runtime layers from the approved magic-book pixel artwork.

Only the art definitions before MENU are evaluated; preview/animation generation
is not run. LZ4 blocks decode directly to the existing unused DDR resource range.
"""
from pathlib import Path
import ast
import hashlib
import json
import math
import struct
from itertools import groupby
from PIL import Image
from book_opening_animation import _clasp

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'assets/ui/magic_book_v5/runtime'
OUT.mkdir(exist_ok=True)
source = ROOT/'tools/prepare_magic_book_ui_v5.py'
nodes = []
for node in ast.parse(source.read_text(encoding='utf-8')).body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'MENU' for t in node.targets):
        break
    nodes.append(node)
art = {'__file__': str(source)}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), art)

def lz4(data):
    data = bytes(data)
    out = bytearray(); seen = {}; anchor = at = 0
    def extra(n):
        while n >= 255: out.append(255); n -= 255
        out.append(n)
    while at+12 <= len(data):
        key = data[at:at+4]; old = seen.get(key, -65536); seen[key] = at
        if at-old > 65535 or data[old:old+4] != key:
            at += 1; continue
        end = at+4
        while end < len(data)-5 and data[end] == data[old+end-at]: end += 1
        literal, length = at-anchor, end-at-4
        out.append((min(literal, 15)<<4)|min(length, 15))
        if literal >= 15: extra(literal-15)
        out.extend(data[anchor:at]); out.extend(struct.pack('<H', at-old))
        if length >= 15: extra(length-15)
        for n in range(at+1, end): seen[data[n:n+4]] = n
        anchor = at = end
    literal = len(data)-anchor
    out.append(min(literal, 15)<<4)
    if literal >= 15: extra(literal-15)
    out.extend(data[anchor:])
    return bytes(out)

def un_lz4(data):
    out = bytearray(); at = 0
    while at < len(data):
        token = data[at]; at += 1; literal = token>>4
        if literal == 15:
            while True:
                n = data[at]; at += 1; literal += n
                if n != 255: break
        out.extend(data[at:at+literal]); at += literal
        if at == len(data): break
        offset = int.from_bytes(data[at:at+2], 'little'); at += 2
        length = (token&15)+4
        if (token&15) == 15:
            while True:
                n = data[at]; at += 1; length += n
                if n != 255: break
        for _ in range(length): out.append(out[-offset])
    return bytes(out)

half = lambda im: im.resize((im.width//2, im.height//2), Image.Resampling.NEAREST)
layers = [('desk', half(art['desk']())), ('spread', half(art['open_base'](False))),
          ('cover', half(art['cover_art'](False).crop((170,32,480,448)))),
          ('front', half(art['cover_art'](False,False,False).crop((174,32,452,428)))),
          ('clasp', half(_clasp()))]
ornament = Image.new('RGBA', (640, 480)); art['ornament'](ornament)
box = ornament.getbbox(); box = (box[0]//2*2, box[1]//2*2, (box[2]+1)//2*2, (box[3]+1)//2*2)
layers.append(('ornament', half(ornament.crop(box))))
for name, im in art['ICONS'].items(): layers.append(('icon_'+name, im))
layers.append(('cursor', art['CURSOR']))
# Keep animation textures/icons before the temporary snapshot/cache. Large
# static layers are needed only while composing a new menu selection.
by_name = dict(layers)
layers = [(name, by_name[name]) for name in
          ['front','clasp','ornament']+[n for n, _ in layers if n.startswith('icon_')]+['cursor','cover']]
layers += [('desk_runs', Image.new('RGBA',(2048,4))),
           ('desk', by_name['desk']), ('spread', by_name['spread'])]
raw = bytearray(); descriptors = []
for name, im in layers:
    rgba=im.convert('RGBA')
    values = [0 if a < 128 else art['to565']((r,g,b)) for r,g,b,a in
              (rgba.get_flattened_data() if hasattr(rgba,'get_flattened_data') else rgba.getdata())]
    data = struct.pack('<'+'H'*len(values), *values)
    descriptors.append({'name': name, 'offset': len(raw), 'w': im.width, 'h': im.height,
                        'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    raw.extend(data); im.save(OUT/(name+'.png'))
values = struct.unpack('<'+'H'*(len(raw)//2), raw)
palette = sorted(set(values)); assert len(palette) <= 64
lookup = {v:i for i,v in enumerate(palette)}; tokens = []
for value, group in groupby(values):
    length = sum(1 for _ in group)
    tokens.extend((min(1023,length-n)<<6)|lookup[value] for n in range(0,length,1023))
rle = struct.pack('<'+'H'*len(tokens), *tokens)
compressed = lz4(rle); assert un_lz4(compressed) == rle
snapshot_offset, cache_offset = 0x41000, 0x66A00
assert next(d['offset'] for d in descriptors if d['name']=='desk')+0x16000 <= snapshot_offset
assert snapshot_offset+153600 <= cache_offset
assert cache_offset+614400 <= 0x100000
(OUT/'book_layers.rgb565').write_bytes(raw)
(OUT/'book_layers.lz4').write_bytes(compressed)
def array(ctype, name, values, fmt):
    return f'static const {ctype} {name}[{len(values)}] = {{\n'+'\n'.join(
        '    '+','.join(fmt(v) for v in values[n:n+16])+',' for n in range(0,len(values),16))+'\n};'
header = ['/* Generated by tools/prepare_book_menu.py. */', '#ifndef BOOK_MENU_ASSETS_H',
          '#define BOOK_MENU_ASSETS_H', '#include <stdint.h>', '#define BOOK_ASSET_BASE (ASSET_BASE+0x16000u)',
          f'#define BOOK_ASSET_BYTES {len(raw)}u', f'#define BOOK_COMPRESSED_BYTES {len(compressed)}u',
          f'#define BOOK_RLE_BYTES {len(rle)}u', '#define BOOK_SNAPSHOT_BASE (ASSET_BASE+0x41000u)',
          '#define BOOK_SNAPSHOT_BYTES 153600u',
          '#define BOOK_CACHE_BASE (ASSET_BASE+0x66A00u)', '#define BOOK_CACHE_BYTES 614400u',
          f'#define BOOK_ORNAMENT_X {box[0]}u', f'#define BOOK_ORNAMENT_Y {box[1]}u',
          'typedef struct { uint32_t offset; uint16_t w,h; } BookLayer;', 'enum {']
header.extend('    BOOK_'+d['name'].upper()+',' for d in descriptors)
header.extend(['    BOOK_LAYER_COUNT', '};', 'static const BookLayer book_layers[BOOK_LAYER_COUNT] = {'])
header.extend('    {'+f'{d["offset"]}u,{d["w"]}u,{d["h"]}u'+'},' for d in descriptors)
header.extend(['};', array('uint16_t', 'book_palette', palette, lambda v: f'0x{v:04x}'),
               array('uint8_t', 'book_lz4', compressed, lambda v: f'0x{v:02x}'),
               array('int16_t', 'book_sine', [round(math.sin(n*math.pi/128)*1024) for n in range(257)], str), '#endif', ''])
(ROOT/'software/book_menu_assets.h').write_text('\n'.join(header), encoding='utf-8')
manifest = {'runtime_integrated': True, 'expanded_ddr_bytes': len(raw), 'compressed_bytes': len(compressed),
            'snapshot_bytes':153600, 'cache_bytes':614400, 'total_ddr_bytes':cache_offset+614400-0x16000,
            'snapshot_base':'0x01241000', 'cache_base':'0x01266A00',
            'shared_with_demo_images':True, 'resource_pool_bytes':1048576, 'rle_bytes':len(rle),
            'ddr_base': '0x01216000', 'layers': descriptors, 'ornament_origin': box[:2],
            'animation': 'One cached target page, sparse desk runs and scanline projection; vblank pacing; demo images reload after shared cache use',
            'board_tested': False}
(OUT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
(ROOT/'sim/book_asset_size.vh').write_text(
    '// Generated by tools/prepare_book_menu.py.\n`define BOOK_ASSET_BASE 32\'h01216000\n'+
    f'`define BOOK_ASSET_END 32\'h{0x01200000+cache_offset+614400:08x}\n',encoding='ascii')
print(json.dumps({'layers': len(layers), 'ddr_bytes': len(raw), 'compressed_bytes': len(compressed)}, indent=2))
