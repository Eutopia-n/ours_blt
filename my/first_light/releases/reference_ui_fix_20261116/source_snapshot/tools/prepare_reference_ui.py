"""Lossless RGB565 resources taken from the user's local HTML, never redrawn.

Shared base plus transparent deltas keeps all nine native menu layouts small.
Only menu textures occupy the existing 1 MiB DDR pool; the game has no scenery.
"""
from pathlib import Path
import ast, base64, hashlib, io, json, math, struct
from itertools import groupby
from PIL import Image,ImageDraw
from book_opening_animation import _clasp, _page_texture

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/ui/magic_book_v5/runtime/reference'
OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'tools/prepare_magic_book_ui_v5.py'
nodes=[]
for node in ast.parse(source.read_text(encoding='utf-8')).body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MENU' for t in node.targets):break
    nodes.append(node)
art={'__file__':str(source)}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),art)
codec={}
nodes=[n for n in ast.parse((ROOT/'tools/prepare_book_menu.py').read_text(encoding='utf-8')).body
       if isinstance(n,ast.FunctionDef) and n.name in ('lz4','un_lz4')]
codec['struct']=struct
exec(compile(ast.Module(body=nodes,type_ignores=[]),'codec','exec'),codec)
s=(ROOT/'assets/ui/magic_book_v5/魔法书交互预览.html').read_text(encoding='utf-8')
pages,_=json.JSONDecoder().raw_decode(s[s.index('const pages=')+12:])
pages={k:Image.open(io.BytesIO(base64.b64decode(v.split(',')[1]))).convert('RGBA') for k,v in pages.items()}
def raw(im):
    return struct.pack('<'+'H'*(im.width*im.height),*[0 if a<128 else art['to565']((r,g,b))
        for r,g,b,a in im.convert('RGBA').getdata()])
def opaque_raw(im):
    return struct.pack('<'+'H'*(im.width*im.height),*[((r>>3)<<11)|((g>>2)<<5)|(b>>3) for r,g,b in im.convert('RGB').getdata()])
