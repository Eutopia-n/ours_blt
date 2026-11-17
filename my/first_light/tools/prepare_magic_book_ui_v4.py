"""Build the magic-book UI art and an offline interaction prototype.

All drawings are deterministic pixel art. Firmware and game logic are untouched.
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
from book_opening_animation import FRAME_COUNT, FRAME_MS, create_opening_frames

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'assets/ui/magic_book_v4'
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


def footers(im,left='选择',right='打开',back=True,page=1):
    key(im,44,418,'W');key(im,78,418,'S',left)
    key(im,350,418,'ENTER',right)
    if back:key(im,532,418,'A','返回')
    text(im,282,446,str(page),'muted',small=True)
    text(im,584,446,str(page+1),'muted',small=True)


MENU={
    'home':[('基础演示','3项功能','basic'),('高阶演示','3项功能','advanced'),('冰霜幸存者','生存360秒','game')],
    'basic':[('矩形填充','RGB565 硬件填充','fill'),('图像复制','DDR 图像复制','copy'),('双缓冲','垂直消隐交换','buffer')],
    'advanced':[('颜色键','黑色变为透明','key'),('透明混合','W加5 D减5','alpha'),('SPRITE压力','60 FPS','pressure')]
}


def menu(group,selected):
    im=PAGE_BASE.copy()
    title={'home':'二维实验室','basic':'基础演示','advanced':'高阶演示'}[group]
    centered(im,166,44,title,'brown',large=True)
    centered(im,474,46,'选择演示' if group=='home' else '选择功能','brown',large=True)
    # The unchanged hero stands inside a faint manuscript illustration.
    half=im.resize((320,240),Image.Resampling.NEAREST);d=ImageDraw.Draw(half)
    medallion(d,83,121,44,bright=False)
    for sx in (-1,1):
        curve(d,[(83+sx*7,170),(83+sx*37,181),(83+sx*54,161),(83+sx*43,155)],'page_edge')
        curve(d,[(83+sx*15,87),(83+sx*51,74),(83+sx*48,95),(83+sx*41,92)],'page_edge')
    for n in range(7):rune(d,58+n*8,69,n,'page_edge')
    d.ellipse((56,144,110,150),fill=c('page_edge'))
    im=half.resize((640,480),Image.Resampling.NEAREST)
    hero(im,118,194,3)
    centered(im,166,350,'冰霜幸存者','brown')
    centered(im,166,378,'RISC-V + FPGA','muted',small=True)
    for i,(title,detail,kind) in enumerate(MENU[group]):
        y=110+i*90
        active=i==selected
        d=ImageDraw.Draw(im)
        if active:
            d.polygon([(350,y),(586,y),(594,y+8),(594,y+65),(586,y+73),
                       (350,y+73),(342,y+65),(342,y+8)],fill=c('page_edge'))
            d.rectangle((346,y+4,590,y+69),fill=c('select'))
            d.line((354,y+2,582,y+2),fill=c('gold'))
            d.line((354,y+71,582,y+71),fill=c('gold'))
            for xx,sx in ((348,1),(588,-1)):
                d.line((xx,y+16,xx,y+6,xx+sx*12,y+6),fill=c('gold_dark'),width=2)
                d.line((xx,y+57,xx,y+67,xx+sx*12,y+67),fill=c('gold_dark'),width=2)
        else:
            d.line((354,y+74,582,y+74),fill=c('page_edge'))
            d.polygon([(468,y+72),(470,y+74),(468,y+76),(466,y+74)],fill=c('gold'))
        im.alpha_composite(ICONS[kind],(354,y+20))
        text(im,398,y+10,title,'leather_dark' if active else 'brown',large=kind!='pressure')
        text(im,400,y+48,detail,'brown' if active else 'muted')
        if active:im.alpha_composite(CURSOR,(326,y+26))
    footers(im,back=True,page={'home':1,'basic':3,'advanced':5}[group])
    return im


def title_pair(im,left,right):
    centered(im,166,46,left,'brown',large=True)
    centered(im,474,46,right,'brown',large=True)


def stats(im,x,y,labels):
    for i,(label,value) in enumerate(labels):
        text(im,x,y+i*30,label,'brown')
        text(im,x+136,y+i*30,value,'leather_dark')


def demo_fill():
    im=PAGE_BASE.copy()
    title_pair(im,'矩形填充','绘制结果')
    text(im,46,106,'CPU / FPGA','brown')
    stats(im,46,150,[('CPU FPS','--'),('FPGA FPS','--'),('FILL_US','--'),('SPEEDUP','--')])
    text(im,46,310,'32 X 24 RGB565','muted')
    frame(im,(346,110,248,250),'desk','gold_dark')
    d=ImageDraw.Draw(im)
    for i,(x,y) in enumerate(((366,138),(466,168),(398,232),(530,286),(464,310))):
        d.rectangle((x,y,x+31,y+23),fill=c(('blue','gold_light','ice','green','red')[i]))
    footers(im,'调整','详情',page=7)
    return im


def image_sample():
    # Illustrative copy-page art for this layout proposal, not a hardware sample.
    im=Image.new('RGBA',(240,180),c('page_light'))
    d=ImageDraw.Draw(im)
    d.rectangle((0,0,239,179),fill=c('blue'))
    d.rectangle((0,90,239,179),fill=c('green'))
    d.polygon([(0,90),(120,128),(239,90),(239,150),(0,150)],fill=c('leather_dark'))
    d.ellipse((172,18,207,53),fill=c('gold_light'))
    d.polygon([(88,179),(104,153),(134,153),(150,179)],fill=c('page_edge'))
    return im


def demo_copy():
    im=PAGE_BASE.copy()
    title_pair(im,'DDR原图','复制结果')
    image=image_sample()
    for x in (44,354):
        frame(im,(x-4,146,248,188),'desk','gold_dark')
        im.alpha_composite(image,(x,150))
    text(im,48,108,'SOURCE','muted');text(im,358,108,'FPGA COPY','muted')
    text(im,50,356,'CPU FPS --','brown');text(im,360,356,'FPGA FPS --','brown')
    footers(im,'调整','详情',page=9)
    return im


def demo_buffer():
    im=PAGE_BASE.copy()
    title_pair(im,'双缓冲','防撕裂')
    for x in (46,356):text(im,x,108,'S 切换模式','brown')
    frame(im,(42,148,556,220),'leather_dark','gold_dark')
    d=ImageDraw.Draw(im)
    for y in range(176,350,38):d.line((48,y,591,y),fill=c('stone'),width=2)
    for x in (188,300,412):d.rectangle((x,156,x+23,358),fill=c('page_highlight'))
    footers(im,'速度','暂停',page=11)
    return im


def effects(kind):
    im=PAGE_BASE.copy()
    title_pair(im,'原图参考','颜色键' if kind=='key' else '透明混合')
    for n,left in enumerate((62,372)):
        text(im,left,106,'COLOR KEY' if kind=='key' else 'ALPHA','brown')
        frame(im,(left-8,146,224,208),'desk','gold_dark')
        d=ImageDraw.Draw(im)
        for row in range(12):
            for col in range(13):
                x,y=left+col*16,154+row*16
                d.rectangle((x,y,x+15,y+15),fill=c('gold' if (row+col)%2 else 'green'))
        if n==0:d.rectangle((left+40,186,left+167,313),fill=(0,0,0,255))
        diamond=[(left+104,190),(left+164,250),(left+104,310),(left+44,250)]
        d.polygon(diamond,fill=c('ice' if n==0 or kind=='key' else 'blue'))
        if kind=='alpha' and n:
            # Preview the same RGB565 component-wise alpha rule as the driver.
            overlay=im.copy();ImageDraw.Draw(overlay).polygon(diamond,fill=c('ice'))
            mask=Image.new('1',(640,480));ImageDraw.Draw(mask).polygon(diamond,fill=1)
            for y in range(190,311):
                for x in range(left+44,left+165):
                    if mask.getpixel((x,y)):
                        fg,bg=to565(c('ice')),to565(c('gold' if ((x-left)//16+(y-154)//16)%2 else 'green'))
                        r=(((fg>>11)&31)*127+((bg>>11)&31)*128+127)//255
                        g=(((fg>>5)&63)*127+((bg>>5)&63)*128+127)//255
                        b=((fg&31)*127+(bg&31)*128+127)//255
                        im.putpixel((x,y),(*expand((r<<11)|(g<<5)|b),255))
    centered(im,166,370,'颜色键关' if kind=='key' else '不透明参考','muted')
    centered(im,474,370,'颜色键开' if kind=='key' else '透明度128/255','brown')
    footers(im,'调整','预设',page=13 if kind=='key' else 15)
    return im


def pressure():
    im=PAGE_BASE.copy();title_pair(im,'SPRITE压力','FPGA')
    text(im,46,104,'SPRITES 32','brown');text(im,356,104,'FPS -- MAX60 --','brown')
    frame(im,(42,144,556,244),'desk','gold_dark')
    d=ImageDraw.Draw(im)
    for n in range(32):
        x,y=62+(n*71)%508,170+(n*43)%190
        d.polygon([(x,y-8),(x+8,y),(x,y+8),(x-8,y)],fill=c('blue'))
        d.line((x,y-7,x-6,y,x,y+6),fill=c('ice'),width=2)
    footers(im,'数量','暂停',page=17)
    return im


def game(state='play'):
    im=PAGE_BASE.copy();title_pair(im,'冰霜幸存者','生命100')
    text(im,46,100,'等级2 经验','brown');text(im,356,100,'时间30 FPS --','brown')
    # This viewport is a proposed new camera area. Existing game code is not rescaled or cropped.
    frame(im,(42,124,556,274),'desk','gold_dark')
    d=ImageDraw.Draw(im)
    for x in range(48,592,32):
        d.rectangle((x,130,x+30,142),fill=c('stone'))
        d.line((x+2,130,x+28,130),fill=c('ice'))
    altar=Image.open(ROOT/'assets/scenery/frame_0.png').convert('RGBA')
    im.alpha_composite(altar,(256,194))
    hero(im,304,240,1)
    raw=(ROOT/'assets/game/game.rgb565').read_bytes()
    for i,(x,y) in enumerate(((108,184),(478,230),(202,336),(526,344))):
        values=struct.unpack_from('<1024H',raw,(16+i%3)*2048)
        enemy=Image.new('RGBA',(32,32),T)
        for j,v in enumerate(values):
            if v:enemy.putpixel((j%32,j//32),(*expand(v),255))
        im.alpha_composite(enemy,(x,y))
    for x,y in ((170,240),(440,330),(390,190)):
        d=ImageDraw.Draw(im);d.polygon([(x,y-5),(x+3,y),(x,y+5),(x-3,y)],fill=c('ice'))
    if state!='play':
        frame(im,(124,166,392,188),'page_light','gold')
        titles={'ready':'冰霜幸存者','paused':'已暂停','upgrade':'升级选择','over':'游戏结束','won':'你已生存'}
        centered(im,320,182,titles[state],'brown',large=True)
        if state=='ready':
            centered(im,320,232,'生存360秒','brown')
            centered(im,320,268,'技能自动释放','muted')
            centered(im,320,310,'ENTER 开始','leather_dark')
        elif state=='upgrade':
            for i,label in enumerate(('奥术强化','快速施法','冰霜法环')):
                if i==0:frame(im,(148,224,344,26),'select','gold')
                text(im,174,230+i*34,label,'leather_dark' if i==0 else 'brown')
        else:
            centered(im,320,238,'时间30 击杀51','brown')
            centered(im,320,278,'ENTER 继续' if state=='paused' else 'ENTER 再来一局','leather_dark')
            centered(im,320,316,'A 返回菜单','muted')
    key(im,46,420,'W/S/A/D','移动')
    key(im,352,420,'ENTER','开始' if state=='ready' else '暂停')
    text(im,282,446,'19','muted',small=True);text(im,584,446,'20','muted',small=True)
    return im


SCREENS={'cover':cover_art()}
for group in MENU:
    for n in range(3):SCREENS[f'{group}_{n}']=menu(group,n)
SCREENS.update({'fill':demo_fill(),'copy':demo_copy(),'buffer':demo_buffer(),
                'key':effects('key'),'alpha':effects('alpha'),'pressure':pressure()})
for state in ('ready','play','paused','upgrade','over','won'):
    SCREENS['game_'+state]=game(state)
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
                'home_back':'A closes the book in this prototype; firmware behavior is not yet changed'},
    'game_view_proposal':[46,128,548,266],
    'game_view_current':[8,80,624,360],
    'game_layout_note':'New viewport and HUD layout require camera/clipping and pixel tests; no production change in this deliverable.',
    'cross_spread_views':['buffer','pressure','game'],
    'cross_spread_note':'Book remains visible around the drawing window; no gutter shadow is painted over effect/game pixels.',
    'opening':{'frames':FRAME_COUNT,'step_ms':FRAME_MS,'motion_ms':(FRAME_COUNT-1)*FRAME_MS,
               'frame_directory':'animation_smooth','legacy_frame_directory':'animation',
               'render_strategy':'Reference animation only. Separate cover, body, curved leaf and clasp. Do not keep all full-screen frames in DDR.'},
    'fonts':'Existing font_cn.h and font5x7.h; large titles and hero previews use nearest integer scaling.'
}
(OUT/'layout.json').write_text(json.dumps(LAYOUT,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'source/theme.json').write_text(json.dumps(THEME,ensure_ascii=False,indent=2),encoding='utf-8')
MANIFEST={
    'name':'magic_book_v4','version':4,'canvas':[640,480],
    'runtime_integrated':False,'screens':list(SCREENS),'opening_frames':len(OPENING),
    'atlas':{'size':[256,256],'stride':512,'raw_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()},
    'embedded':{'palette_colors':len(palette),'rle_bytes':len(tokens)*2,'descriptor_bytes':len(ASSETS)*10,
                'c_data_bytes':len(palette)*2+len(tokens)*2+len(ASSETS)*10,'rle_shift':6,'rle_mask':63,
                'excluded':'Full-screen background, cover/open book layers, preview frames, new drawing code and original player are not part of this C data size.'},
    'assets':[{'id':i,'name':a['name'],'rect':a['rect'],'margin':a['margin'],'role':a['role']} for i,a in enumerate(ASSETS)],
    'source_player_sha256':hashlib.sha256((ROOT/'assets/player/walk_32.png').read_bytes()).hexdigest(),
    'sources':{'new_art':'Original pixel book shapes and ornaments; no AI image generation service used.',
               'reuse':'Original player/scenery/game art and menu_pixel_v2 component PNGs; original rights apply.'},
    'checks':{'rle_roundtrip':True,'binary_alpha':True,'existing_font_glyphs':True},
    'performance_values':'-- denotes unmeasured; game counters are visual fixtures, not hardware results.'
}
(OUT/'manifest.json').write_text(json.dumps(MANIFEST,ensure_ascii=False,indent=2),encoding='utf-8')

# A self-contained browser prototype uses the exact 640x480 raster pages.
encoded={name:'data:image/png;base64,'+base64.b64encode((OUT/'previews'/f'{name}.png').read_bytes()).decode('ascii') for name in SCREENS}
encoded_open=['data:image/png;base64,'+base64.b64encode((OUT/'animation_smooth'/f'open_{i:03d}.png').read_bytes()).decode('ascii') for i in range(len(OPENING))]
HTML='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>魔法书界面预览</title>
<style>*{box-sizing:border-box}body{margin:0;background:#111a29;color:#ead9b0;font:15px "Microsoft YaHei",sans-serif;display:grid;place-items:center;min-height:100vh}main{padding:22px;width:min(100%,1000px)}h1{font-size:24px;margin:0 0 12px}p{color:#a7b7c9;line-height:1.7}.stage{position:relative;width:100%;max-width:960px;aspect-ratio:4/3;border:1px solid #3b455a;background:#182235}.stage img{display:block;width:100%;height:100%;image-rendering:pixelated;object-fit:contain}.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}button,select{background:#243752;border:1px solid #57738c;color:#ecd9b0;font:inherit;padding:9px 15px;border-radius:5px;cursor:pointer}button:hover{background:#31516d}small{display:block;color:#9eacbb;margin-top:14px}.hot{position:absolute;background:transparent!important;border:0;padding:0;border-radius:0;display:none}.hot:hover{outline:2px solid #d9ba79}.hot:focus-visible{outline:2px solid white}</style>
<main><h1>魔法书 · 界面交互预览</h1><p>Enter 打开 / 进入，W、S 选择，A 返回。封面、菜单、演示和游戏均在同一本书中。</p><div class="stage"><img id="screen" alt="魔法书界面"><button class="hot" data-row="0" aria-label="选择第一项"></button><button class="hot" data-row="1" aria-label="选择第二项"></button><button class="hot" data-row="2" aria-label="选择第三项"></button></div>
<div class="actions"><button data-key="w">W 上一项</button><button data-key="s">S 下一项</button><button data-key="enter">Enter 进入</button><button data-key="a">A 返回</button><select id="jump" aria-label="直接查看页面"><option value="cover">封面</option><option value="home">演示目录</option><option value="basic">基础菜单</option><option value="advanced">高阶菜单</option><option value="fill">矩形填充</option><option value="copy">图像复制</option><option value="buffer">双缓冲</option><option value="key">颜色键</option><option value="alpha">透明混合</option><option value="pressure">压力测试</option><option value="game_ready">游戏准备</option><option value="game_play">游戏运行</option><option value="game_paused">游戏暂停</option><option value="game_upgrade">游戏升级</option><option value="game_over">游戏结束</option><option value="game_won">游戏胜利</option></select></div>
<small>电脑端美术原型，未接入 FPGA。演示数据“--”表示未测量；游戏数值为排版示例。演示按钮仅切换预览页面。</small></main>
<script>const pages=PAGE_DATA,opening=OPEN_DATA;let state='cover',selected=0,busy=false;const screen=document.querySelector('#screen'),menuStates=['home','basic','advanced'];function render(){screen.src=pages[menuStates.includes(state)?state+'_'+selected:state];document.querySelectorAll('.hot').forEach(b=>{b.style.display=menuStates.includes(state)?'block':'none';b.style.left=(342/640*100)+'%';b.style.top=((110+Number(b.dataset.row)*90)/480*100)+'%';b.style.width=(254/640*100)+'%';b.style.height=(76/480*100)+'%'})}const delay=ms=>new Promise(r=>setTimeout(r,ms));async function openBook(){busy=true;for(const f of opening){screen.src=f;await delay(70)}state='home';selected=0;busy=false;render()}async function turn(next){busy=true;const old=screen.src;state=next;selected=0;render();const target=screen.src;screen.src=old;screen.style.opacity='.7';await delay(90);screen.src=target;screen.style.opacity='1';busy=false}async function act(k){if(busy)return;if(state==='cover'){if(k==='enter')await openBook();return}if(menuStates.includes(state)){if(k==='w'||k==='s'){selected=(selected+(k==='w'?2:1))%3;render()}else if(k==='enter'){await turn(state==='home'?['basic','advanced','game_ready'][selected]:state==='basic'?['fill','copy','buffer'][selected]:['key','alpha','pressure'][selected])}else if(k==='a'){if(state==='home'){state='cover';render()}else await turn('home')}return}if(k==='a'){await turn(state.startsWith('game')?'home':['fill','copy','buffer'].includes(state)?'basic':'advanced')}else if(k==='enter'&&state.startsWith('game')){state=state==='game_play'?'game_paused':'game_play';render()}}document.querySelectorAll('[data-key]').forEach(b=>b.onclick=()=>act(b.dataset.key));document.querySelectorAll('.hot').forEach(b=>b.onclick=()=>{selected=Number(b.dataset.row);act('enter')});document.addEventListener('keydown',e=>{if(e.target.tagName==='SELECT')return;if(['w','s','a','enter'].includes(e.key.toLowerCase())){e.preventDefault();act(e.key.toLowerCase())}});document.querySelector('#jump').onchange=e=>{if(busy)return;state=e.target.value;selected=0;render()};render();</script></html>'''
HTML=HTML.replace('PAGE_DATA',json.dumps(encoded,separators=(',',':'))).replace('OPEN_DATA',json.dumps(encoded_open,separators=(',',':')))
HTML=HTML.replace('<img id="screen" alt="魔法书界面">',
    '<img id="screen" alt="魔法书界面"><canvas id="leaf" width="640" height="480" style="display:none;position:absolute;inset:0;width:100%;height:100%;image-rendering:pixelated;pointer-events:none"></canvas>')
old_turn="async function turn(next){busy=true;const old=screen.src;state=next;selected=0;render();const target=screen.src;screen.src=old;screen.style.opacity='.7';await delay(90);screen.src=target;screen.style.opacity='1';busy=false}"
new_turn=r'''async function loadRaster(src){const im=new Image();im.src=src;await im.decode();return im}
async function turn(next){
busy=true;const old=await loadRaster(screen.src);state=next;selected=0;render();const target=await loadRaster(screen.src);
const layer=document.querySelector('#leaf'),ctx=layer.getContext('2d');ctx.imageSmoothingEnabled=false;layer.style.display='block';
for(let n=0;n<=10;n++){
 const t=n/10,w=Math.max(2,Math.round(Math.abs(Math.cos(Math.PI*t))*292/2)*2);
 ctx.drawImage(target,0,0);ctx.drawImage(old,22,38,292,410,22,38,292,410);
 if(t<.5)ctx.drawImage(old,326,38,292,410,326,38,w,410);
 else ctx.drawImage(target,22,38,292,410,326-w,38,w,410);
 ctx.fillStyle='#79664d';ctx.fillRect(t<.5?326+w-2:326-w,38,2,410);
 await delay(45);
}
layer.style.display='none';busy=false;render();
}'''
assert old_turn in HTML
HTML=HTML.replace(old_turn,new_turn)
HTML=HTML.replace("for(const f of opening){screen.src=f;await delay(70)}",
    "const decoded=await Promise.all(opening.map(loadRaster));for(const f of decoded){screen.src=f.src;await delay(20)}")
HTML=HTML.replace('background:#111a29','background:#11121e').replace('background:#182235','background:#171626')
HTML=HTML.replace('background:#243752','background:#292c51').replace('border:1px solid #57738c','border:1px solid #887252')
HTML=HTML.replace('background:#31516d','background:#3d4267')
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
for row,(name,caption) in enumerate((('cover','封面'),('home_0','演示目录'))):
    y=76+row*526
    for col,version in enumerate(('magic_book_v3','magic_book_v4')):
        x=20+col*660
        d.text((x,y),('之前' if col==0 else '优化后')+' · '+caption,font=label,fill=c('ice')[:3])
        preview=Image.open(ROOT/'assets/ui'/version/'previews'/f'{name}.png').convert('RGB')
        comparison.paste(preview,(x,y+30))
comparison.save(OUT/'优化前后对比.png')
sheet('全部页面总览.png','所有界面都在书页中',[(n,l) for n,l in [
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

with zipfile.ZipFile(OUT.parent/'magic_book_v4.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():archive.write(p,p.relative_to(ROOT).as_posix())
    archive.write(Path(__file__).resolve(),'tools/prepare_magic_book_ui_v4.py')
    archive.write(Path(__file__).with_name('book_opening_animation.py'),'tools/book_opening_animation.py')
print(json.dumps({'output':str(OUT),'screens':len(SCREENS),'opening_frames':len(OPENING),
    'components':len(ASSETS),'palette':len(palette),'c_data_bytes':MANIFEST['embedded']['c_data_bytes'],
    'runtime_integrated':False,'status':'PASS'},ensure_ascii=False,indent=2))
