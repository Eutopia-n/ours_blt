"""Capture the actual firmware UI and compare against the immutable HTML PNGs.

Also export real projection descriptors and an independent scalar framebuffer
for the AXI RTL regression. Native captures do not measure board frame rate.
"""
from pathlib import Path
import os,argparse,warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)
import ast,base64,io,json,re,struct,subprocess
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'software/build/reference_ui_check';OUT.mkdir(parents=True,exist_ok=True)
# Native host support is fixed here; the compatibility wrapper delegates to this checker.
prelude='\n#include <windows.h>\n#include <stdint.h>\n#include <assert.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include "render.h"\n#include "font5x7.h"\n#include "font_cn.h"\n#undef ASSET_BASE\n#undef FRAMEBUFFER\n#define ASSET_BASE 0x10000000u\n#define FRAMEBUFFER 0x11000000u\nstatic uint32_t draw_buffer=FRAMEBUFFER_B,active_page,display_enabled,clock_value;\nstatic uint32_t menu_level,menu_group,menu_item[2],menu_repaint_pages;\nstatic uint32_t keys[16],key_count,key_pos,cover_events,menu_events,present_count;\nstatic uint32_t cache_copies;\nstatic uint64_t cpu_fill_pixels;\nstatic uint16_t last_front[640*480];\nstatic uint32_t draw_page(void){return draw_buffer==FRAMEBUFFER_B;}\nstatic uint32_t cycle_now(void){return clock_value+=1500000u;}\nstatic void fail(const char *s){fprintf(stderr,"%s\\n",s);abort();}\nstatic void cpu_fill(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c){\n    cpu_fill_pixels+=(uint64_t)w*h;\n    assert(x+w<=640u && y+h<=480u);\n    assert(!display_enabled || draw_page()!=active_page);\n    for(uint32_t row=0;row<h;++row) {\n        uint16_t *p=(void*)(uintptr_t)(draw_buffer+(y+row)*1280u+x*2u);\n        for(uint32_t col=0;col<w;++col)p[col]=c;\n    }\n}\nstatic void paint(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c,uint32_t hw){\n    (void)hw;cpu_fill(x,y,w,h,c);\n}\nstatic void draw_player(uint32_t frame,uint32_t x,uint32_t y,uint32_t hw){\n    (void)frame;(void)x;(void)y;(void)hw;\n}\nstatic void publish_pixels(void){}\nstatic void uart_number(const char *s,uint32_t v){(void)s;(void)v;}\nint copy_image(uint32_t source,uint32_t stride,uint32_t x,uint32_t y,uint32_t w,uint32_t h){\n    if(source==ASSET_BASE+0x66A00u)++cache_copies;\n    assert(source>=ASSET_BASE && source+(h-1u)*stride+w*2u<=ASSET_BASE+ASSET_BYTES);\n    assert(x+w<=640u && y+h<=480u && (!display_enabled || draw_page()!=active_page));\n    for(uint32_t row=0;row<h;++row)memcpy((void*)(uintptr_t)(draw_buffer+(y+row)*1280u+x*2u),\n        (void*)(uintptr_t)(source+row*stride),w*2u);\n    return 0;\n}\nstatic int host_present(void){\n    if(display_enabled)assert(!memcmp(last_front,(void*)(uintptr_t)(active_page ? FRAMEBUFFER_B:FRAMEBUFFER),FRAMEBUFFER_BYTES));\n    active_page=draw_page();draw_buffer=active_page ? FRAMEBUFFER:FRAMEBUFFER_B;\n    memcpy(last_front,(void*)(uintptr_t)(active_page ? FRAMEBUFFER_B:FRAMEBUFFER),FRAMEBUFFER_BYTES);\n    ++present_count;return 0;\n}\n#define present_frame host_present\nstatic void host_write(uint32_t address,uint32_t value){\n    assert(address==GFX_BASE+GFX_DISPLAY && value==1u);display_enabled=value;\n}\n#define mmio_write host_write\nstatic void puts_uart(const char *s){\n    if(!strncmp(s,"BOOK COVER",10))++cover_events;\n    if(!strncmp(s,"MENU",4))++menu_events;\n}\nstatic uint32_t button_event(void){assert(key_pos<key_count);return keys[key_pos++];}\nstatic void script(uint32_t a,uint32_t b,uint32_t c,uint32_t d){\n    keys[0]=a;keys[1]=b;keys[2]=c;keys[3]=d;key_count=4;key_pos=0;\n}\nstatic void save(const char *name){\n    char path[220];snprintf(path,sizeof(path),"reports/book_%s.ppm",name);\n    FILE *f=fopen(path,"wb");assert(f);fprintf(f,"P6\\n640 480\\n255\\n");\n    const uint16_t *p=(void*)(uintptr_t)draw_buffer;\n    for(uint32_t n=0;n<640u*480u;++n){\n        fputc(((p[n]>>11)&31u)*255u/31u,f);fputc(((p[n]>>5)&63u)*255u/63u,f);fputc((p[n]&31u)*255u/31u,f);\n    }\n    fclose(f);\n}\n'
prelude=prelude.replace('#include "render.h"','#define UI_NATIVE_REFERENCE\n#include "render.h"')
prelude=prelude.replace('assert(address==GFX_BASE+GFX_DISPLAY && value==1u);display_enabled=value;','(void)address;(void)value;')
prelude=prelude.replace('static void host_write(uint32_t address,uint32_t value){\n    (void)address;(void)value;\n}',r'''
static uint32_t uart_space,uart_frame_writes,uart_captured;
static char uart_capture[32768];
static void uart_putc(char c){
    assert(uart_captured+1<sizeof(uart_capture));
    uart_capture[uart_captured++]=c;uart_capture[uart_captured]=0;
}
static void host_write(uint32_t address,uint32_t value){
    if(address==SYSTEM_UART_0_IO_CTRL){
        assert(uart_space && ++uart_frame_writes<=32u);--uart_space;
        uart_putc((char)value);
    }
}
''')
main=(ROOT/'software/main.c').read_text(encoding='utf-8')
game_ui=(ROOT/'software/reference_game_ui.h').read_text(encoding='utf-8')
ui_words={word for literal in re.findall(r'"([^"\n]*)"',game_ui)
          for word in re.findall(r'[A-Za-z]+',literal)}
