"""Validate the actual C-baked map against independent raster geometry and art."""
from pathlib import Path
from array import array
from PIL import Image
import json,sys
ROOT=Path(__file__).resolve().parents[1]
world=array('H');world.frombytes((ROOT/'reports/dungeon_world.rgb565').read_bytes())
tiles=array('H');tiles.frombytes((ROOT/'assets/dungeon/tiles.rgb565').read_bytes())
if sys.byteorder!='little':world.byteswap();tiles.byteswap()
assert len(world)==2048*1408 and len(tiles)==8*1024
counts={'background':0,'roads':0,'walls':0}
for y in range(1408):
    for x in range(2048):
        tx=x%32;ty=y%32
        if y<32:tile=4 if x<32 else 5 if x>=2016 else 0;kind='walls'
        elif y>=1376:tile=6 if x<32 else 7 if x>=2016 else 1;kind='walls'
        elif x<32:tile=2;kind='walls'
        elif x>=2016:tile=3;kind='walls'
        else:
            kind='background';tile=-1
        expected=0x1085 if tile<0 else tiles[tile*1024+ty*32+tx]
        assert world[y*2048+x]==expected,(x,y,world[y*2048+x],expected)
        counts[kind]+=1
assert counts['walls']==2048*1408-(2048-64)*(1408-64)
# No per-frame tile list: the immutable buffer is the render source.
meta=json.loads((ROOT/'assets/dungeon/manifest.json').read_text())
assert meta['world_rgb565_bytes']==0 and meta['wall_ddr_bytes']==434176
def rgb(p):return (((p>>11)&31)*255//31,((p>>5)&63)*255//63,(p&31)*255//31)
preview=Image.frombytes('RGB',(2048,1408),bytes(channel for p in world for channel in rgb(p)))
altar=array('H');altar.frombytes((ROOT/'assets/scenery/scenery.rgb565').read_bytes())
if sys.byteorder!='little':altar.byteswap()
altar_size=128;assert len(altar)==altar_size*altar_size
for y in range(altar_size):
    for x in range(altar_size):
        if altar[y*altar_size+x]:preview.putpixel((1024-altar_size//2+x,704-altar_size//2+y),rgb(altar[y*altar_size+x]))
preview.save(ROOT/'reports/dungeon_world.png')
(ROOT/'reports/dungeon_geometry.json').write_text(json.dumps({'dimensions':[2048,1408],'pixels_verified':len(world),
    'wall_width':32,'ring_radii':[],'altar_size':128,'center':[1024,704],'pixels':counts},indent=2)+'\n')
print(f'DUNGEON GEOMETRY PASSED: {len(world)} RGB565 pixels; no floor/roads, 4 W1 walls/corners, 128px altar; {counts}')
