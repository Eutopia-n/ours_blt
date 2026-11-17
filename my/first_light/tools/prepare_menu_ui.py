"""Build original pixel menu art, RGB565 data and project-sized previews.

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
OUT = ROOT / 'assets/ui/menu_pixel_v1'
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
    """Return the stepped border for a reusable nine-slice panel."""
    def draw(d, image):
        n = size
        def cut(x0, y0, x1, y1, c, k=2):
            d.polygon([(x0+k,y0),(x1-k,y0),(x1,y0+k),(x1,y1-k),
                       (x1-k,y1),(x0+k,y1),(x0,y1-k),(x0,y0+k)], fill=color(c))
        cut(0,0,n-1,n-1,'ink')
        edge = {'normal':'edge','selected':'cyan','pressed':'cyan_dark',
                'disabled':'panel_light','header':'gold_dark'}[state]
        fill = 'focus_fill' if state in ('selected','pressed') else 'panel_shadow' if state=='disabled' else 'panel'
        cut(0,0,n-2,n-2,edge)
        cut(1,1,n-3,n-3,fill,1)
        d.line((3,1,n-6,1), fill=color('ice' if state=='selected' else 'steel' if state=='header' else 'panel_light'))
        d.line((1,3,1,n-6), fill=color('cyan_dark' if state=='selected' else 'panel_light'))
        d.line((3,n-3,n-5,n-3), fill=color('ink'))
        d.line((n-3,3,n-3,n-5), fill=color('ink'))
        if state=='pressed':
            d.line((2,2,n-5,2),fill=color('deep'))
        if state=='header':
            for x,y in ((3,3),(n-6,3),(3,n-6),(n-6,n-6)):
                d.point((x,y),fill=color('gold_light'))
    return draw


def background_art(grid):
    def draw(d, image):
        d.rectangle((0,0,15,15),fill=color('background'))
        if grid:
            d.line((0,0,15,0),fill=color('tile_mark'))
            d.line((0,0,0,15),fill=color('tile_mark'))
            d.point((0,0),fill=color('panel_light'))
        else:
            for xy in ((3,5),(12,11)):
                d.point(xy,fill=color('tile_mark'))
    return draw


def icon_art(kind):
    """Author each 16x16 menu icon with the shared, limited palette."""
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
            box(2,3,13,13,'ink');box(1,2,12,12,'edge');box(2,3,11,11,'deep')
            box(3,4,6,7,'gold');box(7,4,10,7,'blue');box(3,8,6,10,'cyan');box(7,8,10,10,'violet')
            line((3,4,6,4),'gold_light');line((7,4,10,4),'paper');spark(13,3)
        elif kind=='advanced':
            diamond(8,8,7,'ink');diamond(8,7,6,'cyan_dark');diamond(8,7,5,'cyan')
            d.polygon([(8,2),(8,7),(3,7)],fill=color('ice'))
            d.polygon([(8,2),(13,7),(8,7)],fill=color('blue'))
            d.polygon([(8,7),(13,7),(8,12)],fill=color('violet'))
            line((3,7,8,7,8,12),'paper');spark(2,2);spark(13,12,'cyan')
        elif kind=='game':
            d.polygon([(5,2),(10,2),(13,6),(13,10),(11,13),(4,13),(2,10),(2,6)],fill=color('ink'))
            d.polygon([(5,2),(10,2),(12,6),(11,10),(4,10),(3,6)],fill=color('blue_dark'))
            d.polygon([(5,3),(9,3),(11,6),(4,6)],fill=color('blue'))
            box(5,6,10,9,'gold');box(5,6,10,6,'gold_light')
            box(6,7,6,8,'ink');box(9,7,9,8,'ink')
            box(4,10,11,12,'blue_dark');box(6,10,9,12,'cyan');box(3,13,5,13,'steel');box(10,13,12,13,'steel')
            d.point((4,4),fill=color('ice'))
        elif kind=='fill':
            box(1,3,13,13,'ink');box(1,2,12,11,'edge');box(2,3,11,10,'deep')
            box(3,4,7,6,'gold');box(5,7,10,9,'cyan');box(9,3,11,5,'coral')
            line((3,4,7,4),'gold_light');line((5,7,10,7),'ice');spark(13,2)
        elif kind=='copy':
            box(1,2,9,11,'ink');box(1,1,8,10,'steel');box(2,2,7,9,'paper')
            box(3,3,6,5,'blue');line((3,7,6,7),'blue_dark')
            box(6,5,14,14,'ink');box(6,4,13,13,'cyan_dark');box(7,5,12,12,'ice')
            box(8,6,11,8,'blue');line((8,10,11,10),'cyan_dark');line((8,11,10,11),'cyan_dark')
        elif kind=='buffer':
            box(1,4,9,12,'ink');box(1,3,8,11,'edge');box(2,4,7,10,'blue_dark')
            box(7,6,14,14,'ink');box(7,5,13,13,'cyan_dark');box(8,6,12,12,'focus_inner')
            line((5,1,12,1,12,3),'gold');d.polygon([(10,2),(14,2),(12,4)],fill=color('gold'))
            line((9,14,3,14,3,12),'cyan');d.polygon([(1,12),(5,12),(3,10)],fill=color('cyan'))
            line((3,5,6,5),'blue');line((9,7,11,7),'ice')
        elif kind=='key':
            box(1,3,11,13,'ink');box(1,2,10,12,'edge')
            for y in range(3,12,3):
                for x in range(2,10,3):
                    box(x,y,min(x+2,9),min(y+2,11),'panel_light' if (x//3+y//3)%2 else 'deep')
            diamond(6,7,3,'cyan');box(6,7,9,9,'violet')
            box(10,8,14,10,'gold_dark');box(11,7,13,9,'gold');box(9,10,11,11,'gold')
            box(7,11,9,12,'gold');box(7,12,7,14,'gold');d.point((12,8),fill=color('ink'))
        elif kind=='alpha':
            box(1,2,10,11,'ink');box(1,1,9,9,'blue_dark');box(2,2,8,8,'blue')
            box(6,6,14,14,'ink');box(5,5,13,13,'violet');box(6,6,12,12,'violet')
            box(5,5,9,9,'cyan');box(6,6,8,8,'ice')
            line((2,2,8,2),'paper');line((6,12,12,12),'steel')
        elif kind=='pressure':
            for x,y in ((4,5),(11,5),(8,11)):
                diamond(x,y+1,4,'ink');diamond(x,y,3,'gold')
                d.polygon([(x-3,y),(x,y-3),(x+3,y)],fill=color('cyan'))
                d.polygon([(x-3,y),(x+3,y),(x,y+3)],fill=color('coral'))
                d.point((x,y-2),fill=color('ice'))
        else:
            raise ValueError(kind)
    return draw


def chip_art(d, image):
    d.rectangle((5,5,19,19),fill=color('ink'))
    for at in range(7,19,3):
        d.rectangle((at,2,at+1,4),fill=color('steel'))
        d.rectangle((at,20,at+1,22),fill=color('steel'))
        d.rectangle((2,at,4,at+1),fill=color('steel'))
        d.rectangle((20,at,22,at+1),fill=color('steel'))
    d.rectangle((5,5,18,18),fill=color('edge'))
    d.rectangle((6,6,17,17),fill=color('panel_shadow'))
    d.polygon([(11,7),(16,12),(11,17),(7,12)],fill=color('cyan_dark'))
    d.polygon([(11,8),(15,12),(11,16),(8,12)],fill=color('cyan'))
    d.polygon([(11,8),(11,12),(8,12)],fill=color('ice'))
    d.polygon([(11,12),(15,12),(11,16)],fill=color('blue'))
    d.point((6,6),fill=color('gold_light'))


def cursor_art(phase):
    def draw(d, image):
        d.polygon([(1,1),(6,6),(1,11)],fill=color('ink'))
        d.polygon([(1,1),(5,5),(1,9)],fill=color('gold'))
        d.line((1,2,4,5),fill=color('gold_light'))
        if phase in (1,2):
            d.point((7,5),fill=color('ice' if phase==2 else 'cyan'))
        if phase==3:
            d.line((0,4,1,5,0,6),fill=color('cyan'))
    return draw


sprite('background_tile', (16,16), background_art(False), role='tile')
sprite('grid_tile', (16,16), background_art(True), role='tile')
for state in ('normal','selected','pressed','disabled'):
    sprite('panel_'+state, (12,12), panel_art(state), margin=8, role='nine_slice')
sprite('header_panel', (16,16), panel_art('header',16), margin=12, role='nine_slice')
sprite('icon_well', (12,12), panel_art('pressed'), margin=8, role='nine_slice')
sprite('keycap_normal', (12,12), panel_art('normal'), margin=8, role='nine_slice')
sprite('keycap_pressed', (12,12), panel_art('selected'), margin=8, role='nine_slice')
for kind in ('basic','advanced','game','fill','copy','buffer','key','alpha','pressure'):
    sprite('icon_'+kind,(16,16),icon_art(kind),role='icon')
sprite('chip_emblem',(24,24),chip_art,role='emblem')
for phase in range(4):
    sprite('cursor_'+str(phase),(8,12),cursor_art(phase),role='cursor')


def separator_art(d, image):
    d.line((0,2,15,2),fill=color('edge'))
    d.line((0,3,15,3),fill=color('ink'))
    d.point((7,2),fill=color('gold'))


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
    draw_text(image,x+(width-len(key)*12)//2,y+6,key,'paper')
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
    """Compose a proposed menu from the delivered, reusable asset pieces."""
    result = Image.new('RGBA',(640,480),color('background'))
    tile = BY_NAME['grid_tile']['image']
    for y in range(0,480,32):
        for x in range(0,640,32):
            result.alpha_composite(tile,(x,y))
    d = ImageDraw.Draw(result)
    d.rectangle((16,16,623,463),outline=color('panel_light'),width=2)
    for x,y,dx,dy in ((16,16,1,1),(622,16,-1,1),(16,462,1,-1),(622,462,-1,-1)):
        d.line((x,y,x+dx*14,y),fill=color('gold'),width=2)
        d.line((x,y,x,y+dy*14),fill=color('gold'),width=2)
    result.alpha_composite(nine_slice('header_panel',592,88),(24,24))
    result.alpha_composite(BY_NAME['chip_emblem']['image'],(48,44))
    if glyphs:
        draw_text(result,116,42,{'home':'二维实验室','basic':'基础演示','advanced':'高阶演示'}[group],'white',large=True)
        draw_text(result,118,82,'RISC-V + FPGA','muted')
        draw_text(result,466,44,'TI60','gold')
        draw_text(result,466,70,'MENU','steel')
    player = Image.open(ROOT/'assets/player/walk_32.png').convert('RGBA').crop((0,0,32,32))
    if glyphs:
        result.alpha_composite(nine_slice('icon_well',48,48),(548,44))
        result.alpha_composite(player,(556,52))
    for index,(title,subtitle,kind) in enumerate(MENU[group]):
        y = 132+index*76
        active = index==selected
        result.alpha_composite(nine_slice('panel_selected' if active else 'panel_normal',576,68),(32,y))
        result.alpha_composite(nine_slice('icon_well',48,48),(48,y+10))
        result.alpha_composite(BY_NAME['icon_'+kind]['image'],(56,y+18))
        if active:
            d = ImageDraw.Draw(result)
            d.rectangle((36,y+14,37,y+52),fill=color('ice'))
            result.alpha_composite(BY_NAME['cursor_0']['image'],(580,y+22))
        if glyphs:
            width = draw_text(result,120,y+6,title,'white' if active else 'paper',large=True)
            assert width<=410
            width = draw_text(result,122,y+46,subtitle,'ice' if active else 'muted')
            assert width<=438,subtitle
            draw_text(result,534,y+12,f'{index+1:02d}','gold' if active else 'steel')
    divider = BY_NAME['separator_tile']['image']
    for x in range(32,608,32):
        result.alpha_composite(divider,(x,374))
    result.alpha_composite(nine_slice('panel_disabled',592,52),(24,392))
    if glyphs:
        key_hint(result,40,404,'W','')
        key_hint(result,76,404,'S','选择')
        key_hint(result,230,404,'ENTER','打开' if group=='home' else '开始')
        if group!='home':
            key_hint(result,466,404,'A','返回')
        draw_text(result,34,450,'6项演示 + 幸存者游戏' if group=='home' else '选择功能','steel')
        draw_text(result,536,450,f'{selected+1:02d}/03','gold',ascii_scale=1)
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


header=['/* Generated by tools/prepare_menu_ui.py; not included by firmware yet. */',
        '#ifndef MENU_UI_ASSETS_H','#define MENU_UI_ASSETS_H','#include <stdint.h>',
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
    'header':{'rect':[24,24,592,88],'frame':'header_panel','title_origin':[116,42],
              'title_cn_scale':2,'title_ascii_scale':3,'subtitle_origin':[118,82]},
    'rows':[{'rect':[32,132+i*76,576,68],'icon_rect':[56,150+i*76,32,32],
             'title_origin':[120,138+i*76],'description_origin':[122,178+i*76]}
            for i in range(3)],
    'footer_rect':[24,392,592,52], 'footer_text_y':450,
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
    'name':THEME['name'],'version':1,'authoring':'Original deterministic pixel art; no AI image service used.',
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
        'preview_only_player':'assets/player/walk_32.png; original user-provided art, original rights apply.'},
    'checks':{'atlas_rle_roundtrip':True,'binary_alpha':True,'color_key_opaque_collision':False,
              'atlas_bounds':True,'project_glyph_coverage':True}}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Human-readable sheets use a display font only for captions outside the assets.
label_font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
title_font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc',28)
sheet=Image.new('RGB',(2000,604),expand(rgb565((14,21,38))))
d=ImageDraw.Draw(sheet)
d.text((24,16),'像素风菜单 · 640×480 资源组合预览',font=title_font,fill=color('paper')[:3])
for i,(group,label) in enumerate((('home','主菜单'),('basic','基础演示菜单'),('advanced','高阶演示菜单'))):
    x=20+i*660
    d.text((x,70),label,font=label_font,fill=color('ice')[:3])
    sheet.paste(menu_preview(group,0).convert('RGB'),(x,104))
sheet.save(OUT/'菜单效果总览.png')

board=Image.new('RGB',(1120,760),color('deep')[:3])
d=ImageDraw.Draw(board)
d.text((28,20),'MENU PIXEL UI / 资源板',font=title_font,fill=color('paper')[:3])
d.text((28,68),'2×2 像素网格 · 统一调色板 · 边框 / 图标 / 按键 / 光标',font=label_font,fill=color('muted')[:3])
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

# The archive preserves paths relative to my/first_light for project reuse.
with zipfile.ZipFile(OUT.parent/'menu_pixel_v1.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(OUT.rglob('*')):
        if path.is_file():
            archive.write(path,path.relative_to(ROOT).as_posix())
    archive.write(Path(__file__).resolve(),'tools/prepare_menu_ui.py')

print(json.dumps({'output':str(OUT),'assets':len(ASSETS),'palette_colors':len(palette),
                  'atlas_bytes':len(atlas_bytes),'rle_bytes':len(tokens)*2,
                  'c_data_bytes':manifest['embedded']['c_data_bytes'],
                  'previews':len(layouts),'checks':'PASS'},ensure_ascii=False,indent=2))
