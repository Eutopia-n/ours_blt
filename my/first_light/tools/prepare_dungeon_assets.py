"""Compile W1 wall modules; floor art is retained as an unused historical source."""
from pathlib import Path
from PIL import Image
import hashlib,json,struct

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/dungeon'
SIZE=32
# Original 1254px previews. Each crop is one slab / one oriented wall module.
CROPS=[
    ('north','W1',(147,270,286,388)),
    ('south','W1',(147,862,286,981)),
    ('west','W1',(32,389,144,519)),
    ('east','W1',(1102,389,1222,519)),
    ('nw','W1',(32,260,145,389)),
    ('ne','W1',(1102,260,1222,389)),
    ('sw','W1',(32,862,145,982)),
    ('se','W1',(1102,862,1222,982)),
]

def main():
    sources={n:Image.open(OUT/'source'/f'{n}.png').convert('RGBA')for n in ['W1']}
    frames=[]
    for name,source,box in CROPS:
        crop=sources[source].crop(box).resize((SIZE,SIZE),Image.Resampling.NEAREST)
        # Static, opaque backdrop: transparent edge pixels become the existing navy.
        base=Image.new('RGBA',crop.size,(16,16,41,255));base.alpha_composite(crop)
        frames.append(base.convert('RGB'))
    atlas=Image.new('RGB',(SIZE*len(frames),SIZE))
    for n,im in enumerate(frames):atlas.paste(im,(n*SIZE,0))
    q=atlas.quantize(colors=64,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE).convert('RGB')
    raw=[]
    for n in range(len(frames)):
        raw.append([((r>>3)<<11)|((g>>2)<<5)|(b>>3)for r,g,b in q.crop((n*SIZE,0,(n+1)*SIZE,SIZE)).getdata()])
    palette=sorted(set(p for frame in raw for p in frame));lookup={p:i for i,p in enumerate(palette)}
    assert len(palette)<=64
    tokens=[];offsets=[0]
    for frame in raw:
        i=0
        while i<len(frame):
            run=1
            while i+run<len(frame)and frame[i+run]==frame[i]and run<1023:run+=1
            tokens.append((run<<6)|lookup[frame[i]]);i+=run
        offsets.append(len(tokens))
    assert [palette[t&63]for t in tokens for _ in range(t>>6)]==sum(raw,[])
    def array(typ,name,values):
        return f'static const {typ} {name}[{len(values)}]={{\n'+''.join('    '+','.join(map(str,values[i:i+16]))+',\n'for i in range(0,len(values),16))+'};\n'
    header='''/* Generated from approved W1 by prepare_dungeon_assets.py. */
#ifndef DUNGEON_ASSETS_H
#define DUNGEON_ASSETS_H
#include <stdint.h>
#define DUNGEON_TILE_SIZE 32u
#define DUNGEON_TILE_COUNT 8u
#define DUNGEON_TILE_BASE (ASSET_BASE+0x30000u)
#define DUNGEON_TILE_BYTES (DUNGEON_TILE_COUNT*2048u)
'''
    header+=array('uint16_t','dungeon_palette',palette)+array('uint16_t','dungeon_rle',tokens)+array('uint16_t','dungeon_offsets',offsets)+'#endif\n'
    (ROOT/'software/dungeon_assets.h').write_text(header,encoding='utf-8')
    blob=b''.join(struct.pack('<H',p)for frame in raw for p in frame);(OUT/'tiles.rgb565').write_bytes(blob)
    for n,frame in enumerate(raw):
        im=Image.new('RGB',(SIZE,SIZE));im.putdata([(((p>>11)&31)*255//31,((p>>5)&63)*255//63,(p&31)*255//31)for p in frame]);im.save(OUT/f'{CROPS[n][0]}.png')
    meta={'selected':['W1'],'tile_size':SIZE,'tile_count':len(raw),'tile_ddr_bytes':len(blob),
          'compressed_rom_bytes':2*(len(tokens)+len(palette)+len(offsets)),
          'world_size':[2048,1408],'world_rgb565_bytes':0,
          'wall_ddr_bytes':434176,'wall_ddr_base':'0x01240000','wall_ddr_end_exclusive':'0x012aa000',
          'road_width':0,'ring_radii':[],
          'source_sha256':{n:hashlib.sha256((OUT/'source'/f'{n}.png').read_bytes()).hexdigest()for n in sources},
          'crops':[{'name':n,'source':s,'crop':box}for n,s,box in CROPS],
          'sha256':hashlib.sha256(blob).hexdigest(),'palette_colors':len(palette)}
    (OUT/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('DUNGEON ASSETS:',json.dumps({k:meta[k]for k in ['selected','tile_ddr_bytes','compressed_rom_bytes','wall_ddr_bytes','palette_colors']}))

if __name__=='__main__':main()
