"""Author project-native 32px frost sprites; keep the original player intact.

Normal firmware builds only read the resulting PNGs, using the standard-library
RGB565 packer. Pillow is needed here only when editing/regenerating the artwork.
"""
from pathlib import Path
import hashlib
import json
import math
import struct
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'assets/game/source/frost_v1'
OUT = ROOT/'assets/game/frost_v1'
for folder in (SOURCE, OUT/'png', OUT/'rgb565', OUT/'reserve/png', OUT/'reserve/rgb565'):
    folder.mkdir(parents=True, exist_ok=True)

# Clustered shading, a single dark contour and restrained brass accents match
# the blue-hood player and the indigo/gold book. No antialiasing or gradients.
COLORS = {
    'ink':'101626', 'edge':'23334b', 'navy':'273657', 'blue_dark':'185574',
    'blue':'248bac', 'cyan':'49c8dc', 'ice':'a3edf2', 'white':'edf6e8',
    'violet_dark':'393155', 'violet':'705a9b', 'lilac':'b69cda',
    'gold_dark':'68513c', 'gold':'b88b50', 'gold_light':'f2d491',
    'bone_shadow':'938d9b', 'bone':'d5d3cb', 'red_dark':'66334d',
    'red':'be6370', 'green':'78bd9b',
    'heart_red':'ce404e', 'heart_light':'f5817e', 'heart_shadow':'822c48',
    'xp_dark':'165e61', 'xp_mid':'219c8b', 'xp_light':'67dbc1', 'xp_white':'c8ffe0',
}
PAL = {k:tuple(bytes.fromhex(v))+(255,) for k,v in COLORS.items()}


class Pixel:
    """Small integer-coordinate painter; all contours land on real pixels."""
    def __init__(self):
        self.im = Image.new('RGBA',(32,32))
        self.d = ImageDraw.Draw(self.im)

    def box(self,box,color):
        self.d.rectangle(box,fill=PAL[color])

    def line(self,points,color,width=1):
        self.d.line(points,fill=PAL[color],width=width)

    def poly(self,points,color,outline=None):
        self.d.polygon(points,fill=PAL[color])
        if outline:self.line(points+[points[0]],outline)

    def dot(self,x,y,color):
        self.d.point((x,y),fill=PAL[color])


def crystal(p,cx,cy,w=5,h=10,tone='blue',spark=False):
    p.poly([(cx,cy-h),(cx+w,cy-1),(cx,cy+h),(cx-w,cy-1)],'ink')
    p.poly([(cx,cy-h+2),(cx+w-2,cy-1),(cx,cy+h-2),(cx-w+2,cy-1)],tone)
    p.poly([(cx,cy-h+2),(cx,cy+h-3),(cx-w+2,cy-1)],'cyan')
    p.line([(cx,cy-h+2),(cx-w+2,cy-1)],'ice')
    p.line([(cx,cy-h+3),(cx,cy-2)],'white')
    if spark:
        p.line([(cx+w+1,cy-7),(cx+w+1,cy-3)],'gold_light')
        p.line([(cx+w-1,cy-5),(cx+w+3,cy-5)],'gold_light')


def slime(phase):
    p=Pixel();low=phase
    p.poly([(7,27),(7,19+low),(9,19+low),(9,14+low),(12,11+low),(20,11+low),
            (23,14+low),(23,19+low),(25,19+low),(25,27),(22,29),(10,29)],'ink')
    p.poly([(9,25),(10,17+low),(13,13+low),(19,13+low),(22,17+low),(23,26),
            (20,27),(12,27)],'blue_dark')
    p.poly([(10,19+low),(12,14+low),(19,13+low),(21,16+low),(21,24),(13,25),(10,23)],'blue')
    p.poly([(11,18+low),(13,14+low),(18,14+low),(17,17+low)],'cyan')
    for x in (13,19):
        p.box((x,19+low,x+2,22+low),'ink');p.dot(x,19+low,'gold_light')
    p.line([(15,24+low),(17,24+low)],'ice')
    p.line([(10,27),(13,27)],'cyan');p.line([(19,27),(22,27)],'blue')
    crystal(p,16,9+low,4,6)
    p.dot(10,22,'ice');p.dot(21,24,'cyan')
    return p.im


