"""Check the real solid-background/dirty-restore renderer against a full redraw.

Runs on the host, with actual sprite RGB565 pixels and no FPGA access.
"""
from pathlib import Path
import argparse
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--cc', required=True, type=Path)
args = parser.parse_args()
view = (ROOT/'software/game_view.h').read_text(encoding='utf-8')
out = ROOT/'software/build/flat_background_check'
out.mkdir(parents=True, exist_ok=True)


def function(name):
    match = re.search(r'^static [^;{]*\b'+name+r'\([^;{]*\)\s*\{', view, re.M)
    assert match, name
    depth = 0
    for token in re.finditer(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*|[{}]', view[match.end()-1:], re.S):
        if token.group() == '{':
            depth += 1
        elif token.group() == '}':
            depth -= 1
            if not depth:
                return view[match.start():match.end()-1+token.end()]
    raise ValueError(name)


prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "survivor_game.h"
#include "game_frame_bounds.h"
#define ASSET_BASE 0x01200000u
#define GAME_ASSET_BASE (ASSET_BASE+0x4000u)
#define GAME_FRAME_COUNT GAME_FRAME_BOUNDS_COUNT
#define GFX_BLEND_ALPHA 1u
#define GFX_BLEND_KEY 2u
'''
for name in ('GAME_BACKGROUND_COLOR', 'GAME_VIEW_WIDTH', 'GAME_VIEW_HEIGHT', 'GAME_DIRTY_TILE',
             'GAME_DIRTY_COLS', 'GAME_DIRTY_ROWS'):
    prefix += re.search(r'^#define '+name+r'[^\n]+', view, re.M).group()+'\n'
prefix += r'''
typedef struct {uint8_t first,last,top,bottom;} GameDirtyRect;
static uint16_t pages[2][640*480],reference[640*480],pixels[GAME_FRAME_COUNT*1024];
static uint32_t game_assets_ready=1,game_capture_page,game_capture_dirty,page;
static uint8_t game_page_valid[2],game_page_playing[2],game_dirty_valid[2];
static uint32_t game_page_dirty[2][GAME_DIRTY_ROWS];
static void fail(const char *s) {fprintf(stderr,"%s\n",s);exit(1);}
static uint16_t mix(uint16_t f,uint16_t b,unsigned a) {
    unsigned r=(((f>>11)&31)*a+((b>>11)&31)*(255-a)+127)/255;
    unsigned g=(((f>>5)&63)*a+((b>>5)&63)*(255-a)+127)/255;
    unsigned blue=((f&31)*a+(b&31)*(255-a)+127)/255;
    return (uint16_t)((r<<11)|(g<<5)|blue);
}
static void paint(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c,uint32_t hw) {
    assert(hw==1 && x>=GAME_X_MIN && y>=GAME_Y_MIN && x+w<=GAME_X_MAX && y+h<=GAME_Y_MAX);
    for(unsigned j=y;j<y+h;j++)for(unsigned i=x;i<x+w;i++)pages[page][j*640+i]=c;
}
static int blend_image(uint32_t src,uint32_t stride,uint32_t x,uint32_t y,uint32_t w,uint32_t h,
                       uint8_t alpha,uint16_t key,uint32_t flags) {
    assert(src>=GAME_ASSET_BASE && src+(h-1)*stride+w*2<=GAME_ASSET_BASE+sizeof(pixels));
    assert(stride==64 && key==0 && flags==(GFX_BLEND_ALPHA|GFX_BLEND_KEY));
    assert(x>=GAME_X_MIN && y>=GAME_Y_MIN && x+w<=GAME_X_MAX && y+h<=GAME_Y_MAX);
    unsigned start=(src-GAME_ASSET_BASE)/2;
    for(unsigned j=0;j<h;j++)for(unsigned i=0;i<w;i++) {
        uint16_t f=pixels[start+j*32+i];unsigned at=(y+j)*640+x+i;
        if(f)pages[page][at]=mix(f,pages[page][at],alpha);
    }
    return 0;
}
'''
tests = r'''
/* Independent oracle scans every source pixel and redraws the full view. */
static void reference_sprite(unsigned frame,int x,int y,unsigned alpha) {
    for(int j=0;j<32;j++)for(int i=0;i<32;i++) {
        int sx=x-16+i,sy=y-16+j;uint16_t c=pixels[frame*1024+j*32+i];
        if(c && sx>=GAME_X_MIN && sx<GAME_X_MAX && sy>=GAME_Y_MIN && sy<GAME_Y_MAX) {
            unsigned at=(unsigned)sy*640+(unsigned)sx;
            reference[at]=mix(c,reference[at],alpha);
        }
    }
}
int main(void) {
    FILE *f=fopen("assets/game/game.rgb565","rb");
    assert(f && fread(pixels,2,GAME_FRAME_COUNT*1024,f)==GAME_FRAME_COUNT*1024);fclose(f);
    for(unsigned p=0;p<2;p++)for(unsigned i=0;i<640*480;i++)pages[p][i]=0xdead;
    for(unsigned n=0;n<360;n++) {
        page=n&1;unsigned playing=(n/30)%3==1;
        game_draw_world_floor(page,(int)(n*13)%1425,(int)(n*7)%1049,playing,n);
        for(unsigned i=0;i<640*480;i++)reference[i]=0xdead;
        for(unsigned y=GAME_Y_MIN;y<GAME_Y_MAX;y++)for(unsigned x=GAME_X_MIN;x<GAME_X_MAX;x++)
            reference[y*640+x]=GAME_BACKGROUND_COLOR;
        if(n%11!=0)for(unsigned actor=0;actor<5;actor++) {
            int x=(int)((n*19+actor*137)%680)-20;
            int y=60+(int)((n*11+actor*73)%400);
            unsigned frame=actor==0?n%16:16+(n+actor)%(GAME_FRAME_COUNT-16);
            unsigned alpha=actor<3?255:220;
            game_sprite(frame,x,y,alpha);reference_sprite(frame,x,y,alpha);
        }
        if(n%29==0) {
            /* Cover most of the view, forcing the full-clear fallback later. */
            paint(8,80,600,350,0x1234,1);game_record_dirty_rect(8,80,600,350);
            for(unsigned y=80;y<430;y++)for(unsigned x=8;x<608;x++)reference[y*640+x]=0x1234;
        }
        if(memcmp(pages[page],reference,sizeof(reference))) {
            fprintf(stderr,"Background mismatch: frame=%u page=%u playing=%u\n",n,page,playing);
            return 1;
        }
    }
    puts("PASS: 360 alternating-page frames; camera movement, clipping, empty frames, translucent sprites, pause/resume and full-clear fallback match a full RGB565 redraw.");
    return 0;
}
'''
source = out/'background_host_check.c'
source.write_text(prefix+'\n'.join(function(n) for n in (
    'game_record_dirty_rect', 'game_fill_background_rect', 'game_restore_dirty_tiles',
    'game_draw_world_floor', 'game_sprite'))+tests, encoding='utf-8')
env = dict(os.environ)
env['PATH'] = str(args.cc.parent)+os.pathsep+env['PATH']
binary = out/'background_host_check.exe'
subprocess.run([str(args.cc), '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                '-Isoftware', str(source), '-o', str(binary)], cwd=ROOT, env=env, check=True)
subprocess.run([str(binary)], cwd=ROOT, env=env, check=True)
