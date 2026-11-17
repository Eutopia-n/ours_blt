"""Build the magic-book UI art and an offline interaction prototype.

All drawings are deterministic pixel art. This generator does not edit firmware.
"""
from pathlib import Path
import base64
import hashlib
import json
import math
import random
import re
import struct
import zipfile

from PIL import Image, ImageDraw, ImageFont
from book_opening_animation import FRAME_COUNT, FRAME_MS, create_opening_frames, ease, _project_sheet

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'assets/ui/magic_book_v5'
PREVIOUS = ROOT/'assets/ui/menu_pixel_v2'
for name in ('png','rgb565','embedded','previews','animation','animation_smooth','source'):
    (OUT/name).mkdir(parents=True,exist_ok=True)

THEME = {
    'ink':'#111222','desk':'#171626','desk_light':'#202039',
    'leather':'#292c51','leather_dark':'#1b1c35','leather_light':'#3d4267',
    'blue':'#2889ac','ice':'#9ae2e4','glow':'#d6f6e9',
    'gold_dark':'#68503d','gold':'#ac8751','gold_light':'#e4c98b',
    'gold_mid':'#c5a76c','metal_shadow':'#423641',
    'page_shadow':'#a28b67','page_edge':'#c1a57a','page':'#e0cda3',
    'page_light':'#efdfb8','page_highlight':'#f7ebca','page_faint':'#e8d6ad',
    'brown':'#514239','muted':'#887252','select':'#f7e9be',
    'stone':'#65768b','red':'#ad6262','green':'#6c9578',
    'magic_dark':'#294454','magic_mid':'#3b6577'
}


def to565(rgb):
    r,g,b=rgb[:3]
    return max(1,((r>>3)<<11)|((g>>2)<<5)|(b>>3))