def acolyte(phase):
    p=Pixel();shift=phase
    p.poly([(8,29),(10,22),(10,13),(12,8),(20,8),(23,12),(23,22),(25,29),
            (20,28),(17,30),(14,28),(11,30)],'ink')
    p.poly([(11,25),(12,14),(14,10),(19,10),(21,14),(22,25),(20,27),(18,26),
            (16,28),(13,27)],'violet_dark')
    p.poly([(12,20),(13,12),(16,10),(16,24),(13,27)],'navy')
    p.line([(12,24),(12,27),(15,27)],'blue')
    p.poly([(12,13),(13,10),(19,10),(21,13),(20,19),(18,20),(14,20),(12,18)],'bone_shadow')
    p.poly([(13,12),(15,11),(19,11),(20,13),(19,17),(17,19),(14,18),(13,16)],'bone')
    p.line([(14,11),(18,11)],'white')
    p.box((13,14,15,16),'ink');p.box((18,14,20,16),'ink')
    p.dot(14,15,'cyan');p.dot(18,15,'cyan')
    p.line([(16,17),(16,19)],'ink');p.dot(18,19,'ink')
    p.line([(10,22+shift),(8,23+shift),(8,26+shift)],'bone')
    p.box((22,21-shift,24,23-shift),'bone');p.line([(25,15),(25,29)],'gold_dark')
    p.line([(26,16),(26,28)],'gold');crystal(p,25,13,3,5)
    p.box((15,22,19,23),'gold_dark');p.dot(17,22,'gold_light')
    return p.im


def bat(phase):
    p=Pixel()
    wing=[(14,18),(10,10),(6,8),(6,13),(2,11),(3,19),(6,22),(9,20),(12,23),(15,22)] if not phase else [
          (14,17),(10,14),(5,15),(2,20),(6,20),(5,25),(10,23),(12,25),(15,21)]
    for flip in (False,True):
        points=[(31-x if flip else x,y) for x,y in wing]
        p.poly(points,'violet_dark','ink')
        p.line([(31-x if flip else x,y) for x,y in [(13,18),(9,13 if not phase else 18),(5,15 if not phase else 21)]],'violet',2)
        p.line([(31-x if flip else x,y) for x,y in [(12,18),(9,17 if not phase else 20),(7,18 if not phase else 22)]],'lilac')
    p.poly([(12,23),(12,16),(11,10),(15,13),(18,13),(21,10),(20,17),(20,23),(16,26)],'ink')
    p.poly([(14,21),(14,16),(17,15),(19,17),(18,23),(16,24)],'navy')
    p.line([(13,17),(15,18)],'ice');p.line([(18,18),(20,17)],'ice')
    p.dot(15,21,'white');p.dot(18,21,'white');p.dot(17,14,'gold')
    return p.im


def guardian(phase,elite=False):
    if elite:return commander(phase)
    p=Pixel()
    # Broad closed armour and a shield distinguish this from the robed units.
    p.poly([(3,25),(3,16),(7,12),(8,7),(11,4),(21,4),(24,8),(24,12),(28,15),
            (30,23),(27,28),(22,28),(22,31),(17,31),(16,28),(14,31),(9,31),(9,28),(5,28)],'ink')
    p.poly([(8,15),(10,8),(13,6),(20,6),(22,9),(22,16),(19,18),(12,18)],'blue_dark')
    p.poly([(10,9),(13,6),(19,6),(21,9),(20,11),(10,11)],'blue')
    p.line([(11,8),(14,6),(19,6)],'ice')
    p.box((10,11,21,13),'ink');p.line([(12,12),(14,12)],'cyan');p.line([(18,12),(20,12)],'cyan')
    p.line([(16,8),(16,16)],'bone');p.line([(17,8),(17,15)],'blue')
    p.poly([(7,16),(11,17),(21,17),(25,20),(22,27),(10,27),(7,23)],'navy','ink')
    p.poly([(11,19),(16,18),(21,19),(20,24),(16,27),(12,24)],'blue_dark')
    p.line([(12,19),(16,18),(20,19)],'ice');p.line([(16,21),(16,24)],'cyan')
    p.line([(14,22),(18,22)],'white')
    p.poly([(3,17+phase),(5,14+phase),(10,16+phase),(9,23+phase),(5,25+phase),(3,23+phase)],'blue_dark','ink')
    p.line([(4,17+phase),(6,15+phase),(9,17+phase)],'ice');p.box((4,22+phase,7,24+phase),'blue')
    p.poly([(22,17-phase),(26,15-phase),(30,18-phase),(29,25-phase),(25,29-phase),(21,24-phase)],'blue_dark','ink')
    p.line([(23,18-phase),(26,16-phase),(29,19-phase),(28,24-phase),(25,27-phase)],'ice')
    p.line([(26,19-phase),(25,25-phase)],'cyan')
    p.box((10,28,14,29+phase),'blue_dark');p.box((18,28,22,30-phase),'blue_dark')
    p.line([(10,29+phase),(14,29+phase)],'blue');p.line([(18,30-phase),(22,30-phase)],'blue')
    return p.im


