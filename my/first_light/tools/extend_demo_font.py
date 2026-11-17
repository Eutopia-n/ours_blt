"""Append missing demo glyphs using the same local Fusion Pixel 12px font.

Existing game/menu glyphs stay byte-for-byte identical and in the same order.
"""
from pathlib import Path
import argparse,re
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--font',type=Path,default=ROOT.parents[3]/'素材/像素游戏字体样张与字库/fonts/fusion12/fusion-pixel-12px-monospaced-zh_hans.ttf')
args=parser.parse_args()
path=ROOT/'software/font_cn.h';source=path.read_text(encoding='utf-8')
existing={int(cp,16):[int(x,16) for x in re.findall(r'0x[0-9a-f]+',rows)]
          for cp,rows in re.findall(r'\{0x([0-9a-f]+),\{([^}]+)\}\}',source)}
font=ImageFont.truetype(str(args.font),12)
def bitmap(cp):
    im=Image.new('1',(14,14));ImageDraw.Draw(im).text((1,1),chr(cp),font=font,fill=1)
    return [sum(im.getpixel((x,y))<<x for x in range(14)) for y in range(14)]
assert all(bitmap(ord(c))==existing[ord(c)] for c in '矩形填充颜色键透明度'),'Font differs from the existing Fusion Pixel glyphs'
needed=set()
for name in ('software/main.c','software/basic_demo.h','software/effects_demo.h'):
    for literal in re.findall(r'"((?:[^"\\]|\\.)*)"',(ROOT/name).read_text(encoding='utf-8')):
        needed.update(ord(c) for c in literal if ord(c)>127)
added=sorted(needed-existing.keys())
lines=[]
for cp in added:
    rows=bitmap(cp);assert any(rows),hex(cp)
    lines.append('    {0x%x,{%s}}, // %s\n'%(cp,','.join('0x%04x'%v for v in rows),chr(cp)))
if lines:
    at=source.index('\n};',source.index('static const FontCnGlyph font_cn_glyphs[]'))
    source=source[:at+1]+''.join(lines)+source[at+1:]
    path.write_text(source,encoding='utf-8',newline='\n')
print('Added',len(added),'Fusion Pixel glyphs:', ''.join(chr(cp) for cp in added),'; all original glyphs preserved')
