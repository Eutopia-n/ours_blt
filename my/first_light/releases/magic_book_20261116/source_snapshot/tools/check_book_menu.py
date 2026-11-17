"""Run the actual book renderer, upload and navigation against guarded DDR.

Native framebuffer captures verify firmware drawing, not measured board FPS.
"""
from pathlib import Path
import argparse
import os
import re
import shutil
import subprocess
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--cc',type=Path,required=True)
args=parser.parse_args()
main=(ROOT/'software/main.c').read_text(encoding='utf-8')
def function(name,source=main):
    match=re.search(r'^static [^;{]*\b'+name+r'\([^;{]*\)\s*\{',source,re.M)
    assert match,name
    depth=0
    for token in re.finditer(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*|[{}]',source[match.end()-1:],re.S):
        if token.group()=='{':depth+=1
        if token.group()=='}':depth-=1
        if not depth:return re.sub(r'__asm__ volatile\s*\(.*?\);','',source[match.start():match.end()-1+token.end()],flags=re.S)
    raise AssertionError(name)

prelude=r'''
#include <windows.h>
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "render.h"
#include "font5x7.h"
#include "font_cn.h"
#undef ASSET_BASE
#undef FRAMEBUFFER
#define ASSET_BASE 0x10000000u
#define FRAMEBUFFER 0x11000000u
static uint32_t draw_buffer=FRAMEBUFFER_B,active_page,display_enabled,clock_value;
static uint32_t menu_level,menu_group,menu_item[2],menu_repaint_pages;
static uint32_t keys[16],key_count,key_pos,cover_events,menu_events,present_count;
static uint16_t last_front[640*480];
static uint32_t draw_page(void){return draw_buffer==FRAMEBUFFER_B;}
static uint32_t cycle_now(void){return clock_value+=1500000u;}
static void fail(const char *s){fprintf(stderr,"%s\n",s);abort();}
static void cpu_fill(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c){
    assert(x+w<=640u && y+h<=480u);
    assert(!display_enabled || draw_page()!=active_page);
    for(uint32_t row=0;row<h;++row) {
        uint16_t *p=(void*)(uintptr_t)(draw_buffer+(y+row)*1280u+x*2u);
        for(uint32_t col=0;col<w;++col)p[col]=c;
    }
}
static void paint(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c,uint32_t hw){
    (void)hw;cpu_fill(x,y,w,h,c);
}
static void draw_player(uint32_t frame,uint32_t x,uint32_t y,uint32_t hw){
    (void)frame;(void)x;(void)y;(void)hw;
}
static void publish_pixels(void){}
static int host_present(void){
    if(display_enabled)assert(!memcmp(last_front,(void*)(uintptr_t)(active_page ? FRAMEBUFFER_B:FRAMEBUFFER),FRAMEBUFFER_BYTES));
    active_page=draw_page();draw_buffer=active_page ? FRAMEBUFFER:FRAMEBUFFER_B;
    memcpy(last_front,(void*)(uintptr_t)(active_page ? FRAMEBUFFER_B:FRAMEBUFFER),FRAMEBUFFER_BYTES);
    ++present_count;return 0;
}
#define present_frame host_present
static void host_write(uint32_t address,uint32_t value){
    assert(address==GFX_BASE+GFX_DISPLAY && value==1u);display_enabled=value;
}
#define mmio_write host_write
static void puts_uart(const char *s){
    if(!strncmp(s,"BOOK COVER",10))++cover_events;
    if(!strncmp(s,"MENU",4))++menu_events;
}
static uint32_t button_event(void){assert(key_pos<key_count);return keys[key_pos++];}
static void script(uint32_t a,uint32_t b,uint32_t c,uint32_t d){
    keys[0]=a;keys[1]=b;keys[2]=c;keys[3]=d;key_count=4;key_pos=0;
}
static void save(const char *name){
    char path[220];snprintf(path,sizeof(path),"reports/book_%s.ppm",name);
    FILE *f=fopen(path,"wb");assert(f);fprintf(f,"P6\n640 480\n255\n");
    const uint16_t *p=(void*)(uintptr_t)draw_buffer;
    for(uint32_t n=0;n<640u*480u;++n){
        fputc(((p[n]>>11)&31u)*255u/31u,f);fputc(((p[n]>>5)&63u)*255u/63u,f);fputc((p[n]&31u)*255u/31u,f);
    }
    fclose(f);
}
'''
parts=[prelude]
for name in ('font_column','text_at_width','text_at','decimal','number_at','decimal_field','number_field_at'):
    parts.append(function(name))
parts+=['#include "book_menu.h"',function('menu_screen'),r'''
enum {DEMO_FILL,DEMO_COPY,DEMO_BUFFER,DEMO_KEY,DEMO_ALPHA,DEMO_BENCH};
#define BENCH_VARIANTS 4u
static uint32_t sprite_count=1u,bench_size_index=3u,bench60_pass;
static const uint8_t bench_sizes[4]={4,16,24,32};
static uint32_t bench_sources[4]={ASSET_BASE+0x2800u+0x680u,ASSET_BASE+0x2800u,ASSET_BASE+0x2800u+0x200u,ASSET_BASE+0x2800u+0x800u};
static const char *const demo_names[6]={"矩形填充","图像复制","双缓冲","颜色键","透明混合","SPRITE 压力"};
static const char *const demo_details[6]={"","","","","","FPGA ALPHA + COLOR KEY / 60 FPS"};
static const char *const action_labels[6]={"","","","","","W加5 S减5 长按连发"};
static uint32_t fps[2],render_us[2],samples[2],burst_ar[2],burst_aw[2],sprite_best_60[4];
static uint32_t game_hud_number_valid[2],game_hud_numbers[2][12];
''']
for name in ('sprite_pixel_sized','blend_rgb565','bounce','sprite_seed'):
    parts.append(function(name))
parts.append(r'''
static int host_blend(uint32_t source,uint32_t stride,uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint8_t alpha,uint16_t key,uint32_t flags){
    assert(draw_page()!=active_page);
    for(uint32_t row=0;row<h;++row)for(uint32_t col=0;col<w;++col){
        const uint16_t *s=(void*)(uintptr_t)(source+row*stride+col*2u);
        uint16_t *d=(void*)(uintptr_t)(draw_buffer+(y+row)*1280u+(x+col)*2u);
        *d=blend_rgb565(*s,*d,alpha,key,flags);
    }
    return 0;
}
#define blend_image host_blend
''')
parts.append(function('draw_bench_sprite'))
scene=function('scene')
scene=scene[scene.index('default: // Performance scene'):scene.index('    publish_pixels();')]
parts.append('static void scene(uint32_t frame,uint32_t hw,uint32_t demo,uint32_t variant) {\n(void)variant;\nswitch(demo) {\n'+
             scene+'\npublish_pixels();}\n')
parts.append(function('game_hud_number',(ROOT/'software/game_view.h').read_text(encoding='utf-8')))
parts+=[function('bench_hud'),function('bench_prime_framebuffers'),r'''
int main(void){
    assert(VirtualAlloc((void*)(uintptr_t)(ASSET_BASE-65536u),ASSET_BYTES+131072u,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    assert(VirtualAlloc((void*)(uintptr_t)(FRAMEBUFFER-65536u),2u*FRAMEBUFFER_BYTES+131072u,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    memset((void*)(uintptr_t)(ASSET_BASE-65536u),0xa5,ASSET_BYTES+131072u);
    memset((void*)(uintptr_t)(FRAMEBUFFER-65536u),0x5a,2u*FRAMEBUFFER_BYTES+131072u);
    FILE *f=fopen("assets/game/game.rgb565","rb");assert(f);
    assert(fread((void*)(uintptr_t)PLAYER_ASSET_BASE,1,2048,f)==2048);fclose(f);
    uint8_t *before=malloc(ASSET_BYTES);assert(before);memcpy(before,(void*)(uintptr_t)ASSET_BASE,ASSET_BYTES);
    book_init_assets();
    uint8_t *expected=malloc(BOOK_ASSET_BYTES);assert(expected);
    f=fopen("assets/ui/magic_book_v5/runtime/book_layers.rgb565","rb");assert(f);
    assert(fread(expected,1,BOOK_ASSET_BYTES,f)==BOOK_ASSET_BYTES);fclose(f);
    assert(!memcmp(expected,(void*)(uintptr_t)BOOK_ASSET_BASE,BOOK_ASSET_BYTES));
    for(uint32_t n=0;n<ASSET_BYTES;++n)if(n<BOOK_ASSET_BASE-ASSET_BASE || n>=BOOK_ASSET_BASE-ASSET_BASE+BOOK_ASSET_BYTES)
        assert(*(uint8_t*)(uintptr_t)(ASSET_BASE+n)==before[n]);
    book_init_assets();assert(!memcmp(expected,(void*)(uintptr_t)BOOK_ASSET_BASE,BOOK_ASSET_BYTES));
    for(uint32_t level=0;level<3u;++level)for(uint32_t choice=0;choice<3u;++choice){
        menu_level=level!=0;menu_group=level ? level-1u:choice;
        if(level)menu_item[menu_group]=choice;
        book_menu_frame();char name[40];snprintf(name,sizeof(name),"menu_%u_%u",level,choice);save(name);
    }
    menu_level=0;menu_group=0;book_menu_frame();book_capture();
    for(uint32_t n=0;n<=120u;++n){
        book_opening_frame(n);
        char name[40];snprintf(name,sizeof(name),"opening_%03u",n);save(name);
    }
    book_cover();save("cover");
    menu_level=menu_group=menu_item[0]=0;book_closed=1;
    script(16,0,16,16);assert(menu_screen()==0u && !book_closed && cover_events==1u);
    for(uint32_t group=0;group<2u;++group)for(uint32_t item=0;item<3u;++item){
        menu_level=1;menu_group=group;menu_item[group]=item;
        script(16,0,0,0);assert(menu_screen()==group*3u+item);
    }
    menu_level=1;menu_group=1;menu_item[1]=2;
    script(2,16,0,0);assert(menu_screen()==3u && menu_item[1]==0);
    menu_level=1;menu_item[1]=0;
    script(1,16,0,0);assert(menu_screen()==5u && menu_item[1]==2);
    menu_level=0;menu_group=2;script(16,0,0,0);assert(menu_screen()==8u);
    menu_level=1;menu_group=0;menu_item[0]=1;script(4,16,16,0);
    assert(menu_screen()==1u && menu_item[0]==1u);
    menu_level=0;menu_group=2;script(4,0,16,0);keys[4]=16;key_count=5;
    assert(menu_screen()==8u && !book_closed && cover_events==2u);
    menu_level=1;menu_group=0;menu_item[0]=0;menu_repaint_pages=2;
    uint32_t old=present_count;script(16,0,0,0);assert(menu_screen()==0u && present_count==old+2u);
    assert(!memcmp((void*)(uintptr_t)FRAMEBUFFER,(void*)(uintptr_t)FRAMEBUFFER_B,FRAMEBUFFER_BYTES));
    // The actual pressure branch/HUD/entry keep the book visible until a full
    // back page is ready. Old code's DISPLAY=0 fails host_write immediately.
    for(uint32_t variant=0;variant<4u;++variant){
        uint16_t *p=(void*)(uintptr_t)bench_sources[variant];uint32_t size=bench_sizes[variant];
        for(uint32_t y=0;y<size;++y)for(uint32_t x=0;x<size;++x)p[y*size+x]=sprite_pixel_sized(size,y,x);
    }
    old=present_count;bench_prime_framebuffers();
    assert(display_enabled && present_count==old+2u);
    assert(!memcmp((void*)(uintptr_t)FRAMEBUFFER,(void*)(uintptr_t)FRAMEBUFFER_B,FRAMEBUFFER_BYTES));
    save("pressure_entry");
    menu_level=1;menu_group=1;menu_item[1]=2;script(16,0,0,0);assert(menu_screen()==5u);
    for(uint32_t n=0;n<65536u;++n){
        assert(*(uint8_t*)(uintptr_t)(ASSET_BASE-65536u+n)==0xa5);
        assert(*(uint8_t*)(uintptr_t)(ASSET_BASE+ASSET_BYTES+n)==0xa5);
        assert(*(uint8_t*)(uintptr_t)(FRAMEBUFFER-65536u+n)==0x5a);
        assert(*(uint8_t*)(uintptr_t)(FRAMEBUFFER+2u*FRAMEBUFFER_BYTES+n)==0x5a);
    }
    assert(!memcmp(expected,(void*)(uintptr_t)BOOK_ASSET_BASE,BOOK_ASSET_BYTES));
    puts("BOOK MENU PASS: exact asset upload; 9 pages; 121 animation poses; cover/open/close; all6 routes; game entry; wraparound/return selection; both-page priming; actual pressure entry + return; guards; no active-page writes or display disable.");
    return 0;
}
''']
out=ROOT/'software/build/book_menu_check';out.mkdir(exist_ok=True)
source=out/'check.c';source.write_text('\n'.join(parts),encoding='utf-8')
env=dict(os.environ);env['PATH']=str(args.cc.parent)+os.pathsep+env.get('PATH','')
subprocess.run([str(args.cc),'-std=c11','-O2','-Wall','-Wextra','-Werror','-finput-charset=UTF-8',
    '-fexec-charset=UTF-8','-Wno-unused-function','-Isoftware',str(source),'-o',str(out/'check.exe')],cwd=ROOT,env=env,check=True)
r=subprocess.run([str(out/'check.exe')],cwd=ROOT,env=env,capture_output=True,text=True)
(ROOT/'reports/book_menu_check.log').write_text(r.stdout+r.stderr,encoding='utf-8');print(r.stdout+r.stderr)
if r.returncode:raise SystemExit(r.returncode)
for p in (ROOT/'reports').glob('book_*.ppm'):
    with Image.open(p) as im:im.save(p.with_suffix('.png'))
for name,group in (('home',0),('basic',1),('advanced',2)):
    for suffix in ('.ppm','.png'):
        shutil.copy2(ROOT/f'reports/book_menu_{group}_0{suffix}',ROOT/f'reports/ui_check_{name}{suffix}')
frames=[Image.open(ROOT/f'reports/book_opening_{n:03}.png').convert('RGB') for n in range(0,121,2)]
frames[0].save(ROOT/'reports/book_firmware_opening.gif',save_all=True,append_images=frames[1:],duration=40,loop=0)
gallery=Image.new('RGB',(1920,1440))
for group in range(3):
    for choice in range(3):gallery.paste(Image.open(ROOT/f'reports/book_menu_{group}_{choice}.png'),(choice*640,group*480))
gallery.save(ROOT/'reports/book_firmware_menus.png')
print('Firmware captures exported; animation timing in GIF is illustrative, not board performance.')