def rle(data):
    values=struct.unpack('<'+'H'*(len(data)//2),data)
    palette=sorted(set(values));bits=max(1,(len(palette)-1).bit_length());assert bits<=10
    index={v:i for i,v in enumerate(palette)};maximum=(1<<(16-bits))-1
    out=bytearray()
    for v,g in groupby(values):
        n=sum(1 for _ in g)
        for offset in range(0,n,maximum):out.extend(struct.pack('<H',(min(maximum,n-offset)<<bits)|index[v]))
    return bytes(out),palette,bits
stream=bytearray();desc=[]
def add(name,data,w,h,base=0,delta=False):
    packed,palette,bits=rle(data); compressed=codec['lz4'](packed)
    assert codec['un_lz4'](compressed)==packed
    d=dict(name=name,offset=len(stream),compressed=len(compressed),rle=len(packed),bytes=len(data),
           w=w,h=h,base=base,delta=delta,palette=palette,bits=bits,sha256=hashlib.sha256(data).hexdigest())
    stream.extend(compressed);desc.append(d);(OUT/(name+'.rgb565')).write_bytes(data)
    return len(desc)-1
half=lambda im:im.resize((im.width//2,im.height//2),Image.Resampling.NEAREST)
front=art['cover_art'](False,False,False).crop((174,32,452,428))
book=art['open_base'](False)
leaf=half(_page_texture(book,'right'))
unlatched=half(art['cover_art'](True,False,True))
cover=half(art['cover_art'](False,False,True).crop((170,32,480,448)))
images=[front,half(book),leaf,cover]
texture_palette=sorted(set(v for im in images for v in struct.unpack('<'+'H'*(im.width*im.height),raw(im))))
assert len(texture_palette)<=64
front_palette=texture_palette
for name,im,address in zip(('front','blank','leaf','cover'),images,(0x8000,0x23000,0x36000,0x3f000)):
    data=raw(im);values=struct.unpack('<'+'H'*(len(data)//2),data)
    indices=bytes(texture_palette.index(v) for v in values)
    if len(indices)&1:indices+=bytes(1)
    add(name,indices,im.width,im.height,address)
desk=half(art['desk']());colors=sorted(set(struct.unpack('<'+'H'*76800,raw(desk))));assert len(colors)<=16
lookup={v:i for i,v in enumerate(colors)};v=struct.unpack('<'+'H'*76800,raw(desk))
assert len(colors)<=4
packed=bytes(sum(lookup[v[i+j]]<<(j*2) for j in range(4)) for i in range(0,len(v),4))
packed=b''.join(packed[y*80:(y+1)*80]+bytes(48) for y in range(240))
add('desk',packed,128,240,0x48800)
add('clasp',raw(_clasp()),54,40,0x50000)
for i,(name,im) in enumerate(art['ICONS'].items()):add('icon_'+name,raw(im),32,32,0x51200+i*2048)
add('cursor',raw(art['CURSOR']),art['CURSOR'].width,art['CURSOR'].height,0x55a00)
orn=Image.new('RGBA',(640,480));art['ornament'](orn)
add('ornament',raw(half(orn.crop((72,158,262,340)))),95,91,0x56000)

hero=Image.open(ROOT/'assets/player/walk_32.png').convert('RGBA').crop((0,0,32,32))
add('hero',raw(hero),32,32,0x5a400)
add('hero_home',opaque_raw(pages['home_0'].crop((118,192,214,288))),96,96,0x5b000)
add('hero_chapter',opaque_raw(pages['basic_0'].crop((214,280,278,344))),64,64,0x5b000)
add('hero_game',opaque_raw(pages['game_ready'].crop((118,192,214,288))),96,96,0x5b000)
add('cover_clasp',raw(pages['cover'].crop((418,222,472,262))),54,40,0x50000)
# Game decoration uses the same transient space as the book spread/cover.
node=next(n for n in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='game_illustration')
exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),art)
orn=Image.new('RGBA',(640,480));saved=art['hero'];art['hero']=lambda *a,**k:None
art['game_illustration'](orn);art['hero']=saved
add('game_ornament',raw(half(orn.crop((66,144,266,340)))),100,98,0x23000)
stream.extend(bytes((-len(stream))%4))
(OUT/'ui_stream.bin').write_bytes(stream)
(OUT/'ui_stream.hex').write_text(''.join(f'{v:08x}\n' for v in struct.unpack('<'+'I'*(len(stream)//4),stream)),encoding='ascii')
header=['/* Generated by prepare_reference_ui.py from the local HTML. */','#ifndef REFERENCE_UI_ASSETS_H',
 '#define REFERENCE_UI_ASSETS_H','#define BOOK_CACHE_BASE (ASSET_BASE+0x60000u)',
 '#define BOOK_CACHE_BYTES 614400u','#define BOOK_COMMAND_BASE (ASSET_BASE+0x4000u)',
 '#define BOOK_SCRATCH_BASE (ASSET_BASE+0x60000u)',
 'typedef struct {uint32_t offset,compressed,rle,bytes,base;uint16_t w,h,bits,palette;} BookResource;',
 'enum {' ]
header+=['BOOK_'+d['name'].upper()+',' for d in desc];header+=['BOOK_RESOURCE_COUNT};',
 'static const BookResource book_resources[]={']
palettes=[]
for d in desc:
    d['palette_offset']=len(palettes);palettes+=d['palette']
header+=['{'+','.join(str(d[k])+'u' for k in ('offset','compressed','rle','bytes','base','w','h','bits','palette_offset'))+'},' for d in desc]
corner=Image.new('1',(254,74));d=ImageDraw.Draw(corner)
for xx,sx in ((6,1),(247,-1)):
    d.line((xx,16,xx,6,xx+sx*12,6),fill=1,width=2)
    d.line((xx,57,xx,67,xx+sx*12,67),fill=1,width=2)
corner_values=[]
for x,y in ((5,5),(234,5),(5,55),(234,55)):
    corner_values += [sum(corner.getpixel((x+col,y+row))<<col for col in range(15)) for row in range(15)]
header+=['};','static const uint16_t book_corner_masks[]={'+','.join(hex(c) for c in corner_values)+'};']
header+=['static const uint16_t book_front_palette[]={'+','.join(hex(c) for c in front_palette)+'};','static const uint16_t book_resource_palette[]={'+','.join(hex(c) for c in palettes)+'};','static const uint16_t book_desk_palette[16]={'+','.join(hex(c) for c in colors+[0]*(16-len(colors)))+'};',
 'static const int16_t book_sine[1025]={'+','.join(str(round(math.sin(n*math.pi/512)*16384)) for n in range(1025))+'};','#endif','']
(ROOT/'software/reference_ui_assets.h').write_text('\n'.join(header),encoding='utf-8')
(ROOT/'rtl/ui_front_palette.vh').write_text(''.join(f'6\'d{i}:front_color=16\'h{c:04x};\n' for i,c in enumerate(front_palette)),encoding='ascii')
rom=['module ui_asset_rom(input wire clk,input wire [12:0] address,output reg [31:0] data);','reg [3:0] bank;always @(posedge clk)bank<=address[12:9];']
assert len(stream)<=32768, 'UI ROM exceeds the 13-bit APB word address'
assert all(d['base']+d['bytes']<=0x60000 for d in desc), 'UI texture overlaps the native page cache'
words=struct.unpack('<'+'I'*(len(stream)//4),stream)
for i in range((len(words)+511)//512):
    values=list(words[i*512:(i+1)*512]);values+=([0]*(512-len(values)))
    path=f'assets/ui/magic_book_v5/runtime/reference/rom_{i:02}.hex'
    (ROOT/path).write_text(''.join(f'{v:08x}\n' for v in values),encoding='ascii')
    rom += [f'reg [31:0] rom{i}[0:511],q{i};',f'initial $readmemh("{path}",rom{i});',f'always @(posedge clk)q{i}<=rom{i}[address[8:0]];']
rom+=['always @* case(bank)']+[f"4'd{i}:data=q{i};" for i in range((len(words)+511)//512)]+['default:data=0;endcase','endmodule','']
(ROOT/'rtl/ui_asset_rom.v').write_text('\n'.join(rom),encoding='ascii')
(ROOT/'rtl/ui_rom_size.vh').write_text(f'`define UI_ROM_WORDS {len(stream)//4}\n',encoding='ascii')
manifest=dict(reference_html_sha256=hashlib.sha256(s.encode()).hexdigest(),rom_bytes=len(stream),
 resources=desc,desk_palette=colors,resource_pool_bytes=1048576,game_background_textures=False,board_tested=False)
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(rom_bytes=len(stream),resources=[(d['name'],d['compressed'],d['rle']) for d in desc])))
