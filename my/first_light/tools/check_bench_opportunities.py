"""Pixel-exact host prototype for stable tiled benchmark composition.

This is a feasibility/DDR-payload model, not implemented RTL, synthesis,
CPU timing, AXI latency, board FPS, or MAX60. It extracts the real firmware
texture and motion functions and compares complete 640x480 RGB565 frames.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def extract_function(source, name):
    match = re.search(r'^static [^;{]*\b' + name + r'\([^;{]*\)\s*\{', source, re.M)
    assert match, name
    depth = 0
    for token in re.finditer(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*|[{}]', source[match.end()-1:], re.S):
        if token[0] == '{':
            depth += 1
        elif token[0] == '}':
            depth -= 1
        if not depth:
            return source[match.start():match.end()-1+token.end()]
    raise AssertionError(name)


HARNESS = r'''
#include <assert.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define W 640
#define H 480
#define TILE 32
#define COLS 20
#define BINS (20*9)
#define Y0 152
#define Y1 408
#define CLEAR 0x0843
typedef struct { uint16_t x,y; } Position;
static uint16_t scalar[W*H],tiled[W*H],tile_ram[TILE*TILE];
static unsigned checks;
/* Firmware functions inserted below, unchanged. */
__FIRMWARE_FUNCTIONS__
static uint16_t reference(uint16_t f,uint16_t b,unsigned alpha,int key) {
    if(key && !f)return b;
    unsigned r=((f>>11)*alpha+(b>>11)*(255-alpha)+127)/255;
    unsigned g=(((f>>5)&63)*alpha+((b>>5)&63)*(255-alpha)+127)/255;
    unsigned blue=((f&31)*alpha+(b&31)*(255-alpha)+127)/255;
    return (uint16_t)((r<<11)|(g<<5)|blue);
}
/* Separate implementation: bounded normalization used by the RTL. */
static unsigned channel(unsigned f,unsigned b,unsigned alpha) {
    unsigned v=f*alpha+b*(255-alpha)+127;
    return (v+1+(v>>8))>>8;
}
static uint16_t tile_blend(uint16_t f,uint16_t b,unsigned alpha,int key) {
    if(key && !f)return b;
    return (uint16_t)((channel(f>>11,b>>11,alpha)<<11)|
        (channel((f>>5)&63,(b>>5)&63,alpha)<<5)|channel(f&31,b&31,alpha));
}
static int maximum(int a,int b) { return a>b?a:b; }
static int minimum(int a,int b) { return a<b?a:b; }
static unsigned bin_id(unsigned tx,unsigned ty) {
    assert(tx<COLS && ty>=Y0/TILE && ty<(Y1+TILE-1)/TILE);
    return (ty-Y0/TILE)*COLS+tx;
}
static unsigned bursts(unsigned byte_address,unsigned words) {
    unsigned count=0;
    while(words) {
        unsigned n=minimum(16,minimum(words,(4096-(byte_address&4095))/4));
        assert(n);words-=n;byte_address+=n*4;++count;
    }
    return count;
}
static Position *positions(unsigned n,unsigned side,uint32_t frame) {
    Position *p=calloc(n?n:1,sizeof(*p));assert(p);
    for(unsigned i=0;i<n;++i) {
        uint32_t seed=sprite_seed(i);
        p[i].x=8+bounce((seed&65535u)+frame*(1+((seed>>16)&7u)),632u-side);
        p[i].y=160+bounce((seed>>16)+frame*(1+((seed>>24)&3u)),240u-side);
    }
    return p;
}
static void check(unsigned side,unsigned n,uint32_t frame,unsigned alpha,int key,
                  Position *p,int report) {
    assert(side>0 && side<=32 && n<=65535);
    unsigned counts[BINS]={0},offsets[BINS+1]={0},cursor[BINS];
    uint16_t texture[32*32];
    for(unsigned y=0;y<side;++y)for(unsigned x=0;x<side;++x)
        texture[y*side+x]=sprite_pixel_sized(side,y,x);
    for(unsigned i=0;i<n;++i) {
        assert(p[i].x+side<=W && p[i].y>=Y0 && p[i].y+side<=Y1);
        for(unsigned ty=p[i].y/TILE;ty<=(p[i].y+side-1)/TILE;++ty)
            for(unsigned tx=p[i].x/TILE;tx<=(p[i].x+side-1)/TILE;++tx)
                ++counts[bin_id(tx,ty)];
    }
    for(unsigned b=0;b<BINS;++b)offsets[b+1]=offsets[b]+counts[b];
    uint16_t *indices=calloc(offsets[BINS]?offsets[BINS]:1,sizeof(*indices));assert(indices);
    memcpy(cursor,offsets,sizeof(cursor));
    /* Append in original draw order. Different tiles have disjoint pixels. */
    for(unsigned i=0;i<n;++i)
        for(unsigned ty=p[i].y/TILE;ty<=(p[i].y+side-1)/TILE;++ty)
            for(unsigned tx=p[i].x/TILE;tx<=(p[i].x+side-1)/TILE;++tx)
                indices[cursor[bin_id(tx,ty)]++]=(uint16_t)i;
    for(unsigned j=0;j<W*H;++j)scalar[j]=tiled[j]=(uint16_t)((j*73u)^(j>>8));
    for(unsigned y=Y0;y<Y1;++y)for(unsigned x=0;x<W;++x)scalar[y*W+x]=CLEAR;
    uint64_t bg_words=0,bg_bursts=0;
    for(unsigned i=0;i<n;++i)for(unsigned y=0;y<side;++y) {
        int first=-1,last=-1;
        for(unsigned x=0;x<side;++x) {
            uint16_t f=texture[y*side+x];
            unsigned d=(p[i].y+y)*W+p[i].x+x;
            scalar[d]=reference(f,scalar[d],alpha,key);
            if(!key || f) { if(first<0)first=(int)x;last=(int)x; }
        }
        if(first>=0) {
            unsigned left=(p[i].x+first)/2,right=(p[i].x+last)/2;
            unsigned words=right-left+1;
            bg_words+=words;bg_bursts+=bursts((p[i].y+y)*1280+left*4,words);
        }
    }
    for(unsigned b=0;b<BINS;++b) {
        unsigned tx=(b%COLS)*TILE,ty=(b/COLS+Y0/TILE)*TILE;
        for(unsigned j=0;j<TILE*TILE;++j)tile_ram[j]=CLEAR;
        for(unsigned j=offsets[b];j<offsets[b+1];++j) {
            unsigned i=indices[j];
            if(j>offsets[b])assert(indices[j-1]<i);
            for(unsigned y=maximum(p[i].y,ty);y<(unsigned)minimum(p[i].y+side,ty+TILE);++y)
                for(unsigned x=maximum(p[i].x,tx);x<(unsigned)minimum(p[i].x+side,tx+TILE);++x) {
                    unsigned k=(y-ty)*TILE+x-tx;
                    tile_ram[k]=tile_blend(texture[(y-p[i].y)*side+x-p[i].x],tile_ram[k],alpha,key);
                }
        }
        /* Only commit the viewport; HUD/border pixels remain untouched. */
        for(unsigned y=maximum(ty,Y0);y<(unsigned)minimum(ty+TILE,Y1);++y)
            memcpy(tiled+y*W+tx,tile_ram+(y-ty)*TILE,TILE*sizeof(uint16_t));
    }
    for(unsigned j=0;j<W*H;++j)if(scalar[j]!=tiled[j]) {
        fprintf(stderr,"Mismatch side=%u n=%u frame=%" PRIu32 " alpha=%u key=%d pixel=%u\n",
            side,n,frame,alpha,key,j);exit(2);
    }
    ++checks;
    if(report) {
        const uint64_t clear_bytes=W*(Y1-Y0)*2;
        const uint64_t batches=(n+511)/512,source_bytes=side*side*2;
        const uint64_t current=clear_bytes+n*32+(n?batches*source_bytes:0)+bg_words*8;
        /* Proposed direct-position bins avoid random index->position fetches.
           Estimate a 64-byte common header and 181 uint32_t offsets. */
        const uint64_t bin_bytes=64+sizeof(offsets)+offsets[BINS]*4;
        const uint64_t fused=clear_bytes+bin_bytes+(n?source_bytes:0);
        const uint64_t generic=current-bg_words*8-n*32-(n?batches*source_bytes:0)+
            bin_bytes+(n?source_bytes:0);
        unsigned active=0;uint64_t touched_bytes=0;
        for(unsigned b=0;b<BINS;++b)if(counts[b]) {
            unsigned ty=(b/COLS+Y0/TILE)*TILE;
            ++active;touched_bytes+=TILE*(minimum(ty+TILE,Y1)-maximum(ty,Y0))*2;
        }
        printf("CASE %u %u %" PRIu32 " %" PRIu64 " %" PRIu64 " %" PRIu64
               " %u %u %" PRIu64 " %" PRIu64 " %" PRIu64 "\n",
            side,n,frame,current,fused,generic+2*touched_bytes,offsets[BINS],active,
            bg_words*8,bg_bursts,bin_bytes);
    }
    free(indices);
}
int main(void) {
    const unsigned sides[]={4,16,24,32},loads[]={128,512,1024,4096};
    const uint32_t frames[]={0,37,36000};
    for(unsigned s=0;s<4;++s)for(unsigned k=0;k<4;++k)for(unsigned f=0;f<3;++f) {
        Position *p=positions(loads[k],sides[s],frames[f]);
        check(sides[s],loads[k],frames[f],128,1,p,1);free(p);
    }
    /* Empty, one sprite, overflowed motion phase, odd/right/bottom edges,
       heavy overlaps crossing four tiles, Alpha endpoints, Key off. */
    const unsigned alphas[]={0,1,127,128,254,255};
    for(unsigned s=0;s<4;++s) {
        Position p[7]={{609,369},{609,369},{607,367},{608,368},{9,153},{0,152},{0,152}};
        p[0].x=p[1].x=W-sides[s];p[0].y=p[1].y=Y1-sides[s];
        check(sides[s],0,0,128,1,p,0);
        for(unsigned a=0;a<6;++a)for(unsigned key=0;key<2;++key)
            check(sides[s],7,0,alphas[a],key,p,0);
        Position *q=positions(1,sides[s],UINT32_MAX-16);
        check(sides[s],1,UINT32_MAX-16,128,1,q,0);free(q);
    }
    printf("TILING PIXELS PASSED checks=%u pixels_per_frame=%u\n",checks,W*H);
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', type=Path, default=Path('C:/mingw64/bin/gcc.exe'))
    parser.add_argument('--rtl-profile', type=Path, help='Cross-check baseline payload and burst counts against firmware-motion RTL profiling')
    args = parser.parse_args()
    out = ROOT/'software/build/bench_opportunities'
    out.mkdir(parents=True, exist_ok=True)
    firmware = (ROOT/'software/main.c').read_text(encoding='utf-8')
    functions = '\n'.join(extract_function(firmware, n) for n in ('sprite_pixel_sized', 'bounce', 'sprite_seed'))
    c_source = HARNESS.replace('__FIRMWARE_FUNCTIONS__', functions)
    source = out/'check.c'
    source.write_text(c_source, encoding='utf-8')
    binary = out/'check.exe'
    env = dict(os.environ, PATH=str(args.cc.parent)+os.pathsep+os.environ.get('PATH', ''))
    compile_result = subprocess.run([str(args.cc), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                                     str(source), '-o', str(binary)], capture_output=True, text=True, env=env)
    (ROOT/'reports/bench_opportunities_compile.log').write_text(compile_result.stdout+compile_result.stderr, encoding='utf-8')
    compile_result.check_returncode()
    result = subprocess.run([str(binary)], capture_output=True, text=True, env=env)
    log = result.stdout+result.stderr
    (ROOT/'reports/bench_opportunities_run.log').write_text(log, encoding='utf-8')
    result.check_returncode()
    assert 'TILING PIXELS PASSED checks=104' in log, log[-2000:]
    names = ('side', 'count', 'frame', 'current_payload_bytes', 'fused_tile_payload_bytes',
             'separate_clear_tile_payload_bytes', 'tile_fragments', 'active_tiles',
             'current_background_rw_bytes', 'current_background_bursts_each_direction', 'tile_bin_bytes')
    cases = [dict(zip(names, map(int, line.split()[1:]))) for line in log.splitlines() if line.startswith('CASE ')]
    assert len(cases) == 48
    for case in cases:
        case['payload_ratio_current_over_fused_tile'] = round(case['current_payload_bytes']/case['fused_tile_payload_bytes'], 3)
        case['current_cpu_position_store_bytes'] = case['count']*4
        case['proposed_cpu_bin_upload_bytes'] = case['tile_bin_bytes']-64
        case['compact_position_payload_bytes'] = case['count']*4+((case['count']+511)//512)*32
    report = {
        'scope': 'Host pixel/DDR-payload feasibility model only; no new RTL, CPU timing, synthesis, board FPS, or MAX60',
        'pixel_checks': 104,
        'pixels_per_check': 640*480,
        'tile_rgb565_buffer_bytes': 32*32*2,
        'proposed_tile_common_header_bytes': 64,
        'background': 'Same firmware 640x256 clear at y=152, color 0x0843; same motion, texture, Alpha128, Key0 and order',
        'traffic_exclusions': ['CPU memory traffic (store sizes reported separately)', 'HUD', 'HDMI scanout',
                               'AXI handshakes, stalls, arbitration and refresh', 'CPU binning time and raster cycles'],
        'notes': ['Fused tiles initialize to clear color in RAM and write only the viewport once.',
                  'Separate-clear tiles retain the existing DDR clear, load/write touched tiles once.',
                  'Direct destination words are repeated in each intersecting tile, keeping original order.',
                  'A 2 KiB tile fits the existing background arrays by capacity; inference and routing are unverified.',
                  'This is not a speedup factor; CPU bucket construction and blend processing may dominate.'],
        'source_sha256': {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
                          ('software/main.c', 'rtl/fill_engine.v', 'rtl/render_batch.v','rtl/tile_renderer.v', 'rtl/render_subsystem.v',
                           'tools/check_bench_opportunities.py')},
        'native_harness_sha256': hashlib.sha256(c_source.encode()).hexdigest(),
        'cases': cases,
    }
    if args.rtl_profile:
        rtl = json.loads((ROOT/args.rtl_profile).read_text())
        assert rtl['positions'] == 'firmware frame zero'
        for name, value in rtl['source_sha256'].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == value, name
        matched = 0
        for phase, timing in zip(rtl['exclusive_phase_cycles'], rtl['cases']):
            if phase['key'] != 1 or phase['count'] != 128:
                continue
            case = next(c for c in cases if c['side'] == phase['side'] and c['count'] == 128 and c['frame'] == 0)
            assert case['current_payload_bytes'] == (phase['read_words']+phase['write_words'])*4+640*256*2
            assert case['current_background_bursts_each_direction'] == timing['AW']
            matched += 1
        assert matched == 8
        report['baseline_rtl_cross_checks'] = matched
        report['baseline_rtl_profile_sha256'] = hashlib.sha256((ROOT/args.rtl_profile).read_bytes()).hexdigest()
    (ROOT/'reports/bench_opportunities.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(f'PASS {report["pixel_checks"]} complete-frame comparisons; 48 payload cases; not FPS/MAX60')
    for case in cases:
        if case['frame'] == 0 and case['count'] in (128, 1024, 4096):
            print(f'{case["side"]}x{case["side"]} N={case["count"]}: payload '
                  f'{case["current_payload_bytes"]}->{case["fused_tile_payload_bytes"]} B, '
                  f'ratio={case["payload_ratio_current_over_fused_tile"]}; '
                  f'CPU upload {case["current_cpu_position_store_bytes"]}->{case["proposed_cpu_bin_upload_bytes"]} B')


if __name__ == '__main__':
    main()
