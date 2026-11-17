"""Compare actual C demo pages with the user's immutable local HTML.

Only measured values and moving test viewports are excluded. All other pixels,
including labels, fonts, badges, rules, spacing and footers, must match RGB565.
The copy/effects test images are compared as well because they are deterministic.
"""
from pathlib import Path
import base64, io, json
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/demo_reference'
OUT.mkdir(exist_ok=True)
html=(ROOT/'assets/ui/magic_book_v5/魔法书交互预览.html').read_text(encoding='utf-8')
pages,_=json.JSONDecoder().raw_decode(html[html.index('const pages=')+12:])
cases=[('fill','basic_reference_0_0_0',[(16,176,624,400)]),
 ('fill_detail','basic_reference_0_1_0',[(352,176,608,368)]),
 ('copy','basic_reference_1_0_0',[]),('copy_2','basic_reference_1_0_1',[]),
 ('copy_detail','basic_reference_1_1_0',[]),
 ('buffer','basic_reference_2_0_0',[]),('buffer_paused','basic_reference_2_0_1',[]),
 ('buffer_double','basic_reference_2_1_0',[]),('buffer_double_paused','basic_reference_2_1_1',[]),
 ('key','basic_effects_demo3_bg0_variant1',[]),('key_off','basic_effects_demo3_bg0_variant0',[]),
 ('key_magenta','basic_effects_demo3_bg0_variant3',[]),
 ('alpha','basic_effects_demo4_bg0_variant2',[]),('alpha_0','basic_effects_demo4_bg0_variant0',[]),
 ('alpha_128','basic_effects_demo4_bg0_variant1',[]),
 ('pressure_1','book_reference_pressure_entry',[(0,152,640,408)])]
results={}
for key,name,exclusions in cases:
    actual=Image.open(ROOT/'reports'/f'{name}.png').convert('RGB')
    raw=Image.open(io.BytesIO(base64.b64decode(pages[key].split(',')[1]))).convert('RGB')
    expected=Image.frombytes('RGB',raw.size,bytes(v for r,g,b in raw.getdata() for v in ((r>>3)*255//31,(g>>2)*255//63,(b>>3)*255//31)))
    if key.startswith('buffer'):
        exclusions += [(16,176,624,400),(176,84,296,98),(176,110,296,124),(496,84,616,98)]
    if key.startswith(('key','alpha')):
        exclusions += [(120,124,168,138)]
    mask=Image.new('1',(640,480),1);md=ImageDraw.Draw(mask)
    for x0,y0,x1,y1 in exclusions:md.rectangle((x0,y0,x1-1,y1-1),fill=0)
    diff=ImageChops.difference(actual,expected);diff.paste((0,0,0),mask=ImageChops.invert(mask.convert('L')))
    count=sum(v!=(0,0,0) for v in diff.getdata());results[key]={'different_pixels':count,'compared_pixels':sum(mask.getdata()),'excluded_rectangles':exclusions}
    diff.save(OUT/f'{key}_diff.png')
    if count:
        pts=[(x,y,actual.getpixel((x,y)),expected.getpixel((x,y))) for y in range(480) for x in range(640) if diff.getpixel((x,y))!=(0,0,0)]
        print(key,count,'bounds',diff.getbbox(),'first',pts[:3])
    if key in ('fill','copy','buffer','key','alpha','pressure_1'):actual.save(OUT/f'{key}.png')
(OUT/'comparison.json').write_text(json.dumps(results,indent=2)+'\n')
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
gallery=Image.new('RGB',(1280,1512),'#171626');gd=ImageDraw.Draw(gallery)
for n,(key,label) in enumerate([('fill','矩形填充'),('copy','图像复制'),('buffer','双缓冲'),('key','颜色键'),('alpha','透明混合'),('pressure_1','压力测试')]):
    x=n%2*640;y=n//2*504;gd.text((x+12,y+2),label,font=font,fill='#e4ca8c');gallery.paste(Image.open(OUT/f'{key}.png'),(x,y+24))
gallery.save(ROOT/'reports/reference_demo_gallery.png')
assert all(v['different_pixels']==0 for v in results.values()),'Demo layout differs from the local HTML'
print(f'PASS DEMO REFERENCE: {len(results)} actual C demo pages; static layouts and deterministic test images match RGB565.')