def expand(v):
    return ((v>>11)*255//31,((v>>5)&63)*255//63,(v&31)*255//31)


C={name:(*expand(to565(tuple(bytes.fromhex(value[1:])))),255) for name,value in THEME.items()}
T=(0,0,0,0)


def c(name):return C[name]


# These are the actual existing firmware bitmap fonts, including glyph limits.
CN={int(cp,16):[int(n,16) for n in re.findall(r'0x[0-9a-fA-F]+',rows)]
    for cp,rows in re.findall(r'\{0x([0-9a-fA-F]+),\{([^}]+)\}\}',
                              (ROOT/'software/font_cn.h').read_text(encoding='utf-8'))}
LATIN=[[int(v,16) for v in re.findall(r'0x[0-9a-fA-F]+',row)]
       for row in re.findall(r'\{([^{}]+)\}',(ROOT/'software/font5x7.h').read_text())]
PUNCT={' ':[0]*5,'-':[8]*5,'+':[8,8,62,8,8],'/':[32,16,8,4,2],
       '_':[64]*5,':':[0,20,0,0,0],'.':[0,64,0,0,0]}


def text_width(s,large=False,small=False):
    return sum((28 if large else 14) if ord(ch)>127 else (18 if large else 6 if small else 12) for ch in s)


def text(im,x,y,s,ink='ink',large=False,small=False):
    d=ImageDraw.Draw(im)
    start=x
    for ch in s:
        if ord(ch)>127:
            assert ord(ch) in CN,f'Missing existing glyph: {ch!r}'
            k=2 if large else 1
            for row,bits in enumerate(CN[ord(ch)]):
                for col in range(14):
                    if bits&(1<<col):d.rectangle((x+col*k,y+row*k,x+(col+1)*k-1,y+(row+1)*k-1),fill=c(ink))
            x+=14*k
        else:
            ch=ch.upper()
            n=ord(ch)-48 if '0'<=ch<='9' else ord(ch)-65+10 if 'A'<=ch<='Z' else -1
            columns=LATIN[n] if n>=0 else PUNCT[ch]
            k=3 if large else 1 if small else 2
            oy=4 if large else 0
            for col,bits in enumerate(columns):
                for row in range(7):
                    if bits&(1<<row):d.rectangle((x+col*k,y+oy+row*k,x+(col+1)*k-1,y+oy+(row+1)*k-1),fill=c(ink))
            x+=6*k
    assert 0<=start<=x<=640 and 0<=y and y+(28 if large else 14)<=480,s
    return x-start


def centered(im,cx,y,s,ink='ink',large=False,small=False):
    return text(im,cx-text_width(s,large,small)//2,y,s,ink,large,small)


def grid_art(size,painter):
    im=Image.new('RGBA',size,T)
    painter(ImageDraw.Draw(im),im)
    return im.resize((size[0]*2,size[1]*2),Image.Resampling.NEAREST)


def frost(d,cx,cy,r):
    for pts in ((cx,cy-r,cx,cy+r),(cx-r,cy,cx+r,cy),
                (cx-r+2,cy-r+2,cx+r-2,cy+r-2),(cx-r+2,cy+r-2,cx+r-2,cy-r+2)):
        d.line(pts,fill=c('blue'),width=2)
    d.polygon([(cx,cy-3),(cx+3,cy),(cx,cy+3),(cx-3,cy)],fill=c('ice'))
    d.point((cx,cy),fill=c('page_highlight'))


def curve(d,points,tone='gold',width=1):
    """Rasterize a cubic pen stroke without antialiasing."""
    coords=[]
    for n in range(31):
        t=n/30;u=1-t
        coords.append(tuple(round(u*u*u*points[0][k]+3*u*u*t*points[1][k]+
                                  3*u*t*t*points[2][k]+t*t*t*points[3][k]) for k in (0,1)))
    d.line(coords,fill=c(tone),width=width)


def rune(d,x,y,n,tone='gold',scale=1):
    """Small invented inscription; decorative, never used as UI text."""
    paths=[[(0,6),(0,0),(4,2),(0,4)],[(0,0),(4,3),(0,6),(0,0)],
           [(0,1),(4,1),(2,3),(2,6)],[(0,0),(0,6),(4,6),(4,2),(0,2)],
           [(0,0),(4,4),(0,4),(4,0),(2,6)],[(2,0),(2,6),(0,4),(4,2)],
           [(0,0),(4,0),(0,6),(4,6)],[(0,6),(2,0),(4,6),(0,3),(4,3)]]
    d.line([(x+a*scale,y+b*scale) for a,b in paths[n%len(paths)]],fill=c(tone),width=scale)


def star(d,x,y,r=3,tone='gold_light'):
    d.line((x-r,y,x+r,y),fill=c(tone))
    d.line((x,y-r,x,y+r),fill=c(tone))
    if r>2:d.point((x-1,y-1),fill=c(tone));d.point((x+1,y+1),fill=c(tone))


def medallion(d,cx,cy,r=42,bright=True):
    """Concentric engraved seal with a faceted ice crystal at its center."""
    ring='gold' if bright else 'page_edge'
    light='gold_light' if bright else 'page_edge'
    base='leather_dark' if bright else 'page_light'
    if bright:
        d.ellipse((cx-r-5,cy-r-5,cx+r+5,cy+r+5),fill=c('ink'))
        d.ellipse((cx-r-3,cy-r-3,cx+r+3,cy+r+3),fill=c('gold_dark'))
    d.ellipse((cx-r,cy-r,cx+r,cy+r),outline=c(light))
    d.ellipse((cx-r+3,cy-r+3,cx+r-3,cy+r-3),outline=c(ring))
    inset=max(5,round(r*.25))
    d.ellipse((cx-r+inset,cy-r+inset,cx+r-inset,cy+r-inset),fill=c(base),outline=c(ring))
    for n in range(12):
        a=n*math.pi/6-math.pi/2
        x,y=round(cx+(r-6)*math.cos(a)),round(cy+(r-6)*math.sin(a))
        if n%3 and r>25:rune(d,x-1,y-2,n,ring)
        elif n%3:d.point((x,y),fill=c(ring))
        else:star(d,x,y,2,light)
    rr=round(r*.65)
    pts=[(round(cx+rr*math.cos(-math.pi/2+n*math.pi/3)),round(cy+rr*math.sin(-math.pi/2+n*math.pi/3))) for n in range(6)]
    d.line([pts[n] for n in (0,2,4,0)],fill=c('magic_mid' if bright else 'page_edge'))
    d.line([pts[n] for n in (1,3,5,1)],fill=c('magic_mid' if bright else 'page_edge'))
    if bright:
        for rr,tone in ((round(r*.45),'magic_dark'),(round(r*.35),'magic_mid')):
            d.ellipse((cx-rr,cy-rr,cx+rr,cy+rr),fill=c(tone))
        def gem(points):return [(cx+round(x*r/40),cy+round(y*r/40)) for x,y in points]
        d.polygon(gem([(0,-17),(12,0),(0,17),(-12,0)]),fill=c('ink'))
        d.polygon(gem([(0,-15),(10,0),(0,15),(-10,0)]),fill=c('blue'))
        d.polygon(gem([(0,-14),(0,13),(-9,0)]),fill=c('ice'))
        d.polygon(gem([(0,-14),(7,0),(0,-3),(-7,0)]),fill=c('glow'))
        d.line(gem([(0,1),(7,0)]),fill=c('magic_mid'))
        if r>25:star(d,cx-13,cy-12,3,'glow')


def corner_ornament(d,x,y,sx,sy):
    """One engraved brass corner; mirror it around the cover."""
    def pts(points):return [(x+sx*a,y+sy*b) for a,b in points]
    d.polygon(pts([(0,0),(25,0),(21,4),(13,5),(9,9),(5,13),(4,21),(0,25)]),fill=c('metal_shadow'))
    d.polygon(pts([(1,1),(23,1),(20,3),(12,4),(8,8),(4,12),(3,20),(1,23)]),fill=c('gold'))
    d.line(pts([(2,18),(2,2),(18,2)]),fill=c('gold_light'))
    curve(d,pts([(5,17),(6,2),(23,3),(12,11)]),'gold_dark')
    curve(d,pts([(5,17),(17,19),(18,7),(12,11)]),'gold_dark')
    d.polygon(pts([(6,6),(8,5),(10,8),(8,10),(5,8)]),fill=c('leather_dark'))
    d.point((x+sx*7,y+sy*7),fill=c('gold_light'))


def desk():
    im=Image.new('RGBA',(320,240),c('desk'));d=ImageDraw.Draw(im)
    # A quiet circular spell field replaces the horizontal dashboard-like lines.
    for r in (108,112,137):
        d.ellipse((160-r,122-r,160+r,122+r),outline=c('desk_light'))
    for n in range(16):
        a=n*math.pi/8
        x,y=round(160+123*math.cos(a)),round(122+103*math.sin(a))
        rune(d,x,y,n,'desk_light')
    for x,y,r in ((48,35,2),(262,51,3),(34,174,2),(286,202,2),(67,214,1),(277,116,1)):
        star(d,x,y,r,'magic_mid')
    return im.resize((640,480),Image.Resampling.NEAREST)


def open_base(backdrop=True):
    """Warm curved parchment, layered leaves and a leather-bound spine."""
    im=desk().resize((320,240),Image.Resampling.NEAREST) if backdrop else Image.new('RGBA',(320,240),T)
    d=ImageDraw.Draw(im)
    left=[(7,16),(36,11),(86,9),(128,13),(158,21),(158,224),(128,230),(86,233),(36,231),(7,226)]
    right=[(162,21),(192,13),(234,9),(284,11),(313,16),(313,226),(284,231),(234,233),(192,230),(162,224)]
    for points in (left,right):
        d.polygon([(x+2,y+3) for x,y in points],fill=c('ink'))
        d.polygon(points,fill=c('leather'))
        d.line(points+[points[0]],fill=c('gold_dark'))
    d.rectangle((155,24,165,225),fill=c('leather_dark'))
    for offset,tone in ((6,'page_shadow'),(4,'page_edge'),(2,'page_light'),(0,'page')):
        d.polygon([(12,18),(40,14),(86,12),(128,16),(157,24),(157,216+offset),
                   (128,222+offset),(86,226+offset),(40,224+offset),(12,219+offset)],fill=c(tone))
        d.polygon([(163,24),(192,16),(234,12),(280,14),(308,18),(308,219+offset),
                   (280,224+offset),(234,226+offset),(192,222+offset),(163,216+offset)],fill=c(tone))
    # Page interiors remain quiet enough for exact pixel and alpha demonstrations.
    d.polygon([(16,20),(40,17),(86,15),(128,19),(151,25),(151,214),(128,219),
               (86,223),(40,221),(16,217)],fill=c('page_light'))
    d.polygon([(169,25),(192,19),(234,15),(280,17),(304,20),(304,217),(280,221),
               (234,223),(192,219),(169,214)],fill=c('page_light'))
    for x,tone in ((148,'page_faint'),(151,'page'),(153,'page_edge'),(155,'page_shadow'),
                   (157,'gold_dark'),(159,'brown'),(160,'brown'),(161,'gold_dark'),
                   (163,'page_shadow'),(165,'page_edge'),(167,'page'),(169,'page_faint')):
        curve(d,[(x,25),(x-2 if x<160 else x+2,70),(x-2 if x<160 else x+2,173),(x,215)],tone)
    rng=random.Random(410)
    for _ in range(140):
        x=rng.randrange(18,303);y=rng.randrange(24,216)
        if 147<x<173:continue
        d.point((x,y),fill=c('page_faint'))
    for x0,x1 in ((26,143),(177,294)):
        d.line((x0,42,x1,42),fill=c('page_edge'))
        d.line((x0+6,44,x1-6,44),fill=c('page_faint'))
        mid=(x0+x1)//2
        for x in (mid-5,mid,mid+5):d.polygon([(x,40),(x+2,42),(x,44),(x-2,42)],fill=c('gold'))
        for y in (37,200):
            curve(d,[(x0-5,y+6),(x0-10,y-7),(x0+8,y-5),(x0+2,y+1)],'page_edge')
            curve(d,[(x1+5,y+6),(x1+10,y-7),(x1-8,y-5),(x1-2,y+1)],'page_edge')
        d.line((x0,204,x1,204),fill=c('page_edge'))
    # Edge marginalia, binding stitches, turned corner, and a silk bookmark.
    for y in (56,98,143,184):
        rune(d,18,y,y//10,'page_edge');rune(d,298,y,y//13,'page_edge')
    for y in (32,70,108,146,184,211):d.line((158,y,162,y+1),fill=c('gold'))
    d.polygon([(288,220),(304,206),(304,218)],fill=c('page_shadow'))
    d.polygon([(288,220),(302,206),(299,217)],fill=c('page_highlight'))
    d.line((288,220,302,206),fill=c('page_edge'))
    d.polygon([(239,224),(250,223),(250,239),(245,235),(239,239)],fill=c('ink'))
    d.polygon([(240,224),(249,224),(249,237),(245,233),(240,237)],fill=c('leather'))
    d.line((242,225,242,233),fill=c('gold'))
    return im.resize((640,480),Image.Resampling.NEAREST)


PLAYER=Image.open(ROOT/'assets/player/walk_32.png').convert('RGBA').crop((0,0,32,32))


def hero(im,x,y,k=3):
    im.alpha_composite(PLAYER.resize((32*k,32*k),Image.Resampling.NEAREST),(x,y))


def cover_art(backdrop=True,clasp=True,page_block=True):
    im=desk().resize((320,240),Image.Resampling.NEAREST) if backdrop else Image.new('RGBA',(320,240),T)
    d=ImageDraw.Draw(im)
    silhouette=[(91,16),(221,16),(228,22),(228,205),(221,214),(91,214),(87,210),(87,21)]
    if page_block:
        d.ellipse((85,205,239,223),fill=c('ink'))
        d.polygon([(x+5,y+3) for x,y in silhouette],fill=c('ink'))
        d.polygon([(x+3,y+1) for x,y in silhouette],fill=c('gold_dark'))
        d.rectangle((102,22,232,209),fill=c('page_edge'))
        for y in range(25,209,3):d.line((220,y,231,y),fill=c('page_light' if y%2 else 'page_shadow'))
    d.polygon(silhouette,fill=c('leather_dark'))
    d.polygon([(96,18),(220,18),(225,23),(225,205),(220,211),(96,211),(93,206),(93,23)],fill=c('leather'))
    d.line((96,20,219,20,223,24,223,204),fill=c('leather_light'))
    d.line((96,209,220,209),fill=c('ink'))
    rng=random.Random(122)
    for _ in range(220):
        x=rng.randrange(99,220);y=rng.randrange(24,206)
        d.point((x,y),fill=c('leather_dark' if _%3 else 'leather_light'))
    d.rectangle((88,23,96,207),fill=c('leather_dark'))
    d.line((96,25,96,205),fill=c('gold_dark'))
    for y in (34,71,164,199):
        d.rectangle((88,y,96,y+5),fill=c('ink'))
        d.line((89,y+1,95,y+1),fill=c('gold'))
        d.line((89,y+3,95,y+3),fill=c('gold_dark'))
    d.rectangle((104,29,215,200),outline=c('gold_dark'))
    d.rectangle((107,32,212,197),outline=c('gold'))
    for y in range(39,194,6):
        d.point((101,y),fill=c('gold_dark'));d.point((218,y),fill=c('gold_dark'))
    for x,y,sx,sy in ((101,26,1,1),(218,26,-1,1),(101,203,1,-1),(218,203,-1,-1)):
        corner_ornament(d,x,y,sx,sy)
    # The seal is the cover's focal point, surrounded by engraved vinework.
    for sx in (-1,1):
        curve(d,[(159+sx*7,74),(159+sx*60,68),(159+sx*55,95),(159+sx*43,88)],'gold_dark')
        curve(d,[(159+sx*5,169),(159+sx*58,172),(159+sx*55,148),(159+sx*44,155)],'gold')
        curve(d,[(159+sx*20,170),(159+sx*15,183),(159+sx*44,184),(159+sx*34,174)],'gold_dark')
    medallion(d,159,121,40)
    for y in (84,162):
        d.polygon([(159,y-3),(162,y),(159,y+3),(156,y)],fill=c('gold_light'))
    for n in range(9):rune(d,125+n*8,184,n,'gold')
    # A sculpted clasp connects the fore edge with the embossed cover.
    if clasp:
        d.polygon([(213,111),(229,111),(235,115),(235,125),(229,129),(213,129),(209,125),(209,115)],fill=c('ink'))
        d.polygon([(214,113),(229,113),(233,117),(233,123),(229,127),(214,127),(212,124),(212,116)],fill=c('gold_dark'))
        d.line((214,114,229,114,232,117),fill=c('gold_light'))
        d.polygon([(221,115),(226,120),(221,125),(216,120)],fill=c('leather_dark'))
        d.polygon([(221,116),(224,120),(221,123),(218,120)],fill=c('ice'))
    star(d,124,89,2,'ice');star(d,194,153,2,'ice')
    im=im.resize((640,480),Image.Resampling.NEAREST)
    centered(im,318,90,'二维实验室','gold_light',large=True)
    centered(im,318,128,'FROST GRIMOIRE','gold',small=True)
    centered(im,318,348,'RISC-V + FPGA','gold_light')
    if backdrop:centered(im,320,446,'ENTER 打开','gold_light')
    return im


ICONS={kind:Image.open(PREVIOUS/'png'/('icon_'+kind+'.png')).convert('RGBA')
       for kind in ('basic','advanced','game','fill','copy','buffer','key','alpha','pressure')}
CURSOR=Image.open(PREVIOUS/'png/cursor_0.png').convert('RGBA')
PAGE_BASE=open_base()


def frame(im,rect,fill='page',edge='gold_dark'):
    x,y,w,h=rect
    d=ImageDraw.Draw(im)
    d.polygon([(x+4,y),(x+w-5,y),(x+w-1,y+4),(x+w-1,y+h-5),
               (x+w-5,y+h-1),(x+4,y+h-1),(x,y+h-5),(x,y+4)],fill=c('gold_dark'))
    d.rectangle((x+2,y+2,x+w-3,y+h-3),fill=c(edge))
    d.rectangle((x+4,y+4,x+w-5,y+h-5),fill=c(fill))
    d.line((x+6,y+2,x+w-7,y+2),fill=c('gold_light'))
    for xx,yy,sx,sy in ((x+3,y+3,1,1),(x+w-4,y+3,-1,1),
                       (x+3,y+h-4,1,-1),(x+w-4,y+h-4,-1,-1)):
        d.line((xx,yy+sy*8,xx,yy,xx+sx*8,yy),fill=c('gold'))


def key(im,x,y,label,caption=''):
    w=max(26,len(label)*12+12)
    d=ImageDraw.Draw(im)
    d.rectangle((x,y+1,x+w-1,y+22),outline=c('page_edge'),width=2)
    d.line((x+2,y+23,x+w-2,y+23),fill=c('page_shadow'))
    text(im,x+6,y+5,label,'brown')
    if caption:text(im,x+w+8,y+5,caption,'brown')
    return w


def hint_row(im,x,y,items):
    """Compact keycaps keep instructions inside each leaf's safe area."""
    d=ImageDraw.Draw(im)
    for label,caption in items:
        w=max(18,len(label)*6+8)
        d.rectangle((x,y-2,x+w-1,y+15),outline=c('page_shadow'))
        text(im,x+4,y+3,label,'brown',small=True)
        if caption:text(im,x+w+5,y,caption,'brown')
        x+=w+5+text_width(caption)+10
    assert x<=620,items


def footers(im,left=(('W','选择'),('S','')),right=(('ENTER','打开'),('A','返回')),page=1):
    hint_row(im,46,423,left);hint_row(im,346,423,right)
    text(im,280,448,str(page),'muted',small=True)
    text(im,580,448,str(page+1),'muted',small=True)


def chapter_tabs(im,chapter=0):
    """Numbered cloth tabs identify the three existing sections."""
    d=ImageDraw.Draw(im)
    for n in range(3):
        y=112+n*52;active=n==chapter
        d.polygon([(615,y),(635,y),(639,y+4),(639,y+32),(635,y+36),(615,y+36)],fill=c('gold_dark'))
        d.rectangle((617,y+2,636,y+33),fill=c('leather' if active else 'page_edge'))
        d.line((618,y+3,635,y+3),fill=c('gold_light'))
        text(im,622,y+13,str(n+1).zfill(2),'ice' if active else 'brown',small=True)


def heading(im,left,right,chapter=0):
    centered(im,166,46,left,'brown',large=True)
    centered(im,474,46,right,'brown',large=True)
    chapter_tabs(im,chapter)


def ornament(im,cx=166,cy=237):
    half=Image.new('RGBA',(320,240),T);d=ImageDraw.Draw(half)
    medallion(d,cx//2,cy//2,39,bright=False)
    for sx in (-1,1):
        curve(d,[(cx//2+sx*5,cy//2+46),(cx//2+sx*41,cy//2+61),
                 (cx//2+sx*55,cy//2+37),(cx//2+sx*43,cy//2+35)],'page_edge')
    im.alpha_composite(half.resize((640,480),Image.Resampling.NEAREST))


def entry(im,x,y,title,detail,icon,active=False,width=254):
    d=ImageDraw.Draw(im)
    if active:
        d.polygon([(x+8,y),(x+width-9,y),(x+width-1,y+8),(x+width-1,y+65),
                   (x+width-9,y+73),(x+8,y+73),(x,y+65),(x,y+8)],fill=c('page_edge'))
        d.rectangle((x+4,y+4,x+width-5,y+69),fill=c('select'))
        for xx,sx in ((x+6,1),(x+width-7,-1)):
            d.line((xx,y+16,xx,y+6,xx+sx*12,y+6),fill=c('gold_dark'),width=2)
            d.line((xx,y+57,xx,y+67,xx+sx*12,y+67),fill=c('gold_dark'),width=2)
        d.line((x+20,y+2,x+width-21,y+2),fill=c('gold'))
        im.alpha_composite(CURSOR,(x-16,y+26))
    else:
        d.line((x+12,y+74,x+width-13,y+74),fill=c('page_edge'))
        d.polygon([(x+width//2,y+72),(x+width//2+2,y+74),
                   (x+width//2,y+76),(x+width//2-2,y+74)],fill=c('gold'))
    im.alpha_composite(icon,(x+12,y+20))
    text(im,x+56,y+11,title,'leather_dark' if active else 'brown',large=text_width(title,large=True)<=width-62)
    text(im,x+56,y+49,detail,'brown' if active else 'muted',small=text_width(detail)>width-62)


MENU={
    'home':[('基础演示','绘制 / 复制 / 缓冲','basic'),('高阶演示','颜色键 / 透明混合','advanced'),('冰霜幸存者','生存360秒','game')],
    'basic':[('矩形填充','RGB565 硬件填充','fill'),('图像复制','256 X 192 图像','copy'),('双缓冲','垂直消隐交换','buffer')],
    'advanced':[('颜色键','匹配色跳过写入','key'),('透明混合','前景与背景混合','alpha'),('SPRITE压力','ALPHA + COLOR KEY','pressure')]
}
MENU_CAPTIONS={
    'fill':('32 X 24 RGB565','CPU / FPGA'),
    'copy':('256 X 192 RGB565','DDR 图像复制'),
    'buffer':('VBLANK / DOUBLE BUFFER','单缓冲与双缓冲'),
    'key':('COLOR KEY / RGB565','黑色 / 品红色'),
    'alpha':('ALPHA / 0 - 255','透明度越大 越透明'),
    'pressure':('SPRITE / 32 X 32','FPGA 硬件绘制')
}


def menu(group,selected):
    im=PAGE_BASE.copy()
    heading(im,{'home':'二维实验室','basic':'基础演示','advanced':'高阶演示'}[group],
            '选择演示' if group=='home' else '选择功能',0 if group!='advanced' else 1)
    title,detail,kind=MENU[group][selected]
    centered(im,166,110,'INDEX' if group=='home' else 'BASIC' if group=='basic' else 'ARCANA','muted',small=True)
    ornament(im)
    if group=='home':
        hero(im,118,192,3)
        centered(im,166,336,title,'brown')
        centered(im,166,365,'RISC-V + FPGA','muted',small=True)
    else:
        icon=ICONS[kind].resize((96,96),Image.Resampling.NEAREST)
        im.alpha_composite(icon,(118,190))
        hero(im,214,280,2)
        line1,line2=MENU_CAPTIONS[kind]
        centered(im,166,344,line1,'muted',small=True)
        centered(im,166,370,line2,'brown')
    for n,(label,subtitle,option) in enumerate(MENU[group]):
        entry(im,342,126+n*88,label,subtitle,ICONS[option],n==selected)
    footers(im,page={'home':1,'basic':3,'advanced':5}[group])
    return im


def metric_tile(im,x,y,label,value='--',w=108):
    d=ImageDraw.Draw(im)
    d.rectangle((x,y,x+w-1,y+74),fill=c('page_faint'))
    d.line((x,y,x+w-1,y),fill=c('page_edge'))
    text(im,x+8,y+10,label,'muted',small=True)
    centered(im,x+w//2,y+34,value,'leather_dark',large=True)


def engine_badge(im,x,y,label='FPGA'):
    d=ImageDraw.Draw(im);w=len(label)*6+16
    d.rectangle((x,y,x+w,y+18),fill=c('leather'))
    text(im,x+8,y+6,label,'gold_light',small=True)


def demo_base(title,kind):
    """Fullscreen demo shell; no parchment, spine, book corners or page tabs."""
    im=Image.new('RGBA',(640,480),c('ink'));d=ImageDraw.Draw(im)
    d.rectangle((0,0,639,43),fill=c('leather_dark'))
    d.line((0,44,639,44),fill=c('gold_dark'))
    im.alpha_composite(ICONS[kind],(16,6))
    text(im,60,9,title,'page_highlight',large=True)
    engine_badge(im,554,13)
    d.line((16,416,623,416),fill=c('leather_light'))
    return im


def demo_footer(im,line1,line2):
    text(im,16,430,line1,'page_highlight');text(im,16,454,line2,'ice')


def demo_window(im,rect,bg=0x084b):
    x,y,w,h=rect;d=ImageDraw.Draw(im)
    d.rectangle((x-3,y-3,x+w+2,y+h+2),outline=c('stone'))
    d.rectangle((x,y,x+w-1,y+h-1),fill=(*expand(bg),255))


def compare_metrics(im,op):
    d=ImageDraw.Draw(im)
    for x,label in ((16,'CPU'),(336,'FPGA')):
        d.rectangle((x,54,x+287,140),fill=c('desk'))
        engine_badge(im,x+8,60,label)
        for n,name in enumerate(('FPS',op,'RENDER_US')):
            text(im,x+72,62+n*26,name,'page_highlight')
            text(im,x+246,62+n*26,'--','gold_light')
    text(im,16,148,'SPEEDUP --','ice');text(im,336,148,'MB/S --','ice')


def seed32(n):
    value=((n+1)*0x9e3779b9)&0xffffffff
    value^=(value<<13)&0xffffffff;value^=value>>17;value^=(value<<5)&0xffffffff
    return value&0xffffffff


def bounce(value,limit):
    value%=limit*2
    return limit*2-value if value>limit else value


def demo_fill(detail=False):
    im=demo_base('矩形填充','fill');compare_metrics(im,'FILL_US')
    d=ImageDraw.Draw(im)
    if detail:
        for n,label in enumerate(('AR','AW','RD WAIT','WR WAIT','LOAD')):
            text(im,20,184+n*36,label,'page_highlight');text(im,240,184+n*36,'8' if label=='LOAD' else '--','gold_light')
        demo_window(im,(352,176,256,192))
    else:demo_window(im,(16,176,608,224))
    for n in range(8):
        seed=seed32(n);x=16+2*bounce(seed&65535,288);y=176+bounce(seed>>16,200)
        if detail:x=352+(x-16)%224;y=176+(y-176)%168
        d.rectangle((x,y,x+31,y+23),fill=(*expand((0x07ff,0xffe0,0xf81f,0x07e0,0xf800,0x001f)[n%6]),255))
    if detail:text(im,20,388,'AXI MAX 16 X 32BIT','stone')
    if not detail:text(im,16,402,'LOAD 8 / 32 X 24','stone',small=True)
    demo_footer(im,'W方块数量  D换色  ENTER'+('图像' if detail else '详情'),'S切换 CPU/FPGA  A返回')
    return im


def image_sample(image=0):
    # Exact procedural test picture from basic_demo_data.h, kept at 256x192.
    im=Image.new('RGBA',(256,192))
    for y in range(192):
        for x in range(256):
            if not image:
                r,g,b=3+y//20,24+y//8,31-y//14
                if (x-198)**2+(y-42)**2<19**2:r,g,b=31,56,8
                if y>96+(x if x<128 else 255-x)//3:r,g,b=4,30+(x//16)%12,9
                if y>151:r,g,b=7+(x//16)%5,38+(y//8)%12,12
                if y>160 and x>112-(y-160)//2 and x<144+(y-160)//2:r,g,b=22,43,18
            else:
                r,g,b=2,5+y//12,12+y//12
                height=45+((x//32)*23)%90
                if x%32<27 and y>182-height:
                    r,g,b=5,9,13
                    if x%8>2 and y%12>4:r,g,b=31,43,7
                if y>182:r,g,b=10,12,18
            value=(r<<11)|(g<<5)|b
            if x<3 or x>=253 or y<3 or y>=189:value=0xf81f if image else 0x07ff
            elif 10<=x<34 and 10<=y<46:
                px,py=x-10,y-10
                mark=(10<=px<15) if not image else (py<5 or 16<=py<21 or py>=31 or (px>=19 if py<18 else px<5))
                value=0xffff if mark else 0x0843
            im.putpixel((x,y),(*expand(value),255))
    return im


COPY_IMAGES=[image_sample(0),image_sample(1)]


def demo_copy(detail=False,image=0):
    im=demo_base('图像复制','copy');compare_metrics(im,'COPY_US')
    if detail:
        for n,label in enumerate(('AR','AW','RD WAIT','WR WAIT','LOAD')):
            text(im,20,184+n*36,label,'page_highlight');text(im,240,184+n*36,'1' if label=='LOAD' else '--','gold_light')
    else:
        demo_window(im,(32,176,256,192));im.alpha_composite(COPY_IMAGES[image],(32,176))
    demo_window(im,(352,176,256,192));im.alpha_composite(COPY_IMAGES[image],(352,176))
    text(im,32,390,'图像 '+str(image+1),'stone');text(im,352,390,'256 X 192 RGB565','stone')
    demo_footer(im,'W复制次数  D换图  ENTER'+('图像' if detail else '详情'),'S切换 CPU/FPGA  A返回')
    return im


def demo_buffer(mode=0,paused=False):
    im=demo_base('双缓冲','buffer')
    text(im,16,56,'双缓冲 / 后台绘制后换页' if mode else '单缓冲 / 扫描中写前台','ice')
    for x,items in ((16,(('SWAPS','--'),('WAIT_US','--'),('OUT_HZ','--'))),
                    (336,(('MISSED','--'),('PAUSED','YES' if paused else 'NO'),('STEP','8')))):
        for n,(label,value) in enumerate(items):
            text(im,x,84+n*26,label,'page_highlight');text(im,x+160,84+n*26,value,'gold_light')
    demo_window(im,(16,176,608,224))
    d=ImageDraw.Draw(im)
    for y in range(200,400,40):d.line((16,y,623,y),fill=(*expand(0x7bef),255),width=2)
    for x in (120,216,312):d.rectangle((x,184,x+23,391),fill=(*expand(0xffff),255))
    demo_footer(im,'W切换速度  S切换模式  ENTER'+('继续' if paused else '暂停'),'D参考线  A返回')
    return im


def effects(kind,transparency=128,enabled=1,background=0,key_index=0):
    im=demo_base('颜色键' if kind=='key' else '透明混合',kind)
    if kind=='alpha':
        text(im,24,60,'透明度 '+str(transparency)+'/255','page_highlight')
        text(im,328,60,'前景权重 '+str(255-transparency)+'/255','ice')
        text(im,24,92,'前景与背景混合  透明度越大 越透明','stone')
    else:
        text(im,24,60,'透明色 '+('品红色 F81F' if key_index else '黑色 0000'),'page_highlight')
        text(im,328,60,'颜色键开' if enabled else '颜色键关','ice')
        text(im,24,92,'匹配透明色的像素跳过写入','stone')
    text(im,24,124,'采样像素核对 --/8','gold_light')
    text(im,48,164,'不透明参考' if kind=='alpha' else '原图 颜色键关','page_highlight')
    text(im,352,164,'硬件混合结果' if kind=='alpha' else '颜色键开' if enabled else '颜色键关','page_highlight')
    for panel,left in enumerate((48,352)):
        demo_window(im,(left,192,240,192))
        for yy in range(192):
            for xx in range(240):
                cell=((xx//16)^(yy//16))&1
                bg=(0x7bef if cell else 0x2945) if background else (0x0514 if cell else 0xfca0)
                value=bg
                if 56<=xx<184 and 32<=yy<160:
                    x,y=xx-56,yy-32
                    fg=(0xf81f if key_index else 0) if abs(x-63)+abs(y-63)>60 else 0x07ff if y<43 else 0xf800 if y<86 else 0xffe0
                    if not panel or kind=='key' and not enabled:value=fg
                    elif kind=='key':value=bg if fg==(0xf81f if key_index else 0) else fg
                    else:
                        alpha=255-transparency
                        r=(((fg>>11)&31)*alpha+((bg>>11)&31)*transparency+127)//255
                        g=(((fg>>5)&63)*alpha+((bg>>5)&63)*transparency+127)//255
                        b=((fg&31)*alpha+(bg&31)*transparency+127)//255
                        value=(r<<11)|(g<<5)|b
                im.putpixel((left+xx,192+yy),(*expand(value),255))
    demo_footer(im,'W透明度+5  D透明度-5' if kind=='alpha' else 'W开关去背  D切换透明色',
                'ENTER预设  S换背景  A返回' if kind=='alpha' else 'S换背景  A返回')
    return im


GAME_RAW=(ROOT/'assets/game/game.rgb565').read_bytes()
GAME_SPRITES={}
for index in range(16,len(GAME_RAW)//2048):
    sprite=Image.new('RGBA',(32,32),T)
    for n,value in enumerate(struct.unpack_from('<1024H',GAME_RAW,index*2048)):
        if value:sprite.putpixel((n%32,n//32),(*expand(value),255))
    GAME_SPRITES[index]=sprite


def pressure(count=31):
    im=demo_base('SPRITE压力','pressure');d=ImageDraw.Draw(im)
    for x,label,value in ((16,'SPRITES',str(count)),(234,'FPS','--'),(440,'MAX60','--')):
        text(im,x,60,label,'page_highlight');text(im,x,88,value,'gold_light',large=True)
    text(im,16,126,'SIZE 32 X 32','stone');text(im,336,126,'DDR RD/WR --/--','stone')
    demo_window(im,(0,152,640,256),0x0843)
    for n in range(count):
        seed=seed32(n);x=8+bounce(seed&65535,600);y=160+bounce(seed>>16,208)
        im.alpha_composite(GAME_SPRITES[19],(x,y))
    demo_footer(im,'W加5  S减5  长按连发','D换尺寸  A返回')
    return im


def bar(im,rect,value,maximum,tone):
    x,y,w,h=rect;d=ImageDraw.Draw(im)
    d.rectangle((x,y,x+w-1,y+h-1),fill=c('leather_dark'),outline=c('gold_dark'))
    fill=round((w-4)*value/maximum)
    if fill:
        d.rectangle((x+2,y+2,x+1+fill,y+h-3),fill=c(tone))
        d.line((x+2,y+2,x+1+fill,y+2),fill=c('gold_light' if tone=='red' else 'ice'))


def game_panel(im,rect,selected=False):
    frame(im,rect,'leather_dark','blue' if selected else 'leather_light')


def skill_image(index,size=96):
    source=GAME_SPRITES[index];source=source.crop(source.getbbox())
    maximum=64 if size>32 else 24;k=max(1,min(maximum//source.width,maximum//source.height))
    source=source.resize((source.width*k,source.height*k),Image.Resampling.NEAREST)
    image=Image.new('RGBA',(size,size),T);image.alpha_composite(source,((size-source.width)//2,(size-source.height)//2))
    return image


def game_illustration(im,icon=None):
    half=Image.new('RGBA',(320,240),T);d=ImageDraw.Draw(half);cx,cy=83,120
    for r,tone in ((48,'magic_dark'),(45,'magic_mid'),(36,'blue')):
        d.ellipse((cx-r,cy-r,cx+r,cy+r),outline=c(tone))
    for n in range(12):
        angle=n*math.pi/6
        rune(d,round(cx+41*math.cos(angle))-2,round(cy+41*math.sin(angle))-3,n,'magic_mid')
    for x in (52,114):star(d,x,156,2,'gold')
    im.alpha_composite(half.resize((640,480),Image.Resampling.NEAREST))
    if icon is None:hero(im,118,192,3)
    else:im.alpha_composite(icon,(118,192))


def game_entry(im,y,title,detail,icon,active=False):
    game_panel(im,(342,y,254,76),active)
    im.alpha_composite(icon,(354,y+20))
    text(im,398,y+11,title,'ice' if active else 'page_highlight',large=True)
    text(im,398,y+49,detail,'gold_light' if active else 'stone')
    if active:im.alpha_composite(CURSOR,(326,y+26))


def game_footer(im,left,right):
    ImageDraw.Draw(im).line((16,444,623,444),fill=c('leather_light'))
    text(im,16,456,left,'page_highlight');text(im,352,456,right,'ice')


def game_field(im):
    # Match GAME_BACKGROUND_COLOR: a solid fill needs no background bitmap.
    # Preserve the firmware's original 624x360 camera viewport.
    field=Image.new('RGBA',(624,360),(*expand(0x1085),255))
    field.alpha_composite(PLAYER,(296,164))
    for index,x,y in ((16,108,82),(17,484,126),(18,188,268),(24,536,272),(25,408,220)):
        field.alpha_composite(GAME_SPRITES[index],(x,y))
    for index,x,y in ((19,188,40),(19,354,284),(33,240,306),(34,510,46)):
        field.alpha_composite(GAME_SPRITES[index],(x,y))
    field.alpha_composite(GAME_SPRITES[21],(360,164))
    im.alpha_composite(field,(8,80))


def game(state='play',choice=0):
    im=demo_base('' if state in ('play','paused') else '冰霜幸存者' if state=='ready' else '选择强化' if state=='upgrade' else '你已生存' if state=='won' else '游戏结束','game')
    if state in ('play','paused'):
        text(im,60,14,'冰霜幸存者','page_highlight')
        im.alpha_composite(GAME_SPRITES[23].resize((16,16),Image.Resampling.NEAREST),(200,12))
        bar(im,(226,16,144,12),100,100,'red');text(im,390,14,'100','page_highlight')
        text(im,476,14,'00:30','gold_light')
        text(im,16,54,'等级02','page_highlight');bar(im,(108,56,168,12),18,30,'blue')
        text(im,300,54,'18/30','stone');text(im,396,54,'击杀51','page_highlight');text(im,518,54,'FPS --','ice')
        game_field(im)
        if state=='paused':
            shade=Image.new('RGBA',(640,480),(7,10,21,110));im=Image.alpha_composite(im,shade)
            game_panel(im,(100,178,440,174),True)
            centered(im,320,194,'已暂停','page_highlight',large=True)
            centered(im,320,248,'ENTER 继续游戏','ice');centered(im,320,284,'A 返回菜单','gold_light')
            game_footer(im,'A 返回菜单','ENTER 继续')
        else:game_footer(im,'W/S/A/D 移动','ENTER 暂停')
    elif state=='upgrade':
        game_illustration(im,skill_image((20,22,21)[choice]))
        names=('奥术强化','快速施法','冰霜法环');details=('伤害+1','更快施法','法环更多');indices=(20,22,21)
        centered(im,320,70,'LEVEL UP / 03','gold_light')
        centered(im,166,344,names[choice],'ice');centered(im,166,374,details[choice],'stone')
        for n in range(3):game_entry(im,126+n*88,names[n],details[n],skill_image(indices[n],32),n==choice)
        game_footer(im,'W/S 选择强化','D 暂停  ENTER 选择')
    elif state=='ready':
        game_illustration(im)
        centered(im,320,70,'FROST SURVIVOR','gold_light')
        for n,(label,value) in enumerate((('时间','360秒'),('技能','自动释放'),('移动','W/S/A/D'))):
            y=128+n*64;text(im,356,y,label,'stone');text(im,438,y,value,'page_highlight')
            ImageDraw.Draw(im).line((354,y+36,586,y+36),fill=c('magic_dark'))
        centered(im,166,344,'生存360秒','ice');centered(im,166,374,'技能自动释放','stone')
        game_entry(im,330,'开始游戏','ENTER',ICONS['game'],True)
        game_footer(im,'A 返回菜单','ENTER 开始')
    else:
        won=state=='won';game_illustration(im)
        centered(im,320,70,'VICTORY' if won else 'END OF RUN','gold_light' if won else 'red')
        centered(im,166,344,'生存360秒' if won else '冰霜幸存者','ice')
        for n,(label,value) in enumerate((('时间','06:00' if won else '00:30'),('击杀','--'),('等级','--'))):
            y=128+n*66;text(im,356,y,label,'stone');text(im,476,y,value,'gold_light')
            ImageDraw.Draw(im).line((354,y+38,586,y+38),fill=c('magic_dark'))
        game_entry(im,330,'再来一局','ENTER',ICONS['game'],True)
        game_footer(im,'A 返回菜单','ENTER 开始')
    return im


SCREENS={'cover':cover_art()}
for group in MENU:
    for n in range(3):SCREENS[f'{group}_{n}']=menu(group,n)
SCREENS.update({'fill':demo_fill(),'fill_detail':demo_fill(True),'copy':demo_copy(),'copy_2':demo_copy(image=1),
                'copy_detail':demo_copy(True),'buffer':demo_buffer(),'buffer_double':demo_buffer(1),
                'buffer_paused':demo_buffer(0,True),'buffer_double_paused':demo_buffer(1,True),
                'key':effects('key'),'key_off':effects('key',enabled=0),'key_magenta':effects('key',key_index=1),
                'alpha':effects('alpha',transparency=255),'alpha_0':effects('alpha',transparency=0),
                'alpha_128':effects('alpha',transparency=128),'pressure':pressure(),'pressure_1':pressure(1)})
for state in ('ready','play','paused','upgrade','over','won'):SCREENS['game_'+state]=game(state)
for choice in (1,2):SCREENS['game_upgrade_'+str(choice)]=game('upgrade',choice)
for name,im in SCREENS.items():im.convert('RGB').save(OUT/'previews'/f'{name}.png')


def opening_frames():
    return create_opening_frames(desk(),SCREENS['cover'],cover_art(clasp=False),
        cover_art(False,clasp=False,page_block=False),PAGE_BASE,SCREENS['home_0'],
        open_base(False).getchannel('A'))


OPENING,OPENING_TIMING=opening_frames()
# Retire only this generator's earlier two-digit exports before writing numbered frames.
for old_frame in (OUT/'animation_smooth').glob('open_??.png'):
    if re.fullmatch(r'open_\d{2}\.png',old_frame.name):old_frame.unlink()
for n,im in enumerate(OPENING):im.convert('RGB').save(OUT/'animation_smooth'/f'open_{n:03d}.png')
# Use one shared palette for the entire GIF, avoiding frame-by-frame color flicker.
palette_sample=Image.new('RGB',(640*4,480*3))
for i,n in enumerate(round(i*(FRAME_COUNT-1)/11) for i in range(12)):
    palette_sample.paste(OPENING[n].convert('RGB'),((i%4)*640,(i//4)*480))
gif_palette=palette_sample.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
gif_frames=[im.convert('RGB').quantize(palette=gif_palette,dither=Image.Dither.NONE) for im in OPENING]
gif_frames[0].save(OUT/'打开魔法书.gif',save_all=True,append_images=gif_frames[1:],
                duration=[600]+[FRAME_MS]*(FRAME_COUNT-2)+[1500],loop=0,disposal=1,optimize=False)
(OUT/'打开魔法书_流畅版.gif').write_bytes((OUT/'打开魔法书.gif').read_bytes())
(OUT/'source/opening_timing.json').write_text(json.dumps({
    'frame_count':FRAME_COUNT,'frame_ms':FRAME_MS,'motion_ms':(FRAME_COUNT-1)*FRAME_MS,
    'phases':{'unlock':[0,.16],'cover':[.12,.76],'following_leaf':[.28,.90],'settle':[.90,1]},
    'samples':OPENING_TIMING},indent=2),encoding='utf-8')

# Individual tiles provide an implementation path without storing all preview frames.
ASSETS=[]


def asset(name,im,role,margin=0):
    ASSETS.append({'name':name,'image':im,'role':role,'margin':margin})


for kind,im in ICONS.items():asset('icon_'+kind,im,'icon')
for n in range(4):
    asset('cursor_'+str(n),Image.open(PREVIOUS/'png'/f'cursor_{n}.png').convert('RGBA'),'cursor')
for state in ('normal','selected','pressed','disabled'):
    tile=Image.new('RGBA',(48,48),T)
    fill={'normal':'page_light','selected':'select','pressed':'page','disabled':'page'}[state]
    frame(tile,(0,0,48,48),fill,'gold' if state=='selected' else 'page_edge')
    asset('card_'+state,tile,'nine_slice',12)


def seal(d,im):medallion(d,18,18,12)


def bookmark(d,im):
    d.polygon([(0,0),(9,0),(9,23),(5,19),(0,23)],fill=c('ink'))
    d.polygon([(1,0),(8,0),(8,21),(5,18),(1,21)],fill=c('leather'))
    d.line((2,1,2,17),fill=c('gold'))
    d.polygon([(5,7),(7,10),(5,13),(3,10)],fill=c('ice'))


asset('frost_seal',grid_art((36,36),seal),'emblem')
asset('bookmark',grid_art((10,24),bookmark),'decoration')


def parchment(d,im):
    d.rectangle((0,0,15,15),fill=c('page_light'))
    d.line((3,5,4,5),fill=c('page_faint'))
    d.point((12,11),fill=c('page_faint'))


def leather(d,im):
    d.rectangle((0,0,15,15),fill=c('leather'))
    for x,y in ((3,3),(11,11),(8,6)):d.point((x,y),fill=c('leather_dark'))
    d.point((12,3),fill=c('leather_light'))


def corner(d,im):
    corner_ornament(d,0,0,1,1)


def page_corner(d,im):
    d.polygon([(0,15),(15,0),(15,15)],fill=c('page_shadow'))
    d.polygon([(1,14),(14,1),(14,14)],fill=c('page_highlight'))
    d.line((1,14,14,1),fill=c('gold'))


def spine(d,im):
    for x,tone in enumerate(('page','page_edge','page_shadow','brown','ink','brown','page_shadow','page_edge')):
        d.line((x,0,x,31),fill=c(tone))


asset('parchment_tile',grid_art((16,16),parchment),'tile')
asset('leather_tile',grid_art((16,16),leather),'tile')
asset('cover_corner',grid_art((26,26),corner),'corner')
asset('page_curl',grid_art((16,16),page_corner),'corner')
asset('spine_strip',grid_art((8,32),spine),'tile')
for state in ('normal','active'):
    tab=Image.new('RGBA',(24,40),T);d=ImageDraw.Draw(tab)
    d.polygon([(0,0),(19,0),(23,4),(23,35),(19,39),(0,39)],fill=c('gold_dark'))
    d.rectangle((2,2,20,37),fill=c('leather' if state=='active' else 'page_edge'))
    d.line((3,3,19,3),fill=c('gold_light'))
    asset('chapter_tab_'+state,tab,'tab')
for tone in ('red','blue'):
    meter=Image.new('RGBA',(48,12),T)
    bar(meter,(0,0,48,12),1,1,tone)
    asset('meter_'+tone,meter,'horizontal_bar',4)

# A deterministic scan pack keeps every sprite aligned to an even coordinate.
atlas=Image.new('RGBA',(256,256),T)
occupied=[]
for a in sorted(ASSETS,key=lambda a:(-a['image'].height,-a['image'].width,a['name'])):
    w,h=a['image'].size
    placed=False
    for y in range(2,255-h,2):
        for x in range(2,255-w,2):
            if not any(x<ox+ow+2 and x+w+2>ox and y<oy+oh+2 and y+h+2>oy for ox,oy,ow,oh in occupied):
                a['rect']=[x,y,w,h];occupied.append((x,y,w,h));atlas.alpha_composite(a['image'],(x,y));placed=True;break
        if placed:break
    assert placed,a['name']


def raw565(im):
    pixels=[];raw=im.convert('RGBA').tobytes()
    for at in range(0,len(raw),4):
        r,g,b,a=raw[at:at+4]
        assert a in (0,255)
        pixels.append(to565((r,g,b)) if a else 0)
    return pixels,struct.pack('<'+'H'*len(pixels),*pixels)


atlas.save(OUT/'book_ui_atlas.png')
pixels,data=raw565(atlas);(OUT/'book_ui_atlas.rgb565').write_bytes(data)
for a in ASSETS:
    a['image'].save(OUT/'png'/f'{a["name"]}.png')
    (OUT/'rgb565'/f'{a["name"]}.rgb565').write_bytes(raw565(a['image'])[1])
PAGE_BASE.save(OUT/'spread_background.png')
(OUT/'spread_background.rgb565').write_bytes(raw565(PAGE_BASE)[1])
cover_image=cover_art(False)
cover_bounds=cover_image.getbbox()
cover_layer=cover_image.crop(cover_bounds)
cover_layer.save(OUT/'cover_layer.png')
(OUT/'cover_layer.rgb565').write_bytes(raw565(cover_layer)[1])
open_layer=open_base(False)
open_layer.save(OUT/'open_book_layer.png')
(OUT/'open_book_layer.rgb565').write_bytes(raw565(open_layer)[1])
desk().save(OUT/'desk_background.png')

# A common 16-bit RLE token, extended to six-bit palette indices for both themes.
palette=[0]+sorted(set(pixels)-{0});assert len(palette)<=64
lookup={v:i for i,v in enumerate(palette)};tokens=[];at=0
while at<len(pixels):
    end=at+1
    while end<len(pixels) and pixels[end]==pixels[at] and end-at<1023:end+=1
    tokens.append(((end-at)<<6)|lookup[pixels[at]]);at=end
decoded=[]
for token in tokens:decoded.extend([palette[token&63]]*(token>>6))
assert decoded==pixels
(OUT/'embedded/book_palette.rgb565').write_bytes(struct.pack('<'+'H'*len(palette),*palette))
(OUT/'embedded/book_rle.bin').write_bytes(struct.pack('<'+'H'*len(tokens),*tokens))


def array(name,values):
    return f'static const uint16_t {name}[{len(values)}] = {{\n'+'\n'.join(
        '    '+','.join(f'0x{v:04x}' for v in values[n:n+12])+',' for n in range(0,len(values),12))+'\n};'


header=['/* Generated magic-book component atlas; not integrated into firmware. */',
        '#ifndef BOOK_UI_ASSETS_H','#define BOOK_UI_ASSETS_H','#include <stdint.h>',
        '#define BOOK_UI_ATLAS_WIDTH 256u','#define BOOK_UI_ATLAS_HEIGHT 256u',
        '#define BOOK_UI_STRIDE 512u','#define BOOK_UI_COLOR_KEY 0u',
        '/* RLE token: length=token>>6, palette index=token&63. */',
        array('book_ui_palette',palette),array('book_ui_rle',tokens),
        'typedef struct { uint16_t x,y,w,h; uint8_t margin; } BookUiRect;','enum {']
for i,a in enumerate(ASSETS):header.append(f'    BOOK_UI_{a["name"].upper()} = {i},')
header+=['    BOOK_UI_COUNT','};','static const BookUiRect book_ui_rects[BOOK_UI_COUNT] = {']
for a in ASSETS:header.append('    {'+','.join(str(v) for v in [*a['rect'],a['margin']])+'}, // '+a['name'])
header+=['};','#endif','']
(OUT/'embedded/book_ui_assets.h').write_text('\n'.join(header),encoding='utf-8')

LAYOUT={
    'canvas':[640,480],'book_bounds':[14,18,622,462],
    'cover_layer':{'origin':list(cover_bounds[:2]),'size':list(cover_layer.size),'color_key':0},
    'open_book_layer':{'origin':[0,0],'size':[640,480],'color_key':0},
    'left_page_safe':[42,48,256,354],'right_page_safe':[342,48,256,354],
    'gutter_reserved':[300,42,40,366],
    'navigation':['cover','home','basic / advanced','demo or game'],
    'controls':{'cover':'Enter opens the book','menu':'W/S select; Enter opens; A returns',
                'home_back':'A closes the book in both firmware and prototype'},
    'game_view_proposal':[8,80,624,360],
    'game_view_current':[8,80,624,360],
    'game_layout_note':'Original fullscreen viewport retained. New HUD art is a proposal; solid background and frost sprites are implemented in firmware.',
    'game_art':{'style':'frost_pixel_v1','runtime_frames':len(GAME_RAW)//2048,
                'runtime_bytes':len(GAME_RAW),'background_texture_bytes':0},
    'game_background':{'mode':'solid_fill','rgb565':0x1085,'texture_bytes':0,
                       'removed_ddr_bytes':434176+16384+32768,
                       'note':'Firmware also skips scenery/tile loading and wall rendering. Original source assets are preserved.'},
    'book_views':['cover','home','basic','advanced'],
    'fullscreen_demo_views':['fill','copy','buffer','key','alpha','pressure'],
    'demo_regions':{'copy_source':[32,176,256,192],'copy_result':[352,176,256,192],
                    'effect_left':[48,192,240,192],'effect_right':[352,192,240,192],
                    'fill_and_buffer':[16,176,608,224],'pressure':[0,152,640,256]},
    'fullscreen_game_views':['game_ready','game_play','game_paused','game_upgrade','game_over','game_won'],
    'cross_spread_views':[],
    'cross_spread_note':'Only the cover and menus use a book. All demos and all game states are fullscreen.',
    'opening':{'frames':FRAME_COUNT,'step_ms':FRAME_MS,'motion_ms':(FRAME_COUNT-1)*FRAME_MS,
               'frame_directory':'animation_smooth',
               'render_strategy':'Reference animation only. Separate cover, body, curved leaf and clasp. Do not keep all full-screen frames in DDR.'},
    'fonts':'Existing font_cn.h and font5x7.h; large titles and hero previews use nearest integer scaling.'
}
runtime_path=OUT/'runtime/manifest.json'
runtime_menu=json.loads(runtime_path.read_text(encoding='utf-8')) if runtime_path.exists() else None
menu_integrated=runtime_menu is not None and '#include "book_menu.h"' in (ROOT/'software/main.c').read_text(encoding='utf-8')
LAYOUT['runtime_menu_integrated']=menu_integrated
LAYOUT['runtime_demo_skin_integrated']=(ROOT/'software/demo_skin.h').exists()
(OUT/'layout.json').write_text(json.dumps(LAYOUT,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'source/theme.json').write_text(json.dumps(THEME,ensure_ascii=False,indent=2),encoding='utf-8')
MANIFEST={
    'name':'magic_book_v5','version':5,'canvas':[640,480],
    'runtime_integrated':False,'screens':list(SCREENS),'opening_frames':len(OPENING),
    'atlas':{'size':[256,256],'stride':512,'raw_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()},
    'embedded':{'palette_colors':len(palette),'rle_bytes':len(tokens)*2,'descriptor_bytes':len(ASSETS)*10,
                'c_data_bytes':len(palette)*2+len(tokens)*2+len(ASSETS)*10,'rle_shift':6,'rle_mask':63,
                'excluded':'Full-screen background, cover/open book layers, preview frames, new drawing code and original player are not part of this C data size.'},
    'assets':[{'id':i,'name':a['name'],'rect':a['rect'],'margin':a['margin'],'role':a['role']} for i,a in enumerate(ASSETS)],
    'source_player_sha256':hashlib.sha256((ROOT/'assets/player/walk_32.png').read_bytes()).hexdigest(),
    'sources':{'new_art':'Original pixel book shapes and ornaments; no AI image generation service used.',
               'reuse':'Original player/game art and menu_pixel_v2 component PNGs; original rights apply. Game background textures are unused.'},
    'checks':{'rle_roundtrip':True,'binary_alpha':True,'existing_font_glyphs':True},
    'performance_values':'-- denotes unmeasured; game counters are visual fixtures, not hardware results.'
}
MANIFEST['runtime_menu_integrated']=menu_integrated
MANIFEST['runtime_demo_skin_integrated']=(ROOT/'software/demo_skin.h').exists()
if menu_integrated:
    MANIFEST['runtime_menu']=runtime_menu
    MANIFEST['runtime_scope']='Cover, menus and six fullscreen demo skins integrated; game HUD proposals remain a prototype'
(OUT/'manifest.json').write_text(json.dumps(MANIFEST,ensure_ascii=False,indent=2),encoding='utf-8')

# A self-contained browser prototype uses the exact 640x480 raster pages.
encoded={name:'data:image/png;base64,'+base64.b64encode((OUT/'previews'/f'{name}.png').read_bytes()).decode('ascii') for name in SCREENS}
encoded_open=['data:image/png;base64,'+base64.b64encode((OUT/'animation_smooth'/f'open_{i:03d}.png').read_bytes()).decode('ascii') for i in range(len(OPENING))]
labels={'home':'演示目录','basic':'基础菜单','advanced':'高阶菜单','fill':'矩形填充','fill_detail':'填充详情',
    'copy':'图像复制','copy_2':'复制测试图二','copy_detail':'复制详情','buffer':'单缓冲','buffer_double':'双缓冲',
    'buffer_paused':'单缓冲暂停','buffer_double_paused':'双缓冲暂停','key':'颜色键开','key_off':'颜色键关',
    'key_magenta':'品红颜色键','alpha':'透明度255','alpha_0':'透明度0','alpha_128':'透明度128','pressure':'压力31个',
    'pressure_1':'压力1个','game_ready':'游戏准备','game_play':'游戏运行','game_paused':'游戏暂停',
    'game_upgrade':'升级选择一','game_upgrade_1':'升级选择二','game_upgrade_2':'升级选择三','game_over':'游戏结束','game_won':'游戏胜利'}
options='<option value="cover">封面</option>'+''.join(f'<option value="{key}">{label}</option>' for key,label in labels.items())
GAME_SPRITES[19].save(OUT/'source/gem.png')
gem='data:image/png;base64,'+base64.b64encode((OUT/'source/gem.png').read_bytes()).decode('ascii')
HTML=(ROOT/'tools/magic_book_preview_v5.html').read_text(encoding='utf-8')
for token,value in {'__OPTIONS__':options,'__PAGES__':json.dumps(encoded,separators=(',',':')),
    '__OPENING__':json.dumps(encoded_open,separators=(',',':')),'__LATIN__':json.dumps(LATIN,separators=(',',':')),
    '__CHINESE__':json.dumps(CN,separators=(',',':')),'__PALETTE__':json.dumps({name:to565(value) for name,value in C.items()}),
    '__GEM__':json.dumps(gem)}.items():HTML=HTML.replace(token,value)
(OUT/'魔法书交互预览.html').write_text(HTML,encoding='utf-8')

label=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
heading=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc',28)


def sheet(filename,title,items,columns=2):
    rows=math.ceil(len(items)/columns)
    im=Image.new('RGB',(20+columns*660,102+rows*526),c('desk')[:3]);d=ImageDraw.Draw(im)
    d.text((20,16),title,font=heading,fill=c('page_light')[:3])
    for i,(name,caption) in enumerate(items):
        x,y=20+(i%columns)*660,76+(i//columns)*526
        d.text((x,y),caption,font=label,fill=c('ice')[:3])
        im.paste(SCREENS[name].convert('RGB'),(x,y+30))
    im.save(OUT/filename)


sheet('封面与内页.png','魔法书 · 从封面进入演示目录',[('cover','启动封面'),('home_0','翻开后的演示目录')])
comparison=Image.new('RGB',(1340,1130),c('desk')[:3]);d=ImageDraw.Draw(comparison)
d.text((20,16),'魔法书优化 · 封面与内页',font=heading,fill=c('page_light')[:3])
for row,(name,caption) in enumerate((('basic_1','基础演示菜单'),('game_upgrade','升级选择'))):
    y=76+row*526
    for col,version in enumerate(('magic_book_v4','magic_book_v5')):
        x=20+col*660
        d.text((x,y),('之前' if col==0 else '优化后')+' · '+caption,font=label,fill=c('ice')[:3])
        preview=Image.open(ROOT/'assets/ui'/version/'previews'/f'{name}.png').convert('RGB')
        comparison.paste(preview,(x,y+30))
comparison.save(OUT/'优化前后对比.png')
sheet('菜单与全屏演示.png','书页选择演示 · 进入后全屏展示',[('basic_1','魔法书内的演示菜单'),('copy','独立全屏演示')])
sheet('全屏功能预览.png','演示与游戏均为全屏 · 魔法书用于封面与菜单',[('copy','全屏图像复制'),('game_play','全屏游戏 · 保留原视口')])
sheet('游戏全屏预览.png','游戏全屏 · 运行与技能选择',[('game_play','运行界面'),('game_upgrade_1','升级选择')])
sheet('后续页面重点.png','后续页面 · 菜单、全屏演示与游戏',[(n,l) for n,l in [
    ('basic_1','基础章节'),('advanced_1','高阶章节'),('copy','复制演示 · 全屏'),('alpha_128','混合演示 · 全屏'),
    ('game_ready','游戏准备'),('game_upgrade_1','升级选择')]])
sheet('全部页面总览.png','只有封面和菜单用魔法书 · 演示与游戏全屏',[(n,l) for n,l in [
    ('cover','封面'),('home_0','演示目录'),('basic_0','基础演示菜单'),('advanced_0','高阶演示菜单'),
    ('fill','矩形填充'),('copy','图像复制'),('buffer','双缓冲'),('key','颜色键'),('alpha','透明混合'),
    ('pressure','Sprite 压力测试'),('game_ready','游戏准备'),('game_play','游戏运行'),
    ('game_paused','游戏暂停'),('game_upgrade','游戏升级'),('game_over','游戏结束'),('game_won','游戏胜利')]],4)
contact=Image.new('RGB',(1340,850),c('desk')[:3]);d=ImageDraw.Draw(contact)
d.text((20,16),'魔法书展开 · 动画关键帧',font=heading,fill=c('page_light')[:3])
for i,n in enumerate((0,20,44,64,88,120)):
    x,y=20+(i%3)*440,70+(i//3)*380
    contact.paste(OPENING[n].convert('RGB').resize((420,315),Image.Resampling.NEAREST),(x,y))
    d.text((x,y+322),f'{n:02d} / {FRAME_COUNT-1}  -  {n*FRAME_MS/1000:.2f}s',font=label,fill=c('ice')[:3])
contact.save(OUT/'开书动画分镜.png')


def page_turn_frames(old,target,backward=False,count=33):
    """A curved leaf for book pages; fullscreen demos use a separate fade."""
    if backward:
        return [im.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for im in page_turn_frames(
            old.transpose(Image.Transpose.FLIP_LEFT_RIGHT),target.transpose(Image.Transpose.FLIP_LEFT_RIGHT),False,count)]
    front=old.crop((326,38,618,448))
    back=target.crop((22,38,314,448)).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    frames=[]
    for n in range(count):
        if not n:frames.append(old.copy());continue
        if n==count-1:frames.append(target.copy());continue
        t=n/(count-1);progress=ease(t);angle=math.pi*progress
        im=target.copy();im.paste(old.crop((0,0,320,480)),(0,0))
        layer,shadow,_=_project_sheet(front,back,326-12*progress,38,292,410,angle,.30*math.sin(angle))
        im=Image.alpha_composite(im,shadow);im=Image.alpha_composite(im,layer)
        if t>.92:im=Image.blend(im,target,ease((t-.92)/.08))
        frames.append(im)
    return frames


def fullscreen_transition(old,target,count=15):
    dark=Image.new('RGBA',(640,480),c('ink'));frames=[]
    for n in range(count):
        t=n/(count-1)
        frames.append(Image.blend(old,dark,ease(t*2)) if t<.5 else Image.blend(dark,target,ease(t*2-1)))
    return frames


walk=[SCREENS['home_0']];holds=[600]
for segment,hold in ((page_turn_frames(SCREENS['home_0'],SCREENS['basic_0']),400),
                     ([SCREENS['basic_1']],500),
                     (fullscreen_transition(SCREENS['basic_1'],SCREENS['copy']),900),
                     (fullscreen_transition(SCREENS['copy'],SCREENS['basic_1']),800)):
    walk.extend(segment);holds.extend([20]*(len(segment)-1)+[hold])
samples=Image.new('RGB',(2560,1440))
for i,n in enumerate(round(i*(len(walk)-1)/11) for i in range(12)):
    samples.paste(walk[n].convert('RGB'),((i%4)*640,(i//4)*480))
pal=samples.quantize(colors=256,dither=Image.Dither.NONE)
motion=[im.convert('RGB').quantize(palette=pal,dither=Image.Dither.NONE) for im in walk]
motion[0].save(OUT/'菜单到全屏演示.gif',save_all=True,append_images=motion[1:],duration=holds,loop=0,optimize=False,disposal=1)

with zipfile.ZipFile(OUT.parent/'magic_book_v5.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():archive.write(p,p.relative_to(ROOT).as_posix())
    archive.write(Path(__file__).resolve(),'tools/prepare_magic_book_ui_v5.py')
    archive.write(Path(__file__).with_name('book_opening_animation.py'),'tools/book_opening_animation.py')
    archive.write(Path(__file__).with_name('magic_book_preview_v5.html'),'tools/magic_book_preview_v5.html')
print(json.dumps({'output':str(OUT),'screens':len(SCREENS),'opening_frames':len(OPENING),
    'components':len(ASSETS),'palette':len(palette),'c_data_bytes':MANIFEST['embedded']['c_data_bytes'],
    'runtime_integrated':False,'status':'PASS'},ensure_ascii=False,indent=2))
