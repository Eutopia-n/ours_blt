"""Export a labelled art gallery and illustrative animation from native RGB565.

These pictures show composition and animation, not measured board gameplay.
"""
from pathlib import Path
import json
import math
import struct
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/game/frost_v1'
RAW=(ROOT/'assets/game/game.rgb565').read_bytes()
BASE=(ROOT/'assets/game/source/base_game_v1.rgb565').read_bytes()
NAVY='#101321';PANEL='#191e30';LINE='#38435b';GOLD='#e6c98c';ICE='#9fe4e5';TEXT='#e3e6dc';MUTED='#8c9ab0'
FONT=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',19)
SMALL=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
TITLE=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc',30)
SUB=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc',23)


def expand(v):
    return ((v>>11)*255//31,((v>>5)&63)*255//63,(v&31)*255//31)


def sprite(index,raw=RAW):
    im=Image.new('RGBA',(32,32))
    for n,v in enumerate(struct.unpack_from('<1024H',raw,index*2048)):
        if v:im.putpixel((n%32,n//32),(*expand(v),255))
    return im


def paste(im,asset,x,y,scale=1):
    im.paste(asset.resize((asset.width*scale,asset.height*scale),Image.Resampling.NEAREST),(x,y),asset.resize((asset.width*scale,asset.height*scale),Image.Resampling.NEAREST))


def title(im,y,text,sub=None):
    d=ImageDraw.Draw(im);d.text((28,y),text,font=SUB,fill=ICE)
    if sub:d.text((28,y+35),sub,font=SMALL,fill=MUTED)


def gallery():
    im=Image.new('RGB',(1440,1190),NAVY);d=ImageDraw.Draw(im)
    d.text((28,22),'冰霜魔法 · 游戏美术包',font=TITLE,fill=GOLD)
    d.text((28,70),'保留原蓝帽小人  /  纯色场景  /  冰晶、骨白、紫晶与旧金',font=FONT,fill=MUTED)
    title(im,120,'五类敌人 · 共享两帧动作','原有五类敌人分别获得独立造型；蝙蝠扇翼更快，其余使用轻微呼吸与迈步。')
    enemies=[('霜晶史莱姆',16,26),('白骨学徒',17,27),('暮晶蝙蝠',18,28),('寒霜守卫',24,29),('鎏金统领',25,30)]
    for n,(name,a,b) in enumerate(enemies):
        x=28+n*280;d.rounded_rectangle((x,200,x+264,410),radius=6,fill=PANEL,outline=LINE)
        paste(im,sprite(a),x+24,218,3);paste(im,sprite(b),x+145,218,3)
        d.text((x+22,330),name,font=FONT,fill=TEXT)
        d.text((x+22,365),'32×32 · 两帧',font=SMALL,fill=MUTED)
    title(im,438,'六种升级 · 独立图标')
    for n,(name,index) in enumerate(zip(('奥术强化','快速施法','冰霜法环','迅捷战靴','宝石磁力','治疗符文'),(20,22,21,31,32,23))):
        x=28+n*234;d.rectangle((x,490,x+218,650),fill=PANEL,outline=LINE)
        paste(im,sprite(index),x+61,500,3);d.text((x+36,608),name,font=FONT,fill=GOLD)
    title(im,678,'掉落与角色 · 清楚识别成长','经验按原有数值显示为水晶、晶簇或高阶棱晶；红心继续表示治疗。')
    for n,(name,index) in enumerate((('原角色 · 保留',0),('普通经验',19),('5+ 经验晶簇',33),('10+ 高阶经验',34),('治疗红心 · 重绘',23),('符文法环 · 闪烁',35))):
        x=28+n*234;paste(im,sprite(index),x+61,752,3);d.text((x+18,861),name,font=SMALL,fill=TEXT)
    title(im,916,'扩展素材 · 已制作，暂未接入','符文宝箱、蓝晶药瓶、霜晶花、秘库钥匙、命中星芒、召唤符文；不会随固件加载。')
    for n,(name,label) in enumerate((('chest_0','符文宝箱'),('chest_1','开启'),('vial_0','蓝晶药瓶'),('flower_0','霜晶花'),
                                    ('key_0','秘库钥匙'),('hit_0','命中星芒'),('summon_0','召唤符文'))):
        x=28+n*200;paste(im,Image.open(OUT/'reserve/png'/f'{name}.png').convert('RGBA'),x+26,992,3)
        d.text((x+25,1097),label,font=SMALL,fill=MUTED)
    im.save(OUT/'美术资源总览.png')
    before=Image.new('RGB',(1440,650),NAVY);d=ImageDraw.Draw(before)
    d.text((28,22),'从旧素材到统一的冰霜像素风',font=TITLE,fill=GOLD)
    d.text((28,90),'之前',font=SUB,fill=MUTED);d.text((28,330),'优化后',font=SUB,fill=ICE)
    for n,(name,a,b) in enumerate(enemies):
        x=190+n*245;old=a if a<25 else 24
        paste(before,sprite(old,BASE),x+40,130,4);paste(before,sprite(a),x+40,370,4)
        d.text((x+20,537),name,font=FONT,fill=TEXT)
    before.save(OUT/'敌人优化对比.png')
    heart=Image.new('RGB',(1000,430),NAVY);d=ImageDraw.Draw(heart)
    d.text((28,20),'治疗红心 · 像素轮廓与治疗符号',font=TITLE,fill=GOLD)
    for n,(old,label) in enumerate(((True,'之前 · 柔化边缘'),(False,'优化后 · 红心、金边与治疗十字'))):
        x=30+n*490;d.text((x,82),label,font=FONT,fill=ICE)
        paste(heart,sprite(23,BASE if old else RAW),x+100,128,6)
        paste(heart,sprite(23,BASE if old else RAW),x+190,350)
        d.text((x+230,352),'原尺寸',font=SMALL,fill=MUTED)
    heart.save(OUT/'红心优化对比.png')
    focus=Image.new('RGB',(1280,790),NAVY);d=ImageDraw.Draw(focus)
    d.text((28,20),'本轮重绘 · 经验、守卫、统领、法环',font=TITLE,fill=GOLD)
    for x,y,caption,detail,indices in (
        (28,95,'经验 · 青绿晶簇','加宽晶体，三档外观，避免与法环混淆。',(19,33,34)),
        (672,95,'守卫 · 冰铠与盾牌','加宽肩甲，封闭面甲，表现厚重近战单位。',(24,29)),
        (28,440,'统领 · 法冠与魔法书','骨白面具、紫色长袍、金色法冠与冰杖。',(25,30)),
        (672,440,'法环 · 镂空符文','中心留空，用环形轮廓与符文闪烁表现法术。',(21,35))):
        d.rectangle((x,y,x+580,y+310),fill=PANEL,outline=LINE)
        d.text((x+18,y+14),caption,font=SUB,fill=ICE);d.text((x+18,y+54),detail,font=SMALL,fill=MUTED)
        for n,index in enumerate(indices):
            px=x+30+n*(172 if len(indices)==3 else 250)
            paste(focus,sprite(index),px,y+98,4);paste(focus,sprite(index),px+49,y+254)
    focus.save(OUT/'重点调整预览.png')


def scene(ticks=0,before=False):
    im=Image.open(ROOT/'assets/ui/magic_book_v5/previews/game_play.png').convert('RGBA')
    field=Image.new('RGBA',(624,360),(*expand(0x1085),255))
    source=BASE if before else RAW
    positions=[(0,96,78),(1,480,90),(2,180,260),(3,510,270),(4,420,205),
               (0,190,128),(1,404,72),(2,492,182),(0,108,276)]
    for kind,x,y in positions:
        index=(16,17,18,24,24)[kind] if before else ((16,17,18,24,25),(26,27,28,29,30))[((ticks//(6 if kind==2 else 12))+kind)&1][kind]
        paste(field,sprite(index,source),x,y+((ticks//12+kind)&1))
    for n,(x,y) in enumerate(((188,40),(354,284),(240,306),(510,46),(390,256),(128,170))):
        index=19 if before else (19,19,33,34,33,19)[n]
        paste(field,sprite(index,source),x,y)
    paste(field,sprite(23,source),72,192)
    # The original hero keeps its real walk frames. Effects are compact sprites.
    paste(field,sprite((ticks//8)%4,source),296,164)
    for index,phase in enumerate((ticks, ticks+64)):
        a=phase*math.pi/64;x=round(312+64*math.cos(a))-16;y=round(180+64*math.sin(a))-16
        paste(field,sprite(21 if before or not ((ticks//8+index)&1) else 35,source),x,y)
    d=ImageDraw.Draw(field)
    for n in range(3):
        x=344+(ticks*3+n*24)%104;y=175-n*13
        d.rectangle((x,y,x+4,y+4),fill=(0,255,255,255));d.rectangle((x+1,y+1,x+3,y+3),fill=(160,240,255,255));d.point((x+2,y+2),fill='white')
    im.paste(field,(8,80))
    return im.convert('RGB')


def animation():
    scene().save(OUT/'游戏效果预览.png')
    board=Image.new('RGB',(1340,628),NAVY);d=ImageDraw.Draw(board)
    d.text((20,15),'纯色场景 · 美术替换前后',font=TITLE,fill=GOLD)
    for n,(old,label) in enumerate(((True,'之前'),(False,'优化后 · 原角色与全屏视口保留'))):
        x=20+n*660;d.text((x,76),label,font=FONT,fill=ICE);board.paste(scene(before=old),(x,106))
    board.save(OUT/'游戏优化对比.png')
    frames=[scene(n*3) for n in range(48)]
    samples=Image.new('RGB',(640*4,480*3))
    for i in range(12):samples.paste(frames[i*4],((i%4)*640,(i//4)*480))
    palette=samples.quantize(colors=256,dither=Image.Dither.NONE)
    quantized=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in frames]
    quantized[0].save(OUT/'游戏美术动态预览.gif',save_all=True,append_images=quantized[1:],duration=50,loop=0,optimize=False,disposal=1)


def package():
    runtime=json.loads((ROOT/'assets/game/manifest.json').read_text(encoding='utf-8'))
    directions=('down','left','right','up');catalog=[]
    atlas=Image.new('RGBA',(256,32*((len(RAW)//2048+7)//8)))
    for index in range(len(RAW)//2048):
        name=runtime['frame_names'].get(str(index),f'player_{directions[index//4]}_{index%4}' if index<16 else f'frame_{index}')
        im=sprite(index);im.save(OUT/'png'/f'{name}.png')
        (OUT/'rgb565'/f'{name}.rgb565').write_bytes(RAW[index*2048:(index+1)*2048])
        atlas.paste(im,((index%8)*32,(index//8)*32))
        catalog.append({'index':index,'name':name,'png':f'png/{name}.png','rgb565':f'rgb565/{name}.rgb565'})
    atlas.save(OUT/'spritesheet_rgba.png')
    (OUT/'sprite_catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    for name in ('game.rgb565','manifest.json'):
        (OUT/('runtime_'+name)).write_bytes((ROOT/'assets/game'/name).read_bytes())
    with zipfile.ZipFile(OUT.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():archive.write(p,Path('frost_v1')/p.relative_to(OUT))
        for name in ('game_assets.h','game_frame_bounds.h','game_art_ids.h'):
            archive.write(ROOT/'software'/name,'frost_v1/runtime/'+name)
        for p in sorted((ROOT/'assets/game/source/frost_v1').glob('*')):
            archive.write(p,'frost_v1/source/'+p.name)
        for name in ('prepare_frost_game_art.py','prepare_game_assets.py','preview_frost_game_art.py'):
            archive.write(ROOT/'tools'/name,'frost_v1/tools/'+name)
    print(json.dumps({'output':str(OUT),'runtime_frames':len(RAW)//2048,'runtime_bytes':len(RAW),
                      'reserve_loaded':False,'board_gameplay_capture':False},ensure_ascii=False))


if __name__=='__main__':
    gallery();animation();package()
