"""Exercise real basic-demo C on mapped DDR with a modeled AXI/APB device.

Pixel comparisons and UI previews are host checks, never board performance data.
Shared drivers are extracted unchanged; the complete production basic module is
included. Both framebuffers and every byte outside the test images are guarded.
"""
from pathlib import Path
import argparse,os,re,struct,subprocess,zlib
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--cc',type=Path,default=Path('C:/mingw64/bin/gcc.exe'))
args=parser.parse_args()
main=(ROOT/'software/main.c').read_text(encoding='utf-8')
def function(name,main=main):
    m=re.search(r'^(?:static\s+)?[a-zA-Z_][^;{\n]*\b'+name+r'\([^;{]*\)\s*\{',main,re.M)
    assert m,name
    depth=0
    for t in re.finditer(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*|[{}]',main[m.end()-1:],re.S):
        if t.group()=='{':depth+=1
        if t.group()=='}':depth-=1
        if not depth:return re.sub(r'__asm__ volatile\s*\(.*?\);','',main[m.start():m.end()-1+t.end()],flags=re.S)
    raise AssertionError(name)

prelude=r'''
#include <windows.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "render.h"
// Relocate the host model before inline helpers expand address macros.
#undef ASSET_BASE
#undef FRAMEBUFFER
#define ASSET_BASE 0x10000000u
#define FRAMEBUFFER 0x11000000u
#include "frame_metrics.h"
#include "basic_demo_data.h"
#include "font5x7.h"
#include "font_cn.h"
#include "demo_controls.h"
#define GAME_ASSET_BASE (ASSET_BASE+0x4000u)
#include "game_frame_bounds.h"
#include "game_assets.h"
#define BENCH_VARIANTS 4u
enum {DEMO_FILL,DEMO_COPY,DEMO_BUFFER,DEMO_KEY,DEMO_ALPHA,DEMO_BENCH};
static const char *const demo_details[] __attribute__((unused))={"","","","","","FPGA ALPHA + COLOR KEY / 60 FPS"};
static const char *const demo_names[]={"矩形填充","图像复制","双缓冲","颜色键","透明混合","SPRITE 压力"};
static uint32_t menu_repaint_pages,menu_level,menu_group,menu_item[2],book_closed;
static uint32_t draw_buffer=FRAMEBUFFER,clock_value,video_epoch,presented_page;
static uint32_t regs[64],ar_count,aw_count,rwait_count,wwait_count,hw_calls,drains;
static uint32_t script[160],script_n,script_pos,report_count,advance_poll_clock;
static uint32_t bar_front_writes,bar_back_writes,same_page_requests,page_changes;
typedef struct {uint32_t x,y,w;char label[96];} Field;
static Field fields[2][128];static uint32_t field_count[2];
static uint32_t draw_page(void){return draw_buffer==FRAMEBUFFER_B;}
static uint32_t cycle_now(void){return clock_value+=3u;}
static void publish_pixels(void){++drains;clock_value+=7u;}
static uint32_t host_read(uint32_t a){
    clock_value+=3u;
    switch(a-GFX_BASE){
    case GFX_STATUS:return GFX_DONE|(presented_page ? GFX_ACTIVE_PAGE:0u);
    case GFX_BURST_READ:return ar_count;
    case GFX_BURST_WRITE:return aw_count;
    case GFX_DDR_RWAIT:return rwait_count;
    case GFX_DDR_WWAIT:return wwait_count;
    case GFX_FRAME_COUNT:return video_epoch;
    default:return 0;
    }
}
static void host_write(uint32_t a,uint32_t v){assert(a>=GFX_BASE && (a-GFX_BASE)/4u<64);regs[(a-GFX_BASE)/4u]=v;clock_value+=3u;}
static int wait_render(void){
    uint32_t dst=regs[GFX_DST/4],w=regs[GFX_WIDTH/4],h=regs[GFX_HEIGHT/4],src=regs[GFX_SRC/4];
    assert(dst>=draw_buffer && dst+(h-1u)*1280u+w*2u<=draw_buffer+FRAMEBUFFER_BYTES);
    assert(regs[GFX_STRIDE/4]==1280 && regs[GFX_DRAW_PAGE/4]==draw_page());
    if(dst==draw_buffer && w==640u && h==480u)field_count[draw_page()]=0;
    for(uint32_t y=0;y<h;++y){
        if(regs[GFX_OPERATION/4]==0){
            uint16_t *d=(uint16_t*)(uintptr_t)(dst+y*1280u);
            for(uint32_t x=0;x<w;++x)d[x]=(uint16_t)regs[GFX_COLOR/4];
        }else if(regs[GFX_OPERATION/4]==1){
            memcpy((void*)(uintptr_t)(dst+y*1280u),(void*)(uintptr_t)(src+y*regs[GFX_SRC_STRIDE/4]),w*2u);
            ar_count+=(w*2u+63u)/64u;
        }else{
            assert(regs[GFX_OPERATION/4]==2);
            uint16_t *d=(void*)(uintptr_t)(dst+y*1280u);
            const uint16_t *s=(void*)(uintptr_t)(src+y*regs[GFX_SRC_STRIDE/4]);
            for(uint32_t x=0;x<w;++x){
                uint32_t f=s[x],b=d[x],a=regs[GFX_ALPHA/4],flags=regs[GFX_BLEND_CTRL/4];
                if((flags&GFX_BLEND_KEY) && f==regs[GFX_COLOR_KEY/4])continue;
                if(flags&GFX_BLEND_ALPHA){
                    uint32_t r=(((f>>11)&31)*a+((b>>11)&31)*(255-a)+127)/255;
                    uint32_t g=(((f>>5)&63)*a+((b>>5)&63)*(255-a)+127)/255;
                    uint32_t bl=((f&31)*a+(b&31)*(255-a)+127)/255;
                    d[x]=(uint16_t)((r<<11)|(g<<5)|bl);
                }else d[x]=(uint16_t)f;
            }
            ar_count+=2u*(w*2u+63u)/64u;
        }
        aw_count+=(w*2u+63u)/64u;
    }
    if(w==24u && h==208u && regs[GFX_OPERATION/4]==0u){
        if(draw_page()==presented_page)++bar_front_writes;else ++bar_back_writes;
    }
    ++hw_calls;rwait_count+=11u;wwait_count+=13u;clock_value+=1000u;return 0;
}
#define mmio_read host_read
#define mmio_write host_write
static int host_present(void){
    if(presented_page==draw_page())++same_page_requests;else ++page_changes;
    presented_page=draw_page();draw_buffer=presented_page ? FRAMEBUFFER : FRAMEBUFFER_B;
    clock_value+=FRAME_60_CYCLES;++video_epoch;return 0;
}
#define present_frame host_present
static void fail(const char *s){puts(s);abort();}
static void puts_uart(const char *s){(void)s;}
static void uart_number(const char *s,uint32_t v){(void)v;if(!strcmp(s,"BASIC "))++report_count;}
static uint32_t button_event(void){if(advance_poll_clock)clock_value+=FRAME_60_CYCLES;return script_pos<script_n ? script[script_pos++] : 4u;}
static void draw_player(uint32_t f,uint32_t x,uint32_t y,uint32_t hw){(void)f;(void)x;(void)y;(void)hw;}
static void note_text(uint32_t x,uint32_t y,const char *s,uint32_t width){
    const char *p=s;uint32_t used=0,page=draw_page();
    while(*p){uint32_t cp=font_cn_utf8_next(&p);used+=font_cn_find(cp)?14u:12u;}
    if(used>width){fprintf(stderr,"CLIPPED %s at %u,%u width %u requires %u\n",s,x,y,width,used);exit(2);}
    assert(y+14u<=480u && x+used<=640u && field_count[page]<128);
    for(uint32_t i=0;i<field_count[page];++i){Field *f=&fields[page][i];
        if(x<f->x+f->w && x+used>f->x && y<f->y+14u && y+14u>f->y){
            fprintf(stderr,"OVERLAP %s at %u,%u with %s at %u,%u\n",s,x,y,f->label,f->x,f->y);exit(3);
        }
    }
    Field *f=&fields[page][field_count[page]++];*f=(Field){x,y,used,{0}};snprintf(f->label,sizeof(f->label),"%s",s);
}
static void cpu_fill(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c);
'''
parts=[prelude]
for name in ('select_draw_page','wait_display_page','fill_rect','copy_image','blend_image'):
    parts.append(function(name))
body=function('cpu_fill').replace('cpu_fill(','cpu_fill_impl(',1)
parts.append(body)
parts.append(r'''
static void cpu_fill(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c){
    assert(x+w<=640 && y+h<=480);
    // Erasing an entire numeric field removes its previous text record.
    if(h==14u && w>=24u){uint32_t p=draw_page();
        for(uint32_t i=0;i<field_count[p];){Field *f=&fields[p][i];
            if(f->x>=x && f->x+f->w<=x+w && f->y>=y && f->y+14u<=y+h)
                fields[p][i]=fields[p][--field_count[p]];
            else ++i;
        }
    }
    cpu_fill_impl(x,y,w,h,c);clock_value+=w*h/2u+1u;
}
static void paint(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c,uint32_t hw){
    if(!x && !y && w==640 && h==480)field_count[draw_page()]=0;
    if(hw){if(fill_rect(x,y,w,h,c))fail("host fill failed");}else cpu_fill(x,y,w,h,c);
}
// Actual book drawing/DDR/transition checks live in check_book_menu.py.
static void book_init_assets(void){}
static void book_menu_frame(void){paint(0,0,640,480,0x0843,1);}
static void book_cover(void){book_menu_frame();}
static void book_animate(uint32_t closing){(void)closing;}
static void book_turn(void){}
''')
for name in ('font_column','text_at_width','text_at','decimal','number_at','decimal_field','number_field_at','alpha_value','blend_rgb565','bench_next_size','menu_screen'):
    body=function(name)
    if name=='text_at_width':body=body.replace('uint32_t right=x+width;','uint32_t right=x+width;note_text(x,y,s,width);')
    parts.append(body)
book=(ROOT/'software/book_menu.h').read_text(encoding='utf-8')
parts.append('#include "reference_ui_assets.h"')
parts.append('#define BOOK_GOLD 0xac2au\n#define BOOK_EDGE 0xc52fu')
parts.append('static uint8_t copy_rom[32768];\nstatic uint32_t book_cache_valid;\n'
             'static uint8_t book_stream_byte(uint32_t at){assert(at<sizeof(copy_rom));return copy_rom[at];}')
parts.append(function('book_unpack',book))
for name in ('book_pixels','book_stamp','book_text_width','book_text'):
    parts.append(function(name,book))
parts.append('#include "demo_skin.h"')
parts.append('#include "basic_demo.h"')
parts.append(function('game_decode_runs',(ROOT/'software/game_view.h').read_text(encoding='utf-8')))
parts.append('#include "effects_demo.h"')
parts.append(r'''
static void save_ui(const char *name){
    char path[180];
    if(!strncmp(name,"key_walk_",9))snprintf(path,sizeof(path),"software/build/basic_host/key_frames/%s.ppm",name);
    else snprintf(path,sizeof(path),"reports/basic_%s.ppm",name);
    FILE *f=fopen(path,"wb");assert(f);fprintf(f,"P6\n640 480\n255\n");
    const uint16_t *p=(void*)(uintptr_t)(presented_page ? FRAMEBUFFER_B:FRAMEBUFFER);
    for(uint32_t i=0;i<640u*480u;++i){uint16_t c=p[i];fputc((c>>11)*255/31,f);fputc(((c>>5)&63)*255/63,f);fputc((c&31)*255/31,f);}fclose(f);
}
static void clear_host(void){field_count[0]=field_count[1]=0;basic_field_valid[0]=basic_field_valid[1]=0;basic_number_valid[0]=basic_number_valid[1]=0;}
int main(void){
    assert(VirtualAlloc((void*)(uintptr_t)ASSET_BASE,ASSET_BYTES,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==(void*)(uintptr_t)ASSET_BASE);
    assert(VirtualAlloc((void*)(uintptr_t)FRAMEBUFFER,2*FRAMEBUFFER_BYTES,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==(void*)(uintptr_t)FRAMEBUFFER);
    unsigned char *fb=(void*)(uintptr_t)FRAMEBUFFER,*assets=(void*)(uintptr_t)ASSET_BASE;
    FILE *rom=fopen("assets/ui/magic_book_v5/runtime/reference/ui_stream.bin","rb");assert(rom);
    assert(fread(copy_rom,1,sizeof(copy_rom),rom)>=(size_t)basic_copy_stream[1][0]+basic_copy_stream[1][1]);fclose(rom);
    memset(assets,0xa5,ASSET_BYTES);book_cache_valid=1;basic_init_images();assert(!book_cache_valid);
    unsigned char *snapshot=malloc(2u*BASIC_IMAGE_BYTES),*expected=malloc(2u*FRAMEBUFFER_BYTES);assert(snapshot && expected);
    memcpy(snapshot,(void*)(uintptr_t)BASIC_IMAGE_BASE,2u*BASIC_IMAGE_BYTES);
    for(uint32_t i=0;i<BASIC_IMAGE_BASE-ASSET_BASE;++i)
        if(i<BOOK_SCRATCH_BASE-ASSET_BASE || i>=BOOK_SCRATCH_BASE-ASSET_BASE+BASIC_COPY_INDEX_BYTES+32u)assert(assets[i]==0xa5);
    for(uint32_t i=BASIC_IMAGE_BASE-ASSET_BASE+2u*BASIC_IMAGE_BYTES;i<ASSET_BYTES;++i)assert(assets[i]==0xa5);
    assert(memcmp(snapshot,snapshot+BASIC_IMAGE_BYTES,BASIC_IMAGE_BYTES));
    FILE *decoded=fopen("software/build/basic_host/copy_surfaces.rgb565","wb");assert(decoded);
    assert(fwrite(snapshot,1,2u*BASIC_IMAGE_BYTES,decoded)==2u*BASIC_IMAGE_BYTES);fclose(decoded);
    uint32_t copy_cases=0,fill_cases=0;
    for(uint32_t image=0;image<2;++image)for(uint32_t page=0;page<2;++page)
    for(uint32_t load=0;load<4;++load)for(uint32_t hw=0;hw<2;++hw){
        basic_config=(BasicConfig){load,image,0,0,0,0,0,0};draw_buffer=FRAMEBUFFER+page*FRAMEBUFFER_BYTES;
        memset(fb,0x5a,2u*FRAMEBUFFER_BYTES);memset(expected,0x5a,2u*FRAMEBUFFER_BYTES);
        for(uint32_t y=0;y<192;++y)memcpy(expected+page*FRAMEBUFFER_BYTES+(176u+y)*1280u+704u,snapshot+image*BASIC_IMAGE_BYTES+y*512u,512u);
        BasicSample s;drains=hw_calls=0;ar_count=aw_count=UINT32_MAX-100u;clock_value=UINT32_MAX-500u;
        uint32_t cycles=basic_batch(DEMO_COPY,hw,0,&s);
        assert(drains==2u && cycles>0u && hw_calls==(hw ? basic_copy_counts[load]:0u));
        assert(s.reads==(hw ? basic_copy_counts[load]*1536u:0u) && s.writes==s.reads);
        assert(!memcmp(fb,expected,2u*FRAMEBUFFER_BYTES));assert(!memcmp(snapshot,(void*)(uintptr_t)BASIC_IMAGE_BASE,2u*BASIC_IMAGE_BYTES));++copy_cases;
    }
    for(uint32_t view=0;view<2;++view)for(uint32_t page=0;page<2;++page)
    for(uint32_t load=0;load<4;++load)for(uint32_t hw=0;hw<2;++hw){
        basic_config=(BasicConfig){load,0,3,view,0,0,0,0};draw_buffer=FRAMEBUFFER+page*FRAMEBUFFER_BYTES;
        memset(fb,0x5a,2u*FRAMEBUFFER_BYTES);memset(expected,0x5a,2u*FRAMEBUFFER_BYTES);
        for(uint32_t n=0;n<basic_fill_counts[load];++n){BasicRect r=basic_task_rect(97,n);
            assert(r.x>=16 && r.x+r.w<=624 && r.y>=176 && r.y+r.h<=400 && !(r.x&1u));
            if(view)assert(r.x>=352 && r.x+r.w<=608 && r.y+r.h<=368);
            for(uint32_t y=0;y<r.h;++y)for(uint32_t x=0;x<r.w;++x)
                *(uint16_t*)(expected+page*FRAMEBUFFER_BYTES+(r.y+y)*1280u+(r.x+x)*2u)=r.color;
        }
        BasicSample s;drains=hw_calls=0;(void)basic_batch(DEMO_FILL,hw,97,&s);
        assert(drains==2 && hw_calls==(hw ? basic_fill_counts[load]:0u) && !s.reads);
        assert(!memcmp(fb,expected,2u*FRAMEBUFFER_BYTES));++fill_cases;
    }
    BasicConfig c={0};for(uint32_t i=0;i<4;++i){assert(basic_control(&c,0,1));assert(c.load==(i+1u)%4u);}
    for(uint32_t i=0;i<4;++i){assert(basic_control(&c,1,2));assert(c.mode==((i+1u)&1u));}
    assert(basic_control(&c,1,8) && c.image==1);assert(basic_control(&c,1,16) && c.view==1);
    BasicConfig before=c;assert(!basic_control(&c,1,3) && !memcmp(&c,&before,sizeof(c)));
    assert(basic_control(&c,2,16) && c.paused);assert(basic_control(&c,2,8) && c.grid);
    const uint32_t values[]={0,1,100,9999,UINT32_MAX-1u,UINT32_MAX};
    for(uint32_t i=0;i<6;++i)for(uint32_t j=0;j<6;++j){
        uint64_t ref=values[j] ? (uint64_t)values[i]*100u/values[j]:0;
        assert(basic_ratio100(values[i],values[j])==(ref>999999u?999999u:ref));
    }
    for(uint32_t id=BOOK_ICON_BASIC;id<=BOOK_ICON_PRESSURE;++id){
        static const char *const names[]={"basic","advanced","game","fill","copy","buffer","key","alpha","pressure"};
        char path[200];snprintf(path,sizeof(path),"assets/ui/magic_book_v5/runtime/reference/icon_%s.rgb565",names[id-BOOK_ICON_BASIC]);
        FILE *art=fopen(path,"rb");assert(art);assert(fread((void*)(uintptr_t)(ASSET_BASE+book_resources[id].base),1,2048,art)==2048);fclose(art);
    }
    // Layout previews use explicit synthetic samples; they are not benchmarks.
    for(uint32_t demo=0;demo<3;++demo)for(uint32_t view=0;view<(demo==2?1u:2u);++view)
    for(uint32_t image=0;image<(demo==1?2u:1u);++image)for(uint32_t hw=0;hw<(demo==2?1u:2u);++hw){
        clear_host();basic_config=(BasicConfig){0,image,0,view,0,1,0,1};basic_prime(demo);
        basic_samples[0]=(BasicSample){30,600000,12000,0,0,0,0,1};
        basic_samples[1]=(BasicSample){60,150000,2000,1536,1536,110,130,1};
        if(demo==2)basic_buffer_scene(17);else{
            if(demo==0)paint(view?352:16,176,view?256:608,view?192:224,0x0843,hw);
            BasicSample s;(void)basic_batch(demo,hw,17,&s);
        }
        basic_completed_frame=17;basic_hud(demo,hw);host_present();
        if(demo!=DEMO_BUFFER && view)for(uint32_t i=0;i<field_count[presented_page];++i)
            assert(strcmp(fields[presented_page][i].label,"DST"));
        char name[80];snprintf(name,sizeof(name),"demo%u_view%u_image%u_path%u",demo,view,image,hw);save_ui(name);
    }
    // Reference-layout fixtures use the real page code with no valid samples.
    for(uint32_t demo=0;demo<3u;++demo)for(uint32_t view=0;view<2u;++view)for(uint32_t variant=0;variant<2u;++variant){
        clear_host();draw_buffer=FRAMEBUFFER;
        basic_config=(BasicConfig){0,demo==1u ? variant:0,0,demo<2u ? view:0,demo==2u ? view:0,0,demo==2u ? variant:0,1};
        basic_reset_sample(&basic_samples[0]);basic_reset_sample(&basic_samples[1]);
        basic_swaps=basic_missed=basic_swap_us=basic_video_hz=0;
        basic_prime(demo);basic_hud(demo,1);
        if(demo==DEMO_FILL)paint(view ? 352u:16u,176,view ? 256u:608u,view ? 192u:224u,0x0843,1);
        if(demo!=DEMO_BUFFER){BasicSample r;(void)basic_batch(demo,1,0,&r);}
        host_present();char name[100];snprintf(name,sizeof(name),"reference_%u_%u_%u",demo,view,variant);save_ui(name);
    }
    // Real event loop: no automatic switching; manual mode/reset/exit paths.
    for(uint32_t demo=0;demo<3;++demo){
        clear_host();memset(script,0,sizeof(script));script_n=85;script_pos=report_count=0;
        script[62]=1;script[65]=8;script[68]=16;script[71]=2;script[74]=2;script[77]=2;script[84]=4;
        basic_demo_loop(demo);assert(script_pos==85);
        if(demo!=2)assert(report_count>=2 && basic_config.mode==1 && basic_config.load==1);
        else assert(basic_config.paused && !basic_config.grid && basic_config.speed==1 && basic_config.mode==1);
    }
    // The erased field must accept UINT32_MAX as real data after an invalid sample.
    clear_host();draw_buffer=FRAMEBUFFER;basic_field(0,16,16,120,UINT32_MAX,0,0);basic_field(0,16,16,120,UINT32_MAX,1,0);
    assert(basic_number_valid[0]&1u);
    // More than two old auto-switch windows must still render CPU only.
    for(uint32_t demo=0;demo<2;++demo){
        clear_host();memset(script,0,sizeof(script));script_n=71;script_pos=0;script[70]=4;
        basic_demo_loop(demo);assert(basic_config.mode==0 && basic_samples[0].valid && !basic_samples[1].valid);
    }
    // Both pages of the paused motion scene have the exact same background.
    clear_host();basic_config=(BasicConfig){0,0,0,0,1,1,0,1};draw_buffer=FRAMEBUFFER;basic_buffer_scene(23);
    memcpy(expected,fb,FRAMEBUFFER_BYTES);draw_buffer=FRAMEBUFFER_B;basic_buffer_scene(23);
    for(uint32_t y=176;y<400;++y)assert(!memcmp(expected+y*1280u+32u,fb+FRAMEBUFFER_BYTES+y*1280u+32u,1216));
    // Independent full viewport reference catches erase trails, overlapping old
    // and new bars, both bounce ends, grid restoration and per-page history.
    for(uint32_t speed=0;speed<3u;++speed)for(uint32_t grid=0;grid<2u;++grid){
        clear_host();basic_config=(BasicConfig){0,0,0,0,0,speed,0,grid};
        basic_scene_valid[0]=basic_scene_valid[1]=0;memset(fb,0x5a,2u*FRAMEBUFFER_BYTES);
        const uint32_t phases[]={0,1,2,11,12,23,24,70,71,72};
        for(uint32_t n=0;n<10u;++n)for(uint32_t p=0;p<2u;++p){
            draw_buffer=FRAMEBUFFER+p*FRAMEBUFFER_BYTES;basic_buffer_scene(phases[n]);
            uint32_t phase=(phases[n]*(8u<<speed))%720u,left=24u+(phase>360u?720u-phase:phase);
            for(uint32_t y=0;y<480u;++y)for(uint32_t x=0;x<640u;++x){
                uint16_t ref=0x5a5a;
                if(x>=16u && x<624u && y>=176u && y<400u){
                    ref=grid && y>=200u && (y-200u)%40u<2u ? 0x7bef:0x084b;
                    if(y>=184u && y<392u)for(uint32_t bar=0;bar<3u;++bar)
                        if(x>=left+96u*bar && x<left+96u*bar+24u)ref=0xffff;
                }
                assert(*(const uint16_t*)(uintptr_t)(draw_buffer+y*1280u+x*2u)==ref);
            }
        }
    }
    // Default single-buffer mode stays manual for 70 frames. Only live-page
    // writes can demonstrate tearing; all setup redraws remain on the back.
    clear_host();memset(script,0,sizeof(script));script_n=71;script_pos=0;script[70]=4;
    bar_front_writes=bar_back_writes=same_page_requests=page_changes=0;
    basic_demo_loop(DEMO_BUFFER);
    uint32_t expected_moves=0,last_x=0;
    for(uint32_t n=1;n<=70u;++n){uint32_t phase=(n*8u)%720u,x=phase>360u?720u-phase:phase;
        if(x!=last_x)++expected_moves;
        last_x=x;}
    assert(!basic_config.mode && basic_config.speed==0u && !basic_swaps && bar_front_writes==expected_moves*6u && bar_back_writes==6u);
    assert(same_page_requests==70u && page_changes==2u);
    // Each explicit S toggles exactly once; ordinary frames never toggle mode.
    for(uint32_t toggles=1; toggles<=4u; ++toggles){
        clear_host();memset(script,0,sizeof(script));script_pos=0;script_n=2u*toggles+3u;
        for(uint32_t n=0;n<toggles;++n)script[2u*n+1u]=2u;
        script[script_n-1u]=4u;bar_front_writes=bar_back_writes=0;
        basic_demo_loop(DEMO_BUFFER);assert(basic_config.mode==(toggles&1u));
        assert(bar_front_writes>=6u && bar_back_writes>=6u);
        assert(basic_swaps==((toggles&1u) ? 3u:0u));
        // Exercise the real exit helper from both resulting modes.
        basic_return_to_menu();assert(draw_page()!=presented_page && menu_repaint_pages==2u);
        script_n=1;script_pos=0;script[0]=16;menu_level=1;menu_group=0;menu_item[0]=0;
        assert(menu_screen()==0 && !menu_repaint_pages && !memcmp(fb,fb+FRAMEBUFFER_BYTES,FRAMEBUFFER_BYTES));

    }
    // Pause freezes bars; same-page boundary pacing still runs.
    clear_host();memset(script,0,sizeof(script));script_n=73;script_pos=0;
    script[1]=16u;script[72]=4u;bar_front_writes=bar_back_writes=0;
    basic_demo_loop(DEMO_BUFFER);assert(basic_config.paused && !basic_config.mode);
    assert(bar_front_writes==12u && bar_back_writes==6u);
    // Layout previews show mode labels, not a fabricated torn frame. The
    // independent pixel-clock RTL test captures the actual tear separately.
    for(uint32_t mode=0;mode<2u;++mode){
        clear_host();basic_config=(BasicConfig){0,0,0,0,mode,1,0,1};
        basic_buffer_target(1);basic_prime(DEMO_BUFFER);
        for(uint32_t p=0;p<2u;++p)for(uint32_t i=0;i<field_count[p];++i){
            assert(!strstr(fields[p][i].label,"A页") && !strstr(fields[p][i].label,"B页"));
        }
        basic_buffer_scene(17u);basic_completed_frame=17u;basic_hud(DEMO_BUFFER,1);
        host_present();save_ui(mode ? "buffer_protected":"buffer_tearing");
    }
    // Resynchronize to actual front state and prime two identical menu pages.
    clear_host();presented_page=1;draw_buffer=FRAMEBUFFER_B;basic_return_to_menu();
    assert(draw_buffer==FRAMEBUFFER && menu_repaint_pages==2 && regs[GFX_DRAW_PAGE/4]==0);
    script_n=1;script_pos=0;script[0]=16;menu_level=1;menu_group=0;menu_item[0]=0;
    assert(menu_screen()==0 && !menu_repaint_pages);
    assert(!memcmp(fb,fb+FRAMEBUFFER_BYTES,FRAMEBUFFER_BYTES));
    // Hardware-only effect pages use new DDR assets without changing the game
    // pool, the existing basic images or any byte outside their 64KiB range.
    unsigned char *asset_before=malloc(ASSET_BYTES);assert(asset_before);memcpy(asset_before,assets,ASSET_BYTES);
    effects_init_assets();
    assert(!memcmp(asset_before,assets,EFFECT_BASE-ASSET_BASE));
    assert(!memcmp(asset_before+EFFECT_BASE-ASSET_BASE+2u*EFFECT_BYTES,assets+EFFECT_BASE-ASSET_BASE+2u*EFFECT_BYTES,
        ASSET_BYTES-(EFFECT_BASE-ASSET_BASE+2u*EFFECT_BYTES)));
    uint32_t effect_cases=0;
    for(uint32_t demo=DEMO_ALPHA;demo<=DEMO_ALPHA;++demo)
    for(uint32_t page=0;page<2;++page)for(uint32_t bg=0;bg<2;++bg)
    for(uint32_t variant=0;variant<(demo==DEMO_ALPHA ? 256u:4u);++variant){
        EffectsConfig ec={demo==DEMO_ALPHA ? variant:128u,demo==DEMO_KEY ? variant/2u:0u,variant&1u,bg};
        clear_host();draw_buffer=FRAMEBUFFER+page*FRAMEBUFFER_BYTES;
        effects_draw_scene(demo,&ec);assert(effects_verify(demo,&ec)==8);
        for(uint32_t y=0;y<128u;++y)for(uint32_t x=0;x<128u;++x){
            uint16_t foreground=*(const uint16_t*)(uintptr_t)(EFFECT_BASE+ec.key_index*EFFECT_BYTES+y*256u+x*2u);
            uint32_t cell=(((x+56u)/16u)^((y+32u)/16u))&1u;
            uint32_t background=bg ? (cell ? 0x7befu:0x2945u):(cell ? 0x0514u:0xfca0u),expected_pixel;
            if(demo==DEMO_KEY)expected_pixel=ec.enabled && foreground==(ec.key_index ? 0xf81fu:0u) ? background:foreground;
            else{
                uint32_t a=255u-ec.transparency;
                uint32_t r=(((foreground>>11)&31u)*a+((background>>11)&31u)*(255u-a)+127u)/255u;
                uint32_t g=(((foreground>>5)&63u)*a+((background>>5)&63u)*(255u-a)+127u)/255u;
                uint32_t b=((foreground&31u)*a+(background&31u)*(255u-a)+127u)/255u;
                expected_pixel=(r<<11)|(g<<5)|b;
            }
            assert(*(const uint16_t*)(uintptr_t)(draw_buffer+(224u+y)*1280u+(408u+x)*2u)==expected_pixel);
            assert(*(const uint16_t*)(uintptr_t)(draw_buffer+(224u+y)*1280u+(104u+x)*2u)==foreground);
        }
        ++effect_cases;
    }
    assert(effect_cases==1024u);
    uint16_t walk_reference[4096];
    FILE *walk=fopen("assets/game/game.rgb565","rb");assert(walk);
    assert(fread(walk_reference,2,4096,walk)==4096);fclose(walk);
    effects_init_key_assets();
    for(uint32_t key=0;key<2;++key)for(uint32_t frame=0;frame<4;++frame)
    for(uint32_t y=0;y<64;++y)for(uint32_t x=0;x<64;++x) {
        uint16_t expected=walk_reference[frame*1024u+(y/2u)*32u+x/2u];
        if(!expected)expected=effects_key(key);else if(expected==effects_key(key))expected^=1u;
        assert(*(uint16_t*)(uintptr_t)(effects_walk_source(key,frame)+y*128u+x*2u)==expected);
    }
    assert(!memcmp(asset_before,assets,EFFECT_BASE-ASSET_BASE));
    assert(!memcmp(asset_before+EFFECT_BASE-ASSET_BASE+2u*EFFECT_BYTES,assets+EFFECT_BASE-ASSET_BASE+2u*EFFECT_BYTES,
        ASSET_BYTES-(EFFECT_BASE-ASSET_BASE+2u*EFFECT_BYTES)));
    const uint32_t poses[]={0,1,2,3,4,5,6,7,32,63,64,UINT32_MAX,0};
    uint32_t key_cases=0;
    for(uint32_t page=0;page<2;++page)for(uint32_t bg=0;bg<2;++bg)
    for(uint32_t key=0;key<2;++key)for(uint32_t enabled=0;enabled<2;++enabled) {
        clear_host();draw_buffer=FRAMEBUFFER+page*FRAMEBUFFER_BYTES;
        effects_key_valid[0]=effects_key_valid[1]=0;
        EffectsConfig key_config={128u,key,enabled,bg};
        for(uint32_t step=0;step<sizeof(poses)/sizeof(poses[0]);++step) {
            effects_tick=poses[step];effects_draw_scene(DEMO_KEY,&key_config);
            assert(effects_verify(DEMO_KEY,&key_config)==8);
            uint32_t position=88u;
            for(uint32_t panel=0;panel<2;++panel)
            for(uint32_t y=0;y<192;++y)for(uint32_t x=0;x<240;++x) {
                uint32_t cell=((x/16u)^(y/16u))&1u;
                uint16_t expected=bg ? (cell ? 0x7befu:0x2945u):(cell ? 0x0514u:0xfca0u);
                if(x>=position && x<position+64u && y>=64u && y<128u) {
                    uint16_t fg=walk_reference[(effects_tick&3u)*1024u+((y-64u)/2u)*32u+(x-position)/2u];
                    if(!fg)fg=effects_key(key);else if(fg==effects_key(key))fg^=1u;
                    if(!panel || !enabled || fg!=effects_key(key))expected=fg;
                }
                assert(*(uint16_t*)(uintptr_t)(draw_buffer+(192u+y)*1280u+(48u+panel*304u+x)*2u)==expected);
            }
            ++key_cases;
        }
    }
    assert(key_cases==208u);
    EffectsConfig ec={128u,0,1,0};clear_host();draw_buffer=FRAMEBUFFER;
    effects_draw_scene(DEMO_ALPHA,&ec);
    volatile uint16_t *probe=(void*)(uintptr_t)(draw_buffer+224u*1280u+408u*2u);
    *probe^=1u;assert(effects_verify(DEMO_ALPHA,&ec)==7);*probe^=1u;
    for(uint32_t demo=DEMO_KEY;demo<=DEMO_ALPHA;++demo)
    for(uint32_t bg=0;bg<2;++bg)for(uint32_t v=0;v<(demo==DEMO_ALPHA ? 3u:4u);++v){
        clear_host();draw_buffer=FRAMEBUFFER;
        ec=(EffectsConfig){demo==DEMO_ALPHA ? (v==0 ? 0u:v==1 ? 128u:255u):128u,demo==DEMO_KEY ? v/2u:0u,v&1u,bg};
        demo_skin(demo,"FPGA");demo_window(48,192,240,192);demo_window(352,192,240,192);
        effects_key_valid[0]=effects_key_valid[1]=0;
        effects_draw_scene(demo,&ec);effects_labels(demo,&ec,effects_verify(demo,&ec));host_present();
        char name[80];snprintf(name,sizeof(name),"effects_demo%u_bg%u_variant%u",demo,bg,v);save_ui(name);
    }
    for(uint32_t demo=DEMO_KEY;demo<=DEMO_ALPHA;++demo){
        clear_host();report_count=script_pos=0;
        if(demo==DEMO_ALPHA){script[0]=8;script[1]=1;script[2]=16;script[3]=16;script[4]=2;script[5]=4;script_n=6;}
        else{script[0]=1;script[1]=8;script[2]=2;script[3]=1;script[4]=4;script_n=5;}
        effects_demo_loop(demo);assert(script_pos==script_n && !report_count);
        assert(regs[GFX_OPERATION/4]==2 && regs[GFX_BLEND_CTRL/4]==(demo==DEMO_ALPHA ? GFX_BLEND_ALPHA:GFX_BLEND_KEY));
        if(demo==DEMO_ALPHA)assert(regs[GFX_ALPHA/4]==127);
        else assert(regs[GFX_COLOR_KEY/4]==0xf81fu);
    }
    // Capture two complete stationary walk cycles from actual production C.
    // These previews illustrate animation, not measured board FPS.
    EffectsConfig preview={128u,1u,1u,0u};effects_tick=effects_key_paused=0;
    clear_host();effects_redraw(DEMO_KEY,&preview);
    for(uint32_t frame=0;frame<8u;++frame) {
        effects_tick=frame;effects_draw_key(&preview);
        effects_check_label(effects_verify(DEMO_KEY,&preview));host_present();
        char name[64];snprintf(name,sizeof(name),"key_walk_%03u",frame);save_ui(name);
    }
    clear_host();script_pos=0;script_n=1;script[0]=4;effects_demo_loop(DEMO_ALPHA);
    assert(regs[GFX_ALPHA/4]==0 && effects_verify(DEMO_ALPHA,&(EffectsConfig){255u,0u,1u,0u})==8);
    // Advance idle polls through a cycle-counter wrap. The actual production
    // loop must animate, pause, resume, toggle the key/background and return.
    clear_host();clock_value=UINT32_MAX-2u*EFFECT_WALK_PERIOD;script_pos=0;script_n=80;
    for(uint32_t n=0;n<script_n;++n)script[n]=0;
    script[20]=16;script[35]=16;script[45]=8;script[55]=1;script[65]=2;script[79]=4;
    advance_poll_clock=1;effects_demo_loop(DEMO_KEY);advance_poll_clock=0;
    assert(effects_tick>4 && !effects_key_paused && script_pos==script_n);
    uint32_t retired=draw_buffer;draw_buffer=FRAMEBUFFER+presented_page*FRAMEBUFFER_BYTES;
    assert(effects_verify(DEMO_KEY,&(EffectsConfig){128u,1u,0u,1u})==8);
    draw_buffer=retired;
    effects_init_assets();assert(effects_assets_ready==1);
    assert(*(uint16_t*)(uintptr_t)(EFFECT_BASE+64u*256u+64u*2u)==effects_pixel(0,64,64));
    uint32_t size_index=3u;const uint32_t expected_sizes[]={2u,1u,0u,3u};
    for(uint32_t n=0;n<4u;++n){size_index=bench_next_size(size_index);assert(size_index==expected_sizes[n]);}
    puts("BASIC HOST PASSED: pixel/guard and manual controls; CPU default/no auto-switch over 70 frames; DST hidden; equal page backgrounds; 70-frame default single-buffer/front writes; explicit S toggles, pause, A/B labels removed; authoritative back-page exit and identical two-page menu");
    puts("EFFECTS HOST PASSED: 1024 Alpha cases; 208 full-viewport stationary-walk cases with exact original checkerboards and player-source comparison, two pages/keys and key on/off; fixed centre across frame wrap; 64KiB guards; timer wrap, pause/resume and Alpha resource reload");
    return 0;
}
''')
out=ROOT/'software/build/basic_host';out.mkdir(parents=True,exist_ok=True)
(out/'key_frames').mkdir(exist_ok=True)
source=out/'check.c';source.write_text('\n'.join(parts),encoding='utf-8')
env=os.environ.copy();env['PATH']=str(args.cc.parent)+os.pathsep+env.get('PATH','')
subprocess.run([str(args.cc),'-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-Isoftware',str(source),'-o',str(out/'check.exe')],cwd=ROOT,env=env,check=True)
r=subprocess.run([str(out/'check.exe')],cwd=ROOT,env=env,capture_output=True,text=True)
(ROOT/'reports/basic_demo_host.log').write_text(r.stdout+r.stderr,encoding='utf-8')
print(r.stdout+r.stderr,flush=True)
if r.returncode:raise SystemExit(r.returncode)
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
for path in list((ROOT/'reports').glob('basic_demo*.ppm'))+list((ROOT/'reports').glob('basic_effects*.ppm'))+list((ROOT/'reports').glob('basic_buffer*.ppm'))+list((ROOT/'reports').glob('basic_reference*.ppm'))+list((out/'key_frames').glob('key_walk_*.ppm')):
    header,size,maximum,pixels=path.read_bytes().split(b'\n',3)
    assert (header,size,maximum)==(b'P6',b'640 480',b'255')
    rows=b''.join(b'\0'+pixels[y*1920:(y+1)*1920] for y in range(480))
    path.with_suffix('.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',640,480,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))
    if path.stem.startswith('key_walk_'):path.unlink()