def commander(phase):
    """Crowned archivist: bone mask, long cape, book and crystal staff."""
    p=Pixel()
    p.poly([(7,30),(8,17),(10,14),(10,7),(12,4),(19,4),(22,7),(22,14),
            (24,18),(25,30),(20,28),(16,31),(12,29)],'ink')
    p.poly([(10,18),(13,15),(19,15),(22,18),(23,28),(19,27),(16,29),(11,28)],'violet_dark')
    p.poly([(11,20),(13,17),(15,17),(14,27),(11,28)],'violet')
    p.line([(20,19),(22,27),(20,27)],'violet');p.line([(15,19),(15,26),(17,27)],'gold_dark')
    p.poly([(11,8),(13,6),(18,6),(20,8),(19,13),(17,15),(13,14),(11,11)],'bone_shadow')
    p.poly([(12,8),(14,7),(18,7),(19,9),(17,13),(14,13),(12,11)],'bone')
    p.box((12,9,14,10),'ink');p.box((17,9,19,10),'ink');p.dot(13,10,'ice');p.dot(18,10,'ice')
    p.line([(15,11),(15,13)],'ink')
    p.poly([(10,5),(9,1),(13,3),(16,0),(19,3),(23,1),(22,5),(19,7),(12,7)],'gold_dark','ink')
    p.line([(10,3),(12,5),(20,5),(22,3)],'gold_light');p.dot(16,3,'cyan')
    p.poly([(10,16),(13,15),(16,18),(19,15),(22,16),(19,20),(13,20)],'gold_dark')
    p.line([(11,16),(16,18),(21,16)],'gold');p.dot(16,19,'ice')
    p.poly([(3,18+phase),(9,17+phase),(12,19+phase),(11,25+phase),(5,26+phase),(2,23+phase)],'ink')
    p.box((4,20+phase,9,24+phase),'navy');p.line([(4,19+phase),(9,18+phase),(10,20+phase)],'gold')
    p.line([(4,24+phase),(9,24+phase)],'bone');p.dot(7,21+phase,'cyan')
    p.line([(26,9),(26,30)],'gold_dark',2);p.line([(27,11),(27,29)],'gold')
    p.box((23,18-phase,25,20-phase),'bone');crystal(p,27,7,4,6)
    p.line([(13,29-phase),(15,29-phase)],'gold');p.line([(19,28+phase),(22,28+phase)],'gold_dark')
    return p.im


def gem(tier):
    p=Pixel()
    def chunk(cx,cy,w,h):
        p.poly([(cx-w,cy-3),(cx-3,cy-h),(cx+3,cy-h),(cx+w,cy-3),(cx+w-1,cy+4),(cx,cy+h),(cx-w+1,cy+4)],'ink')
        p.poly([(cx-w+2,cy-2),(cx-2,cy-h+2),(cx+2,cy-h+2),(cx+w-2,cy-2),(cx+w-3,cy+3),(cx,cy+h-2),(cx-w+3,cy+3)],'xp_dark')
        p.poly([(cx-w+2,cy-2),(cx-2,cy-h+2),(cx+1,cy-h+2),(cx,cy+h-2),(cx-w+3,cy+3)],'xp_mid')
        p.poly([(cx-w+2,cy-2),(cx-2,cy-h+2),(cx+1,cy-h+2),(cx+2,cy-2)],'xp_light')
        p.line([(cx-2,cy-h+2),(cx+1,cy-h+2),(cx+2,cy-3)],'xp_white')
        p.line([(cx,cy),(cx,cy+h-3)],'xp_light')
    if tier==0:chunk(16,16,7,9)
    elif tier==1:
        chunk(9,20,5,7);chunk(23,20,5,7);chunk(16,13,7,10)
    else:
        chunk(8,22,6,7);chunk(24,22,6,7);chunk(16,13,8,11)
        p.line([(3,8),(7,8)],'xp_white');p.line([(5,6),(5,10)],'xp_white')
        p.line([(26,8),(30,8)],'xp_light');p.line([(28,6),(28,10)],'xp_light')
    return p.im


