"""Real gem/floor/sprite C rendering against a full RGB565 redraw oracle."""
from pathlib import Path
import argparse,ast,os,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--baseline-view',type=Path);args=parser.parse_args()
OUT=ROOT/'software/build';OUT.mkdir(exist_ok=True)
CC=Path('D:/Xilinx/Vivado/2018.3/msys64/mingw64/bin/gcc.exe')
view=(args.baseline_view or ROOT/'software/game_view.h').read_text()
scene=(ROOT/'software/scenery_view.h').read_text()
def function(source,name):
    m=re.search(r'^static [^;{]*\b'+name+r'\([^;{]*\)\s*\{',source,re.M);assert m,name
    depth=0
    for token in re.finditer(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*|[{}]',source[m.end()-1:],re.S):
        if token.group()=='{':depth+=1
        elif token.group()=='}':
            depth-=1
            if not depth:return source[m.start():m.end()-1+token.end()]
    raise ValueError(name)
# Reuse the established page/dirty-rect harness, without executing its tests.
tree=ast.parse((ROOT/'tools/check_scenery.py').read_text())
prelude=next(ast.literal_eval(n.value)for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='prelude'for t in n.targets))
prelude=prelude[:prelude.index('static int blend_image')]
prelude=prelude.replace('static unsigned frames,minimum=99,maximum;','static unsigned frames;')
if 'dungeon_page_camera[page]'not in view:
    # Historical fixtures use a flat floor and have no world-camera cache.
    prelude=prelude.replace('static int32_t dungeon_camera_x,dungeon_camera_y;\n','').replace('static int16_t dungeon_page_camera[2][2];\n','')
prelude+='\n#include "game_frame_bounds.h"\n#define GFX_BLEND_ALPHA 1u\n#define GAME_ASSET_BASE (ASSET_BASE+0x4000u)\n#define GAME_FRAME_COUNT 25u\nstatic uint32_t game_assets_ready=1,target_drawn;\n'
prelude+=re.search(r'^#define GAME_MAX_DRAW_GEMS[^\n]+',view,re.M).group()+'\n'
if 'static void game_select_gems('in view:
    prelude+='static uint32_t game_gem_selected[(GAME_MAX_GEMS+31u)/32u];\n'
prelude+=r'''
static uint16_t mix565(uint16_t f,uint16_t b,unsigned a) {
    unsigned r=(((f>>11)&31u)*a+((b>>11)&31u)*(255u-a)+127u)/255u;
    unsigned g=(((f>>5)&63u)*a+((b>>5)&63u)*(255u-a)+127u)/255u;
    unsigned blue=((f&31u)*a+(b&31u)*(255u-a)+127u)/255u;
    return (uint16_t)((r<<11)|(g<<5)|blue);
}
static int blend_image(uint32_t source,uint32_t stride,uint32_t x,uint32_t y,uint32_t w,uint32_t h,
                       uint8_t alpha,uint16_t key,uint32_t flags) {
    assert(key==0 && !(source&1u));
    assert(x>=GAME_X_MIN && y>=GAME_Y_MIN && x+w<=GAME_X_MAX && y+h<=GAME_Y_MAX);
    uint16_t *dst=mode?oracle:pages[page],*src;unsigned begin;
    if(source>=0x01220000u) {
        assert(source+(h-1u)*stride+w*2u<=SCENERY_ASSET_BASE+SCENERY_ASSET_BYTES && alpha==255 && flags==GFX_BLEND_KEY);
        src=scene_pixels;begin=(source-0x01220000u)/2u;
    } else {
        assert(source>=GAME_ASSET_BASE && source+(h-1u)*stride+w*2u<=GAME_ASSET_BASE+51200u);
        src=game_pixels;begin=(source-GAME_ASSET_BASE)/2u;
        if(!mode && begin/1024u==19u && x==580u && y==368u)target_drawn=1;
    }
    if(!mode){commands++;source_pixels+=w*h;}
    for(unsigned j=0;j<h;j++)for(unsigned i=0;i<w;i++) {
        uint16_t color=src[begin+j*(stride/2u)+i];if((flags&GFX_BLEND_KEY)&&color==key)continue;
        unsigned at=(y+j)*640u+x+i;dst[at]=(flags&GFX_BLEND_ALPHA)?mix565(color,dst[at],alpha):color;
    }
    return 0;
}
'''
if 'static uint32_t game_draw_gems('in view:helper=function(view,'game_draw_gems')
else:
    a=view.index('    uint32_t gem_drawn=0;\n    sprite_start=cycle_now();',view.index('static uint32_t game_draw('))
    b=view.index('    game_draw_sprite_cycles+=cycle_now()-sprite_start;',a)
    body=view[a:b].replace('    sprite_start=cycle_now();\n','').replace('drawn+=visible; gem_drawn+=visible;','gem_drawn+=visible;')
    helper='static uint32_t game_draw_gems(const SurvivorGame *g,int32_t camera_x,int32_t camera_y) {\n'+body+'return gem_drawn;\n}\n'