assert ui_words<=set(('W','S','A','D','ENTER')),ui_words
def function(name):
    m=re.search(r'^static [^;{]*\b'+name+r'\([^;{]*\)\s*\{',main,re.M);assert m,name
    depth=0
    for token in re.finditer(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*|[{}]',main[m.end()-1:],re.S):
        if token[0]=='{':depth+=1
        if token[0]=='}':depth-=1
        if not depth:return re.sub(r'__asm__ volatile\s*\(.*?\);','',main[m.start():m.end()-1+token.end()],flags=re.S)
parts=[prelude]
parts += [function(n) for n in ('font_column','text_at_width','text_at','decimal','number_at','decimal_field','number_field_at')]
parts+=['uint8_t book_native_rom[65536];','#include "book_menu.h"',function('menu_screen'),r'''
static uint16_t blend565(uint16_t a,uint16_t b,uint32_t alpha){
    uint32_t r=(((a>>11)*alpha+(b>>11)*(255-alpha)+127)/255);
    uint32_t g=((((a>>5)&63)*alpha+((b>>5)&63)*(255-alpha)+127)/255);
    uint32_t bl=(((a&31)*alpha+(b&31)*(255-alpha)+127)/255);
    return (uint16_t)((r<<11)|(g<<5)|bl);
}
static const char *projection_case;
static uint32_t projection_skip;
static void export_projection(const char *,uint32_t,uint16_t);
void book_native_submit(uint32_t background,uint16_t color,uint32_t count){
    uint16_t *frame=(void*)(uintptr_t)draw_buffer;
    for(uint32_t y=0;y<480;++y)for(uint32_t x=0;x<640;++x){
        uint16_t c=color;
        if(background&1u){const uint8_t *p=(void*)(uintptr_t)(background&~1u);uint32_t i=(p[(y/2)*128+(x/2)/4]>>(((x/2)%4)*2))&3;c=book_desk_palette[i];}
        else if(background)c=((uint16_t*)(uintptr_t)background)[y*640+x];
        frame[y*640+x]=c;
    }
    for(uint32_t n=0;n<count;++n){
        const uint32_t *c=(void*)(uintptr_t)(BOOK_COMMAND_BASE+n*32);
        int32_t left=(int16_t)c[2],top=(int16_t)c[3],w=c[2]>>16,h=c[3]>>16;
        uint32_t sw=(c[7]>>8)&1023,sh=(c[7]>>18)&1023,flags=c[6]>>24,alpha=(c[6]>>16)&255,light=c[7]&255;
        for(int32_t y=top<0?0:top;y<top+h&&y<480;++y){
            uint32_t v=(uint32_t)(((uint64_t)(y-top)*c[5]+c[5]/2)>>16);if(sh&&v>=sh)v=sh-1;
            for(int32_t x=left<0?0:left;x<left+w&&x<640;++x){
                uint16_t color=(uint16_t)c[6];
                if(c[0]){
                    uint32_t u=(uint32_t)(((uint64_t)(x-left)*c[4]+c[4]/2)>>16);if(u>=sw)u=sw-1;if(flags&2)u=sw-1-u;
                    color=flags&32 ? book_desk_palette[(*(uint8_t*)(uintptr_t)(c[0]+v*(c[1]&65535)+u/4)>>((u%4)*2))&3]:flags&16 ? book_front_palette[*(uint8_t*)(uintptr_t)(c[0]+v*(c[1]&65535)+u)]:*(uint16_t*)(uintptr_t)(c[0]+v*(c[1]&65535)+u*2);
                    if(((flags&1)&&color==(uint16_t)c[6])||((flags&8)&&(color==4260||color==8455||color==15150)))continue;
                    color=blend565(color,0,light);
                }
                frame[y*640+x]=blend565(color,frame[y*640+x],alpha);
            }
        }
    }
    if(projection_case && projection_skip--==0){export_projection(projection_case,background,color);projection_case=0;}
}
#include "frame_metrics.h"
static uint32_t reference_mmio_read(uint32_t a){(void)a;return 0;}
int blend_image(uint32_t source,uint32_t pitch,uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint8_t alpha,uint16_t key,uint32_t flags){
    for(uint32_t row=0;row<h;++row)for(uint32_t col=0;col<w;++col){
        uint16_t c=*(uint16_t*)(uintptr_t)(source+row*pitch+col*2);
        uint16_t *p=(void*)(uintptr_t)(draw_buffer+(y+row)*1280+(x+col)*2);
        if(!(flags&GFX_BLEND_KEY)||c!=key)*p=blend565(c,*p,(flags&GFX_BLEND_ALPHA)?alpha:255);
    }return 0;
}
#define mmio_read reference_mmio_read
int gfx_batch_submit(uint32_t address,uint32_t count){
    assert(!(address&31u) && address>=ASSET_BASE && address+count*32u<=ASSET_BASE+ASSET_BYTES);
    const GfxBatchCommand *list=(void*)(uintptr_t)address;
    for(uint32_t i=0;i<count;++i){
        const GfxBatchCommand *c=&list[i];uint32_t offset=c->destination-draw_buffer;
        assert(!c->reserved0 && !c->reserved1 && ((c->control&3u)==0u || (c->control&3u)==2u));
        if((c->control&3u)==0u)cpu_fill((offset%1280u)/2u,offset/1280u,c->extent&65535u,c->extent>>16,(uint16_t)c->colors);
        else blend_image(c->source,c->source_stride,(offset%1280u)/2u,offset/1280u,
                         c->extent&65535u,c->extent>>16,(c->control>>8)&255u,c->colors>>16,(c->control>>2)&3u);
    }
    return 0;
}
int gfx_positions_submit(uint32_t s,uint32_t side,uint32_t a,uint32_t n,uint8_t alpha,uint16_t key,uint32_t flags){
    const uint32_t *p=(void*)(uintptr_t)a;
    for(uint32_t i=0;i<n;++i){uint32_t d=p[i]-draw_buffer;blend_image(s,side*2,(d%1280)/2,d/1280,side,side,alpha,key,flags);}return 0;
}
int gfx_tile_submit(uint32_t s,uint32_t side,uint32_t a,uint32_t n,uint8_t alpha,uint16_t key,uint32_t flags,uint16_t clear){
    (void)s;(void)side;(void)a;(void)n;(void)alpha;(void)key;(void)flags;(void)clear;abort();return -1;
}
#include "game_view_host.h"
enum {DEMO_FILL,DEMO_COPY,DEMO_BUFFER,DEMO_KEY,DEMO_ALPHA,DEMO_BENCH};
#define BENCH_VARIANTS 4u
static uint32_t sprite_count=1u,bench_size_index=3u,bench60_pass,bench_batch_size;
static uint32_t bench_tile_cursor[180];
static uint32_t bench_strategy_count,bench_strategy_size,bench_strategy_trials,bench_strategy_peak[2],bench_strategy_tile;
static const uint8_t bench_sizes[4]={4,16,24,32};
static uint32_t bench_sources[4]={ASSET_BASE+0x2e80u,ASSET_BASE+0x2800u,ASSET_BASE+0x2a00u,ASSET_BASE+0x3000u};
static const char *const demo_names[6]={"矩形填充","图像复制","双缓冲","颜色键","透明混合","SPRITE压力"};
static const char *const demo_details[6]={"","","","","","FPGA ALPHA + COLOR KEY / 60 FPS"};
static const char *const action_labels[6]={"","","","","","W加5 S减5 长按连发"};
static uint32_t fps[2],render_us[2],samples[2],burst_ar[2],burst_aw[2],sprite_best_60[4];
#include "demo_skin.h"
''']
for n in ('sprite_pixel_sized','blend_rgb565','bounce','sprite_seed','draw_bench_sprite','bench_batch_frame',
          'bench_compact_frame','bench_tile_positions','bench_tile_frame','bench_render_frame'):
    parts.append(function(n))
scene=function('scene')
scene=scene[scene.index('default: // Performance scene'):scene.index('    publish_pixels();')]
parts.append('static void scene(uint32_t frame,uint32_t hw,uint32_t demo,uint32_t variant){(void)variant;switch(demo){'+scene+'publish_pixels();}')
parts += [function('bench_hud'),function('bench_prime_framebuffers'),r'''
static void save_binary(const char *name,const void *p,uint32_t bytes){FILE *f=fopen(name,"wb");assert(f);assert(fwrite(p,1,bytes,f)==bytes);fclose(f);}
static void export_projection(const char *name,uint32_t background,uint16_t color){
    char path[200];uint32_t metadata[3]={0xa000u|book_command_count,background,color};
    snprintf(path,sizeof(path),"software/build/reference_ui_check/%s_assets.bin",name);save_binary(path,(void*)(uintptr_t)ASSET_BASE,ASSET_BYTES);
    snprintf(path,sizeof(path),"software/build/reference_ui_check/%s_expected.bin",name);save_binary(path,(void*)(uintptr_t)draw_buffer,FRAMEBUFFER_BYTES);
    snprintf(path,sizeof(path),"software/build/reference_ui_check/%s_metadata.bin",name);save_binary(path,metadata,sizeof(metadata));
}
int main(void){
    assert(VirtualAlloc((void*)(uintptr_t)(ASSET_BASE-65536u),ASSET_BYTES+131072u,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    assert(VirtualAlloc((void*)(uintptr_t)(FRAMEBUFFER-65536u),2u*FRAMEBUFFER_BYTES+131072u,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    FILE *f=fopen("assets/ui/magic_book_v5/runtime/reference/ui_stream.bin","rb");assert(f);fread(book_native_rom,1,sizeof(book_native_rom),f);fclose(f);
    book_init_assets();
    for(uint32_t id=0;id<BOOK_RESOURCE_COUNT;++id){
        if(id==BOOK_GAME_ORNAMENT||id==BOOK_HERO_HOME||id==BOOK_HERO_CHAPTER||id==BOOK_HERO_GAME||id==BOOK_CLASP)continue;
        const BookResource *r=&book_resources[id];assert(r->base+r->bytes<=0x60000u);
    }
    book_cover();save("reference_cover");
    for(uint32_t level=0;level<3;++level)for(uint32_t choice=0;choice<3;++choice){
        menu_level=level!=0;menu_group=level ? level-1u:choice;if(level)menu_item[menu_group]=choice;
        book_cache_valid=0;book_menu_frame();char name[64];snprintf(name,sizeof(name),"reference_menu_%u_%u",level,choice);save(name);
    }
    menu_level=0;menu_group=0;book_cache_valid=0;book_menu_frame();book_load(BOOK_CLASP);book_capture();
    for(uint32_t frame=1;frame<120;++frame){
        projection_case=frame==12 ? "bridge":frame==60 ? "curved":frame==104 ? "eyes":frame==119 ? "final":0;projection_skip=0;
        book_open_pose(frame);assert(book_command_count<=512u);
        if(frame>=88u && frame<=110u) {
            const uint16_t *pixels=(void*)(uintptr_t)draw_buffer;uint32_t pupils=0;
            for(uint32_t y=224;y<250;++y)for(uint32_t x=166;x<196;++x)
                if(pixels[y*640u+x]==0)++pupils;
            assert(pupils>=2u); // Previously every zero-colour pupil was discarded.
        }
        char name[80];snprintf(name,sizeof(name),"reference_open_%03u",frame);if(frame%2u==0u||frame==1u||frame==119u)save(name);
        if(frame==60){
            save_binary("software/build/reference_ui_check/commands.bin",(void*)(uintptr_t)BOOK_COMMAND_BASE,book_command_count*32);
            save_binary("software/build/reference_ui_check/assets.bin",(void*)(uintptr_t)ASSET_BASE,ASSET_BYTES);
            save_binary("software/build/reference_ui_check/expected.bin",(void*)(uintptr_t)draw_buffer,FRAMEBUFFER_BYTES);
            printf("COMMANDS %u\n",book_command_count);save_binary("software/build/reference_ui_check/command_count.bin",&book_command_count,4);
        }
    }
    // Execute the actual chapter transition in both directions, including
    // transient texture reuse and the last displayed (retired) buffer.
    for(uint32_t direction=0;direction<2;++direction){
        book_assets_ready=0;book_cache_valid=0;book_init_assets();
        menu_group=0;menu_item[0]=0;menu_level=direction;book_menu_frame();host_present();
        menu_level=!direction;projection_case=direction ? "chapter_back":"chapter_forward";projection_skip=8;book_turn();
        uint32_t displayed=draw_buffer==FRAMEBUFFER ? FRAMEBUFFER_B:FRAMEBUFFER;
        assert(!memcmp((void*)(uintptr_t)displayed,(void*)(uintptr_t)BOOK_CACHE_BASE,FRAMEBUFFER_BYTES));
    }
    book_load(BOOK_GAME_ORNAMENT);book_transient=BOOK_GAME_ORNAMENT;
    init_game_assets();
    SurvivorGame g;game_reset(&g,1);g.ticks=1800;g.level=2;g.xp=18;g.xp_target=30;g.kills=51;
    for(uint32_t state=0;state<=GAME_WON;++state){
        if(state==GAME_PLAY||state==GAME_PAUSED)continue;
        g.state=state;g.options[0]=0;g.options[1]=1;g.options[2]=2;g.choice=0;
        game_ui_key[draw_page()]=0xffffffffu;game_draw(&g,60,0,0,0);char name[64];snprintf(name,sizeof(name),"reference_game_%u",state);save(name);
    }
    int32_t cx=game_camera_x(&g),cy=game_camera_y(&g);
    static const uint16_t positions[5][2]={{124,98},{500,142},{204,284},{552,288},{424,236}};
    for(uint32_t n=0;n<5;++n){g.enemies[n].kind=n;g.enemies[n].hp=g.enemies[n].max_hp=3;g.enemies[n].x=(cx+positions[n][0])*32;g.enemies[n].y=(cy+positions[n][1])*32;}g.enemy_count=5;
    static const uint16_t gems[4][3]={{204,56,1},{370,300,1},{256,322,5},{526,62,10}};
    for(uint32_t n=0;n<4;++n){g.gems[n].x=cx+gems[n][0];g.gems[n].y=cy+gems[n][1];g.gems[n].value=gems[n][2];}g.gem_count=4;
    g.bolts[0]=(GameBolt){(cx+100)*32,(cy+100)*32,0,0,60,1,0};
    g.bolts[1]=(GameBolt){0,0,0,0,60,1,0};g.bolt_count=2;
    g.state=GAME_PLAY;game_hud_pages=0;game_ui_key[draw_page()]=0xffffffffu;
    assert(game_draw(&g,60,0,0,0)==12);save("reference_game_play");
    assert(game_draw_bolt_count==1);
    // Five enemies, four gems, one orb, the hero and one visible projectile.
    assert(game_hud_numbers[draw_page()][7]==12 && game_hud_numbers[draw_page()][8]==2);
    assert(game_hud_numbers[draw_page()][9]==0);
    // A record needs a complete, on-time window; an off-screen object does
    // not enter it. Pauses discard a partial window but preserve the record.
    for(uint32_t n=0;n<29;++n)frame_max60_sample(&game_max60,FRAME_60_CYCLES,1,12);
    assert(game_max60.maximum==0);
    frame_max60_sample(&game_max60,FRAME_60_CYCLES,1,12);
    assert(game_max60.maximum==12);
    for(uint32_t n=0;n<30;++n)frame_max60_sample(&game_max60,FRAME_60_CYCLES+(n==2),1,256);
    assert(game_max60.maximum==12);
    for(uint32_t n=0;n<30;++n)frame_max60_sample(&game_max60,FRAME_60_CYCLES,1+(n==2),256);
    assert(game_max60.maximum==12);
    for(uint32_t n=0;n<29;++n)frame_max60_sample(&game_max60,FRAME_60_CYCLES,1,256);
    frame_max60_clear_window(&game_max60);
    assert(game_max60.maximum==12 && !game_max60.frames);
    for(uint32_t n=0;n<30;++n)frame_max60_sample(&game_max60,FRAME_60_CYCLES,1,256);
    for(uint32_t pass=0;pass<2;++pass) {
        uint32_t p=draw_page();
        game_ui_metrics(256,256,game_max60.maximum,g.kills,60,p);
        assert(game_hud_numbers[p][7]==256 && game_hud_numbers[p][8]==256 && game_hud_numbers[p][9]==256);
        game_ui_metrics(1,2,256,g.kills,60,p);
        assert(game_hud_numbers[p][7]==1 && game_hud_numbers[p][8]==2);
        for(uint32_t y=54;y<68;++y)for(uint32_t x=446;x<482;++x)
            assert(((uint16_t*)(uintptr_t)draw_buffer)[y*640u+x]==0x1084);
        game_ui_metrics(0,0,256,g.kills,60,p);
        assert(!game_hud_numbers[p][7] && !game_hud_numbers[p][8]);
        host_present();game_draw(&g,60,0,0,0);
    }
    game_max60.maximum=12;
    game_draw(&g,60,0,0,0);
    uint16_t live=((uint16_t*)(uintptr_t)draw_buffer)[260*640+320];
    assert(live!=0x1085); // The HUD must not clear the just-drawn hero.
    g.state=GAME_PAUSED;projection_case="pause";projection_skip=0;game_draw(&g,60,0,0,0);save("reference_game_paused");
    g.state=GAME_PLAY;game_draw(&g,60,0,0,0);assert(((uint16_t*)(uintptr_t)draw_buffer)[260*640+320]==live);
    FILE *atlas=fopen("assets/game/game.rgb565","rb");assert(atlas);static uint8_t golden[GAME_ASSET_BYTES];assert(fread(golden,1,sizeof(golden),atlas)==sizeof(golden));assert(fgetc(atlas)==EOF);fclose(atlas);assert(!memcmp(golden,(void*)(uintptr_t)GAME_ASSET_BASE,sizeof(golden)));
    // Exercise both retired pages through every game state and choice.
    for(uint32_t step=0;step<48;++step){g.state=step%6;g.choice=(step/6)%3;game_draw(&g,60,0,0,0);host_present();}

    g.state=GAME_PLAY;
    g.y=(GAME_ALTAR_Y+60)*256;
    g.upgrade_level[UPGRADE_POWER]=3;
    g.upgrade_level[UPGRADE_RATE]=5;
    g.upgrade_level[UPGRADE_ORBIT]=2;
    g.upgrade_level[UPGRADE_SPEED]=1;
    g.upgrade_level[UPGRADE_MAGNET]=4;
    g.relic=RELIC_ICE;
    for(uint32_t i=5;i<34u;++i)
        g.enemies[i]=(GameEnemy){(uint16_t)((80+i*4)*32),120*32,3,3,(uint8_t)((i-5)%5),0};
    g.enemy_count=34;
    cx=game_camera_x(&g);
    cy=game_camera_y(&g);
    g.crown[0].bolt=(GameBolt){(uint16_t)((cx+470)*32),(uint16_t)((cy+174)*32),-192,0,1,12,0};
    assert(game_near_altar(&g));
    for(uint32_t page=0;page<2u;++page) {
        game_draw(&g,60,0,0,0);
        const uint16_t *pixels=(const uint16_t *)(uintptr_t)draw_buffer;
        const volatile uint16_t *altar=(const volatile uint16_t *)(uintptr_t)GAME_ALTAR_BASE;
        uint32_t visible=0;
        for(uint32_t y=0;y<GAME_ALTAR_SIDE;++y)for(uint32_t x=0;x<GAME_ALTAR_SIDE;++x) {
            uint16_t expected=altar[y*GAME_ALTAR_SIDE+x];
            if(expected && pixels[(152+y)*640u+272+x]==expected)++visible;
        }
        assert(visible>4000u && game_hud_numbers[draw_page()][10]);
        if(!page)save("reference_altar_field");
        host_present();
    }
    game_input(&g,0,16);assert(g.state==GAME_ALTAR);
    for(uint32_t page=0;page<2u;++page) {
        assert(game_draw(&g,60,0,0,0)==0);
        if(!page)save("reference_altar_panel");
        host_present();
    }
    game_input(&g,0,16);assert(g.state==GAME_PLAY);
    for(uint32_t i=0;i<GAME_UPGRADE_COUNT;++i)g.upgrade_level[i]=(uint8_t)game_upgrade_max(i);
    uint16_t level_before=g.level;
    g.xp=g.xp_target;g.spawn_wait=1000;g.attack_wait=1000;
    game_tick(&g,0);
    assert(g.state==GAME_PLAY && g.level==level_before+1u && !g.xp);
    game_draw(&g,60,0,0,0);save("reference_altar_maxed");
    game_input(&g,0,16);assert(g.state==GAME_ALTAR);
    game_draw(&g,60,0,0,0);save("reference_altar_maxed_panel");
    game_input(&g,0,16);

    g.crown[0].bolt.x=(uint16_t)((cx+GAME_X_MAX-GAME_X_MIN-1)*32);
    g.crown[0].bolt.vx=32;
    game_tick(&g,0);
    assert(!g.crown[0].bolt.life);
    game_draw(&g,60,0,0,0);save("reference_altar_bolt_exit");
    g.x=(GAME_ALTAR_X+400)*256;
    game_draw(&g,60,0,0,0);
    assert(!game_hud_numbers[draw_page()][10]);
    assert(((const uint16_t *)(uintptr_t)draw_buffer)[200*640u+320]==GAME_BACKGROUND_COLOR);
    puts("ALTAR UI PASSED: field and HUD on both pages, Enter inspection, resume after max level, and no trails after moving away");

    for(uint32_t choice=0;choice<3u;++choice) {
        game_reset(&g,1);
        g.state=GAME_PLAY;g.ticks=7800;g.level=7;g.kills=142;
        g.x=GAME_CHEST_X*256;g.y=GAME_CHEST_Y*256;
        g.chest_state=CHEST_KEY_HELD;g.spawn_wait=g.attack_wait=900u;
        game_tick(&g,0);
        assert(g.state==GAME_UPGRADE && g.chest_state==CHEST_OFFER);
        for(uint32_t i=0;i<choice;++i)game_input(&g,0,2);
        game_draw(&g,60,0,0,0);
        if(!choice)save("reference_relic_offer");
        game_input(&g,0,16);
        assert(g.state==GAME_PLAY && g.relic==choice+1u && g.chest_state==CHEST_OPEN);
        if(g.relic==RELIC_ICE) {
            game_tick(&g,4);
            for(uint32_t i=0;i<23;++i)game_tick(&g,4);
            for(uint32_t i=0;i<22;++i)game_tick(&g,1);
            game_tick(&g,4);
            assert(g.ticks<g.relic_zones[0].until && g.ticks<g.relic_zones[1].until);
            for(uint32_t i=0;i<15;++i)game_tick(&g,4);
        } else if(g.relic==RELIC_SHIELD) {
            for(uint32_t i=0;i<GAME_SHIELD_PICKUPS;++i)
                g.gems[i]=(GameGem){g.x/256,g.y/256,1,0,0};
            game_tick(&g,0);
            assert(g.relic_charge==GAME_SHIELD_PICKUPS);
            for(uint32_t i=0;i<48;++i)game_tick(&g,4);
        } else {
            for(uint32_t i=0;i<18;++i)game_tick(&g,4);
            g.kills+=GAME_DECOY_KILLS;game_tick(&g,0);
            assert(g.ticks<g.relic_zones[0].until);
            for(uint32_t i=0;i<36;++i)game_tick(&g,4);
        }
        int32_t rx=g.x/256,ry=g.y/256;
        for(uint32_t i=0;i<12;++i) {
            int32_t x=rx+(int32_t)(i*61u%380u)-170;
            int32_t y=ry+(int32_t)(i*47u%250u)-120;
            g.enemies[i]=(GameEnemy){x*32,y*32,6,6,(uint8_t)(i%4u),0};
            g.gems[i]=(GameGem){(int16_t)(x+32),(int16_t)(y+20),1,0,0};
        }
        if(g.relic==RELIC_DECOY) {
            for(uint32_t i=0;i<3u;++i)
                g.enemies[i]=(GameEnemy){(GAME_CHEST_X+30+(int32_t)i*20)*32,
                    (GAME_CHEST_Y-40+(int32_t)i*48)*32,6,6,(uint8_t)i,0};
            for(uint32_t i=0;i<17u;++i)game_tick(&g,0);
        }
        assert(game_draw(&g,60,0,0,0)>20u);
        static const char *const names[]={"reference_relic_ice","reference_relic_shield","reference_relic_decoy"};
        save(names[choice]);
    }

    book_assets_ready=0;book_cache_valid=0;book_closed=0;
    for(uint32_t demo=0;demo<6;++demo){menu_level=1;menu_group=demo/3;menu_item[menu_group]=demo%3;script(16,0,0,0);assert(menu_screen()==demo);}
    menu_level=0;menu_group=2;script(16,0,0,0);assert(menu_screen()==8);
    for(uint32_t n=0;n<65536;++n){assert(*(uint8_t*)(uintptr_t)(ASSET_BASE-65536+n)==0);assert(*(uint8_t*)(uintptr_t)(ASSET_BASE+ASSET_BYTES+n)==0);}
    for(uint32_t v=0;v<4;++v){uint16_t *p=(void*)(uintptr_t)bench_sources[v];for(uint32_t y=0;y<bench_sizes[v];++y)for(uint32_t x=0;x<bench_sizes[v];++x)p[y*bench_sizes[v]+x]=sprite_pixel_sized(bench_sizes[v],y,x);}
    display_enabled=1;bench_prime_framebuffers();assert(display_enabled);save("reference_pressure_entry");
    puts("PASS native reference UI: all 119 interior poses; black pupils retained in poses 88..110; 9 menus; cover; 6 demo routes; total visible sprites / active projectile HUD on both pages, digit erasure, empty/full and late/missed-window MAX60 rejection; both chapter directions; 48 state/choice transitions; pause/resume atlas and hero preserved; pool guards");return 0;
}
''']
view=(ROOT/'software/game_view.h').read_text(encoding='utf-8')
view=re.sub(r'__asm__ volatile\s*\(.*?\);','',view,flags=re.S)
(OUT/'game_view_host.h').write_text(view,encoding='utf-8')
c=OUT/'check.c';c.write_text('\n'.join(parts),encoding='utf-8')
parser=argparse.ArgumentParser();parser.add_argument('--cc',default='S:/Tools/xilinx/Vivado/2018.3/msys64/mingw64/bin/gcc.exe');args=parser.parse_args()
cc=args.cc
env=dict(os.environ);env['PATH']=str(Path(cc).parent)+os.pathsep+env.get('PATH','')
subprocess.run([cc,'-std=c99','-O2','-Isoftware',str(c),'software/survivor_game.c','-o',str(OUT/'check.exe')],cwd=ROOT,env=env,check=True)
r=subprocess.run([str(OUT/'check.exe')],cwd=ROOT,env=env,capture_output=True,text=True)
(ROOT/'reports/reference_ui_check.log').write_text(r.stdout+r.stderr,encoding='utf-8');print(r.stdout+r.stderr);r.check_returncode()
# Run the unmodified production game_loop, game_tick and game_draw together.
# Only IO/time are modeled; timing here tests the counter protocol, not board FPS.
live_out=ROOT/'software/build/live_hud';live_out.mkdir(parents=True,exist_ok=True)
live=c.read_text(encoding='utf-8').split('\nint main(void){',1)[0]
live='#include <stdint.h>\nstatic uint32_t live_video,live_frame,live_started,live_deadline,live_submitted;\nstatic uint32_t live_keys(void);\nstatic void live_present(void);\nstatic uint32_t live_is_bolt(uint32_t source);\n'+live
live=live.replace('return clock_value+=1500000u;','return clock_value+=100u;')
live=live.replace('assert(key_pos<key_count);return keys[key_pos++];','return live_keys();')
live=live.replace('++present_count;return 0;','++present_count;live_present();return 0;')
live=live.replace('static uint32_t reference_mmio_read(uint32_t a){(void)a;return 0;}',
                  'static uint32_t reference_mmio_read(uint32_t a){if(a==SYSTEM_UART_0_IO_CTRL+4u)return uart_space<<16;return a==GFX_BASE+GFX_FRAME_COUNT ? live_video:a==GFX_BASE+GFX_CAPABILITIES ? 7u:0;}')
live=live.replace('"reports/book_%s.ppm"','"software/build/live_hud/%s.ppm"')
live=live.replace('uint16_t key,uint32_t flags){','uint16_t key,uint32_t flags){\n    if(!live_is_bolt(source))++live_submitted;',1)
live=live.replace('#include "game_view_host.h"','#include "game_view_host.h"\nstatic uint32_t live_is_bolt(uint32_t source){return (source>=GAME_BOLT_BASE && source<GAME_BOLT_BASE+1536u) || (source>=GAME_ALTAR_BASE && source<GAME_ZONE_BASE);}')
live_base=live
live+=r'''
static uint32_t last_visible[2],last_visible_hash[2],last_record[2],last_record_hash[2],seen_page[2];
static uint32_t live_changes,live_expected_visible,live_expected_active;
static uint32_t region_hash(const uint16_t *p,uint32_t x,uint32_t y,uint32_t w,uint32_t h) {
    uint32_t value=2166136261u;
    for(uint32_t row=0;row<h;++row)for(uint32_t col=0;col<w;++col)
        value=(value^p[(y+row)*640u+x+col])*16777619u;
    return value;
}
static uint32_t live_keys(void) {
    if(survivor.state==GAME_PAUSED)return 4;
    if(live_frame==126u){survivor.x=(GAME_ALTAR_X+80)*256;return 16;}
    ++live_frame;live_started=1;live_submitted=0;
    uint32_t n=live_frame<=30u ? 1u+live_frame%9u:live_frame<=60u ? 20u:
               live_frame<=90u ? GAME_MAX_BOLTS:live_frame<=120u ? 8u:0u;
    uint32_t off=n<=GAME_MAX_BOLTS-2u ? 2u:0u;
    memset(survivor.bolts,0,sizeof(survivor.bolts));
    memset(survivor.enemies,0,sizeof(survivor.enemies));
    survivor.enemy_count=0;survivor.spawn_wait=60000;
    for(uint32_t i=0;i<n;++i)survivor.bolts[i]=(GameBolt){
        (survivor.x/256-96+(int32_t)(i%32u)*6)*32,
        (survivor.y/256-88+(int32_t)(i/32u)*10)*32,0,0,120,1,0};
    for(uint32_t i=0;i<off;++i)survivor.bolts[n+i]=(GameBolt){64*32,64*32,0,0,120,1,0};
    survivor.bolt_count=(uint16_t)(n+off);survivor.kills=live_frame*7u;
    live_expected_visible=n;live_expected_active=n+off;
    return live_frame==1u ? 16u:0u;
}
static void live_present(void) {
    // Hold TX full through the first 30-frame report, then allow uneven bursts.
    uart_space=live_frame<=40u || live_frame%7u==0 ? 0u:live_frame%5u==0 ? 3u:128u;
    uart_frame_writes=0;
    uint32_t refreshes=live_started && survivor.state==GAME_PLAY && live_frame==45u ? 2u:1u;
    live_video+=refreshes;live_deadline+=refreshes*FRAME_60_CYCLES;clock_value=live_deadline;
    if(!live_started || survivor.state!=GAME_PLAY)return;
    uint32_t p=active_page,expected_record=live_frame<=30u ? 0u:live_frame<=90u ? 11u:GAME_MAX_BOLTS+2u;
    // The fixed synthetic fixture also draws one orb and the hero.
    uint32_t expected_sprites=live_expected_visible+2u;
    assert(game_draw_bolt_count==live_expected_visible);
    assert(live_submitted==2u);
    assert(game_hud_numbers[p][7]==expected_sprites);
    assert(game_hud_numbers[p][8]==live_expected_active);
    assert(game_hud_numbers[p][9]==expected_record);
    assert(game_hud_numbers[p][4]==survivor.kills);
    const uint16_t *front=(void*)(uintptr_t)(p ? FRAMEBUFFER_B:FRAMEBUFFER);
    uint32_t count_hash=region_hash(front,434,54,48,14),record_hash=region_hash(front,350,54,36,14);
    if(seen_page[p] && last_visible[p]!=expected_sprites) {
        assert(count_hash!=last_visible_hash[p]);++live_changes;
    }
    if(seen_page[p] && last_record[p]!=expected_record)assert(record_hash!=last_record_hash[p]);
    seen_page[p]=1;last_visible[p]=expected_sprites;last_visible_hash[p]=count_hash;
    last_record[p]=expected_record;last_record_hash[p]=record_hash;
    if(live_frame==15u || live_frame==31u || live_frame==61u || live_frame==91u || live_frame==126u) {
        char name[64];snprintf(name,sizeof(name),"live_%03u",live_frame);
        uint32_t retired=draw_buffer;draw_buffer=p ? FRAMEBUFFER_B:FRAMEBUFFER;save(name);draw_buffer=retired;
    }
}
static void verify_uart_queue(void) {
    const char normal[]="GAME STATE 4294967295\r\n";
    char long_line[501];
    memset(long_line,'X',500);long_line[500]=0;
    game_log_number("GAME STATE ",UINT32_MAX);game_log_end_line();
    assert(!game_log_text(long_line));game_log_end_line();
    game_log_send();assert(!uart_captured); // Zero credits, even with queued data.
    uart_space=3;game_log_send();assert(!strcmp(uart_capture,"GAM"));
    uart_frame_writes=0;uart_space=128;game_log_send();assert(!strcmp(uart_capture,normal));
    assert(game_log_text(long_line));game_log_end_line(); // Wraps the ring.
    uart_captured=0;uart_capture[0]=0;
    for(unsigned frame=0;frame<16;++frame){
        uart_frame_writes=0;uart_space=128;game_log_send();
    }
    assert(uart_captured==502u && !memcmp(uart_capture,long_line,500));
    assert(!strcmp(uart_capture+500,"\r\n") && game_log.read==game_log.write);
    uart_captured=0;uart_capture[0]=0;uart_space=0;
}
int main(void) {
    verify_uart_queue();
    assert(VirtualAlloc((void*)(uintptr_t)(ASSET_BASE-65536u),ASSET_BYTES+131072u,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    assert(VirtualAlloc((void*)(uintptr_t)(FRAMEBUFFER-65536u),2u*FRAMEBUFFER_BYTES+131072u,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    FILE *f=fopen("assets/ui/magic_book_v5/runtime/reference/ui_stream.bin","rb");assert(f);
    fread(book_native_rom,1,sizeof(book_native_rom),f);fclose(f);
    clock_value=UINT32_MAX-10u*FRAME_60_CYCLES;live_deadline=clock_value;live_video=UINT32_MAX-4u;
    display_enabled=1;game_loop();
    assert(live_frame==126u && live_changes>25u && seen_page[0] && seen_page[1]);
    assert(survivor.state==GAME_EXIT && game_bullet_max60.maximum==GAME_MAX_BOLTS && game_max60.maximum==GAME_MAX_BOLTS+2u);
    assert(strstr(uart_capture,"GAME STATE 1\r\nGAME FPS ") && strstr(uart_capture," BULLET_MAX60 "));
    assert(game_log.read==game_log.write && !strcmp(uart_capture+uart_captured-2,"\r\n"));
    puts("GAME UART PASSED: full FIFO, partial bursts, 32-byte frame cap, ring wrap, whole-line drop, HUD pacing and ordered logs");
    printf("LIVE GAME HUD PASSED: 126 synthetic production-loop frames, %u visible-count pixel updates, both pages; 2..%u total visible sprites; 0..%u projectiles and off-screen counts; total record 0->11->%u; late window rejected; CLINT/video wrap; pause/exit; Chinese layout.\n",live_changes,GAME_MAX_BOLTS+2u,GAME_MAX_BOLTS,GAME_MAX_BOLTS+2u);
    return 0;
}
'''
live_source=live_out/'check.c';live_source.write_text(live,encoding='utf-8')
subprocess.run([cc,'-std=c99','-O2','-Isoftware','-I'+str(OUT),str(live_source),'software/survivor_game.c',
                '-o',str(live_out/'check.exe')],cwd=ROOT,env=env,check=True)
lr=subprocess.run([str(live_out/'check.exe')],cwd=ROOT,env=env,capture_output=True,text=True)
(ROOT/'reports/game_live_hud.log').write_text(lr.stdout+lr.stderr,encoding='utf-8')
print(lr.stdout+lr.stderr);lr.check_returncode()
for path in live_out.glob('live_*.ppm'):
    Image.open(path).save(path.with_suffix('.png'));path.unlink()
live_frames=[Image.open(live_out/f'live_{n:03d}.png').convert('RGB') for n in (15,31,61,91,126)]
live_sample=Image.new('RGB',(640*len(live_frames),480))
for n,im in enumerate(live_frames):live_sample.paste(im,(n*640,0))
live_palette=live_sample.quantize(colors=256,dither=Image.Dither.NONE)
live_indexed=[im.quantize(palette=live_palette,dither=Image.Dither.NONE) for im in live_frames]
live_indexed[0].save(ROOT/'reports/game_live_hud.gif',save_all=True,append_images=live_indexed[1:],
                     duration=[350,350,350,350,700],loop=0,optimize=False)
# A second production-loop run uses only button input. Do not inject enemies,
# gems, projectiles, kills, invulnerability or gameplay timers. Count hardware
# sprite submissions independently at blend_image, plus CPU-drawn projectiles.
natural=live_base.replace('"software/build/live_hud/%s.ppm"','"software/build/live_hud/natural_%s.ppm"')
natural='static unsigned natural_held(void);\n'+natural
natural=natural.replace('return a==GFX_BASE+GFX_FRAME_COUNT ? live_video:a==GFX_BASE+GFX_CAPABILITIES ? 7u:0;',
    'return a==GFX_BASE+GFX_FRAME_COUNT ? live_video:a==GFX_BASE+GFX_BUTTON_HELD ? natural_held():a==GFX_BASE+GFX_CAPABILITIES ? 7u:0;')
natural+=r'''
static uint32_t natural_state=255,natural_window,natural_peak,natural_record;
static uint32_t natural_frames,natural_min=0xffffffffu,natural_max,natural_updates;
static uint32_t natural_empty_bolts,natural_peak_bolts,natural_record_updates;
static uint32_t natural_seen[2],natural_count[2],natural_hash[2],natural_record_value[2],natural_record_hash[2];
static uint32_t region_hash(const uint16_t *p,uint32_t x,uint32_t y,uint32_t w,uint32_t h) {
    uint32_t value=2166136261u;
    for(uint32_t row=0;row<h;++row)for(uint32_t col=0;col<w;++col)
        value=(value^p[(y+row)*640u+x+col])*16777619u;
    return value;
}
static unsigned natural_held(void) {
    static const uint32_t direction[4]={8,2,4,1};
    if(survivor.state==GAME_EXIT)return 0;
    return direction[(live_frame/180u)&3u];
}
static uint32_t live_keys(void) {
    if(survivor.state==GAME_PAUSED)return 4;
    if(live_frame==1900u)return 16;
    ++live_frame;live_started=1;live_submitted=0;
    return survivor.state==GAME_READY || survivor.state==GAME_UPGRADE ? 16u:0u;
}
static void live_present(void) {
    uart_space=live_frame%7u==0 ? 0u:128u;
    uart_frame_writes=0;
    ++live_video;live_deadline+=FRAME_60_CYCLES;clock_value=live_deadline;
    if(!live_started)return;
    if(natural_state!=survivor.state)natural_window=natural_peak=0;
    natural_state=survivor.state;
    if(survivor.state!=GAME_PLAY)return;
    ++natural_frames;
    uint32_t p=active_page,visible=live_submitted+game_draw_bolt_count;
    assert(game_hud_numbers[p][7]==visible);
    assert(game_hud_numbers[p][8]==survivor.bolt_count);
    assert(game_hud_numbers[p][9]==natural_record);
    const uint16_t *front=(void*)(uintptr_t)(p ? FRAMEBUFFER_B:FRAMEBUFFER);
    uint32_t hash=region_hash(front,434,54,48,14),record_hash=region_hash(front,350,54,36,14);
    if(natural_seen[p] && natural_count[p]!=visible) {
        assert(natural_hash[p]!=hash);++natural_updates;
    }
    if(natural_seen[p] && natural_record_value[p]!=natural_record) {
        assert(natural_record_hash[p]!=record_hash);++natural_record_updates;
    }
    natural_seen[p]=1;natural_count[p]=visible;natural_hash[p]=hash;
    natural_record_value[p]=natural_record;natural_record_hash[p]=record_hash;
    if(visible<natural_min)natural_min=visible;
    if(visible>natural_max)natural_max=visible;
    if(!game_draw_bolt_count)++natural_empty_bolts;
    if(game_draw_bolt_count>natural_peak_bolts)natural_peak_bolts=game_draw_bolt_count;
    if(visible>natural_peak)natural_peak=visible;
    if(++natural_window==30u) {
        if(natural_peak>natural_record)natural_record=natural_peak;
        natural_window=natural_peak=0;
    }
    if(natural_frames==60u || natural_frames==900u || natural_frames==1680u || natural_frames==1800u) {
        char name[64];snprintf(name,sizeof(name),"%04u",natural_frames);
        uint32_t retired=draw_buffer;draw_buffer=p ? FRAMEBUFFER_B:FRAMEBUFFER;save(name);draw_buffer=retired;
        printf("NATURAL frame=%u total_sprites=%u HUD_record=%u visible_projectiles=%u active_projectiles=%u kills=%u\n",
               natural_frames,visible,game_hud_numbers[p][9],game_draw_bolt_count,survivor.bolt_count,survivor.kills);
    }
}
int main(void) {
    assert(VirtualAlloc((void*)(uintptr_t)(ASSET_BASE-65536u),ASSET_BYTES+131072u,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    assert(VirtualAlloc((void*)(uintptr_t)(FRAMEBUFFER-65536u),2u*FRAMEBUFFER_BYTES+131072u,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    FILE *f=fopen("assets/ui/magic_book_v5/runtime/reference/ui_stream.bin","rb");assert(f);
    fread(book_native_rom,1,sizeof(book_native_rom),f);fclose(f);
    clock_value=UINT32_MAX-10u*FRAME_60_CYCLES;live_deadline=clock_value;live_video=UINT32_MAX-4u;
    display_enabled=1;game_loop();
    assert(survivor.state==GAME_EXIT && natural_frames>=1800u);
    assert(natural_max>20u && natural_record>20u && natural_max>natural_peak_bolts);
    assert(natural_empty_bolts>100u && natural_updates>100u && natural_record_updates>5u);
    assert(natural_seen[0] && natural_seen[1] && game_max60.maximum==natural_record);
    const char *phase=strstr(uart_capture,"GAME_PHASE LOGIC_US ");
    unsigned logic,floor,sprites,other,read_wait,write_wait;
    int end=0;
    assert(phase && sscanf(phase,"GAME_PHASE LOGIC_US %u FLOOR_US %u SPRITE_US %u OTHER_US %u GFX_RWAIT_US %u GFX_WWAIT_US %u%n",
                          &logic,&floor,&sprites,&other,&read_wait,&write_wait,&end)==6);
    assert(!strncmp(phase+end,"\r\n",2));
    printf("NATURAL GAME HUD PASSED: %u production play frames, total visible %u..%u, MAX60=%u; %u actual count pixel updates, %u record pixel updates on both pages; %u zero-projectile frames, projectile peak %u; only movement/start/upgrade buttons, no object-pool injection. Modeled timing, not board FPS.\n",
           natural_frames,natural_min,natural_max,natural_record,natural_updates,natural_record_updates,natural_empty_bolts,natural_peak_bolts);
    return 0;
}
'''
natural_source=live_out/'natural.c';natural_source.write_text(natural,encoding='utf-8')
subprocess.run([cc,'-std=c99','-O2','-Isoftware','-I'+str(OUT),str(natural_source),'software/survivor_game.c',
                '-o',str(live_out/'natural.exe')],cwd=ROOT,env=env,check=True)
nr=subprocess.run([str(live_out/'natural.exe')],cwd=ROOT,env=env,capture_output=True,text=True)
(ROOT/'reports/game_natural_hud.log').write_text(nr.stdout+nr.stderr,encoding='utf-8')
print(nr.stdout+nr.stderr);nr.check_returncode()
for path in live_out.glob('natural_*.ppm'):
    Image.open(path).save(path.with_suffix('.png'));path.unlink()
html=(ROOT/'assets/ui/magic_book_v5/魔法书交互预览.html').read_text(encoding='utf-8')
pages,_=json.JSONDecoder().raw_decode(html[html.index('const pages=')+12:])
def quantize(im):
    return Image.frombytes('RGB',im.size,bytes(v for r,g,b in im.convert('RGB').getdata() for v in ((r>>3)*255//31,(g>>2)*255//63,(b>>3)*255//31)))
results={}
for ppm in (ROOT/'reports').glob('book_reference_*.ppm'):
    actual=Image.open(ppm).convert('RGB');actual.save(ppm.with_suffix('.png'));name=ppm.stem[len('book_reference_'):]
    key='cover' if name=='cover' else None
    m=re.fullmatch(r'menu_(\d)_(\d)',name)
    if m:key=('home','basic','advanced')[int(m[1])]+'_'+m[2]
    if name=='game_0':key='game_ready'
    if key:
        expected=quantize(Image.open(io.BytesIO(base64.b64decode(pages[key].split(',')[1]))))
        diff=ImageChops.difference(actual,expected)
        if key=='game_ready':
            # The user requested Chinese game titles/badge; only these two
            # regions intentionally depart from the old HTML prototype.
            from PIL import ImageDraw
            mask=ImageDraw.Draw(diff)
            mask.rectangle((220,68,420,86),fill=(0,0,0))
            mask.rectangle((554,13,595,33),fill=(0,0,0))
        count=sum(px!=(0,0,0) for px in diff.getdata());results[key]=count
        diff.save(OUT/(key+'_diff.png'))
    ppm.unlink()
(OUT/'pixel_comparison.json').write_text(json.dumps(results,indent=2)+'\n')
(OUT/'localized_game_regions.json').write_text(json.dumps({
    'game_ready':[[220,68,420,86],[554,13,595,33]],
    'note':'Chinese game heading and hardware badge are intentionally changed; all remaining ready-page pixels and every menu/cover pixel are compared.'
},indent=2)+'\n')
print(json.dumps(results,indent=2))
assert all(v==0 for v in results.values()),'Menu pixels must match the local HTML exactly' 
(ROOT/'sim/ui_command_count.vh').write_text('`define UI_TEST_COMMANDS '+str(struct.unpack('<I',(OUT/'command_count.bin').read_bytes())[0])+'\n',encoding='ascii')
for filename in ('commands','assets','expected',*[p.stem for p in OUT.glob('*_assets.bin')],*[p.stem for p in OUT.glob('*_expected.bin')],*[p.stem for p in OUT.glob('*_metadata.bin')]):
    data=(OUT/(filename+'.bin')).read_bytes();(OUT/(filename+'.hex')).write_text(''.join(f'{v:08x}\n' for v in struct.unpack('<'+'I'*(len(data)//4),data)),encoding='ascii')