def power():
    p=Pixel();p.poly([(16,3),(24,7),(28,16),(24,25),(16,29),(8,25),(4,16),(8,7)],'ink')
    p.poly([(16,5),(23,9),(26,16),(22,24),(16,27),(9,23),(6,16),(10,9)],'gold_dark')
    p.line([(9,10),(16,6),(22,10)],'gold_light');p.line([(8,21),(11,24),(16,26)],'gold')
    crystal(p,16,16,6,10)
    for x,y in ((5,5),(26,26)):p.line([(x-1,y),(x+1,y)],'ice');p.line([(x,y-1),(x,y+1)],'ice')
    return p.im


def orbit(phase):
    p=Pixel()
    p.poly([(11,2),(21,2),(29,10),(29,21),(21,29),(10,29),(2,21),(2,11)],'ink')
    p.line([(11,4),(21,4),(27,10),(27,21),(21,27),(10,27),(4,21),(4,11),(11,4)],'blue',2)
    p.line([(11,5),(20,5),(26,11)],'ice');p.line([(26,21),(20,26),(11,26)],'cyan')
    p.d.polygon([(12,8),(20,8),(24,12),(24,20),(20,24),(12,24),(8,20),(8,12)],fill=(0,0,0,0))
    # The empty centre keeps the ring distinct from the filled XP gems.
    for n,(x,y) in enumerate(((16,4),(27,16),(16,27),(4,16))):
        p.poly([(x,y-3),(x+2,y),(x,y+3),(x-2,y)],'white' if (n+phase)%2 else 'cyan')
    for n,(x,y) in enumerate(((8,8),(24,8),(24,24),(8,24))):
        p.line([(x-1,y-1),(x+1,y-1),(x+1,y+1)],'gold' if (n+phase)%2 else 'ice')
    return p.im


def scroll():
    p=Pixel();p.poly([(8,4),(25,4),(28,7),(26,10),(23,10),(23,25),(20,28),(5,28),(3,25),(5,22),(8,22)],'ink')
    p.box((9,6,23,24),'gold');p.box((10,7,21,23),'bone');p.line([(11,7),(21,7)],'white')
    p.line([(6,24),(6,26),(19,26),(21,24)],'gold_light',2)
    p.line([(10,10),(20,10)],'gold_dark');p.line([(11,21),(19,21)],'gold_dark')
    p.poly([(17,11),(12,17),(16,17),(14,22),(21,15),(17,15)],'blue_dark')
    p.line([(17,12),(14,16),(18,16),(16,19)],'cyan')
    p.box((24,6,25,8),'gold_light')
    return p.im


def boots():
    p=Pixel()
    for x,y in ((5,7),(16,4)):
        p.poly([(x,y),(x+8,y),(x+8,y+11),(x+11,y+14),(x+11,y+19),(x-1,y+19),(x-2,y+15),(x+1,y+11)],'ink')
        p.poly([(x+2,y+2),(x+6,y+2),(x+6,y+12),(x+9,y+15),(x+9,y+17),(x,y+17),(x,y+15),(x+3,y+11)],'blue_dark')
        p.line([(x+3,y+3),(x+5,y+3),(x+5,y+11)],'blue')
        p.line([(x+1,y+6),(x+7,y+6)],'gold');p.box((x+3,y+5,x+5,y+7),'gold_light')
        p.line([(x,y+17),(x+9,y+17)],'gold_dark');p.dot(x+8,y+15,'cyan')
    return p.im


