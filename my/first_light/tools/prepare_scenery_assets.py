"""Compile approved transparent cutouts into bounded RGB565 game resources."""
from pathlib import Path
from PIL import Image
import struct,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/scenery'
def sprite(name,size,pad):
    image=Image.open(OUT/'source'/f'{name}_cutout.png').convert('RGBA')
    alpha=image.getchannel('A');assert alpha.getextrema()[0]==0 and alpha.getextrema()[1]==255
    box=alpha.point(lambda a:255 if a>=128 else 0).getbbox();assert box
    crop=image.crop(box)
    scale=min((size-2*pad)/crop.width,(size-2*pad)/crop.height)
    w=max(1,round(crop.width*scale));h=max(1,round(crop.height*scale))
    reduced=crop.resize((w,h),Image.Resampling.NEAREST)
    pixels=[(0,0,0,0)]*(size*size);ox=(size-w)//2;oy=(size-h)//2
    for y in range(h):
        for x in range(w):
            p=reduced.getpixel((x,y))
            if p[3]>=128:pixels[(oy+y)*size+ox+x]=(*p[:3],255)
    return pixels
def main():
    rgba=[sprite('E1',64,2)]
    sizes=[64]
    # One shared modest palette, RGB565 storage; zero remains Color Key.
    rgb=Image.new('RGB',(sum(map(len,rgba)),1));opaque=[];at=0
    for frame in rgba:
        for p in frame:
            rgb.putpixel((at,0),p[:3]);opaque.append(bool(p[3]));at+=1
    q=rgb.quantize(colors=48,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE).convert('RGB')
    packed=[]
    for i,visible in enumerate(opaque):
        r,g,b=q.getpixel((i,0));packed.append(((((r>>3)<<11)|((g>>2)<<5)|(b>>3)) or 1) if visible else 0)
    frames=[];at=0
    for size in sizes:frames.append(packed[at:at+size*size]);at+=size*size
    palette=sorted(set(packed));assert len(palette)<=64
    lookup={p:i for i,p in enumerate(palette)};tokens=[];meta=[];byte_offset=0
    for size,frame in zip(sizes,frames):
        begin=len(tokens);i=0
        while i<len(frame):
            run=1
            while i+run<len(frame)and frame[i+run]==frame[i]and run<1023:run+=1
            tokens.append((run<<6)|lookup[frame[i]]);i+=run
        pts=[(i%size,i//size)for i,p in enumerate(frame)if p]
        bounds=[min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts)+1,max(y for x,y in pts)+1]
        meta.append([byte_offset,begin,len(tokens),size,*bounds]);byte_offset+=size*size*2
    assert byte_offset==8192
    assert [palette[t&63]for t in tokens for _ in range(t>>6)]==packed
    def array(name,values):
        return f'static const uint16_t {name}[{len(values)}]={{\n'+''.join('    '+','.join(map(str,values[i:i+16]))+',\n'for i in range(0,len(values),16))+'};\n'
    header='''#ifndef SCENERY_ASSETS_H
#define SCENERY_ASSETS_H
#include <stdint.h>
#define SCENERY_ASSET_BASE (ASSET_BASE+0x20000u)
#define SCENERY_ASSET_BYTES 8192u
#define SCENERY_FRAME_COUNT 1u
#define SCENERY_ALTAR 0u
typedef struct {uint16_t offset,begin,end;uint8_t size,left,top,right,bottom;} SceneryFrame;
'''
    header+=array('scenery_palette',palette)+array('scenery_rle',tokens)
    header+='static const SceneryFrame scenery_frames[1]={\n'+''.join('    {'+','.join(map(str,m))+'},\n'for m in meta)+'};\n#endif\n'
    (ROOT/'software/scenery_assets.h').write_text(header,encoding='utf-8')
    raw=b''.join(struct.pack('<H',p)for p in packed);(OUT/'scenery.rgb565').write_bytes(raw)
    # Small previews are compiler outputs, not new artistic variants.
    for n,(frame,size)in enumerate(zip(frames,sizes)):
        im=Image.new('RGBA',(size,size))
        im.putdata([(((p>>11)&31)*255//31,((p>>5)&63)*255//63,(p&31)*255//31,255 if p else 0)for p in frame])
        im.save(OUT/f'frame_{n}.png')
    manifest={'selected':['E1'],'palette_colors':len(palette),'ddr_bytes':byte_offset,
              'compressed_bytes':2*(len(palette)+len(tokens))+12*len(meta),'frames':meta,
              'sha256':hashlib.sha256(raw).hexdigest(),'format':'RGB565 little-endian, Color Key 0',
              'ddr_base':'0x01220000'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('SCENERY ASSETS:',json.dumps({k:manifest[k]for k in ['selected','palette_colors','ddr_bytes','compressed_bytes']}))
if __name__=='__main__':main()
