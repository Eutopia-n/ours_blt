"""Check firmware text layout on the host; no RTL simulation or board access.

Extract the real font/HUD/page functions and replace only the hardware access.
Cell bounds are checked for collisions and PNGs use the firmware bitmap glyphs.
"""
from pathlib import Path
import argparse
import os
import re
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--cc', required=True, type=Path, help='Native host C compiler')
args = parser.parse_args()
main = (ROOT / 'software/main.c').read_text(encoding='utf-8')
view = (ROOT / 'software/game_view.h').read_text(encoding='utf-8')
font = (ROOT / 'software/font_cn.h').read_text(encoding='utf-8')
available = {int(cp, 16) for cp in re.findall(r'\{0x([0-9a-fA-F]+),\{', font)}
missing = set()
for source in (main, view, (ROOT / 'software/survivor_game.c').read_text(encoding='utf-8')):
    for literal in re.findall(r'"((?:[^"\\]|\\.)*)"', source):
        missing.update(c for c in literal if ord(c) > 127 and ord(c) not in available)
if missing:
    raise SystemExit(f'Missing Chinese glyphs: {sorted(missing)}')


def function(source, name):
    match = re.search(r'^static [^;{]*\b' + name + r'\([^;{]*\)\s*\{', source, re.M)
    if not match:
        raise ValueError(name)
    start = match.start()
    # Tokenize strings/comments so braces in a comment cannot end a function.
    tokens = re.finditer(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*|[{}]', source[match.end()-1:], re.S)
    depth = 0
    for token in tokens:
        if token.group() == '{':
            depth += 1
        elif token.group() == '}':
            depth -= 1
            if not depth:
                result = source[start:match.end()-1+token.end()]
                return re.sub(r'__asm__ volatile\s*\(.*?\);', '', result, flags=re.S)
    raise ValueError(f'Unterminated {name}')


prelude = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "soc.h"
#include "render.h"
#include "font5x7.h"
#include "font_cn.h"
#include "frame_metrics.h"
#include "survivor_game.h"
#define GAME_ASSET_BASE (ASSET_BASE+0x4000u)
#define GAME_FRAME_COUNT 25u
#define GAME_MAX_DRAW_ENEMIES 64u
#define GAME_MAX_DRAW_GEMS 20u
#define GAME_MAX_DRAW_BOLTS GAME_MAX_BOLTS
#define GAME_MAX_DRAW_LANDMARKS 4u
static uint16_t screen[640*480+2];
static uintptr_t draw_buffer;
static uint32_t page,menu_capture,submitted;
static uint32_t menu_level,menu_group,menu_item[2];
static uint32_t fps[2],render_us[2],samples[2],burst_ar[2],burst_aw[2];
static uint32_t sprite_count=1,bench_size_index=2,bench60_pass;
static const uint8_t bench_sizes[]={4,16,24,32};
static uint32_t sprite_best_60[4];
static uint32_t game_hud_pages,game_hud_number_valid[2],game_hud_bar_valid[2];
static uint32_t game_hud_numbers[2][12],game_hud_bar_value[2][2],game_hud_bar_max[2][2];
static uint16_t game_hud_bar_color[2][2];
static uint32_t game_assets_ready=1;
static FrameMax60 game_max60;
typedef struct { uint32_t x,y,w,h; char label[96]; } Field;
static Field fields[128];
static unsigned field_count,checked;
static uint32_t draw_page(void) { return page; }
static void cpu_fill(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c) {
    assert(x+w<=640 && y+h<=480);
    for(uint32_t j=y;j<y+h;++j) for(uint32_t i=x;i<x+w;++i) screen[1+j*640+i]=c;
}
static void note_field(uint32_t x,uint32_t y,uint32_t w,uint32_t h,const char *label) {
    if(!w) return;
    assert(field_count<128 && x+w<=640 && y+h<=480);
    for(unsigned i=0;i<field_count;++i) {
        Field *f=&fields[i];
        if(x<f->x+f->w && x+w>f->x && y<f->y+f->h && y+h>f->y) {
            fprintf(stderr,"TEXT OVERLAP: %s (%u,%u,%u,%u) / %s (%u,%u,%u,%u)\n",
                label,x,y,w,h,f->label,f->x,f->y,f->w,f->h); exit(2);
        }
    }
    Field *f=&fields[field_count++];
    f->x=x; f->y=y; f->w=w; f->h=h;
    snprintf(f->label,sizeof(f->label),"%s",label);
}
static void note_text(uint32_t x,uint32_t y,const char *s,uint32_t width) {
    const char *at=s; uint32_t used=0;
    while(*at) {
        uint32_t cp=font_cn_utf8_next(&at),cell=font_cn_find(cp) ? 14u : 12u;
        if(used+cell>width) break;
        used+=cell;
    }
    note_field(x,y,used,14,s);
}
static void reset_ui(void) {
    field_count=0; submitted=0; page=0;
    memset(screen,0,sizeof(screen)); screen[0]=screen[640*480+1]=0xbeef;
    memset(game_hud_number_valid,0,sizeof(game_hud_number_valid));
    memset(game_hud_bar_valid,0,sizeof(game_hud_bar_valid)); game_hud_pages=0;
}
static void save_ui(const char *name) {
    assert(screen[0]==0xbeef && screen[640*480+1]==0xbeef);
    char path[200]; snprintf(path,sizeof(path),"reports/ui_check_%s.ppm",name);
    FILE *f=fopen(path,"wb"); assert(f); fprintf(f,"P6\n640 480\n255\n");
    for(unsigned i=1;i<=640*480;++i) {
        uint16_t c=screen[i];
        fputc(((c>>11)&31)*255/31,f); fputc(((c>>5)&63)*255/63,f); fputc((c&31)*255/31,f);
    }
    fclose(f); checked++; printf("UI PASS %s: %u text/number fields\n",name,field_count);
}
static int host_fill(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c) {
    if(!x && !y && w==640 && h==480) field_count=0;
    cpu_fill(x,y,w,h,c); return 0;
}
static void paint(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c,uint32_t hw) {
    (void)hw; host_fill(x,y,w,h,c);
}
static uint32_t host_read(uint32_t address) {
    if(address==GFX_BASE+GFX_VIDEO_SIZE) return 480u<<16|640u;
    if(address==GFX_BASE+GFX_VIDEO_STATUS) return GFX_VIDEO_VALID;
    return 0;
}
static void host_write(uint32_t address,uint32_t value) { (void)address; (void)value; }
static int host_blend(uint32_t source,uint32_t stride,uint32_t x,uint32_t y,
                      uint32_t w,uint32_t h,uint8_t a,uint16_t key,uint32_t flags) {
    (void)source;(void)stride;(void)a;(void)key;(void)flags;
    assert(x+w<=640 && y+h<=480); submitted++; return 0;
}
#define mmio_read host_read
#define mmio_write host_write
#define fill_rect host_fill
#define blend_image host_blend
static void fail(const char *s) { fprintf(stderr,"%s\n",s); exit(3); }
static void publish_pixels(void) {}
static void puts_uart(const char *s) { (void)s; }
static uint32_t button_event(void) { return 16; }
static void draw_player(uint32_t f,uint32_t x,uint32_t y,uint32_t hw) { (void)f;(void)x;(void)y;(void)hw; }
static int host_present(void) {
    if(menu_capture) save_ui(!menu_level ? "home" : menu_group ? "advanced" : "basic");
    page^=1u; return 0;
}
#define present_frame host_present
static void game_draw_world_floor(int32_t x,int32_t y) { (void)x;(void)y; cpu_fill(8,80,624,360,0x18c3); }
static void scene(uint32_t f,uint32_t hw,uint32_t d,uint32_t v) { (void)f;(void)hw;(void)d;(void)v; cpu_fill(0,152,640,256,0x0843); }
'''
# Keep the actual renderer declarations, while excluding their MMIO asm bodies.
prelude = prelude.replace('#include "render.h"', '#define RENDER_H\n' + '\n'.join(
    line for line in (ROOT/'software/render.h').read_text().splitlines()
    if line.startswith('#define ') and line not in ('#define RENDER_H',)))
names = main[main.index('enum { DEMO_FILL'):main.index('static uint32_t menu_level')]
parts = [prelude, names]
for name in ('font_column','text_at_width','text_at','decimal','number_at','decimal_field',
             'number_field_at','alpha_value','hud','menu_screen'):
    body = function(main, name)
    if name == 'text_at_width':
        body = body.replace('uint32_t right=x+width;', 'uint32_t right=x+width; note_text(x,y,s,width);')
    parts.append(body)
parts.append('static uint32_t game_sprite(uint32_t frame,int32_t x,int32_t y,uint32_t alpha);')
for name in ('game_world_sprite','game_bolt','game_sprite','game_bar','game_hud_number','game_panel','game_draw'):
    body = function(view, name)
    if name == 'game_hud_number':
        body = body.replace('// Draw an opaque', 'note_field(x,y,width,14,"numeric HUD");\n    // Draw an opaque')
    parts.append(body)
for name in ('bench_hud','bench_prime_framebuffers'):
    parts.append(function(main, name))
parts.append(r'''
int main(void) {
    draw_buffer=(uintptr_t)&screen[1];
    for(unsigned group=0;group<2;++group) {
        reset_ui(); menu_level=0; menu_group=group; menu_capture=1; (void)menu_screen();
    }
    menu_capture=0;
    fps[0]=30; fps[1]=60; samples[0]=samples[1]=1;
    render_us[0]=123456; render_us[1]=16666;
    burst_ar[0]=burst_aw[0]=burst_ar[1]=burst_aw[1]=UINT32_MAX;
    for(unsigned demo=0;demo<6;++demo) {
        reset_ui(); hud(1,demo,0,UINT32_MAX,255);
        char name[32]; snprintf(name,sizeof(name),"demo_%u",demo); save_ui(name);
    }
    reset_ui(); sprite_count=UINT32_MAX; bench60_pass=1;
    for(unsigned i=0;i<4;++i) sprite_best_60[i]=UINT32_MAX;
    bench_prime_framebuffers(); save_ui("pressure");
    SurvivorGame g; game_reset(&g,12345); g.state=GAME_PLAY;
    g.kills=UINT32_MAX; g.level=999; game_max60.maximum=999;
    reset_ui(); unsigned drawn=game_draw(&g,60,UINT32_MAX,UINT32_MAX,UINT32_MAX);
    assert(drawn==submitted); save_ui("game");
    g.state=GAME_UPGRADE;
    for(unsigned set=0;set<2;++set) {
        for(unsigned n=0;n<3;++n) g.options[n]=(uint8_t)(set*3+n);
        reset_ui(); (void)game_draw(&g,60,16666,12345,12345);
        char name[32]; snprintf(name,sizeof(name),"upgrade_%u",set); save_ui(name);
    }
    for(unsigned n=0;n<6;++n) g.upgrade_level[n]=(uint8_t)game_upgrade_max(n);
    reset_ui(); (void)game_draw(&g,60,16666,12345,12345); save_ui("upgrade_max");
    for(unsigned state=GAME_READY;state<=GAME_WON;++state) {
        if(state==GAME_PLAY || state==GAME_UPGRADE) continue;
        g.state=(uint8_t)state; reset_ui(); (void)game_draw(&g,60,16666,12345,12345);
        char name[32]; snprintf(name,sizeof(name),"state_%u",state); save_ui(name);
    }
    // Exercise the actual clipping and draw budgets with live/off-screen slots.
    game_reset(&g,12345); g.state=GAME_PLAY;
    for(unsigned i=0;i<GAME_MAX_ENEMIES;++i)
        g.enemies[i]=(GameEnemy){g.x/8,g.y/8,10,10,0,0};
    for(unsigned i=0;i<GAME_MAX_BOLTS;++i)
        g.bolts[i]=(GameBolt){g.x/8,g.y/8,0,0,10,1,0};
    for(unsigned i=0;i<GAME_MAX_GEMS;++i)
        g.gems[i]=(GameGem){g.x/256,g.y/256,1,0,0};
    reset_ui(); drawn=game_draw(&g,60,10000,0,0);
    assert(drawn==submitted+48u); unsigned dense=drawn;
    reset_ui(); drawn=game_draw(&g,30,20000,0,0); assert(dense==drawn+32u);
    for(unsigned i=0;i<GAME_MAX_ENEMIES;++i) g.enemies[i].x=g.enemies[i].y=0;
    for(unsigned i=0;i<GAME_MAX_BOLTS;++i) g.bolts[i].x=g.bolts[i].y=0;
    for(unsigned i=0;i<GAME_MAX_GEMS;++i) g.gems[i].x=g.gems[i].y=0;
    reset_ui(); drawn=game_draw(&g,60,10000,0,0); assert(drawn==submitted && dense>drawn+100u);
    // Width overflow displays a marker, while edge glyphs cannot escape DDR.
    char number[11]; decimal_field(number,100000,5); assert(!strcmp(number,"9999+"));
    reset_ui(); text_at(628,466,"W",0xffff); text_at(639,0,"字",0xffff);
    assert(screen[0]==0xbeef && screen[640*480+1]==0xbeef);
    // Replacing a long cached value with a short one must clear every old digit.
    reset_ui(); game_hud_number(0,0,20,20,120,UINT32_MAX,0xffff); field_count=0;
    game_hud_number(0,0,20,20,120,1,0xffff);
    for(unsigned y=20;y<34;++y) for(unsigned x=32;x<140;++x)
        assert(screen[1+y*640+x]==0x10a6);
    field_count=0; game_hud_number(1,0,20,20,120,1,0xffff);
    assert((game_hud_number_valid[0]&1u) && (game_hud_number_valid[1]&1u));
    printf("UI CHECK PASSED: %u previews; collision/edge/overflow guards; actual Sprite clipping and 32/64 budgets\n",checked);
    return 0;
}
''')
build = ROOT / 'software/build'
build.mkdir(exist_ok=True)
source = build / 'ui_host_check.c'
source.write_text('\n'.join(parts), encoding='utf-8')
env = dict(os.environ)
env['PATH'] = str(args.cc.parent) + os.pathsep + str(args.cc.parent.parent.parent/'usr/bin') + os.pathsep + env['PATH']
command = [str(args.cc), '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror', '-finput-charset=UTF-8',
           '-fexec-charset=UTF-8', '-Isoftware', str(source), 'software/survivor_game.c', '-o', str(build/'ui_host_check.exe')]
subprocess.run(command, cwd=ROOT, env=env, check=True)
result = subprocess.run([str(build/'ui_host_check.exe')], cwd=ROOT, env=env, text=True, encoding='utf-8', capture_output=True)
(ROOT/'reports/ui_check.log').write_text(result.stdout+result.stderr, encoding='utf-8')
print(result.stdout+result.stderr)
if result.returncode:
    raise SystemExit(result.returncode)


def chunk(kind, data):
    return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data)&0xffffffff)


for path in (ROOT/'reports').glob('ui_check_*.ppm'):
    header, size, maximum, pixels = path.read_bytes().split(b'\n', 3)
    assert (header, size, maximum) == (b'P6', b'640 480', b'255')
    rows = b''.join(b'\0'+pixels[y*1920:(y+1)*1920] for y in range(480))
    png = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB',640,480,8,2,0,0,0))
    path.with_suffix('.png').write_bytes(png+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))
print(f'All Chinese literals covered by {len(available)} existing bitmap glyphs; PNGs exported.')
