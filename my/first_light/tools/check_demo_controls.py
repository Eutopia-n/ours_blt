"""Host regression for five-step controls and the real demo's Alpha direction.

Uses production controls, scene and CPU blend code. Hardware accesses are stubbed;
this does not claim an FPGA simulation or a board test.
"""
from pathlib import Path
import argparse
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--cc', type=Path, default=Path('C:/mingw64/bin/gcc.exe'))
args = parser.parse_args()
main = (ROOT/'software/main.c').read_text(encoding='utf-8')

def function(name):
    match = re.search(r'^static [^;{]*\b'+name+r'\([^;{]*\)\s*\{', main, re.M)
    assert match, name
    depth = 0
    for token in re.finditer(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*|[{}]',
                             main[match.end()-1:], re.S):
        if token.group() == '{': depth += 1
        if token.group() == '}': depth -= 1
        if not depth:
            body = main[match.start():match.end()-1+token.end()]
            return re.sub(r'__asm__ volatile\s*\(.*?\);', '', body, flags=re.S)
    raise AssertionError(name)

prelude = r'''
#include <assert.h>
#include <stdio.h>
#include "render.h"
#include "demo_controls.h"
enum { DEMO_FILL, DEMO_COPY, DEMO_BUFFER, DEMO_KEY, DEMO_ALPHA, DEMO_BENCH };
static uint32_t sprite_count=1,bench_size_index;
static const uint32_t bench_sizes[]={4,16,24,32};
static uint32_t expect_hw,expect_opacity,seen;
#define paint(...) ((void)0)
#define draw_page() 0u
#define copy_rect(...) 0
#define cpu_copy_sample(...) ((void)0)
#define bounce(...) 0u
#define sprite_seed(...) 0u
#define draw_bench_sprite(...) ((void)0)
#define publish_pixels() ((void)0)
static void fail(const char *s) { puts(s); assert(0); }
static void draw_image(uint32_t x,uint32_t y,uint32_t flags,uint32_t opacity,uint32_t hw) {
    (void)x;(void)y;
    assert(hw==expect_hw && opacity==expect_opacity);
    assert(flags==(seen<4 ? 0u : GFX_BLEND_ALPHA));
    ++seen;
}
'''
tests = r'''
int main(void) {
    uint32_t next=0; int32_t dir=0;
    assert(demo_alpha_update(128,1,1,100,&next,&dir)==133);
    assert(demo_alpha_update(128,4,4,100,&next,&dir)==123);
    for(uint32_t v=0;v<=255;++v) {
        assert(demo_alpha_update(v,1,1,100,&next,&dir)==(v>250 ? 255 : v+5));
        assert(demo_alpha_update(v,4,4,100,&next,&dir)==(v<5 ? 0 : v-5));
    }
    next=0;dir=0;
    uint32_t v=demo_alpha_update(100,1,1,100,&next,&dir),due=next;
    assert(v==105);
    assert(demo_alpha_update(v,0,1,due-1,&next,&dir)==105);
    v=demo_alpha_update(v,0,1,due,&next,&dir);assert(v==110);
    v=demo_alpha_update(v,0,1,next,&next,&dir);assert(v==115);
    assert(demo_alpha_update(v,0,0,next,&next,&dir)==115 && dir==0);
    v=demo_alpha_update(200,4,4,100,&next,&dir);
    assert(v==195 && demo_alpha_update(v,0,4,next,&next,&dir)==190);
    uint32_t start=UINT32_MAX-DEMO_ALPHA_REPEAT_DELAY/2;
    v=demo_alpha_update(100,1,1,start,&next,&dir);due=next;
    assert(demo_alpha_update(v,0,1,start+1,&next,&dir)==105);
    assert(demo_alpha_update(v,0,1,due,&next,&dir)==110);

    for(uint32_t n=1;n<=100;++n) {
        assert(demo_bench_update(n,1,1,100,&next,&dir)==n+5);
        assert(demo_bench_update(n,2,2,100,&next,&dir)==(n<=6 ? 1 : n-5));
    }
    for(uint32_t n=UINT32_MAX-8;n<UINT32_MAX;++n)
        assert(demo_bench_update(n,1,1,100,&next,&dir)==(n>UINT32_MAX-5 ? UINT32_MAX : n+5));
    assert(demo_bench_update(UINT32_MAX,1,1,100,&next,&dir)==UINT32_MAX);
    v=demo_bench_update(1,1,1,100,&next,&dir);due=next;assert(v==6);
    assert(demo_bench_update(v,0,1,due-1,&next,&dir)==6);
    v=demo_bench_update(v,0,1,due,&next,&dir);assert(v==11);
    // A delayed frame performs one increment, never replays an unbounded backlog.
    v=demo_bench_update(v,0,1,next+10*DEMO_BENCH_REPEAT_PERIOD,&next,&dir);assert(v==16);
    assert(demo_bench_update(v,3,3,100,&next,&dir)==16 && dir==0);
    assert(demo_bench_update(v,0,0,100,&next,&dir)==16 && dir==0);
    v=demo_bench_update(11,2,2,100,&next,&dir);assert(v==6);
    assert(demo_bench_update(v,0,2,next,&next,&dir)==1);

    uint16_t previous=0xffff;
    for(uint32_t t=0;t<=255;++t) {
        expect_opacity=255-t;
        assert(alpha_value(t)==expect_opacity);
        for(expect_hw=0;expect_hw<=1;++expect_hw) {
            seen=0;scene(0,expect_hw,DEMO_ALPHA,t);assert(seen==8);
        }
        uint16_t pixel=blend_rgb565(0xffff,0,alpha_value(t),0,GFX_BLEND_ALPHA);
        assert(pixel<=previous);previous=pixel;
    }
    assert(blend_rgb565(0xf81f,0x07e0,alpha_value(0),0,GFX_BLEND_ALPHA)==0xf81f);
    assert(blend_rgb565(0xf81f,0x07e0,alpha_value(255),0,GFX_BLEND_ALPHA)==0x07e0);
    assert(blend_rgb565(0xffff,0,alpha_value(100),0,1)>
           blend_rgb565(0xffff,0,alpha_value(200),0,1));
    puts("DEMO CONTROLS PASSED: +/-5, saturation, hold/release, timer wrap, pressure overflow, CPU/HW inverse Alpha for all 256 levels");
}
'''
out = ROOT/'software/build/demo_controls_host'
out.mkdir(parents=True,exist_ok=True)
source = out/'check.c'
source.write_text(prelude+'\n'.join(function(n) for n in ('alpha_value','blend_rgb565','scene'))+tests,
                  encoding='utf-8')
env = os.environ.copy()
env['PATH'] = str(args.cc.parent)+os.pathsep+env.get('PATH','')
subprocess.run([str(args.cc),'-std=c11','-O2','-Werror','-Isoftware',str(source),'-o',str(out/'check.exe')],
               cwd=ROOT,env=env,check=True)
r = subprocess.run([str(out/'check.exe')],cwd=ROOT,env=env,capture_output=True,text=True)
(ROOT/'reports/demo_controls_5_20261031.log').write_text(r.stdout+r.stderr,encoding='utf-8')
print(r.stdout+r.stderr,flush=True)
if r.returncode: raise SystemExit(r.returncode)
