"""Compare cached scenery/dirty restore against a full redraw pixel oracle."""
from pathlib import Path
import re,subprocess,os,json
ROOT=Path(__file__).resolve().parents[1]
CC=Path('D:/Xilinx/Vivado/2018.3/msys64/mingw64/bin/gcc.exe')
OUT=ROOT/'software/build';OUT.mkdir(exist_ok=True)
view=(ROOT/'software/game_view.h').read_text()
scene=(ROOT/'software/scenery_view.h').read_text()
dungeon=(ROOT/'software/dungeon_view.h').read_text()
def function(source,name):
    m=re.search(r'^static [^;{]*\b'+name+r'\([^;{]*\)\s*\{',source,re.M);assert m,name
    depth=0
    for t in re.finditer(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*|[{}]',source[m.end()-1:],re.S):
        if t.group()=='{':depth+=1
        elif t.group()=='}':
            depth-=1
            if not depth:return source[m.start():m.end()-1+t.end()]
    raise ValueError(name)
prelude=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "survivor_game.h"
#define ASSET_BASE 0x01200000u
#define GFX_BLEND_KEY 2u
#define GAME_BACKGROUND_COLOR 0x1085u
#define GAME_VIEW_WIDTH (GAME_X_MAX-GAME_X_MIN)
#define GAME_VIEW_HEIGHT (GAME_Y_MAX-GAME_Y_MIN)
#define GAME_DIRTY_TILE 32u
#define GAME_DIRTY_COLS ((GAME_VIEW_WIDTH+31u)/32u)
#define GAME_DIRTY_ROWS ((GAME_VIEW_HEIGHT+31u)/32u)
#include "dungeon_map.h"
#include "scenery_assets.h"
typedef struct {uint8_t first,last,top,bottom;} GameDirtyRect;
static uint16_t pages[2][640*480],oracle[640*480],scene_pixels[SCENERY_ASSET_BYTES/2],game_pixels[25*1024];
static uint16_t world_pixels[GAME_WORLD_WIDTH*GAME_WORLD_HEIGHT],dungeon_tiles[DUNGEON_TILE_COUNT*1024];
static uint16_t wall_pixels[DUNGEON_WALL_BYTES/2u];
static uint32_t dungeon_assets_ready,floor_commands,floor_pixels,painted_pixels;
static int32_t dungeon_camera_x,dungeon_camera_y;
static int16_t dungeon_page_camera[2][2];
static uint32_t page,mode,game_capture_page,game_capture_dirty,commands,source_pixels;
static uint32_t game_page_dirty[2][GAME_DIRTY_ROWS];
static uint8_t game_page_valid[2],game_page_playing[2],game_dirty_valid[2];
static unsigned frames,minimum=99,maximum;
static void fail(const char *s){fprintf(stderr,"%s\n",s);assert(0);}
static void paint(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t color,uint32_t hw) {
    (void)hw;assert(x+w<=640 && y+h<=480);
    if(!mode && color==GAME_BACKGROUND_COLOR)painted_pixels+=w*h;
    uint16_t *p=mode?oracle:pages[page];
    for(uint32_t j=y;j<y+h;j++)for(uint32_t i=x;i<x+w;i++)p[j*640+i]=color;
}
static inline int copy_image(uint32_t source,uint32_t stride,uint32_t x,uint32_t y,uint32_t w,uint32_t h) {
    assert((stride==4096u || stride==64u) && !(source&1u));
    assert(source>=DUNGEON_WALL_BASE && source+(h-1u)*stride+w*2u<=DUNGEON_WALL_BASE+DUNGEON_WALL_BYTES);
    assert(x>=GAME_X_MIN && y>=GAME_Y_MIN && x+w<=GAME_X_MAX && y+h<=GAME_Y_MAX);
    uint16_t *p=mode?oracle:pages[page];uint32_t start=(source-DUNGEON_WALL_BASE)/2u;
    if(!mode){floor_commands++;floor_pixels+=w*h;}
    for(unsigned j=0;j<h;j++)for(unsigned i=0;i<w;i++)p[(y+j)*640u+x+i]=wall_pixels[start+j*(stride/2u)+i];
    return 0;
}
static void init_reference_world(void) {
    for(unsigned y=0;y<GAME_WORLD_HEIGHT;y++)for(unsigned x=0;x<GAME_WORLD_WIDTH;x++)
        world_pixels[y*GAME_WORLD_WIDTH+x]=dungeon_pixel(x,y,dungeon_tiles);
    for(unsigned n=0;n<DUNGEON_WALL_BANDS;n++) {
        const DungeonWallBand *b=&dungeon_wall_bands[n];
        for(unsigned y=0;y<b->h;y++)for(unsigned x=0;x<b->w;x++)
            assert(wall_pixels[b->offset/2u+y*b->w+x]==world_pixels[(b->y+y)*GAME_WORLD_WIDTH+b->x+x]);
    }
}
static void reference_background(int cx,int cy) {
    for(unsigned y=0;y<GAME_VIEW_HEIGHT;y++)for(unsigned x=0;x<GAME_VIEW_WIDTH;x++)
        oracle[(GAME_Y_MIN+y)*640+GAME_X_MIN+x]=world_pixels[(cy+y)*GAME_WORLD_WIDTH+cx+x];
}
static int blend_image(uint32_t source,uint32_t stride,uint32_t x,uint32_t y,uint32_t w,uint32_t h,
                       uint8_t alpha,uint16_t key,uint32_t flags) {
    assert(alpha==255 && key==0 && flags==GFX_BLEND_KEY && !(source&1u));
    assert(x>=GAME_X_MIN && y>=GAME_Y_MIN && x+w<=GAME_X_MAX && y+h<=GAME_Y_MAX);
    assert(source>=SCENERY_ASSET_BASE && source+(h-1u)*stride+w*2u<=SCENERY_ASSET_BASE+SCENERY_ASSET_BYTES);
    uint16_t *p=mode?oracle:pages[page];uint32_t begin=(source-0x01220000u)/2u;
    if(!mode){commands++;source_pixels+=w*h;}
    for(uint32_t j=0;j<h;j++)for(uint32_t i=0;i<w;i++) {
        uint16_t color=scene_pixels[begin+j*(stride/2)+i];if(color)p[(y+j)*640+x+i]=color;
    }
    return 0;
}
'''
old='(SCENERY_ASSET_BASE+f->offset)';assert old in scene
init_dungeon=function(dungeon,'init_dungeon_assets').replace('(uintptr_t)DUNGEON_TILE_BASE','(uintptr_t)dungeon_tiles').replace('(uintptr_t)(DUNGEON_WALL_BASE+band->offset)','(uintptr_t)((unsigned char *)wall_pixels+band->offset)')
scene=scene.replace(old,'((uintptr_t)((unsigned char *)scene_pixels+f->offset))')
tests=r'''
static void reset(void) {
    for(unsigned p=0;p<2;p++)for(unsigned i=0;i<640*480;i++)pages[p][i]=0xdead;
    memset(game_page_dirty,0,sizeof(game_page_dirty));memset(game_page_valid,0,sizeof(game_page_valid));
    memset(game_page_playing,0,sizeof(game_page_playing));memset(game_dirty_valid,0,sizeof(game_dirty_valid));
    memset(scenery_page_valid,0,sizeof(scenery_page_valid));memset(scenery_page_count,0,sizeof(scenery_page_count));
}
static void foreground(int32_t x,int32_t y,unsigned frame) {
    int32_t left=x-16,top=y-16;
    uint16_t *p=mode?oracle:pages[page];
    for(int32_t j=0;j<32;j++)for(int32_t i=0;i<32;i++) {
        int32_t dx=left+i,dy=top+j;uint16_t color=game_pixels[frame*1024+j*32+i];
        if(color && dx>=GAME_X_MIN && dx<GAME_X_MAX && dy>=GAME_Y_MIN && dy<GAME_Y_MAX)p[dy*640+dx]=color;
    }
    int32_t x0=left<GAME_X_MIN?GAME_X_MIN:left,y0=top<GAME_Y_MIN?GAME_Y_MIN:top;
    int32_t x1=left+32>GAME_X_MAX?GAME_X_MAX:left+32,y1=top+32>GAME_Y_MAX?GAME_Y_MAX:top+32;
    if(!mode && x0<x1 && y0<y1)game_record_dirty_rect(x0,y0,x1-x0,y1-y0);
}
static void save(const char *name) {
    char path[200];snprintf(path,sizeof(path),"reports/%s.ppm",name);
    FILE *f=fopen(path,"wb");assert(f);fprintf(f,"P6\n624 360\n255\n");
    for(unsigned y=GAME_Y_MIN;y<GAME_Y_MAX;y++)for(unsigned x=GAME_X_MIN;x<GAME_X_MAX;x++) {
        uint16_t c=pages[page][y*640+x];fputc((c>>11)*255/31,f);fputc(((c>>5)&63)*255/63,f);fputc((c&31)*255/31,f);
    }
    fclose(f);
}
static void verify(int32_t cx,int32_t cy,uint32_t ticks,unsigned actors,unsigned playing,unsigned fill) {
    commands=source_pixels=floor_commands=floor_pixels=painted_pixels=0;mode=0;game_capture_dirty=0;
    game_draw_world_floor(page,cx,cy,playing,ticks);
    assert(commands<=1 && source_pixels<=SCENERY_ALTAR_SIZE*SCENERY_ALTAR_SIZE);
    assert(floor_pixels<=30464u);
    SceneryItem items[SCENERY_MAX_ITEMS];unsigned count=scenery_select(cx,cy,ticks,items);
    mode=1;for(unsigned i=0;i<640*480;i++)oracle[i]=0xdead;
    // Reference bypasses the dirty/camera cache and always redraws the full crop.
    reference_background(cx,cy);
    for(unsigned i=0;i<count;i++){SceneryRect r;assert(scenery_rect(&items[i],&r));blend_image(r.source,r.stride,r.x,r.y,r.w,r.h,255,0,GFX_BLEND_KEY);}
    for(mode=0;mode<2;mode++) {
        if(actors) {
            foreground(320,260,0);
            for(unsigned i=0;i<18;i++)foreground(80+(int32_t)(i%6)*86+(int32_t)(ticks%7),130+(int32_t)(i/6)*112,16+i%3);
        }
        if(fill) {
            paint(GAME_X_MIN,GAME_Y_MIN,GAME_VIEW_WIDTH,GAME_VIEW_HEIGHT,0x1234,1);
            if(!mode)game_record_dirty_rect(GAME_X_MIN,GAME_Y_MIN,GAME_VIEW_WIDTH,GAME_VIEW_HEIGHT);
        }
    }
    mode=0;
    if(memcmp(pages[page],oracle,sizeof(oracle))) {
        for(unsigned i=0;i<640*480;i++)if(pages[page][i]!=oracle[i]) {
            fprintf(stderr,"SCENERY MISMATCH frame=%u page=%u camera=(%d,%d) tick=%u pixel=(%u,%u) got=%04x expected=%04x\n",frames,page,cx,cy,ticks,i%640,i/640,pages[page][i],oracle[i]);break;
        }
        assert(0);
    }
    frames++;
}
int main(void) {
    init_dungeon_assets();assert(dungeon_assets_ready);
    init_reference_world();
    FILE *raw=fopen("reports/dungeon_world.rgb565","wb");assert(raw);
    assert(fwrite(world_pixels,2,GAME_WORLD_WIDTH*GAME_WORLD_HEIGHT,raw)==GAME_WORLD_WIDTH*GAME_WORLD_HEIGHT);fclose(raw);
    raw=fopen("assets/dungeon/tiles.rgb565","rb");assert(raw);
    uint16_t expected_tiles[DUNGEON_TILE_COUNT*1024];assert(fread(expected_tiles,2,DUNGEON_TILE_COUNT*1024,raw)==DUNGEON_TILE_COUNT*1024);fclose(raw);
    assert(!memcmp(expected_tiles,dungeon_tiles,sizeof(expected_tiles)));
    init_scenery_assets();assert(scenery_assets_ready);
    FILE *f=fopen("assets/scenery/scenery.rgb565","rb");assert(f);
    uint16_t expected[SCENERY_ASSET_BYTES/2u];assert(fread(expected,2,SCENERY_ASSET_BYTES/2u,f)==SCENERY_ASSET_BYTES/2u);fclose(f);assert(!memcmp(expected,scene_pixels,sizeof(expected)));
    f=fopen("assets/game/game.rgb565","rb");assert(f && fread(game_pixels,2,25*1024,f)==25*1024);fclose(f);
    // World-camera sweep verifies the cap, visibility clipping and altar gate.
    for(int32_t y=0;y<=1048;y+=16)for(int32_t x=0;x<=1424;x+=16) {
        SceneryItem items[1];unsigned count=scenery_select(x,y,30,items),props=0,altars=0;
        for(unsigned i=0;i<count;i++){SceneryRect r;assert(scenery_rect(&items[i],&r));if(items[i].frame==SCENERY_ALTAR)altars++;else props++;}
        if(props<minimum)minimum=props;
        if(props>maximum)maximum=props;
        assert(props==0 && altars<=1);
        SceneryItem altar={(int16_t)(8+1024-x),(int16_t)(80+704-y),SCENERY_ALTAR};SceneryRect r;
        assert(altars==scenery_rect(&altar,&r));
    }
    reset();page=0;verify(712,524,0,0,1,0);assert(commands>0 && floor_commands==0);verify(712,524,0,0,1,0);assert(commands==0 && floor_commands==0);
    page=1;verify(712,524,0,0,1,0);verify(712,524,0,0,1,0);assert(commands==0 && floor_commands==0);
    verify(712,524,10,0,1,0);assert(commands==0);save("scenery_still");
    reset();
    for(unsigned n=0;n<300;n++) {
        page=n&1u;int32_t cx=712,cy=524;uint32_t ticks=n;
        if(n>=20 && n<80){cx=712+(int32_t)(n-20)*3;cy=524+(int32_t)(n-20);}
        if(n>=80 && n<120){cx=0;cy=0;}
        if(n>=120 && n<160){cx=1424;cy=1048;}
        if(n>=160 && n<200){cx=1032+(int32_t)(n-160);cy=680;}
        if(n>=200)ticks=100;
        verify(cx,cy,ticks,1,1,n==220 || n==221);
        if(n==0)save("scenery_center");
        if(n==110)save("scenery_corner");
        if(n==180)save("scenery_altar_edge");
    }
    for(unsigned n=0;n<12;n++){page=n&1u;verify(712,524,100,0,0,0);}
    for(unsigned n=0;n<4;n++){page=n&1u;verify(712,524,101+n,1,1,0);}
    // Wall scrolling / visibility thresholds on both pages, no foreground.
    reset();
    for(unsigned n=0;n<8;n++){page=n&1u;verify(0,0,200,0,1,0);}
    page=0;verify(1,0,200,0,1,0);assert(floor_commands>0 && floor_commands<=2);
    page=1;verify(0,1,200,0,1,0);assert(floor_commands>0 && floor_commands<=2);
    page=0;verify(1424,0,200,0,1,0);save("scenery_northeast");
    page=1;verify(0,1048,200,0,1,0);save("scenery_southwest");
    page=0;verify(1424,1048,200,0,1,0);save("scenery_southeast");
    const int cameras[][2]={{31,31},{32,32},{33,33},{0,0},{31,1048},{32,1048},{1424,31},{1424,32}};
    for(unsigned i=0;i<sizeof(cameras)/sizeof(cameras[0]);i++)for(unsigned p=0;p<2;p++) {page=p;verify(cameras[i][0],cameras[i][1],200,0,1,0);}
    reset();page=0;verify(712,524,200,0,1,0);verify(713,525,200,0,1,0);
    assert(floor_commands==0 && painted_pixels<GAME_VIEW_WIDTH*GAME_VIEW_HEIGHT);
    printf("SCENERY TESTS PASSED: %u full-frame pixel comparisons; world sweep props=%u..%u; 128px altar visibility; exact RLE; packed 424KiB W1 walls, no floor; interior camera skips full restore; all four wall visibility thresholds; foreground occlusion; both pages; 75%% fallback; pause/resume; stationary cache skips commands; altar max1 command/16384 pixels; wall reads <=30464 pixels/frame\n",frames,minimum,maximum);
    return 0;
}
'''
code=prelude+'\n'+init_dungeon+'\n'+function(dungeon,'dungeon_draw_walls')+'\n'+function(view,'game_record_dirty_rect')+'\n'+scene+'\n'
for name in ['game_fill_background_rect','game_restore_dirty_tiles','game_draw_world_floor']:code+=function(view,name)+'\n'
code+=tests
(OUT/'scenery_host.c').write_text(code)
env=dict(os.environ);env['PATH']=str(CC.parent)+os.pathsep+env.get('PATH','')
cmd=[str(CC),'-std=c99','-O2','-Wall','-Wextra','-Werror','-Isoftware',str(OUT/'scenery_host.c'),'-o',str(OUT/'scenery_host.exe')]
r=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True);print(r.stdout+r.stderr);assert not r.returncode
r=subprocess.run([str(OUT/'scenery_host.exe')],cwd=ROOT,env=env,capture_output=True,text=True)
(ROOT/'reports/scenery_host.log').write_text(r.stdout+r.stderr);print(r.stdout+r.stderr)
if r.returncode:raise SystemExit(r.returncode)
from PIL import Image
for p in (ROOT/'reports').glob('scenery_*.ppm'):Image.open(p).save(p.with_suffix('.png'))
