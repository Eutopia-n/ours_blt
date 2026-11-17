"""Pixel equivalence of actual before/after C sprite submission functions.

The RGB565 compositor here models only pixels, not DDR/RTL performance. The
existing render testbench separately verifies the hardware Alpha/Key datapath.
"""
from pathlib import Path
import argparse,importlib.util,os,re,subprocess,struct,json,zipfile,hashlib
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--baseline',type=Path,help='Optional saved entity256 source_project.zip; defaults to the bundled read-only snapshot')
parser.add_argument('--cc',type=Path,default=Path('D:/Xilinx/Vivado/2018.3/msys64/mingw64/bin/gcc.exe'))
parser.add_argument('--current-atlas',action='store_true',help='Test intentional new art with both rendering paths; retain the baseline renderer integrity check')
args=parser.parse_args()
spec=importlib.util.spec_from_file_location('prepare_game_assets',ROOT/'tools/prepare_game_assets.py')
assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)
assert assets.frame_bounds([0]*1024)==(0,0,0,0)
assert assets.frame_bounds([1]*1024)==(0,0,32,32)
for i in [0,31,992,1023,521]:
    frame=[0]*1024;frame[i]=1
    assert assets.frame_bounds(frame)==(i%32,i//32,i%32+1,i//32+1)
try: assets.frame_bounds([1]*1023)
except ValueError: pass
else: raise AssertionError('Invalid dimensions accepted')

raw=(ROOT/'assets/game/game.rgb565').read_bytes()
frames=[struct.unpack('<1024H',raw[n:n+2048]) for n in range(0,len(raw),2048)]
bounds=[assets.frame_bounds(frame) for frame in frames]
header=(ROOT/'software/game_frame_bounds.h').read_text(encoding='utf-8')
generated=[tuple(map(int,m.split(','))) for m in re.findall(r'\{([\d, ]+)\}',header)]
assert generated==bounds
stats=[]
for i,box in enumerate(bounds):
    area=(box[2]-box[0])*(box[3]-box[1])
    stats.append({'frame':i,'bounds':box,'old_pixels':1024,'new_pixels':area,
                  'rectangle_reduction_percent':100*(1024-area)/1024})
(ROOT/'reports/sprite_crop_rectangles.json').write_text(json.dumps(stats,indent=2))
if args.baseline:
    with zipfile.ZipFile(args.baseline) as z:
        view_before=z.read('ours_blt_entity256/software/game_view.h').decode()
        if not args.current_atlas:
            assert raw==z.read('ours_blt_entity256/assets/game/game.rgb565'),'Atlas pixel data changed'
else:
    view_before=(ROOT/'sim/sprite_crop_baseline_game_view.h').read_text(encoding='utf-8')
    snapshot=json.loads((ROOT/'sim/sprite_crop_baseline.json').read_text(encoding='utf-8'))
    if not args.current_atlas:
        assert hashlib.sha256(raw).hexdigest()==snapshot['atlas_sha256'],'Atlas pixel data changed'
    assert hashlib.sha256((ROOT/'sim/sprite_crop_baseline_game_view.h').read_bytes()).hexdigest()==snapshot['view_sha256']
view_after=(ROOT/'software/game_view.h').read_text(encoding='utf-8')
def function(source,name):
    match=re.search(r'^static [^;{]*\b'+name+r'\([^;{]*\)\s*\{',source,re.M)
    assert match,name
    depth=0
    for t in re.finditer(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*|[{}]',source[match.end()-1:],re.S):
        if t.group()=='{': depth+=1
        elif t.group()=='}':
            depth-=1
            if not depth:return source[match.start():match.end()-1+t.end()]
    raise ValueError(name)
prelude=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "survivor_game.h"
#define game_frame_bounds generated_bounds
#include "game_frame_bounds.h"
#undef game_frame_bounds
static uint8_t game_frame_bounds[GAME_FRAME_BOUNDS_COUNT][4];
#define GAME_FRAME_COUNT GAME_FRAME_BOUNDS_COUNT
#define GAME_ASSET_BASE 0x01204000u
#define GFX_BLEND_ALPHA 1u
#define GFX_BLEND_KEY 2u
static uint16_t atlas[GAME_FRAME_COUNT*1024u];
static uint16_t pixels[2][1024];
static uint32_t game_assets_ready=1,mode,submits[2],area[2],dirty[2][4];
static int32_t roi_x,roi_y;
static unsigned cases;
static void fail(const char *s) { fprintf(stderr,"%s\n",s); assert(0); }
static uint16_t composite(uint16_t fg,uint16_t bg,uint32_t alpha) {
    uint32_t r=(((fg>>11)&31)*alpha+((bg>>11)&31)*(255-alpha)+127)/255;
    uint32_t g=(((fg>>5)&63)*alpha+((bg>>5)&63)*(255-alpha)+127)/255;
    uint32_t b=((fg&31)*alpha+(bg&31)*(255-alpha)+127)/255;
    return (uint16_t)((r<<11)|(g<<5)|b);
}
static int blend_image(uint32_t source,uint32_t stride,uint32_t x,uint32_t y,
                       uint32_t w,uint32_t h,uint8_t alpha,uint16_t key,uint32_t flags) {
    assert(stride==64 && key==0 && flags==3 && w && h);
    assert(x>=GAME_X_MIN && y>=GAME_Y_MIN && x+w<=GAME_X_MAX && y+h<=GAME_Y_MAX);
    assert(source>=GAME_ASSET_BASE && !(source&1u));
    uint32_t begin=(source-GAME_ASSET_BASE)/2;
    assert(begin+(h-1)*32+w<=GAME_FRAME_COUNT*1024u);
    submits[mode]++;area[mode]+=w*h;
    for(uint32_t j=0;j<h;j++) for(uint32_t i=0;i<w;i++) {
        int32_t dx=(int32_t)(x+i)-roi_x,dy=(int32_t)(y+j)-roi_y;
        assert(dx>=0 && dx<32 && dy>=0 && dy<32);
        uint16_t fg=atlas[begin+j*32+i];
        if(fg!=key) pixels[mode][dy*32+dx]=composite(fg,pixels[mode][dy*32+dx],alpha);
    }
    dirty[mode][0]=x;dirty[mode][1]=y;dirty[mode][2]=w;dirty[mode][3]=h;
    return 0;
}
static void game_record_dirty_rect(uint32_t x,uint32_t y,uint32_t w,uint32_t h) {
    assert(dirty[mode][0]==x && dirty[mode][1]==y && dirty[mode][2]==w && dirty[mode][3]==h);
}
'''
tests=r'''
static void compare(uint32_t frame,int32_t x,int32_t y,uint32_t alpha) {
    roi_x=x-16;roi_y=y-16;
    for(unsigned i=0;i<1024;i++) pixels[0][i]=pixels[1][i]=(uint16_t)(i*521u+cases*31u);
    memset(submits,0,sizeof(submits));memset(area,0,sizeof(area));
    mode=0; uint32_t old=baseline_game_sprite(frame,x,y,alpha);
    mode=1; uint32_t now=game_sprite(frame,x,y,alpha);
    assert(submits[0]==old && submits[1]==now && area[1]<=area[0]);
    if(memcmp(pixels[0],pixels[1],sizeof(pixels[0]))) {
        fprintf(stderr,"Pixel mismatch frame=%u x=%d y=%d alpha=%u\n",frame,x,y,alpha);assert(0);
    }
    cases++;
}
int main(void) {
    FILE *file=fopen("assets/game/game.rgb565","rb");assert(file);
    assert(fread(atlas,sizeof(uint16_t),GAME_FRAME_COUNT*1024,file)==GAME_FRAME_COUNT*1024);
    fclose(file);memcpy(game_frame_bounds,generated_bounds,sizeof(game_frame_bounds));
    const uint32_t alphas[]={0,1,64,128,160,254,255};
    for(uint32_t frame=0;frame<GAME_FRAME_COUNT;frame++) for(unsigned a=0;a<7;a++) {
        compare(frame,320,240,alphas[a]);compare(frame,321,241,alphas[a]);
        for(int32_t d=-17;d<=17;d++) {
            compare(frame,GAME_X_MIN+d,240,alphas[a]);compare(frame,GAME_X_MAX+d,241,alphas[a]);
            compare(frame,320,GAME_Y_MIN+d,alphas[a]);compare(frame,321,GAME_Y_MAX+d,alphas[a]);
        }
        for(int32_t dx=-17;dx<=17;dx+=3) for(int32_t dy=-17;dy<=17;dy+=3) {
            compare(frame,GAME_X_MIN+dx,GAME_Y_MIN+dy,alphas[a]);
            compare(frame,GAME_X_MAX+dx,GAME_Y_MAX+dy,alphas[a]);
        }
    }
    // Invalid index fallback, unavailable atlas, empty/single-pixel/full frames.
    compare(UINT32_MAX,320,240,160);compare(GAME_FRAME_COUNT,321,241,255);
    game_assets_ready=0;compare(16,320,240,128);assert(!submits[0] && !submits[1]);game_assets_ready=1;
    memset(atlas,0,1024*sizeof(uint16_t));memset(game_frame_bounds[0],0,4);
    compare(0,320,240,255);assert(submits[0]==1 && submits[1]==0);
    atlas[1023]=0xffff;
    game_frame_bounds[0][0]=31;game_frame_bounds[0][1]=31;
    game_frame_bounds[0][2]=32;game_frame_bounds[0][3]=32;
    compare(0,320,240,128);assert(area[1]==1);
    compare(0,GAME_X_MIN-15,GAME_Y_MIN-15,160);
    compare(0,GAME_X_MAX-15,GAME_Y_MAX-15,255);
    for(unsigned i=0;i<1024;i++)atlas[i]=0x1234;
    game_frame_bounds[0][0]=game_frame_bounds[0][1]=0;
    game_frame_bounds[0][2]=game_frame_bounds[0][3]=32;
    compare(0,321,241,160);assert(area[1]==1024);
    printf("SPRITE CROP PIXEL TESTS PASSED: %u cases; all%u frames, seven Alpha values, all viewport edges/corners, odd/even alignment, invalid fallback, unready/empty/1px/full frames; identical RGB565 pixels and dirty bounds\n",cases,GAME_FRAME_COUNT);
    return 0;
}
'''
build=ROOT/'software/build';build.mkdir(exist_ok=True)
source=build/'sprite_crop_host.c'
source.write_text(prelude+'\n'+function(view_before,'game_sprite').replace('game_sprite(', 'baseline_game_sprite(',1)+'\n'+function(view_after,'game_sprite')+'\n'+tests)
env=dict(os.environ);env['PATH']=str(args.cc.parent)+os.pathsep+env.get('PATH','')
exe=build/'sprite_crop_host.exe'
subprocess.run([str(args.cc),'-std=c99','-O2','-Wall','-Wextra','-Werror','-Isoftware',str(source),'-o',str(exe)],cwd=ROOT,env=env,check=True)
result=subprocess.run([str(exe)],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8')
(ROOT/'reports/sprite_crop_pixel.log').write_text(result.stdout+result.stderr)
print(result.stdout+result.stderr,flush=True)
if result.returncode:raise SystemExit(result.returncode)
print('Bounds generator PASS; '+('current art tested on both paths' if args.current_atlas else 'original atlas byte-identical')+'; A/B/C/D_E rectangles:',[stats[i] for i in [16,17,18,24]])