def magnet():
    p=Pixel()
    p.poly([(6,6),(13,6),(13,20),(16,23),(19,20),(19,6),(26,6),(26,22),(21,28),(11,28),(6,22)],'ink')
    p.poly([(8,8),(11,8),(11,21),(15,25),(18,25),(22,21),(22,8),(24,8),(24,21),(20,26),(12,26),(8,21)],'blue')
    p.line([(9,11),(9,21),(13,25)],'cyan');p.line([(23,11),(23,20)],'ice')
    p.box((8,7,11,11),'gold');p.box((21,7,24,11),'gold_light')
    crystal(p,16,10,3,6);p.dot(4,16,'ice');p.dot(28,17,'gold_light')
    return p.im


def healing_heart():
    """Red healing pickup with a crisp heart silhouette and an ivory cross."""
    p=Pixel()
    p.poly([(5,8),(5,6),(8,3),(12,3),(16,6),(20,3),(24,3),(27,6),(27,12),
            (24,17),(16,26),(8,18),(5,12)],'ink')
    p.poly([(7,8),(7,7),(9,5),(12,5),(16,9),(20,5),(23,5),(25,7),(25,12),
            (22,17),(16,23),(10,17),(7,12)],'heart_shadow')
    p.poly([(8,8),(10,6),(12,6),(16,10),(20,6),(23,6),(24,8),(23,13),
            (17,20),(15,21),(10,16),(8,12)],'heart_red')
    p.poly([(8,9),(10,6),(12,6),(15,10),(12,12),(9,12)],'heart_light')
    p.line([(9,5),(12,5),(15,8)],'gold_dark')
    p.line([(20,5),(23,5),(25,7)],'gold')
    p.line([(10,18),(16,24),(23,17)],'gold_dark')
    p.line([(16,23),(20,19)],'gold')
    p.line([(10,7),(12,7)],'white');p.dot(9,8,'white')
    p.box((15,11,17,18),'heart_shadow');p.box((12,13,20,16),'heart_shadow')
    p.line([(16,11),(16,17)],'white');p.line([(13,14),(19,14)],'white')
    p.dot(17,12,'gold_light');p.dot(17,16,'gold_light')
    return p.im


def reserve_art(name,phase=0):
    p=Pixel()
    if name=='hit':
        r=10 if phase else 6
        p.poly([(16,16-r),(18,13),(24,10),(21,15),(27,16),(20,18),(23,23),(17,20),
                (16,16+r),(14,20),(9,23),(11,17),(5,16),(12,14),(10,9),(15,12)],'blue')
        p.line([(16,10),(16,22)],'ice');p.line([(10,16),(22,16)],'ice')
        p.box((14,14,18,18),'white');p.dot(25,7,'gold_light')
    elif name=='summon':
        for n in range(12):
            a=n*math.pi/6+phase*math.pi/12
            x,y=round(16+11*math.cos(a)),round(16+8*math.sin(a))
            p.box((x,y,x+1,y+1),'cyan' if n%3 else 'gold')
        p.line([(10,13),(16,21),(22,13),(10,13)],'blue');p.dot(16,10,'white')
    elif name=='chest':
        p.poly([(5,28),(5,13),(8,9),(24,9),(27,13),(27,28)],'ink')
        p.box((7,14,25,26),'navy');p.box((8,11,24,16),'blue_dark')
        p.line([(7,17),(25,17)],'gold');p.line([(8,12),(8,26),(24,26),(24,12)],'gold_dark')
        p.box((14,16,18,21),'gold');p.dot(16,18,'ice')
        if phase:
            p.box((8,9,24,16),'ink');p.line([(7,8),(9,4),(25,6),(26,10)],'gold')
            crystal(p,16,12,4,8);p.dot(9,6,'white');p.dot(24,3,'ice')
    elif name=='vial':
        p.box((13,4,19,7),'gold_dark');p.line([(13,4),(19,4)],'gold_light')
        p.poly([(12,8),(20,8),(20,13),(24,17),(24,25),(20,29),(12,29),(8,25),(8,17),(12,13)],'ink')
        p.poly([(14,9),(18,9),(18,15),(22,18),(22,24),(19,27),(13,27),(10,24),(10,18),(14,15)],'blue_dark')
        p.box((12,20,20,25),'blue');p.line([(11,18),(11,23),(13,25)],'ice');p.dot(18,20,'cyan')
        p.line([(14,10),(14,14)],'white')
    elif name=='flower':
        p.line([(16,27),(16,15)],'blue_dark',2)
        p.poly([(16,23),(10,19),(11,24),(16,26)],'blue')
        for a in range(6):
            x,y=round(16+6*math.cos(a*math.pi/3)),round(12+6*math.sin(a*math.pi/3))
            p.poly([(16,12),(x-2,y-2),(x+2,y-2),(x+2,y+2)],'cyan','blue_dark')
        p.box((14,10,18,14),'gold_light');p.dot(15,11,'white')
    elif name=='key':
        p.poly([(10,4),(17,4),(21,8),(21,15),(17,19),(14,19),(14,27),(10,29),(7,26),(7,23),(10,23),(10,18),(6,14),(6,8)],'ink')
        p.line([(10,7),(17,7),(18,10),(18,14),(15,16),(10,16),(9,13),(9,10),(10,7)],'gold',2)
        p.line([(12,17),(12,25),(10,26)],'gold_light',2);p.line([(10,23),(7,23)],'gold')
        crystal(p,14,11,3,5)
    return p.im


