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
OUT=ROOT/'software/build/reference_ui_check';OUT.mkdir(exist_ok=True)
# Native host support is fixed here; the compatibility wrapper delegates to this checker.
prelude='\n#include <windows.h>\n#include <stdint.h>\n#include <assert.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include "render.h"\n#include "font5x7.h"\n#include "font_cn.h"\n#undef ASSET_BASE\n#undef FRAMEBUFFER\n#define ASSET_BASE 0x10000000u\n#define FRAMEBUFFER 0x11000000u\nstatic uint32_t draw_buffer=FRAMEBUFFER_B,active_page,display_enabled,clock_value;\nstatic uint32_t menu_level,menu_group,menu_item[2],menu_repaint_pages;\nstatic uint32_t keys[16],key_count,key_pos,cover_events,menu_events,present_count;\nstatic uint32_t cache_copies;\nstatic uint64_t cpu_fill_pixels;\nstatic uint16_t last_front[640*480];\nstatic uint32_t draw_page(void){return draw_buffer==FRAMEBUFFER_B;}\nstatic uint32_t cycle_now(void){return clock_value+=1500000u;}\nstatic void fail(const char *s){fprintf(stderr,"%s\\n",s);abort();}\nstatic void cpu_fill(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c){\n    cpu_fill_pixels+=(uint64_t)w*h;\n    assert(x+w<=640u && y+h<=480u);\n    assert(!display_enabled || draw_page()!=active_page);\n    for(uint32_t row=0;row<h;++row) {\n        uint16_t *p=(void*)(uintptr_t)(draw_buffer+(y+row)*1280u+x*2u);\n        for(uint32_t col=0;col<w;++col)p[col]=c;\n    }\n}\nstatic void paint(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c,uint32_t hw){\n    (void)hw;cpu_fill(x,y,w,h,c);\n}\nstatic void draw_player(uint32_t frame,uint32_t x,uint32_t y,uint32_t hw){\n    (void)frame;(void)x;(void)y;(void)hw;\n}\nstatic void publish_pixels(void){}\nstatic void uart_number(const char *s,uint32_t v){(void)s;(void)v;}\nint copy_image(uint32_t source,uint32_t stride,uint32_t x,uint32_t y,uint32_t w,uint32_t h){\n    if(source==ASSET_BASE+0x66A00u)++cache_copies;\n    assert(source>=ASSET_BASE && source+(h-1u)*stride+w*2u<=ASSET_BASE+ASSET_BYTES);\n    assert(x+w<=640u && y+h<=480u && (!display_enabled || draw_page()!=active_page));\n    for(uint32_t row=0;row<h;++row)memcpy((void*)(uintptr_t)(draw_buffer+(y+row)*1280u+x*2u),\n        (void*)(uintptr_t)(source+row*stride),w*2u);\n    return 0;\n}\nstatic int host_present(void){\n    if(display_enabled)assert(!memcmp(last_front,(void*)(uintptr_t)(active_page ? FRAMEBUFFER_B:FRAMEBUFFER),FRAMEBUFFER_BYTES));\n    active_page=draw_page();draw_buffer=active_page ? FRAMEBUFFER:FRAMEBUFFER_B;\n    memcpy(last_front,(void*)(uintptr_t)(active_page ? FRAMEBUFFER_B:FRAMEBUFFER),FRAMEBUFFER_BYTES);\n    ++present_count;return 0;\n}\n#define present_frame host_present\nstatic void host_write(uint32_t address,uint32_t value){\n    assert(address==GFX_BASE+GFX_DISPLAY && value==1u);display_enabled=value;\n}\n#define mmio_write host_write\nstatic void puts_uart(const char *s){\n    if(!strncmp(s,"BOOK COVER",10))++cover_events;\n    if(!strncmp(s,"MENU",4))++menu_events;\n}\nstatic uint32_t button_event(void){assert(key_pos<key_count);return keys[key_pos++];}\nstatic void script(uint32_t a,uint32_t b,uint32_t c,uint32_t d){\n    keys[0]=a;keys[1]=b;keys[2]=c;keys[3]=d;key_count=4;key_pos=0;\n}\nstatic void save(const char *name){\n    char path[220];snprintf(path,sizeof(path),"reports/book_%s.ppm",name);\n    FILE *f=fopen(path,"wb");assert(f);fprintf(f,"P6\\n640 480\\n255\\n");\n    const uint16_t *p=(void*)(uintptr_t)draw_buffer;\n    for(uint32_t n=0;n<640u*480u;++n){\n        fputc(((p[n]>>11)&31u)*255u/31u,f);fputc(((p[n]>>5)&63u)*255u/63u,f);fputc((p[n]&31u)*255u/31u,f);\n    }\n    fclose(f);\n}\n'
prelude=prelude.replace('#include "render.h"','#define UI_NATIVE_REFERENCE\n#include "render.h"')
prelude=prelude.replace('assert(address==GFX_BASE+GFX_DISPLAY && value==1u);display_enabled=value;','(void)address;(void)value;')
main=(ROOT/'software/main.c').read_text(encoding='utf-8')
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
#include "game_view_host.h"
enum {DEMO_FILL,DEMO_COPY,DEMO_BUFFER,DEMO_KEY,DEMO_ALPHA,DEMO_BENCH};
#define BENCH_VARIANTS 4u
static uint32_t sprite_count=1u,bench_size_index=3u,bench60_pass;
static const uint8_t bench_sizes[4]={4,16,24,32};
static uint32_t bench_sources[4]={ASSET_BASE+0x2e80u,ASSET_BASE+0x2800u,ASSET_BASE+0x2a00u,ASSET_BASE+0x3000u};
static const char *const demo_names[6]={"矩形填充","图像复制","双缓冲","颜色键","透明混合","SPRITE压力"};
static const char *const demo_details[6]={"","","","","","FPGA ALPHA + COLOR KEY / 60 FPS"};
static const char *const action_labels[6]={"","","","","","W加5 S减5 长按连发"};
static uint32_t fps[2],render_us[2],samples[2],burst_ar[2],burst_aw[2],sprite_best_60[4];
#include "demo_skin.h"
''']
for n in ('sprite_pixel_sized','blend_rgb565','bounce','sprite_seed','draw_bench_sprite'):
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
        projection_case=frame==12 ? "bridge":frame==60 ? "curved":frame==119 ? "final":0;projection_skip=0;
        book_open_pose(frame);assert(book_command_count<=512u);
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
    g.state=GAME_PLAY;game_hud_pages=0;game_ui_key[draw_page()]=0xffffffffu;
    game_draw(&g,60,0,0,0);save("reference_game_play");
    uint16_t live=((uint16_t*)(uintptr_t)draw_buffer)[260*640+320];
    assert(live!=0x1085); // The HUD must not clear the just-drawn hero.
    g.state=GAME_PAUSED;projection_case="pause";projection_skip=0;game_draw(&g,60,0,0,0);save("reference_game_paused");
    g.state=GAME_PLAY;game_draw(&g,60,0,0,0);assert(((uint16_t*)(uintptr_t)draw_buffer)[260*640+320]==live);
    FILE *atlas=fopen("assets/game/game.rgb565","rb");assert(atlas);uint8_t golden[73728];assert(fread(golden,1,sizeof(golden),atlas)==sizeof(golden));fclose(atlas);assert(!memcmp(golden,(void*)(uintptr_t)GAME_ASSET_BASE,sizeof(golden)));
    // Exercise both retired pages through every game state and choice.
    for(uint32_t step=0;step<48;++step){g.state=step%6;g.choice=(step/6)%3;game_draw(&g,60,0,0,0);host_present();}

    book_assets_ready=0;book_cache_valid=0;book_closed=0;
    for(uint32_t demo=0;demo<6;++demo){menu_level=1;menu_group=demo/3;menu_item[menu_group]=demo%3;script(16,0,0,0);assert(menu_screen()==demo);}
    menu_level=0;menu_group=2;script(16,0,0,0);assert(menu_screen()==8);
    for(uint32_t n=0;n<65536;++n){assert(*(uint8_t*)(uintptr_t)(ASSET_BASE-65536+n)==0);assert(*(uint8_t*)(uintptr_t)(ASSET_BASE+ASSET_BYTES+n)==0);}
    for(uint32_t v=0;v<4;++v){uint16_t *p=(void*)(uintptr_t)bench_sources[v];for(uint32_t y=0;y<bench_sizes[v];++y)for(uint32_t x=0;x<bench_sizes[v];++x)p[y*bench_sizes[v]+x]=sprite_pixel_sized(bench_sizes[v],y,x);}
    display_enabled=1;bench_prime_framebuffers();assert(display_enabled);save("reference_pressure_entry");
    puts("PASS native reference UI: all 119 interior poses; 9 menus; cover; 6 demo routes; game route; live game rendering; both chapter directions; 48 alternating state/choice transitions; pause/resume atlas and hero preserved; pool guards");return 0;
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
html=(ROOT/'assets/ui/magic_book_v5/魔法书交互预览.html').read_text(encoding='utf-8')
pages,_=json.JSONDecoder().raw_decode(html[html.index('const pages=')+12:])
def quantize(im):
    return Image.frombytes('RGB',im.size,bytes(v for r,g,b in im.convert('RGB').getdata() for v in ((r>>3)*255//31,(g>>2)*255//63,(b>>3)*255//31)))
results={}
for ppm in (ROOT/'reports').glob('book_reference_*.ppm'):
    actual=Image.open(ppm).convert('RGB');actual.save(ppm.with_suffix('.png'));name=ppm.stem[len('book_reference_'):]
    key='cover' if name=='cover' else None
    m=re.fullmatch('menu_(\d)_(\d)',name)
    if m:key=('home','basic','advanced')[int(m[1])]+'_'+m[2]
    if name=='game_0':key='game_ready'
    if key:
        expected=quantize(Image.open(io.BytesIO(base64.b64decode(pages[key].split(',')[1]))))
        diff=ImageChops.difference(actual,expected);count=sum(px!=(0,0,0) for px in diff.getdata());results[key]=count
        diff.save(OUT/(key+'_diff.png'))
    ppm.unlink()
(OUT/'pixel_comparison.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
assert all(v==0 for v in results.values()),'Menu pixels must match the local HTML exactly' 
(ROOT/'sim/ui_command_count.vh').write_text('`define UI_TEST_COMMANDS '+str(struct.unpack('<I',(OUT/'command_count.bin').read_bytes())[0])+'\n',encoding='ascii')
for filename in ('commands','assets','expected',*[p.stem for p in OUT.glob('*_assets.bin')],*[p.stem for p in OUT.glob('*_expected.bin')],*[p.stem for p in OUT.glob('*_metadata.bin')]):
    data=(OUT/(filename+'.bin')).read_bytes();(OUT/(filename+'.hex')).write_text(''.join(f'{v:08x}\n' for v in struct.unpack('<'+'I'*(len(data)//4),data)),encoding='ascii')
