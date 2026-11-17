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
for source in (main, view, (ROOT / 'software/reference_game_ui.h').read_text(encoding='utf-8'), (ROOT / 'software/book_menu.h').read_text(encoding='utf-8'),
               (ROOT / 'software/basic_demo.h').read_text(encoding='utf-8'),
               (ROOT / 'software/effects_demo.h').read_text(encoding='utf-8'),
               (ROOT / 'software/demo_skin.h').read_text(encoding='utf-8'),
               (ROOT / 'software/survivor_game.c').read_text(encoding='utf-8')):
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
#include "game_frame_bounds.h"
#include "game_art_ids.h"
#define GAME_ASSET_BASE (ASSET_BASE+0x4000u)
#define GAME_FRAME_COUNT GAME_FRAME_BOUNDS_COUNT
#define GAME_MAX_DRAW_ENEMIES GAME_MAX_ENEMIES
#define GAME_MAX_DRAW_GEMS 20u
#define GAME_MAX_DRAW_BOLTS GAME_MAX_BOLTS
#define GAME_MAX_DRAW_LANDMARKS 4u
static uint16_t screen[640*480+2];
static uintptr_t draw_buffer;
static uint32_t page,menu_capture,submitted;
static uint32_t host_cycles,display_disables,pressure_presents;
static uint32_t book_closed;
static uint32_t menu_level,menu_group,menu_item[2],menu_repaint_pages;
static uint32_t fps[2],render_us[2],samples[2],burst_ar[2],burst_aw[2];
static uint32_t sprite_count=1,bench_size_index=3,bench60_pass;
static const uint8_t bench_sizes[]={4,16,24,32};
static uint32_t sprite_best_60[4];
static uint32_t game_hud_pages,game_hud_number_valid[2],game_hud_bar_valid[2];
static uint32_t game_hud_numbers[2][12],game_page_valid[2];
static uint32_t game_assets_ready=1;
static uint32_t game_capture_dirty;
static uint32_t game_draw_enemy_count;
static uint32_t game_gem_selected[(GAME_MAX_GEMS+31u)/32u];
static uint32_t game_draw_floor_cycles,game_draw_sprite_cycles,game_draw_other_cycles;
static FrameMax60 game_max60;
typedef struct { uint32_t x,y,w,h; char label[96]; } Field;
static Field fields[128];
static unsigned field_count,checked;
static uint32_t draw_page(void) { return page; }
static uint32_t cycle_now(void) { return host_cycles+=100u; }
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
static void note_text(uint32_t x,uint32_t y,const char *s,uint32_t width,uint32_t requested_width) {
    const char *at=s; uint32_t used=0;
    while(*at) {
        uint32_t cp=font_cn_utf8_next(&at),cell=font_cn_find(cp) ? 14u : 12u;
        used+=cell;
    }
    if(requested_width<640u && used>requested_width) {
        fprintf(stderr,"TEXT CLIP: %s (%u px field, %u px required)\n",s,requested_width,used); exit(4);
    }
    if(used>width) used=width;
    note_field(x,y,used,14,s);
}
static void reset_ui(void) {
    field_count=0; submitted=0; page=0;
    memset(game_gem_selected,0,sizeof(game_gem_selected));
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
static void host_write(uint32_t address,uint32_t value) {
    if(address==GFX_BASE+GFX_DISPLAY && !value)++display_disables;
}
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
static uint32_t key_script[16],key_count,key_pos;
static uint32_t button_event(void) {
    if(key_count) { assert(key_pos<key_count); return key_script[key_pos++]; }
    return 16;
}
static int host_present(void) {
    // This routing mock must not overwrite real book-renderer captures.
    ++pressure_presents;
    page^=1u; return 0;
}
#define present_frame host_present
static void game_draw_world_floor(uint32_t page,int32_t x,int32_t y,uint32_t playing,uint32_t ticks) {
    (void)page;(void)x;(void)y;(void)playing;(void)ticks; cpu_fill(8,80,624,360,0x18c3);
}
static void game_record_dirty_rect(uint32_t x,uint32_t y,uint32_t width,uint32_t height) {
    (void)x;(void)y;(void)width;(void)height;
}
static void scene(uint32_t f,uint32_t hw,uint32_t d,uint32_t v) { (void)f;(void)hw;(void)d;(void)v; cpu_fill(0,152,640,256,0x0843); }
/* Book pixels/upload/animation are checked by check_book_menu.py. This harness
 * retains the real menu input loop while focusing on demo/game HUD fields. */
static void book_init_assets(void) {}
static void book_cover(void) { host_fill(0,0,640,480,0x0843); }
static void book_menu_frame(void) { host_fill(0,0,640,480,0x0843); }
static void book_animate(uint32_t closing) { (void)closing; }
static void book_turn(void) {}
'''
# Keep the actual renderer declarations, while excluding their MMIO asm bodies.
for name in ('GAME_MAX_DRAW_ENEMIES','GAME_MAX_DRAW_GEMS','GAME_MAX_DRAW_BOLTS'):
    actual = re.search(r'^#define '+name+r'\s+[^\n]+', view, re.M)
    assert actual, name
    prelude = re.sub(r'^#define '+name+r'\s+[^\n]+',actual.group(),prelude,flags=re.M)
prelude = prelude.replace('#include "render.h"', '#define RENDER_H\n' + '\n'.join(
    line for line in (ROOT/'software/render.h').read_text().splitlines()
    if line.startswith('#define ') and line not in ('#define RENDER_H',)))
names = main[main.index('enum { DEMO_FILL'):main.index('static uint32_t menu_level')]
parts = [prelude, names]
for name in ('font_column','text_at_width','text_at','decimal','number_at','decimal_field',
             'number_field_at','hud','menu_screen'):
    body = function(main, name)
    if name == 'text_at_width':
        body = body.replace('if(width>640u-x)', 'uint32_t requested_width=width;\n    if(width>640u-x)')
        body = body.replace('uint32_t right=x+width;', 'uint32_t right=x+width; note_text(x,y,s,width,requested_width);')
    parts.append(body)
parts.append('#include "reference_ui_assets.h"\n#define BOOK_GOLD 0xac2au\n#define BOOK_EDGE 0xc52fu')
# The dedicated book/basic harnesses check the real icon pixels on mapped DDR.
parts.append('static void book_stamp(uint32_t id,uint32_t x,uint32_t y,uint32_t s,uint16_t skip) {(void)id;(void)x;(void)y;(void)s;(void)skip;}')
parts.append(function((ROOT/'software/book_menu.h').read_text(encoding='utf-8'),'book_text_width'))
parts.append(function((ROOT/'software/book_menu.h').read_text(encoding='utf-8'),'book_text'))
parts.append('#include "demo_skin.h"')
parts.append('static uint32_t game_sprite(uint32_t frame,int32_t x,int32_t y,uint32_t alpha);')
# Exact new fullscreen game pages are exercised by check_reference_ui.py.
# This older harness retains clipping, dense-workload and legacy metric checks.
parts.append('static uint32_t game_ui_key[2]={255,255};static void game_ui_page(const SurvivorGame *g){(void)g;}static void game_ui_hud(const SurvivorGame *g,uint32_t f,uint32_t p,uint32_t b){(void)g;(void)f;(void)p;(void)b;}static void game_ui_pause(void){}')
for name in ('game_world_sprite','game_bolt','game_sprite','game_hud_number','game_enemy_frame','game_gem_frame','game_gem_visible','game_select_gems','game_draw_gems','game_draw'):
    body = function(view, name)
    if name == 'game_hud_number':
        body = body.replace('// Draw an opaque', 'note_field(x,y,width,14,"numeric HUD");\n    // Draw an opaque')
    parts.append(body)
for name in ('bench_hud','bench_prime_framebuffers'):
    parts.append(function(main, name))
parts.append(r'''
int main(void) {
    draw_buffer=(uintptr_t)&screen[1];
    // Compare panels are exercised by check_basic_demo.py/check_demo_reference.py.
    (void)demo_metrics;
    // Exercise the actual bullet renderer: original edge colors, white core,
    // symmetric brightness falloff, and viewport-edge/off-screen guards.
    for(unsigned piercing=0;piercing<2;++piercing) {
        unsigned radius=piercing ? 3u : 2u;
        GameBolt bolt={160*32,160*32,0,0,10,1,(uint8_t)piercing};
        unsigned cx=GAME_X_MIN+160u,cy=GAME_Y_MIN+160u;
        reset_ui(); assert(game_bolt(&bolt,0,0)==1);
        assert(screen[1+cy*640+cx]==0xffff);
        unsigned previous=32u;
        for(unsigned d=0;d<=radius;++d) {
            uint16_t color=screen[1+cy*640+cx+d];
            unsigned added= piercing ? color&31u : color>>11;
            assert(added<=previous); previous=added;
            assert(screen[1+cy*640+cx-d]==color);
            assert(screen[1+(cy+d)*640+cx]==color);
            assert(screen[1+(cy-d)*640+cx]==color);
        }
        assert(screen[1+cy*640+cx+radius]==(piercing ? 0xffe0 : 0x07ff));
        assert(screen[1+cy*640+cx+radius+1u]==0);
        save_ui(piercing ? "bolt_glow_piercing" : "bolt_glow_normal");
        const int32_t edge_x[]={GAME_X_MIN,GAME_X_MAX-1};
        const int32_t edge_y[]={GAME_Y_MIN,GAME_Y_MAX-1};
        for(unsigned corner=0;corner<4;++corner) {
            bolt.x=(edge_x[corner&1u]-GAME_X_MIN)*32;
            bolt.y=(edge_y[corner>>1]-GAME_Y_MIN)*32;
            reset_ui(); assert(game_bolt(&bolt,0,0)==1);
            for(unsigned y=0;y<480;++y) for(unsigned x=0;x<640;++x)
                if(x<GAME_X_MIN || x>=GAME_X_MAX || y<GAME_Y_MIN || y>=GAME_Y_MAX)
                    assert(screen[1+y*640+x]==0);
            assert(screen[0]==0xbeef && screen[640*480+1]==0xbeef);
        }
        bolt.x=-32; bolt.y=160*32;
        reset_ui(); assert(game_bolt(&bolt,0,0)==0);
        for(unsigned i=1;i<=640*480;++i) assert(screen[i]==0);
    }
    for(unsigned group=0;group<2;++group) {
        reset_ui(); menu_level=0; menu_group=group; menu_capture=1; (void)menu_screen();
    }
    menu_capture=0;
    assert(DEMO_KEY==3 && DEMO_ALPHA==4 && DEMO_BENCH==5);
    for(unsigned group=0;group<2;group++)for(unsigned item=0;item<3;item++) {
        reset_ui();menu_level=1;menu_group=group;menu_item[group]=item;
        assert(menu_screen()==group*3u+item);
    }
    for(unsigned group=0;group<2;group++) {
        reset_ui();menu_level=1;menu_group=group;menu_item[group]=2;
        key_count=2;key_pos=0;key_script[0]=2;key_script[1]=16;
        assert(menu_screen()==group*3u && menu_item[group]==0);
        reset_ui();menu_level=1;menu_item[group]=0;key_pos=0;key_script[0]=1;
        assert(menu_screen()==group*3u+2u && menu_item[group]==2);
    }
    key_count=key_pos=0;reset_ui();menu_level=0;menu_group=2;assert(menu_screen()==8);
    fps[0]=30; fps[1]=60; samples[0]=samples[1]=1;
    render_us[0]=123456; render_us[1]=16666;
    burst_ar[0]=burst_aw[0]=burst_ar[1]=burst_aw[1]=UINT32_MAX;
    for(unsigned demo=0;demo<6;++demo) {
        reset_ui(); hud(1,demo,0,UINT32_MAX,255);
        char name[32]; snprintf(name,sizeof(name),"demo_%u",demo); save_ui(name);
    }
    const unsigned transparency_levels[]={0,100,200,255};
    for(unsigned hw=0;hw<2;++hw) for(unsigned n=0;n<4;++n) {
        unsigned value=transparency_levels[n],found=0;
        reset_ui(); hud(hw,DEMO_ALPHA,0,0,value);
        for(unsigned i=0;i<field_count;++i)
            if(fields[i].x==480 && fields[i].y==144) {
                assert(strtoul(fields[i].label,NULL,10)==value);found=1;
            }
        assert(found);
        char name[40];snprintf(name,sizeof(name),"transparency_%u_%u",hw,value);save_ui(name);
    }
    reset_ui(); sprite_count=UINT32_MAX; bench60_pass=1;
    for(unsigned i=0;i<4;++i) sprite_best_60[i]=UINT32_MAX;
    display_disables=pressure_presents=0;
    bench_prime_framebuffers(); save_ui("pressure");
    assert(display_disables==0u && pressure_presents==2u);
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
    g.enemy_count=GAME_MAX_ENEMIES;g.bolt_count=GAME_MAX_BOLTS;
    reset_ui(); drawn=game_draw(&g,60,10000,0,0);
    assert(GAME_MAX_ENEMIES==256 && GAME_MAX_BOLTS==256);
    assert(game_draw_enemy_count==GAME_MAX_ENEMIES && drawn==submitted+GAME_MAX_BOLTS);
    assert(submitted==GAME_MAX_ENEMIES+GAME_MAX_DRAW_GEMS+g.orbit_count+1u);
    unsigned dense=drawn;
    // A slow measured frame must not silently reduce the requested enemy limit.
    reset_ui(); drawn=game_draw(&g,30,20000,0,0);
    assert(game_draw_enemy_count==GAME_MAX_ENEMIES && drawn==dense);
    for(unsigned i=0;i<GAME_MAX_ENEMIES;++i) g.enemies[i].x=g.enemies[i].y=0;
    for(unsigned i=0;i<GAME_MAX_BOLTS;++i) g.bolts[i].x=g.bolts[i].y=0;
    for(unsigned i=0;i<GAME_MAX_GEMS;++i) g.gems[i].x=g.gems[i].y=0;
    reset_ui(); drawn=game_draw(&g,60,10000,0,0); assert(drawn==submitted && dense>drawn+100u);
    // High slots remain visible even when every earlier slot is off-screen.
    g.enemies[GAME_MAX_ENEMIES-1u].x=g.bolts[255].x=g.x/8;
    g.enemies[GAME_MAX_ENEMIES-1u].y=g.bolts[255].y=g.y/8;
    reset_ui(); drawn=game_draw(&g,60,10000,0,0);
    assert(game_draw_enemy_count==1 && drawn==submitted+1u);
    g.enemies[GAME_MAX_ENEMIES-1u].hp=0; g.bolts[255].life=0;
    reset_ui(); drawn=game_draw(&g,60,10000,0,0);
    assert(game_draw_enemy_count==0 && drawn==submitted);
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
    printf("UI CHECK PASSED: %u legacy metric/clip fixtures (new game UI checked by check_reference_ui.py); all6 menu routes (book pixels checked separately), wraparound and game entry; pressure entry never disables display; collision/edge/overflow guards; actual Sprite clipping, 256 enemies + 256 bolts, high-slot/off-screen/empty guards\n",checked);
    return 0;
}
''')
build = ROOT / 'software/build'
build.mkdir(exist_ok=True)
source = build / 'ui_host_check.c'
source.write_text('\n'.join(parts), encoding='utf-8')
env = dict(os.environ)
env['PATH'] = str(args.cc.parent) + os.pathsep + str(args.cc.parent.parent.parent/'usr/bin') + os.pathsep + env['PATH']
if args.cc.name.lower() in ('cl', 'cl.exe'):
    command = [str(args.cc), '/nologo', '/TC', '/std:c11', '/O2', '/W0', '/utf-8',
               '/Isoftware', str(source), 'software/survivor_game.c',
               '/Fe:'+str(build/'ui_host_check.exe')]
else:
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
