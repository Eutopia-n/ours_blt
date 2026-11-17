"""Build a fantasy menu kit around the project's original blue-hooded player.

Uses Pillow only. Does not modify firmware, RTL or the existing font files.
Art is authored on an integer pixel grid; no antialiasing or AI image service.
"""
from pathlib import Path
import hashlib
import json
import re
import struct
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/ui/menu_pixel_v2'
THEME = json.loads((OUT / 'source/theme.json').read_text(encoding='utf-8'))
for directory in ('png', 'rgb565', 'previews', 'embedded'):
    (OUT / directory).mkdir(parents=True, exist_ok=True)


def rgb565(rgb):
    """Encode one opaque RGB pixel in the framebuffer's native format."""
    r, g, b = rgb[:3]
    value = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    return value if value else 1


def expand(value):
    """Show the exact RGB565 color, including its quantization."""
    return ((value >> 11) * 255 // 31,
            ((value >> 5) & 63) * 255 // 63,
            (value & 31) * 255 // 31)


COLORS = {name: (*expand(rgb565(tuple(bytes.fromhex(value[1:])))), 255)
          for name, value in THEME['palette'].items()}
TRANSPARENT = (0, 0, 0, 0)
ASSETS = []


def color(name):
    return COLORS[name]


def sprite(name, logical_size, painter, margin=0, role='decoration'):
    """Draw a source sprite and enlarge every authored pixel to 2x2."""
    image = Image.new('RGBA', logical_size, TRANSPARENT)
    painter(ImageDraw.Draw(image), image)
    image = image.resize((logical_size[0]*2, logical_size[1]*2), Image.Resampling.NEAREST)
    ASSETS.append({'name': name, 'image': image, 'nine_slice': margin, 'role': role})
    return image


def panel_art(state, size=12):
    """Draw parchment cards, stone headers and blue cloth keycaps."""
    def draw(d, image):
        n = size
        def cut(x0, y0, x1, y1, c, k=2):
            d.polygon([(x0+k,y0),(x1-k,y0),(x1,y0+k),(x1,y1-k),
                       (x1-k,y1),(x0+k,y1),(x0,y1-k),(x0,y0+k)], fill=color(c))
        cut(0,0,n-1,n-1,'ink')
        edge = {'normal':'edge','selected':'gold','pressed':'gold_dark',
                'disabled':'edge','header':'steel','cloth':'cyan_dark'}[state]
        fill = {'selected':'focus_fill','pressed':'focus_inner','disabled':'deep',
                'header':'deep','cloth':'blue_dark'}.get(state,'panel')
        cut(0,0,n-2,n-2,edge)
        cut(1,1,n-3,n-3,fill,1)
        light = 'steel' if state in ('header','disabled') else 'cyan' if state=='cloth' else 'paper'
        d.line((3,1,n-6,1), fill=color(light))
        d.line((1,3,1,n-6), fill=color(light))
        d.line((3,n-3,n-5,n-3), fill=color('ink'))
        d.line((n-3,3,n-3,n-5), fill=color('ink'))
        if state=='pressed':
            d.line((2,2,n-5,2),fill=color('deep'))
        if state=='header':
            d.line((2,4,3,4,3,6),fill=color('tile_mark'))
            d.line((n-4,n-7,n-5,n-7,n-5,n-5),fill=color('background'))
    return draw


def background_art(grid):
    def draw(d, image):
        d.rectangle((0,0,15,15),fill=color('background'))
        d.line((0,15,15,15),fill=color('deep'))
        d.line((0,14,15,14),fill=color('tile_mark'))
        seam = 3 if grid else 11
        d.line((seam,0,seam,13),fill=color('deep'))
        d.line((seam+1,1,seam+1,12),fill=color('tile_mark'))
        d.line((seam+4,3,seam+6,3),fill=color('tile_mark'))
    return draw


def icon_art(kind):
    """Draw quest-book and spell-item icons that fit the existing adventurer."""
    def draw(d, image):
        def box(x0,y0,x1,y1,c):
            d.rectangle((x0,y0,x1,y1),fill=color(c))
        def line(points,c,width=1):
            d.line(points,fill=color(c),width=width)
        def diamond(cx,cy,r,c):
            d.polygon([(cx,cy-r),(cx+r,cy),(cx,cy+r),(cx-r,cy)],fill=color(c))
        def spark(x,y,c='gold_light'):
            line((x-1,y,x+1,y),c);line((x,y-1,x,y+1),c)
        if kind=='basic':
            box(2,2,13,14,'ink');box(1,1,12,12,'edge');box(2,2,11,11,'paper')
            box(2,2,4,11,'blue_dark');box(3,2,3,11,'blue')
            box(5,2,11,11,'panel_light');line((5,3,10,3),'white')
            box(6,5,9,8,'gold_dark');box(7,5,9,7,'gold');line((6,10,9,10),'edge')
            box(10,10,11,13,'blue_dark')
        elif kind=='advanced':
            box(1,3,13,14,'ink');box(1,2,12,12,'blue_dark');box(2,3,11,11,'blue')
            box(2,3,3,11,'cyan_dark');box(11,3,12,11,'edge')
            diamond(7,7,4,'cyan_dark');diamond(7,6,3,'ice');diamond(7,6,1,'white')
            line((4,10,9,10),'gold');spark(13,1,'ice')
        elif kind=='game':
            diamond(8,8,7,'ink');diamond(8,7,6,'edge');diamond(8,7,5,'deep')
            diamond(8,7,3,'blue');line((8,3,8,11),'ice');line((4,7,12,7),'cyan')
            line((6,5,10,9),'ice');line((6,9,10,5),'ice');diamond(8,7,1,'white')
        elif kind=='fill':
            box(2,4,12,14,'ink');box(1,3,11,12,'edge');box(2,4,10,11,'gold')
            box(3,5,7,8,'blue');box(7,8,10,10,'cyan');box(2,4,10,4,'paper')
            line((9,7,13,1),'ink',3);line((9,6,13,1),'panel_shadow')
            line((8,8,10,5),'ice',2);box(7,8,9,9,'cyan')
        elif kind=='copy':
            box(1,1,9,11,'ink');box(2,2,8,10,'panel_light');box(1,1,9,2,'gold_dark')
            line((3,4,7,4),'edge');line((3,6,6,6),'edge')
            box(6,5,14,14,'ink');box(7,6,13,13,'paper');box(6,4,14,6,'gold')
            line((8,8,12,8),'blue');line((8,10,11,10),'edge');box(6,13,14,14,'gold_dark')
        elif kind=='buffer':
            box(1,2,8,11,'ink');box(2,3,7,10,'edge');box(3,4,6,8,'blue_dark')
            box(7,5,14,14,'ink');box(8,6,13,13,'gold_dark');box(9,7,12,11,'blue')
            diamond(4,6,2,'cyan');diamond(10,9,2,'ice')
            line((8,1,12,1,12,3),'cyan');d.polygon([(11,3),(14,3),(12,5)],fill=color('ice'))
        elif kind=='key':
            diamond(5,6,4,'ink');diamond(5,5,3,'gold');diamond(5,5,1,'deep')
            line((7,7,12,12),'ink',4);line((7,7,12,12),'gold_dark',2)
            line((7,6,13,12),'gold');line((10,10,9,12),'gold',2);box(12,12,13,14,'gold')
            spark(12,2,'cyan')
        elif kind=='alpha':
            box(5,1,10,2,'edge');box(6,3,9,5,'steel')
            d.polygon([(5,5),(10,5),(13,9),(13,12),(11,14),(4,14),(2,12),(2,9)],fill=color('ink'))
            d.polygon([(5,6),(10,6),(12,9),(12,12),(10,13),(5,13),(3,12),(3,9)],fill=color('cyan_dark'))
            d.polygon([(4,10),(11,10),(11,12),(5,12)],fill=color('blue'))
            line((5,7,4,8,4,10),'ice');box(9,8,10,9,'white');box(6,1,9,1,'gold')
        elif kind=='pressure':
            for x,y in ((4,6),(11,6),(8,12)):
                diamond(x,y,4,'ink');diamond(x,y-1,3,'blue_dark')
                d.polygon([(x,y-4),(x+2,y-1),(x,y+1)],fill=color('cyan'))
                d.polygon([(x,y-4),(x,y+1),(x-2,y-1)],fill=color('ice'))
        else:
            raise ValueError(kind)
    return draw


def frost_seal_art(d, image):
    """Replace the technology badge with a small frost seal."""
    d.polygon([(9,1),(14,1),(21,8),(21,14),(14,21),(8,21),(2,15),(2,8)],fill=color('ink'))
    d.polygon([(9,2),(14,2),(20,8),(20,14),(14,20),(8,20),(3,14),(3,8)],fill=color('edge'))
    d.polygon([(9,4),(13,4),(18,9),(18,13),(13,18),(9,18),(5,13),(5,9)],fill=color('blue_dark'))
    for points in ((11,5,11,17),(5,11,17,11),(7,7,15,15),(7,15,15,7)):
        d.line(points,fill=color('cyan'),width=2)
    d.polygon([(11,8),(14,11),(11,14),(8,11)],fill=color('ice'))
    d.point((11,11),fill=color('white'))


def banner_art(d, image):
    d.polygon([(3,1),(16,1),(16,25),(12,23),(9,27),(6,23),(3,25)],fill=color('ink'))
    d.polygon([(4,2),(15,2),(15,23),(12,21),(9,25),(6,21),(4,23)],fill=color('blue_dark'))
    d.line((5,3,5,21),fill=color('blue'))
    d.line((14,3,14,21),fill=color('cyan_dark'))
    d.rectangle((2,0,17,1),fill=color('edge'))
    d.rectangle((3,0,16,0),fill=color('gold'))
    d.line((9,6,9,16),fill=color('cyan'))
    d.line((5,11,13,11),fill=color('cyan'))
    d.line((6,8,12,14),fill=color('ice'))
    d.line((6,14,12,8),fill=color('ice'))


def pedestal_art(d, image):
    d.polygon([(8,6),(55,6),(63,12),(63,18),(55,24),(8,24),(0,18),(0,12)],fill=color('ink'))
    d.polygon([(8,6),(55,6),(62,12),(55,18),(8,18),(1,12)],fill=color('steel'))
    d.polygon([(9,8),(54,8),(59,12),(53,16),(10,16),(4,12)],fill=color('tile_mark'))
    d.polygon([(2,15),(9,19),(54,19),(61,15),(61,18),(54,22),(9,22),(2,18)],fill=color('deep'))
    d.line((10,18,53,18),fill=color('background'))
    for points in ((13,11,18,9,45,9,50,11),(13,13,18,15,45,15,50,13)):
        d.line(points,fill=color('cyan_dark'))
    d.line((30,8,33,8),fill=color('ice'))
    for x in (12,26,40,54):
        d.line((x,19,x,21),fill=color('ink'))


def rune_art(d, image):
    d.line((8,1,8,14),fill=color('cyan_dark'),width=2)
    d.line((2,7,14,7),fill=color('cyan_dark'),width=2)
    d.line((4,3,12,11),fill=color('cyan'))
    d.line((4,11,12,3),fill=color('cyan'))
    d.polygon([(8,4),(11,7),(8,10),(5,7)],fill=color('ice'))


def glow_art(d, image):
    d.polygon([(10,5),(22,5),(27,9),(22,13),(10,13),(5,9)],fill=color('deep'))
    d.polygon([(12,6),(20,6),(24,9),(20,11),(12,11),(8,9)],fill=color('cyan_dark'))
    d.line((12,6,20,6),fill=color('cyan'))


def leaf_art(d, image):
    d.line((8,15,7,6),fill=color('ink'),width=2)
    for coords in ((6,9,1,6,2,4,6,6),(8,10,13,6,14,8,10,12),
                   (6,13,2,10,1,12,5,15),(8,7,9,2,11,3,10,7)):
        points=list(zip(coords[0::2],coords[1::2]))
        d.polygon(points,fill=color('green'))
    d.line((7,8,8,14),fill=color('steel'))


def cursor_art(phase):
    def draw(d, image):
        d.polygon([(3,1),(7,6),(3,11),(0,6)],fill=color('ink'))
        d.polygon([(3,2),(6,6),(3,10),(1,6)],fill=color('blue'))
        d.polygon([(3,2),(3,8),(1,6)],fill=color('ice'))
        d.line((3,9,5,6),fill=color('cyan'))
        if phase in (1,2):
            d.point((7,5),fill=color('ice' if phase==2 else 'cyan'))
        if phase==3:
            d.line((0,4,1,5,0,6),fill=color('cyan'))
    return draw


sprite('background_tile', (16,16), background_art(False), role='tile')
sprite('stone_tile', (16,16), background_art(True), role='tile')
for state in ('normal','selected','pressed','disabled'):
    sprite('panel_'+state, (12,12), panel_art(state), margin=8, role='nine_slice')
sprite('header_panel', (16,16), panel_art('header',16), margin=12, role='nine_slice')
sprite('icon_well', (12,12), panel_art('cloth'), margin=8, role='nine_slice')
sprite('keycap_normal', (12,12), panel_art('header'), margin=8, role='nine_slice')
sprite('keycap_pressed', (12,12), panel_art('cloth'), margin=8, role='nine_slice')
for kind in ('basic','advanced','game','fill','copy','buffer','key','alpha','pressure'):
    sprite('icon_'+kind,(16,16),icon_art(kind),role='icon')
sprite('frost_seal',(24,24),frost_seal_art,role='emblem')
sprite('cloth_banner',(20,28),banner_art,role='decoration')
sprite('stone_pedestal',(64,28),pedestal_art,role='decoration')
sprite('frost_rune',(16,16),rune_art,role='decoration')
sprite('pedestal_glow',(32,18),glow_art,role='decoration')
sprite('stone_leaf',(16,16),leaf_art,role='decoration')
for phase in range(4):
    sprite('cursor_'+str(phase),(8,12),cursor_art(phase),role='cursor')


def separator_art(d, image):
    d.line((0,2,15,2),fill=color('steel'))
    d.line((0,3,15,3),fill=color('ink'))
    d.point((7,2),fill=color('cyan_dark'))


sprite('separator_tile',(16,4),separator_art,role='tile')
BY_NAME = {asset['name']: asset for asset in ASSETS}


def nine_slice(name, width, height):
    """Repeat the center/edges while preserving each corner's pixel size."""
    asset = BY_NAME[name]
    image, m = asset['image'], asset['nine_slice']
    assert m and width >= m*2 and height >= m*2 and width%2==height%2==0
    result = Image.new('RGBA',(width,height),TRANSPARENT)
    sx, sy = (0,m,image.width-m,image.width),(0,m,image.height-m,image.height)
    dx, dy = (0,m,width-m,width),(0,m,height-m,height)
    for row in range(3):
        for col in range(3):
            tile = image.crop((sx[col],sy[row],sx[col+1],sy[row+1]))
            for y in range(dy[row],dy[row+1],tile.height):
                for x in range(dx[col],dx[col+1],tile.width):
                    w, h = min(tile.width,dx[col+1]-x),min(tile.height,dy[row+1]-y)
                    result.alpha_composite(tile.crop((0,0,w,h)),(x,y))
    return result


# Reuse the actual project bitmap fonts; preview text is never AI-generated.
font_source = (ROOT/'software/font_cn.h').read_text(encoding='utf-8')
CN = {int(cp,16): [int(n,16) for n in re.findall(r'0x[0-9a-fA-F]+',rows)]
      for cp,rows in re.findall(r'\{0x([0-9a-fA-F]+),\{([^}]+)\}\}',font_source)}
ASCII = [[int(v,16) for v in re.findall(r'0x[0-9a-fA-F]+',row)]
         for row in re.findall(r'\{([^{}]+)\}',(ROOT/'software/font5x7.h').read_text())]
assert len(ASCII)==36
PUNCT = {' ': [0]*5, '-':[8]*5, '+':[8,8,62,8,8], '/':[32,16,8,4,2],
         '_':[64]*5, ':':[0,20,0,0,0], '.':[0,64,0,0,0]}


def draw_text(image, x, y, text, ink, large=False, ascii_scale=None):
    """Render existing glyphs with integer scaling, rejecting missing text."""
    d, start = ImageDraw.Draw(image), x
    for ch in text:
        if ord(ch)>127:
            assert ord(ch) in CN, f'Missing project glyph: {ch}'
            scale = 2 if large else 1
            for row,bits in enumerate(CN[ord(ch)]):
                for col in range(14):
                    if bits & (1<<col):
                        d.rectangle((x+col*scale,y+row*scale,x+(col+1)*scale-1,y+(row+1)*scale-1),fill=color(ink))
            x += 14*scale
        else:
            scale = ascii_scale or (3 if large else 2)
            up = ch.upper()
            n = ord(up)-48 if '0'<=up<='9' else ord(up)-65+10 if 'A'<=up<='Z' else -1
            columns = ASCII[n] if n>=0 else PUNCT.get(up)
            assert columns is not None, f'Missing ASCII glyph: {ch}'
            offset = 4 if large else 0
            for col,bits in enumerate(columns):
                for row in range(7):
                    if bits & (1<<row):
                        d.rectangle((x+col*scale,y+offset+row*scale,x+(col+1)*scale-1,y+offset+(row+1)*scale-1),fill=color(ink))
            x += 6*scale
    assert 0<=start<=x<=image.width and 0<=y and y+(28 if large else 14)<=image.height, text
    return x-start


def key_hint(image, x, y, key, label):
    width = max(28,len(key)*12+20)
    width += width%2
    image.alpha_composite(nine_slice('keycap_normal',width,28),(x,y))
    draw_text(image,x+(width-len(key)*12)//2,y+6,key,'muted')
    draw_text(image,x+width+10,y+6,label,'muted')
    return width


MENU = {
    'home': [('基础演示','3项功能','basic'),('高阶演示','3项功能','advanced'),
             ('冰霜幸存者','自动施法 生存360秒','game')],
    'basic': [('矩形填充','RGB565 硬件填充','fill'),('图像复制','DDR 图像复制到显存','copy'),
              ('双缓冲','垂直消隐交换页面','buffer')],
    'advanced': [('颜色键','黑色像素变为透明','key'),('透明混合','W加5 D减5','alpha'),
                 ('SPRITE 压力','FPGA ALPHA + COLOR KEY','pressure')]
}


def menu_preview(group, selected, glyphs=True):
    """Give the original player a scene, and keep menu cards on the right."""
    result = Image.new('RGBA',(640,480),color('background'))
    # Larger staggered masonry has less visual competition than a UI grid.
    for row,y in enumerate(range(-16,480,32)):
        for col,x in enumerate(range(-32,672,32)):
            tile=BY_NAME['stone_tile' if (row+col)%2 else 'background_tile']['image']
            result.alpha_composite(tile,(x+(16 if row%2 else 0),y))
    d = ImageDraw.Draw(result)
    d.rectangle((16,16,623,463),outline=color('deep'),width=4)
    result.alpha_composite(nine_slice('header_panel',592,88),(24,24))
    result.alpha_composite(BY_NAME['frost_seal']['image'],(44,42))
    if glyphs:
        draw_text(result,112,40,{'home':'二维实验室','basic':'基础演示','advanced':'高阶演示'}[group],'white',large=True)
        draw_text(result,114,80,'RISC-V + FPGA','muted')
        draw_text(result,504,48,'TI60','gold')
    # Cloth and a small platform echo the actual sprite's blue hood and dungeon.
    result.alpha_composite(BY_NAME['cloth_banner']['image'],(94,130))
    result.alpha_composite(BY_NAME['frost_rune']['image'],(52,198))
    result.alpha_composite(BY_NAME['frost_rune']['image'],(156,246))
    result.alpha_composite(BY_NAME['stone_pedestal']['image'],(50,306))
    result.alpha_composite(BY_NAME['pedestal_glow']['image'],(82,304))
    result.alpha_composite(BY_NAME['stone_leaf']['image'],(36,328))
    result.alpha_composite(BY_NAME['stone_leaf']['image'].transpose(Image.Transpose.FLIP_LEFT_RIGHT),(166,326))
    # Reuse the exact existing 32x32 art. No alternate head, costume or face.
    player = Image.open(ROOT/'assets/player/walk_32.png').convert('RGBA').crop((0,0,32,32))
    player = player.resize((96,96),Image.Resampling.NEAREST)
    result.alpha_composite(player,(66,220))
    if glyphs:
        draw_text(result,44,362,'冰霜幸存者','paper')
    for index,(title,subtitle,kind) in enumerate(MENU[group]):
        y = 130+index*84
        active = index==selected
        result.alpha_composite(nine_slice('panel_selected' if active else 'panel_normal',384,72),(232,y))
        result.alpha_composite(BY_NAME['icon_'+kind]['image'],(248,y+18))
        if active:
            result.alpha_composite(BY_NAME['cursor_0']['image'],(210,y+24))
        if glyphs:
            width = draw_text(result,296,y+6,title,'ink',large=True)
            assert width<=272,title
            width = draw_text(result,298,y+48,subtitle,'panel_shadow')
            assert width<=300,subtitle
    result.alpha_composite(nine_slice('header_panel',592,48),(24,404))
    if glyphs:
        key_hint(result,42,414,'W','')
        key_hint(result,78,414,'S','选择')
        key_hint(result,228,414,'ENTER','打开' if group=='home' else '开始')
        if group!='home':
            key_hint(result,466,414,'A','返回')
        draw_text(result,504,462,f'{selected+1:02d}/03','muted',ascii_scale=1)
    return result


def encode(image):
    """Convert binary alpha to the project's zero-valued color key."""
    raw = image.tobytes()
    pixels = []
    for offset in range(0,len(raw),4):
        r,g,b,a = raw[offset:offset+4]
        assert a in (0,255), 'Alpha must be binary for the hardware color key.'
        pixels.append(0 if a==0 else rgb565((r,g,b)))
    return pixels,struct.pack('<'+'H'*len(pixels),*pixels)


# Shelf packing keeps all source rectangles aligned to the two-pixel grid.
atlas = Image.new('RGBA',(256,256),TRANSPARENT)
x,y,row_height = 2,2,0
rectangles=[]
for asset in sorted(ASSETS,key=lambda a:(-a['image'].height,a['name'])):
    image=asset['image']
    if x+image.width+2>256:
        x,y,row_height=2,y+row_height+2,0
    assert y+image.height+2<=256,'Atlas does not fit.'
    atlas.alpha_composite(image,(x,y))
    asset['rect']=[x,y,image.width,image.height]
    rectangles.append(asset)
    x,row_height=x+image.width+2,max(row_height,image.height)

atlas.save(OUT/'menu_ui_atlas.png')
atlas_pixels,atlas_bytes=encode(atlas)
(OUT/'menu_ui_atlas.rgb565').write_bytes(atlas_bytes)
for asset in ASSETS:
    asset['image'].save(OUT/'png'/f'{asset["name"]}.png')
    _,data=encode(asset['image'])
    (OUT/'rgb565'/f'{asset["name"]}.rgb565').write_bytes(data)

# Indexed 16-bit RLE: high 11 bits = run length 1..2047, low 5 = palette.
palette=[0]+sorted(set(atlas_pixels)-{0})
assert len(palette)<=32,'Indexed RLE supports at most 32 colors.'
indices={value:index for index,value in enumerate(palette)}
tokens=[]
at=0
while at<len(atlas_pixels):
    value=atlas_pixels[at]
    end=at+1
    while end<len(atlas_pixels) and atlas_pixels[end]==value and end-at<2047:
        end+=1
    tokens.append(((end-at)<<5)|indices[value])
    at=end
decoded=[]
for token in tokens:
    decoded.extend([palette[token&31]]*(token>>5))
assert decoded==atlas_pixels,'RLE must exactly reproduce every atlas pixel.'
(OUT/'embedded/menu_ui_palette.rgb565').write_bytes(struct.pack('<'+'H'*len(palette),*palette))
(OUT/'embedded/menu_ui_rle.bin').write_bytes(struct.pack('<'+'H'*len(tokens),*tokens))


def c_array(name, values):
    lines=[f'static const uint16_t {name}[{len(values)}] = {{']
    for start in range(0,len(values),12):
        lines.append('    '+', '.join(f'0x{v:04x}' for v in values[start:start+12])+',')
    return '\n'.join(lines+['};'])


header=['/* Generated by tools/prepare_menu_ui_v2.py; not included by firmware yet. */',
        '#ifndef MENU_UI_V2_ASSETS_H','#define MENU_UI_V2_ASSETS_H','#include <stdint.h>',
        '#define MENU_UI_ATLAS_WIDTH 256u','#define MENU_UI_ATLAS_HEIGHT 256u',
        '#define MENU_UI_ATLAS_BYTES 131072u','#define MENU_UI_COLOR_KEY 0u',
        f'#define MENU_UI_RLE_WORDS {len(tokens)}u',
        f'#define MENU_UI_PALETTE_COLORS {len(palette)}u',
        '/* token >> 5 = run length; token & 31 = palette index. */',
        c_array('menu_ui_palette',palette),c_array('menu_ui_rle',tokens),
        'typedef struct { uint16_t x,y,w,h; uint8_t margin; } MenuUiRect;',
        'enum {']
for index,asset in enumerate(ASSETS):
    header.append(f'    MENU_UI_{asset["name"].upper()} = {index},')
header+=['    MENU_UI_COUNT','};','static const MenuUiRect menu_ui_rects[MENU_UI_COUNT] = {']
for asset in ASSETS:
    header.append('    {'+','.join(str(v) for v in [*asset['rect'],asset['nine_slice']])+'}, // '+asset['name'])
header+=['};','#endif','']
(OUT/'embedded/menu_ui_assets.h').write_text('\n'.join(header),encoding='utf-8')

layouts=[]
for group in MENU:
    for selected in range(3):
        path=OUT/'previews'/f'menu_{group}_{selected}.png'
        menu_preview(group,selected).convert('RGB').save(path)
        layouts.append({'group':group,'selected':selected,'path':'previews/'+path.name})
    menu_preview(group,0,False).save(OUT/'previews'/f'menu_{group}_art_only.png')

layout={
    'canvas':[640,480], 'safe_frame':[16,16,608,448],
    'header':{'rect':[24,24,592,88],'frame':'header_panel','title_origin':[112,40],
              'title_cn_scale':2,'title_ascii_scale':3,'subtitle_origin':[114,80]},
    'hero':{'source':'assets/player/walk_32.png','source_rect':[0,0,32,32],
            'destination':[66,220,96,96],'scale':3,'filter':'nearest',
            'runtime_note':'Reuse existing character; implement integer scaling or one-time expansion during integration.'},
    'decorations':{'banner':[94,130,40,56],'pedestal':[50,306,128,56]},
    'rows':[{'rect':[232,130+i*84,384,72],'icon_rect':[248,148+i*84,32,32],
             'title_origin':[296,136+i*84],'description_origin':[298,178+i*84],
             'cursor_rect':[210,154+i*84,16,24]}
            for i in range(3)],
    'footer_rect':[24,404,592,48], 'footer_text_y':462,
    'navigation':{'previous':'W','next':'S','enter':'ENTER','back':'A'},
    'cursor':{'frames':['cursor_0','cursor_1','cursor_2','cursor_3'],
              'optional_frame_ms':150,'static_frame':'cursor_0'},
    'render_notes':[
        'Preview layout proposal; existing menu_screen has not been modified.',
        'Body uses existing font_cn.h / font5x7.h; large titles need an integer-scaling text helper.',
        'PNG alpha is binary; transparent atlas pixels are RGB565 0x0000.',
        'Use explicit 512-byte source stride for atlas regions; individual assets use width*2.',
        'Nine-slice margins are already in output pixels; repeat edges and center without filtering.'
    ]}
(OUT/'layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

manifest={
    'name':THEME['name'],'version':2,'authoring':'Original deterministic pixel art; no AI image service used.',
    'style':'Fantasy quest menu matched to the original blue-hooded player; no alternate player design.',
    'canvas':[640,480],'pixel_grid':2,'atlas':{'size':[256,256],'stride_bytes':512,
        'format':'RGB565 little endian','color_key':0,'raw_bytes':len(atlas_bytes),
        'sha256':hashlib.sha256(atlas_bytes).hexdigest()},
    'embedded':{'palette_colors':len(palette),'palette_bytes':len(palette)*2,
        'rle_words':len(tokens),'rle_bytes':len(tokens)*2,
        'descriptor_bytes':len(ASSETS)*10,
        'c_data_bytes':len(palette)*2+len(tokens)*2+len(ASSETS)*10,
        'token':'uint16_t: (run_length << 5) | palette_index; length 1..2047'},
    'palette':{name:{'rgb':list(rgba[:3]),'rgb565':f'0x{rgb565(rgba):04x}'} for name,rgba in COLORS.items()},
    'assets':[{'id':i,'name':a['name'],'rect':a['rect'],'nine_slice_margin':a['nine_slice'],
               'role':a['role'],'raw_file':'rgb565/'+a['name']+'.rgb565',
               'png_file':'png/'+a['name']+'.png'} for i,a in enumerate(ASSETS)],
    'previews':layouts,'runtime_integrated':False,
    'existing_dependencies':{'fonts':['software/font_cn.h','software/font5x7.h'],
        'preview_only_player':'assets/player/walk_32.png; exact front frame at 3x nearest neighbor; original user-provided art, original rights apply.',
        'player_sha256':hashlib.sha256((ROOT/'assets/player/walk_32.png').read_bytes()).hexdigest()},
    'checks':{'atlas_rle_roundtrip':True,'binary_alpha':True,'color_key_opaque_collision':False,
              'atlas_bounds':True,'project_glyph_coverage':True}}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Human-readable sheets use a display font only for captions outside the assets.
label_font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
title_font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc',28)
sheet=Image.new('RGB',(2000,604),expand(rgb565((14,21,38))))
d=ImageDraw.Draw(sheet)
d.text((24,16),'蓝色冒险者 · 像素风菜单 v2',font=title_font,fill=color('paper')[:3])
for i,(group,label) in enumerate((('home','主菜单'),('basic','基础演示菜单'),('advanced','高阶演示菜单'))):
    x=20+i*660
    d.text((x,70),label,font=label_font,fill=color('ice')[:3])
    sheet.paste(menu_preview(group,0).convert('RGB'),(x,104))
sheet.save(OUT/'菜单效果总览.png')

board=Image.new('RGB',(1120,760),color('deep')[:3])
d=ImageDraw.Draw(board)
d.text((28,20),'蓝色冒险者 / 菜单资源 v2',font=title_font,fill=color('paper')[:3])
d.text((28,68),'角色原图复用 · 羊皮纸卡片 · 石墙 / 蓝色斗篷 / 冰霜魔法',font=label_font,fill=color('muted')[:3])
for i,kind in enumerate(('basic','advanced','game','fill','copy','buffer','key','alpha','pressure')):
    x,y=36+(i%5)*212,122+(i//5)*150
    img=BY_NAME['icon_'+kind]['image'].resize((96,96),Image.Resampling.NEAREST)
    board.paste(img,(x,y),img)
    d.text((x,y+104),kind.upper(),font=label_font,fill=color('paper')[:3])
for i,state in enumerate(('normal','selected','pressed','disabled')):
    x,y=36+i*268,454
    p=nine_slice('panel_'+state,240,80)
    board.paste(p,(x,y),p)
    d.text((x,y+90),state.upper(),font=label_font,fill=color('paper')[:3])
for i,rgba in enumerate(COLORS.values()):
    x,y=36+i*40,618
    d.rectangle((x,y,x+30,y+30),fill=rgba[:3])
d.text((36,682),f'{len(ASSETS)} 个组件 / 图集 256×256 / C常量数据 {manifest["embedded"]["c_data_bytes"]} 字节',font=label_font,fill=color('muted')[:3])
board.save(OUT/'美术资源板.png')

comparison=Image.new('RGB',(1340,570),color('deep')[:3])
d=ImageDraw.Draw(comparison)
d.text((20,18),'上一版：科技面板',font=title_font,fill=color('muted')[:3])
d.text((680,18),'这一版：与原角色统一的冒险风',font=title_font,fill=color('paper')[:3])
previous=ROOT/'assets/ui/menu_pixel_v1/previews/menu_home_0.png'
if previous.exists():
    comparison.paste(Image.open(previous).convert('RGB'),(20,70))
comparison.paste(menu_preview('home',0).convert('RGB'),(680,70))
comparison.save(OUT/'风格修改对比.png')

# The archive preserves paths relative to my/first_light for project reuse.
with zipfile.ZipFile(OUT.parent/'menu_pixel_v2.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(OUT.rglob('*')):
        if path.is_file():
            archive.write(path,path.relative_to(ROOT).as_posix())
    archive.write(Path(__file__).resolve(),'tools/prepare_menu_ui_v2.py')

print(json.dumps({'output':str(OUT),'assets':len(ASSETS),'palette_colors':len(palette),
                  'atlas_bytes':len(atlas_bytes),'rle_bytes':len(tokens)*2,
                  'c_data_bytes':manifest['embedded']['c_data_bytes'],
                  'previews':len(layouts),'checks':'PASS'},ensure_ascii=False,indent=2))
