"""Build the magic-book UI art and an offline interaction prototype.

All drawings are deterministic pixel art. Firmware and game logic are untouched.
"""
from pathlib import Path
import base64
import hashlib
import json
import math
import re
import struct
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'assets/ui/magic_book_v3'
PREVIOUS = ROOT/'assets/ui/menu_pixel_v2'
for name in ('png','rgb565','embedded','previews','animation','source'):
    (OUT/name).mkdir(parents=True,exist_ok=True)

THEME = {
    'ink':'#171925','desk':'#182235','desk_light':'#25334a',
    'leather':'#053479','leather_dark':'#09224b','leather_light':'#0755a1',
    'blue':'#008bce','ice':'#8cd8ed',
    'gold_dark':'#805839','gold':'#b68b4f','gold_light':'#ebc983',
    'page_shadow':'#a68c62','page_edge':'#c6aa77','page':'#dfc99c',
    'page_light':'#eeddb4','page_highlight':'#f5e7c9',
    'brown':'#5a4938','muted':'#79664d','select':'#f5e4bc',
    'stone':'#65768b','red':'#ad6262','green':'#6c9578'
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


def desk():
    im=Image.new('RGBA',(320,240),c('desk'))
    d=ImageDraw.Draw(im)
    for y in (14,86,166,230):
        d.line((0,y,319,y),fill=c('ink'))
        d.line((0,y+1,319,y+1),fill=c('desk_light'))
    for x,y in ((22,48),(300,55),(12,200),(296,188)):
        d.line((x,y,x+8,y),fill=c('desk_light'))
    return im.resize((640,480),Image.Resampling.NEAREST)


def open_base():
    """Open book with page stacks and a visible, reserved center gutter."""
    im=desk().resize((320,240),Image.Resampling.NEAREST)
    d=ImageDraw.Draw(im)
    d.polygon([(8,15),(110,9),(160,16),(211,9),(313,15),(317,228),
               (212,233),(160,228),(108,233),(4,228)],fill=c('ink'))
    d.polygon([(7,13),(109,9),(160,15),(211,9),(313,13),(314,225),
               (212,230),(160,225),(108,230),(5,225)],fill=c('leather_dark'))
    d.line((8,14,108,10,159,16,211,10,312,14),fill=c('gold'),width=2)
    for offset,tone in ((6,'page_shadow'),(4,'page_edge'),(2,'page_light')):
        d.polygon([(12,18),(108,14),(158,21),(158,219+offset),(108,225+offset),
                   (11,221+offset)],fill=c(tone))
        d.polygon([(162,21),(211,14),(308,18),(309,221+offset),(212,225+offset),
                   (162,219+offset)],fill=c(tone))
    d.polygon([(12,17),(108,13),(158,20),(158,219),(108,224),(12,220)],fill=c('page'))
    d.polygon([(162,20),(211,13),(308,17),(308,220),(212,224),(162,219)],fill=c('page_light'))
    d.rectangle((16,22,148,216),fill=c('page_light'))
    d.rectangle((172,22,303,216),fill=c('page_light'))
    for x,tone in ((149,'page'),(152,'page_edge'),(155,'page_shadow'),(158,'brown'),
                   (160,'ink'),(161,'brown'),(164,'page_shadow'),(167,'page_edge'),(170,'page')):
        d.rectangle((x,22,x+1,216),fill=c(tone))
    for x0,x1 in ((20,146),(174,300)):
        d.line((x0,41,x1,41),fill=c('page_edge'))
        d.line((x0,204,x1,204),fill=c('page_edge'))
        for xx in (x0,x1):
            d.polygon([(xx,39),(xx+2,41),(xx,43),(xx-2,41)],fill=c('gold_dark'))
    # Cloth markers protrude below the page block, not over page content.
    d.polygon([(235,221),(244,221),(244,237),(240,234),(235,237)],fill=c('leather_dark'))
    d.line((237,222,237,234),fill=c('blue'))
    return im.resize((640,480),Image.Resampling.NEAREST)


PLAYER=Image.open(ROOT/'assets/player/walk_32.png').convert('RGBA').crop((0,0,32,32))


def hero(im,x,y,k=3):
    im.alpha_composite(PLAYER.resize((32*k,32*k),Image.Resampling.NEAREST),(x,y))


def cover_art():
    im=desk().resize((320,240),Image.Resampling.NEAREST)
    d=ImageDraw.Draw(im)
    d.rectangle((91,19,234,218),fill=c('ink'))
    d.rectangle((89,17,231,215),fill=c('gold_dark'))
    d.rectangle((94,18,229,212),fill=c('page_edge'))
    for y in range(22,212,4):d.line((222,y,229,y),fill=c('page_light'))
    d.polygon([(89,16),(222,16),(228,22),(228,208),(222,214),(89,214),(87,210),(87,20)],fill=c('ink'))
    d.rectangle((91,18,222,210),fill=c('leather'))
    d.rectangle((88,20,96,210),fill=c('leather_dark'))
    d.line((98,20,98,210),fill=c('leather_light'))
    for y in (30,66,164,198):
        d.rectangle((88,y,97,y+4),fill=c('gold_dark'))
        d.line((89,y,96,y),fill=c('gold'))
    d.rectangle((103,27,214,200),outline=c('gold_dark'),width=1)
    d.rectangle((105,29,212,198),outline=c('leather_light'),width=1)
    for x,y,dx,dy in ((103,27,1,1),(214,27,-1,1),(103,200,1,-1),(214,200,-1,-1)):
        d.polygon([(x,y),(x+dx*14,y),(x+dx*9,y+dy*3),(x+dx*3,y+dy*9),(x,y+dy*14)],fill=c('gold'))
        d.line((x+dx,y+dy,x+dx*9,y+dy),fill=c('gold_light'))
    for y in range(35,196,8):
        d.point((107,y),fill=c('blue'))
        d.point((210,y),fill=c('blue'))
    d.polygon([(158,68),(188,99),(158,130),(128,99)],fill=c('ink'))
    d.polygon([(158,69),(186,99),(158,128),(130,99)],fill=c('gold_dark'))
    d.polygon([(158,73),(182,99),(158,124),(134,99)],fill=c('leather_dark'))
    frost(d,158,99,18)
    d.rectangle((217,108,234,118),fill=c('ink'))
    d.rectangle((218,109,233,116),fill=c('gold_dark'))
    d.rectangle((222,109,227,116),fill=c('gold'))
    d.rectangle((223,110,225,114),fill=c('ice'))
    im=im.resize((640,480),Image.Resampling.NEAREST)
    centered(im,318,62,'TI60','gold_light')
    centered(im,318,96,'二维实验室','page_highlight',large=True)
    hero(im,284,270,2)
    centered(im,318,368,'RISC-V + FPGA','gold_light')
    centered(im,320,446,'ENTER 打开','page_highlight')
    return im


ICONS={kind:Image.open(PREVIOUS/'png'/('icon_'+kind+'.png')).convert('RGBA')
       for kind in ('basic','advanced','game','fill','copy','buffer','key','alpha','pressure')}
CURSOR=Image.open(PREVIOUS/'png/cursor_0.png').convert('RGBA')
PAGE_BASE=open_base()


def frame(im,rect,fill='page',edge='gold_dark'):
    x,y,w,h=rect
    d=ImageDraw.Draw(im)
    d.rectangle((x,y,x+w-1,y+h-1),fill=c('brown'))
    d.rectangle((x+2,y+2,x+w-3,y+h-3),fill=c(edge))
    d.rectangle((x+4,y+4,x+w-5,y+h-5),fill=c(fill))


def key(im,x,y,label,caption=''):
    w=max(26,len(label)*12+12)
    frame(im,(x,y,w,24),'page','page_shadow')
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
    # The original character appears as a book illustration, not a new avatar.
    ImageDraw.Draw(im).ellipse((104,292,228,310),fill=c('page_edge'))
    hero(im,118,192,3)
    ImageDraw.Draw(im).line((92,320,240,320),fill=c('gold'),width=2)
    centered(im,166,342,'冰霜幸存者','brown')
    centered(im,166,136,'RISC-V + FPGA','muted')
    for i,(title,detail,kind) in enumerate(MENU[group]):
        y=110+i*90
        active=i==selected
        frame(im,(342,y,254,76),'select' if active else 'page',
              'gold' if active else 'page_edge')
        im.alpha_composite(ICONS[kind],(354,y+20))
        text(im,398,y+10,title,'ink',large=kind!='pressure')
        text(im,400,y+48,detail,'brown')
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
    cover=SCREENS['cover'].crop((174,32,472,434))
    spread=SCREENS['home_0']
    frames=[]
    for n in range(13):
        t=n/12
        if n==0:frames.append(SCREENS['cover'].copy());continue
        if n==12:frames.append(spread.copy());continue
        im=desk()
        pivot=int((174+146*t)//2)*2
        y=int((32-12*t)//2)*2
        height=int((402+38*t)//2)*2
        width=int((298+10*t)//2)*2
        right=spread.crop((320,20,628,460)).resize((width,height),Image.Resampling.NEAREST)
        im.alpha_composite(right,(pivot,y))
        leaf_width=max(2,int(abs(math.cos(math.pi*t))*width)//2*2)
        if t<.5:
            face=cover.resize((leaf_width,height),Image.Resampling.NEAREST)
            im.alpha_composite(face,(pivot,y))
        else:
            face=spread.crop((12,20,320,460)).resize((leaf_width,height),Image.Resampling.NEAREST)
            im.alpha_composite(face,(pivot-leaf_width,y))
        ImageDraw.Draw(im).line((pivot,y+10,pivot,y+height-10),fill=c('brown'),width=2)
        frames.append(im)
    return frames


OPENING=opening_frames()
for n,im in enumerate(OPENING):im.convert('RGB').save(OUT/'animation'/f'open_{n:02d}.png')
OPENING[0].save(OUT/'打开魔法书.gif',save_all=True,append_images=OPENING[1:],
                duration=[900]+[70]*11+[1700],loop=0,disposal=2)

# Individual tiles provide an implementation path without storing all preview frames.
ASSETS=[]


def asset(name,im,role,margin=0):
    ASSETS.append({'name':name,'image':im,'role':role,'margin':margin})


for kind,im in ICONS.items():asset('icon_'+kind,im,'icon')
for n in range(4):
    asset('cursor_'+str(n),Image.open(PREVIOUS/'png'/f'cursor_{n}.png').convert('RGBA'),'cursor')
for state in ('normal','selected','pressed','disabled'):
    asset('card_'+state,Image.open(PREVIOUS/'png'/f'panel_{state}.png').convert('RGBA'),'nine_slice',8)
asset('frost_seal',Image.open(PREVIOUS/'png/frost_seal.png').convert('RGBA'),'emblem')
asset('bookmark',Image.open(PREVIOUS/'png/cloth_banner.png').convert('RGBA'),'decoration')


def parchment(d,im):
    d.rectangle((0,0,15,15),fill=c('page_light'))
    d.line((3,5,5,5),fill=c('page'))
    d.point((12,11),fill=c('page'))


def leather(d,im):
    d.rectangle((0,0,15,15),fill=c('leather'))
    d.line((3,3,5,3),fill=c('leather_light'))
    d.line((11,11,12,11),fill=c('leather_dark'))


def corner(d,im):
    d.polygon([(0,0),(15,0),(11,3),(3,11),(0,15)],fill=c('gold_dark'))
    d.polygon([(1,1),(13,1),(9,3),(3,9),(1,13)],fill=c('gold'))
    d.line((2,2,10,2),fill=c('gold_light'))


def page_corner(d,im):
    d.polygon([(0,15),(15,0),(15,15)],fill=c('page_shadow'))
    d.polygon([(1,14),(14,1),(14,14)],fill=c('page_highlight'))
    d.line((1,14,14,1),fill=c('gold'))


def spine(d,im):
    for x,tone in enumerate(('page','page_edge','page_shadow','brown','ink','brown','page_shadow','page_edge')):
        d.line((x,0,x,31),fill=c(tone))


asset('parchment_tile',grid_art((16,16),parchment),'tile')
asset('leather_tile',grid_art((16,16),leather),'tile')
asset('cover_corner',grid_art((16,16),corner),'corner')
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
    'canvas':[640,480],'book_bounds':[10,18,620,446],
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
    'opening':{'frames':13,'step_ms':70,'render_strategy':'Reference animation only. Reconstruct from base book and a variable-width leaf; do not retain 13 full screens in DDR.'},
    'fonts':'Existing font_cn.h and font5x7.h; large titles and hero previews use nearest integer scaling.'
}
(OUT/'layout.json').write_text(json.dumps(LAYOUT,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'source/theme.json').write_text(json.dumps(THEME,ensure_ascii=False,indent=2),encoding='utf-8')
MANIFEST={
    'name':'magic_book_v3','version':3,'canvas':[640,480],
    'runtime_integrated':False,'screens':list(SCREENS),'opening_frames':len(OPENING),
    'atlas':{'size':[256,256],'stride':512,'raw_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()},
    'embedded':{'palette_colors':len(palette),'rle_bytes':len(tokens)*2,'descriptor_bytes':len(ASSETS)*10,
                'c_data_bytes':len(palette)*2+len(tokens)*2+len(ASSETS)*10,'rle_shift':6,'rle_mask':63,
                'excluded':'Full-screen background, preview frames, new drawing code and original player are not part of this C data size.'},
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
encoded_open=['data:image/png;base64,'+base64.b64encode((OUT/'animation'/f'open_{i:02d}.png').read_bytes()).decode('ascii') for i in range(len(OPENING))]
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
sheet('全部页面总览.png','所有界面都在书页中',[(n,l) for n,l in [
    ('cover','封面'),('home_0','演示目录'),('basic_0','基础演示菜单'),('advanced_0','高阶演示菜单'),
    ('fill','矩形填充'),('copy','图像复制'),('buffer','双缓冲'),('key','颜色键'),('alpha','透明混合'),
    ('pressure','Sprite 压力测试'),('game_ready','游戏准备'),('game_play','游戏运行'),
    ('game_paused','游戏暂停'),('game_upgrade','游戏升级'),('game_over','游戏结束'),('game_won','游戏胜利')]],4)
contact=Image.new('RGB',(1340,850),c('desk')[:3]);d=ImageDraw.Draw(contact)
d.text((20,16),'魔法书展开 · 动画关键帧',font=heading,fill=c('page_light')[:3])
for i,n in enumerate((0,2,4,6,8,12)):
    x,y=20+(i%3)*440,70+(i//3)*380
    contact.paste(OPENING[n].convert('RGB').resize((420,315),Image.Resampling.NEAREST),(x,y))
    d.text((x,y+322),f'{n:02d} / 12',font=label,fill=c('ice')[:3])
contact.save(OUT/'开书动画分镜.png')

with zipfile.ZipFile(OUT.parent/'magic_book_v3.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():archive.write(p,p.relative_to(ROOT).as_posix())
    archive.write(Path(__file__).resolve(),'tools/prepare_magic_book_ui.py')
print(json.dumps({'output':str(OUT),'screens':len(SCREENS),'opening_frames':len(OPENING),
    'components':len(ASSETS),'palette':len(palette),'c_data_bytes':MANIFEST['embedded']['c_data_bytes'],
    'runtime_integrated':False,'status':'PASS'},ensure_ascii=False,indent=2))