scene=scene.replace('(SCENERY_ASSET_BASE+f->offset)','((uintptr_t)((unsigned char *)scene_pixels+f->offset))')
dungeon=(ROOT/'software/dungeon_view.h').read_text()
init_dungeon=function(dungeon,'init_dungeon_assets').replace('(uintptr_t)DUNGEON_TILE_BASE','(uintptr_t)dungeon_tiles').replace('(uintptr_t)(DUNGEON_WALL_BASE+band->offset)','(uintptr_t)((unsigned char *)wall_pixels+band->offset)')
draw_walls=function(dungeon,'dungeon_draw_walls')+'\n'if 'dungeon_draw_walls('in view else''
code=prelude+init_dungeon+'\n'+draw_walls+function(view,'game_record_dirty_rect')+'\n'+scene+'\n'
for name in ['game_fill_background_rect','game_restore_dirty_tiles','game_draw_world_floor','game_sprite']:
    code+=function(view,name)+'\n'
if 'game_world_sprite('in helper:code+=function(view,'game_world_sprite')+'\n'
if 'static void game_select_gems('in view:
    code+=function(view,'game_gem_visible')+'\n'+function(view,'game_select_gems')+'\n'
code+=helper+'\n'
code+=r'''
static SurvivorGame game;
static unsigned ref_ids[20],ref_count,max_gem_commands;
static int ref_bounds[2][4];
static int reference_visible(unsigned id,int cx,int cy) {
    if(!game.gems[id].value)return 0;
    int *bounds=ref_bounds[game.gems[id].kind?1u:0u];
    int x=GAME_X_MIN+game.gems[id].x-cx-16,y=GAME_Y_MIN+game.gems[id].y-cy-16;
    return x+bounds[0]<GAME_X_MAX && x+bounds[2]>GAME_X_MIN &&
           y+bounds[1]<GAME_Y_MAX && y+bounds[3]>GAME_Y_MIN;
}
static int reference_member(unsigned id) {
    for(unsigned n=0;n<ref_count;n++)if(ref_ids[n]==id)return 1;
    return 0;
}
static void reference_select(int cx,int cy) {
    // Independent ID-list model: retain visible members and fill vacancies.
    unsigned kept=0;
    for(unsigned n=0;n<ref_count;n++)if(reference_visible(ref_ids[n],cx,cy))ref_ids[kept++]=ref_ids[n];
    ref_count=kept;
    for(unsigned i=0;i<GAME_MAX_GEMS && ref_count<20;i++)
        if(!reference_member(i) && reference_visible(i,cx,cy))ref_ids[ref_count++]=i;
}
static void reset(void) {
    for(unsigned p=0;p<2;p++)for(unsigned i=0;i<640*480;i++)pages[p][i]=0xdead;
    memset(&game,0,sizeof(game));memset(game_page_dirty,0,sizeof(game_page_dirty));
    memset(game_page_valid,0,sizeof(game_page_valid));memset(game_page_playing,0,sizeof(game_page_playing));
    memset(game_dirty_valid,0,sizeof(game_dirty_valid));memset(scenery_page_valid,0,sizeof(scenery_page_valid));
    memset(scenery_page_count,0,sizeof(scenery_page_count));page=mode=0;
    ref_count=0;
#ifndef EXPECT_BASELINE
    memset(game_gem_selected,0,sizeof(game_gem_selected));
#endif
}
static void reference_sprite(unsigned frame,int x,int y,unsigned alpha) {
    // Independent full 32x32 source scan: no renderer crop bounds or draw cap.
    for(int j=0;j<32;j++)for(int i=0;i<32;i++) {
        int sx=x-16+i,sy=y-16+j;unsigned color=game_pixels[frame*1024u+j*32+i];
        if(color && sx>=GAME_X_MIN && sx<GAME_X_MAX && sy>=GAME_Y_MIN && sy<GAME_Y_MAX)
            oracle[sy*640+sx]=mix565((uint16_t)color,oracle[sy*640+sx],alpha);
    }
}
static void cover(unsigned value) {
    // A previous foreground object covers some gems, then moves elsewhere.
    unsigned x=GAME_X_MIN+40u+(value%9u)*48u,y=GAME_Y_MIN+30u+(value%5u)*45u;
    paint(x,y,45,37,0xf800u,1);
    if(!mode)game_record_dirty_rect(x,y,45,37);
}
static void frame(int cx,int cy,unsigned playing,unsigned occlude,unsigned compare) {
    game.x=(cx+312)*256;game.y=(cy+180)*256;
    reference_select(cx,cy);
    mode=0;commands=source_pixels=target_drawn=0;
    game_draw_world_floor(page,cx,cy,playing,game.ticks);
    unsigned before_commands=commands,before_pixels=source_pixels;
    SurvivorGame before=game;
    unsigned submitted=game_draw_gems(&game,cx,cy);
    assert(!memcmp(&before,&game,sizeof(game)));
    assert(submitted<=20 && commands-before_commands<=20 && source_pixels-before_pixels<=20u*31u*27u);
    if(commands-before_commands>max_gem_commands)max_gem_commands=commands-before_commands;
#ifndef EXPECT_BASELINE
    assert(submitted==ref_count);
    for(unsigned i=0;i<GAME_MAX_GEMS;i++)assert(!!(game_gem_selected[i>>5]&(1u<<(i&31u)))==reference_member(i));
#endif
    if(compare) {
        for(unsigned i=0;i<640*480;i++)oracle[i]=0xdead;
        mode=1;reference_background(cx,cy);
        SceneryItem items[SCENERY_MAX_ITEMS];unsigned n=scenery_select(cx,cy,game.ticks,items);
        for(unsigned i=0;i<n;i++){SceneryRect r;assert(scenery_rect(&items[i],&r));blend_image(r.source,r.stride,r.x,r.y,r.w,r.h,255,0,GFX_BLEND_KEY);}
        for(unsigned i=0;i<GAME_MAX_GEMS;i++)if(reference_member(i))
            reference_sprite(game.gems[i].kind?23u:19u,GAME_X_MIN+game.gems[i].x-cx,GAME_Y_MIN+game.gems[i].y-cy,220);
    }
    if(occlude){mode=0;cover(occlude);if(compare){mode=1;cover(occlude);}}
    mode=0;
    if(compare && memcmp(pages[page],oracle,sizeof(oracle))) {
        for(unsigned i=0;i<640*480;i++)if(pages[page][i]!=oracle[i]) {
            fprintf(stderr,"GEM PIXEL MISMATCH frame=%u page=%u playing=%u camera=%d,%d pixel=%u,%u actual=%04x expected=%04x submitted=%u\n",
                frames,page,playing,cx,cy,i%640,i/640,pages[page][i],oracle[i],submitted);break;
        }
        assert(0);
    }
    frames++;page^=1u;
}
static void populate(int cx,int cy) {
    for(unsigned i=0;i<GAME_MAX_GEMS;i++)game.gems[i]=(GameGem){(int16_t)(cx+30+(i%12u)*48u),(int16_t)(cy+20+(i/12u)*42u),1,(uint8_t)(i%5u==0),0};
}
int main(void) {
    FILE *f=fopen("assets/game/game.rgb565","rb");assert(f && fread(game_pixels,2,25*1024,f)==25*1024);fclose(f);
    // Derive reference visibility from raw art, independently of the generated
    // production bbox header; use the same rectangular clipping semantics.
    for(unsigned kind=0;kind<2;kind++) {
        ref_bounds[kind][0]=ref_bounds[kind][1]=32;
        unsigned frame=kind?23u:19u;
        for(int y=0;y<32;y++)for(int x=0;x<32;x++)if(game_pixels[frame*1024u+y*32+x]) {
            if(x<ref_bounds[kind][0])ref_bounds[kind][0]=x;
            if(y<ref_bounds[kind][1])ref_bounds[kind][1]=y;
            if(x+1>ref_bounds[kind][2])ref_bounds[kind][2]=x+1;
            if(y+1>ref_bounds[kind][3])ref_bounds[kind][3]=y+1;
        }
    }
    init_scenery_assets();assert(scenery_assets_ready);
    init_dungeon_assets();assert(dungeon_assets_ready);
    init_reference_world();
    assert(GAME_MAX_DRAW_GEMS==20);
    // Keep slot95 alive while lower slots fill/free around the former cap20.
    reset();for(unsigned i=0;i<19;i++)game.gems[i]=(GameGem){(int16_t)(30+(i%10)*35),(int16_t)(30+(i/10)*40),1,0,0};
    game.gems[95]=(GameGem){580,300,1,0,0};unsigned visible[3];
    frame(0,0,1,0,0);visible[0]=target_drawn;
    game.gems[19]=(GameGem){380,80,1,0,0};frame(0,0,1,0,0);visible[1]=target_drawn;
    game.gems[0].value=0;frame(0,0,1,0,0);visible[2]=target_drawn;
    printf("SLOT95 visibility=%u,%u,%u value=%u cap=%u\n",visible[0],visible[1],visible[2],game.gems[95].value,GAME_MAX_DRAW_GEMS);
#ifdef EXPECT_BASELINE
    assert(visible[0] && !visible[1] && visible[2] && game.gems[95].value==1);
    puts("BASELINE GEM FLICKER REPRODUCED: uncollected high slot disappears/reappears as low slots are reused");return 0;
#endif
    assert(visible[0] && visible[1] && visible[2]);
    reset();populate(712,524);
    for(unsigned n=0;n<180;n++) {
        game.ticks=n;
        for(unsigned i=0;i<20;i++)game.gems[i].value=(uint16_t)((n/3+i)%3?1:0);
        int cx=712,cy=524;if(n>=60 && n<120){cx+=((int)n-60)*3;cy+=((int)n-60);}
        if(n>=120){cx=1024+(int)(n-120);cy=680;}
        frame(cx,cy,1,n%4u?0:n+1u,1);
    }
    reset();populate(712,524);for(unsigned n=0;n<12;n++){game.ticks=n;frame(712,524,1,0,1);}
    // Repeated alpha draws while paused must not brighten alternating pages.
    for(unsigned n=0;n<12;n++)frame(712,524,0,n%3u?0:7,1);
    for(unsigned n=0;n<8;n++){game.ticks++;frame(712,524,1,0,1);}
    // Expiry/pickup of every slot erases both pages, including slot95.
    for(unsigned i=0;i<GAME_MAX_GEMS;i++)game.gems[i].value=0;
    for(unsigned n=0;n<4;n++)frame(712,524,1,0,1);
    reset();populate(0,0);
    game.gems[95]=(GameGem){0,0,60000,1,0};
    for(unsigned n=0;n<4;n++)frame(0,0,1,0,1);
    game.gems[95]=(GameGem){GAME_WORLD_WIDTH-1,GAME_WORLD_HEIGHT-1,1,0,0};
    for(unsigned n=0;n<4;n++)frame(1424,1048,1,0,1);
    reset();populate(712,524);for(unsigned i=0;i<GAME_MAX_GEMS;i++)game.gems[i].kind=1;
    for(unsigned n=0;n<8;n++)frame(712,524,1,n%2?3:0,1);
    assert(max_gem_commands==20);
    printf("GEM FLICKER TESTS PASSED: %u frames; max_gem_commands=%u; stable20 selection from 96 slots, low-slot reuse, both pages, original alpha/key pixels, camera/clipping, foreground restore, pause/resume, pickup/empty/high95, gameplay data unchanged\n",frames,max_gem_commands);
    return 0;
}
'''
label='baseline'if args.baseline_view else'current'
(OUT/f'gem_flicker_{label}.c').write_text(code)
env=dict(os.environ);env['PATH']=str(CC.parent)+os.pathsep+env.get('PATH','')
commands=[([CC,'-std=c99','-O2','-Wall','-Wextra','-Werror','-Isoftware',*(['-DEXPECT_BASELINE']if args.baseline_view else[]),OUT/f'gem_flicker_{label}.c','software/survivor_game.c','-o',OUT/f'gem_flicker_{label}.exe'],'build'),([OUT/f'gem_flicker_{label}.exe'],'run')]
for command,phase in commands:
    r=subprocess.run(list(map(str,command)),cwd=ROOT,env=env,capture_output=True,text=True)
    output=r.stdout+r.stderr;(ROOT/f'reports/gem_flicker_{label}_{phase}.log').write_text(output)
    print(output,flush=True)
    if r.returncode:raise SystemExit(r.returncode)