def rgba565(im):
    result=[]
    for r,g,b,a in im.getdata():
        result.append(0 if a<128 else max(1,((r>>3)<<11)|((g>>2)<<5)|(b>>3)))
    return b''.join(struct.pack('<H',v) for v in result)


def main():
    sprites={
        16:('frost_slime_0','霜晶史莱姆',slime(0)),17:('bone_acolyte_0','白骨学徒',acolyte(0)),
        18:('rune_bat_0','暮晶蝙蝠',bat(0)),19:('xp_crystal','经验水晶',gem(0)),
        20:('power_seal','奥术强化',power()),21:('orbit_crystal_0','冰霜法环',orbit(0)),
        22:('cast_scroll','快速施法',scroll()),23:('healing_heart','治疗红心',healing_heart()),
        24:('frost_guardian_0','寒霜守卫',guardian(0)),
        25:('crown_guardian_0','鎏金统领',guardian(0,True)),
        26:('frost_slime_1','霜晶史莱姆',slime(1)),27:('bone_acolyte_1','白骨学徒',acolyte(1)),
        28:('rune_bat_1','暮晶蝙蝠',bat(1)),29:('frost_guardian_1','寒霜守卫',guardian(1)),
        30:('crown_guardian_1','鎏金统领',guardian(1,True)),31:('swift_boots','迅捷战靴',boots()),
        32:('crystal_magnet','宝石磁力',magnet()),33:('xp_cluster','经验晶簇',gem(1)),
        34:('xp_crown','高阶经验棱晶',gem(2)),35:('orbit_crystal_1','冰霜法环',orbit(1)),
    }
    entries=[]
    for index,(name,label,im) in sprites.items():
        im.save(SOURCE/f'{name}.png');im.save(OUT/'png'/f'{name}.png')
        raw=rgba565(im);(OUT/'rgb565'/f'{name}.rgb565').write_bytes(raw)
        entries.append({'index':index,'name':name,'label':label,'path':f'{name}.png','sha256':hashlib.sha256(raw).hexdigest()})
    meta={'style':'frost_pixel_v1','frame_count':36,'base':'../base_game_v1.rgb565',
          'player_frames_preserved':list(range(16)),'healing_heart_redesigned':23,
          'frames':entries,'enemy_frames':[[16,17,18,24,25],[26,27,28,29,30]],
          'upgrade_icons':[20,22,21,31,32,23],'gem_frames':[19,33,34],
          'reserve_loaded_by_firmware':False}
    (SOURCE/'art.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    reserve=[]
    for kind,phases,label in [('hit',2,'命中星芒'),('summon',2,'召唤符文'),('chest',2,'符文宝箱'),
                               ('vial',1,'蓝晶药瓶'),('flower',1,'霜晶花'),('key',1,'秘库钥匙')]:
        for phase in range(phases):
            name=f'{kind}_{phase}';im=reserve_art(kind,phase);im.save(OUT/'reserve/png'/f'{name}.png')
            (OUT/'reserve/rgb565'/f'{name}.rgb565').write_bytes(rgba565(im))
            reserve.append({'name':name,'label':label,'frame':phase,'integrated':False})
    meta['reserve']=reserve
    (OUT/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    subprocess.run([sys.executable,ROOT/'tools/prepare_game_assets.py'],check=True,cwd=ROOT)
    print('Frost art: 20 authored runtime frames, 9 reserve frames; original player retained, red healing heart redesigned.')


if __name__=='__main__':
    main()