from PIL import Image
surfaces=struct.unpack('<'+str(2*256*192)+'H',(out/'copy_surfaces.rgb565').read_bytes())
def resized(rgb, width, height):
    def mix(a,b,n):
        return tuple((c*(32-n)+d*n)//32 for c,d in zip(a,b))
    for y in range(192):
        row,fy=divmod(y*height*32//192,32)
        below=min(height-1,row+1)
        for x in range(256):
            col,fx=divmod(x*width*32//256,32)
            right=min(width-1,col+1)
            top=mix(rgb[row*width+col],rgb[row*width+right],fx)
            bottom=mix(rgb[below*width+col],rgb[below*width+right],fx)
            r,g,b=mix(top,bottom,fy)
            yield (r<<11)|(g<<5)|b
for i,name in enumerate(('supertuxkart','0ad')):
    with Image.open(ROOT/'assets/basic_copy'/f'{name}.png') as source:
        im=source.convert('RGB').quantize(16,dither=Image.Dither.NONE).convert('RGB')
    rgb=[(r>>3,g>>2,b>>3) for r,g,b in im.getdata()]
    assert tuple(resized(rgb,*im.size))==surfaces[i*256*192:(i+1)*256*192],name
message='COPY ART PASSED: both ROM screenshots, all 98304 RGB565 pixels verified against source images'
with (ROOT/'reports/basic_demo_host.log').open('a',encoding='utf-8') as log:log.write(message+'\n')
print(message,flush=True)
walk_frames=[Image.open(out/f'key_frames/key_walk_{n:03d}.png').convert('RGB') for n in range(8)]
sample=Image.new('RGB',(1280,960))
for n in range(4):sample.paste(walk_frames[n],((n%2)*640,(n//2)*480))
palette=sample.quantize(colors=256,dither=Image.Dither.NONE)
indexed=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in walk_frames]
indexed[0].save(ROOT/'reports/key_walk_preview.gif',save_all=True,append_images=indexed[1:],duration=100,loop=0,optimize=False)
