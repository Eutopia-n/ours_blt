"""Compare real pre-integration/game batch C frames, then replay C DMA lists in RTL.

Requires check_reference_ui.py's generated host scaffolding. Host clocks and
modeled renderer cycles are not board FPS or MAX60 measurements.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,struct,subprocess
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'software/build/game_batch';OUT.mkdir(parents=True,exist_ok=True)
p=argparse.ArgumentParser();p.add_argument('--cc',type=Path,default=Path('C:/mingw64/bin/gcc.exe'))
p.add_argument('--modelsim',type=Path,default=Path('D:/modelsim/win64'))
p.add_argument('--before-view',type=Path,help='Prior game_view.h for identical-scene hardware comparisons')
a=p.parse_args()
inputs=('software/game_view.h','software/game_frame_bounds.h','software/game_batch.h','software/survivor_game.h','software/survivor_game.c','software/render.h','rtl/fill_engine.v',
        'rtl/render_batch.v','rtl/render_subsystem.v','software/game_assets.h','software/reference_game_ui.h',
        'tools/check_game_batch.py')
hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in inputs}
template=(ROOT/'software/build/reference_ui_check/check.c').read_text(encoding='utf-8').split('\nint main(void){',1)[0]
template=template.replace('static uint32_t reference_mmio_read(uint32_t a){(void)a;return 0;}',
    'static uint32_t reference_mmio_read(uint32_t a){return a==GFX_BASE+GFX_CAPABILITIES ? test_caps:0;}')
template=template.replace('cpu_fill_pixels+=(uint64_t)w*h;',
    'cpu_fill_pixels+=(uint64_t)w*h;if(!in_gpu)test_cpu_pixels+=(uint64_t)w*h;')
template=template.replace('(void)hw;cpu_fill(x,y,w,h,c);',
    'if(hw){++single_draws;++in_gpu;}cpu_fill(x,y,w,h,c);if(hw)--in_gpu;')
template=template.replace('uint16_t key,uint32_t flags){\n    for',
    'uint16_t key,uint32_t flags){\n    if(!in_gpu)++single_draws;\n    for',1)
start=template.index('int gfx_batch_submit(');end=template.index('int gfx_tile_submit(',start)
template=template[:start]+r'''
static void capture_begin(void) {
    if(!capture || capture_started)return;capture_started=1;
    char path[160];snprintf(path,sizeof(path),"software/build/game_batch/initial_%u.bin",capture_id);
    FILE *f=fopen(path,"wb");assert(f);
    fwrite((void*)(uintptr_t)FRAMEBUFFER,1,2*FRAMEBUFFER_BYTES,f);fclose(f);
    snprintf(path,sizeof(path),"software/build/game_batch/assets_%u.bin",capture_id);f=fopen(path,"wb");assert(f);
    fwrite((void*)(uintptr_t)ASSET_BASE,1,ASSET_BYTES,f);fclose(f);
}
static void capture_end(void) {
    if(!capture)return;
    char path[160];snprintf(path,sizeof(path),"software/build/game_batch/gpu_expected_%u.bin",capture_id);
    FILE *f=fopen(path,"wb");assert(f);
    fwrite((void*)(uintptr_t)FRAMEBUFFER,1,2*FRAMEBUFFER_BYTES,f);fclose(f);
}
int gfx_batch_submit(uint32_t address,uint32_t count){
    assert(!(address&31u)&&count<=512);capture_begin();++submissions;mixed_commands+=count;
    const GfxBatchCommand *list=(void*)(uintptr_t)address;
    if(capture){uint32_t h[6]={2,count,0,0,0,0};fwrite(h,4,6,capture);fwrite(list,32,count,capture);}
    ++in_gpu;
    for(uint32_t i=0;i<count;++i){
        const GfxBatchCommand *c=&list[i];uint32_t d=c->destination-draw_buffer;
        assert(c->destination>=draw_buffer && d<FRAMEBUFFER_BYTES && !c->reserved0&&!c->reserved1);
        unsigned w=c->extent&65535,h=c->extent>>16;assert(d/1280+h<=480 && (d%1280)/2+w<=640);
        if((c->control&3)==0)cpu_fill((d%1280)/2,d/1280,w,h,c->colors);
        else {assert((c->control&3)==2);
            blend_image(c->source,c->source_stride,(d%1280)/2,d/1280,w,h,
                        (c->control>>8)&255,c->colors>>16,(c->control>>2)&3);}
    }
    --in_gpu;capture_end();return 0;
}
int gfx_positions_submit(uint32_t source,uint32_t side,uint32_t address,uint32_t count,uint8_t alpha,uint16_t key,uint32_t flags){
    assert(!key&&count<=4096);capture_begin();++submissions;position_objects+=count;
    const uint32_t *list=(void*)(uintptr_t)address;
    if(capture){uint32_t h[6]={3,count,source,side,alpha,flags};fwrite(h,4,6,capture);fwrite(list,4,count,capture);}
    ++in_gpu;
    for(uint32_t i=0;i<count;++i){uint32_t d=list[i]-draw_buffer;
        assert(list[i]>=draw_buffer && d/1280+side<=480 && (d%1280)/2+side<=640);
        blend_image(source,side*2,(d%1280)/2,d/1280,side,side,alpha,key,flags);}
    --in_gpu;capture_end();return 0;
}
''' +template[end:]
template='#include <stdint.h>\n#include <stdio.h>\nstatic uint32_t test_caps,in_gpu,single_draws,submissions,mixed_commands,position_objects,capture_started,capture_id;\nstatic uint64_t test_cpu_pixels;static FILE *capture;\n'+template
main=r'''
static uint8_t expected_frame[2*FRAMEBUFFER_BYTES],front_before[FRAMEBUFFER_BYTES];
static void verify_zone_art(void) {
    assert(game_upgrade_icon(6)==GAME_ART_RELIC_RUNE);
    assert(game_upgrade_icon(8)==GAME_ART_RELIC_CIRCLE);
    SurvivorGame g;
    game_reset(&g,1);
    g.x=128*256;g.y=120*256; // Match the zero camera passed to the renderer.
    g.chest_state=CHEST_OPEN;
    g.relic_zones[0].until=90;
    const int centres[][2]={{320,240},{GAME_X_MIN+6,240},{GAME_X_MAX-2,240},
                           {320,GAME_Y_MIN+3},{320,GAME_Y_MAX-2}};
    draw_buffer=FRAMEBUFFER;
    uint16_t *pixels=(uint16_t*)(uintptr_t)draw_buffer;
    const unsigned ticks[]={0,31,48},alphas[]={80,235,155};
    for(unsigned slot=0;slot<2;++slot)for(unsigned phase=0;phase<3;++phase) {
        int side=slot==0 ? 48:24;
        g.relic=slot==0 ? RELIC_ICE:RELIC_DECOY;
        g.ticks=ticks[phase];
        unsigned source=slot==0 ? GAME_ART_RELIC_RUNE:GAME_ART_RELIC_CIRCLE;
        const uint16_t *art=(const uint16_t*)(uintptr_t)(GAME_ASSET_BASE+source*2048u);
        for(unsigned c=0;c<5;++c) {
            int left=centres[c][0]-side/2,top=centres[c][1]-side/2;
            g.relic_zones[0].x=(int16_t)(centres[c][0]-GAME_X_MIN);
            g.relic_zones[0].y=(int16_t)(centres[c][1]-GAME_Y_MIN);
            memset(pixels,0,FRAMEBUFFER_BYTES);
            game_batch_begin();
            assert(game_draw_relics(&g,game_camera_x(&g),game_camera_y(&g))==1u);
            game_batch_end();
            for(int y=0;y<480;++y)for(int x=0;x<640;++x) {
                uint16_t expected=0;
                if(x>=GAME_X_MIN && x<GAME_X_MAX && y>=GAME_Y_MIN && y<GAME_Y_MAX &&
                   x>=left && x<left+side && y>=top && y<top+side) {
                    unsigned u=(unsigned)((x-left+0.5)*32/side);
                    unsigned v=(unsigned)((y-top+0.5)*32/side);
                    expected=blend565(art[v*32+u],0,alphas[phase]);
                }
                assert(pixels[y*640+x]==expected);
            }
        }
    }
    puts("RELIC ART PASSED: fixed 48x48 ice rune and 24x24 decoy circle; alpha pulse and four-edge clipping");
}
static void verify_enemy_sizes(void) {
    GameEnemy enemy={0};
    const unsigned fixed_sides[]={24,32,24,32,40};
    for(unsigned kind=0;kind<5;++kind){
        enemy.kind=(uint8_t)kind;
        for(unsigned hp=1;hp<=255;++hp){
            enemy.max_hp=(uint8_t)hp;
            enemy.hp=enemy.max_hp;
            assert(game_enemy_side(&enemy)==fixed_sides[kind]);
            enemy.hp=1;
            assert(game_enemy_side(&enemy)==fixed_sides[kind]);
        }
    }
    const unsigned ids[]={16,17,18,24,25,26,27,28,29,30};
    const int locations[][2]={{320,240},{GAME_X_MIN-10,200},{GAME_X_MAX+10,200},
                             {320,GAME_Y_MIN-10},{320,GAME_Y_MAX+10},{GAME_X_MAX+20,200}};
    draw_buffer=FRAMEBUFFER;
    uint16_t *pixels=(uint16_t*)(uintptr_t)draw_buffer;
    for(unsigned side=24;side<=40;side+=8)for(unsigned i=0;i<10;++i){
        unsigned frame=game_enemy_frame(i%5,0,i/5,side);
        const uint16_t *original=(const uint16_t*)(uintptr_t)(GAME_ASSET_BASE+ids[i]*2048);
        const uint16_t *asset=(const uint16_t*)(uintptr_t)(
            side==32 ? GAME_ASSET_BASE+ids[i]*2048:
            (side==24 ? GAME_ENEMY_SIZE_BASE:GAME_ENEMY_LARGE_BASE)+i*side*side*2);
        for(unsigned y=0;y<side;++y)for(unsigned x=0;x<side;++x){
            unsigned ox=(unsigned)((x+0.5)*32/side),oy=(unsigned)((y+0.5)*32/side);
            assert(asset[y*side+x]==original[oy*32+ox]);
        }
        for(unsigned n=0;n<6;++n){
            int cx=locations[n][0],cy=locations[n][1],left=cx-(int)side/2,top=cy-(int)side/2;
            memset(pixels,0,FRAMEBUFFER_BYTES);
            game_batch_begin();
            unsigned visible=game_sprite(frame,cx,cy,255);
            game_batch_end();
            assert(n!=0 || visible==1);
            assert(n!=5 || visible==0);
            for(int y=0;y<480;++y)for(int x=0;x<640;++x){
                uint16_t want=0;
                if(x>=GAME_X_MIN && x<GAME_X_MAX && y>=GAME_Y_MIN && y<GAME_Y_MAX &&
                   x>=left && x<left+(int)side && y>=top && y<top+(int)side)
                    want=asset[(y-top)*side+x-left];
                assert(pixels[y*640+x]==want);
            }
        }
    }
    puts("ENEMY SIZES PASSED: 24/32/40, fixed by kind across HP values; exact atlas texels and 180 clipped frames");
}
static void fixture(SurvivorGame *g,unsigned scenario) {
    game_reset(g,0x6d2b79f5);g->state=GAME_PLAY;g->orbit_count=scenario ? 4:0;
    unsigned enemies=scenario==0?0:scenario==1?1:scenario==2?20:scenario==5||scenario==6?0:GAME_MAX_ENEMIES;
    unsigned bolts=scenario==0?0:scenario==1?1:scenario==2?40:scenario==10?3:GAME_MAX_BOLTS;
    unsigned gems=scenario==0?0:scenario==1?1:scenario==2?32:scenario==5||scenario==6?0:96;
    int cx=game_camera_x(g),cy=game_camera_y(g);
    for(unsigned i=0;i<enemies;++i){GameEnemy *e=&g->enemies[i];
        int x=8+(int)((i*37)%624),y=80+(int)((i*23)%360);
        if(scenario==4){x=310+i%4;y=260+i%5;}
        if(scenario==9&&i%3==0){x=i%2?0:640;y=i%2?75:445;}
        e->x=(cx+x-8)*32;e->y=(cy+y-80)*32;
        e->kind=i%5;e->max_hp=(uint8_t)(6+i%5*6);e->hp=e->max_hp;
        e->flash=scenario==7||i%3==0?100:0;
        if(scenario==10){e->kind=i%8u==0 ? 4u:i%4u;e->flash=i%8u==1 ? 100u:0u;}
    }
    for(unsigned i=0;i<bolts;++i){GameBolt *b=&g->bolts[i];
        int x=8+(int)((i*53)%624),y=80+(int)((i*31)%360);
        if(scenario==4){x=310+i%3;y=260+i%3;}
        if(scenario==9){x=i%4==0?8:i%4==1?631:i%4==2?7:632;y=i%2?80:439;}
        b->x=(cx+x-8)*32;b->y=(cy+y-80)*32;b->life=90;b->pierce=scenario==5?0:scenario==6?2:i%3?1:0;
    }
    for(unsigned i=0;i<gems;++i){GameGem *gem=&g->gems[i];gem->value=i%3==0?10:i%3==1?5:1;gem->kind=i%11==0;
        gem->x=(int16_t)(cx+(i*47)%624);gem->y=(int16_t)(cy+(i*29)%360);}
    g->enemy_count=enemies;g->bolt_count=bolts;g->gem_count=gems;
    if(scenario==3 || scenario==5 || scenario==6) {
        g->chest_state=CHEST_OPEN;
        g->relic=scenario==3 ? RELIC_ICE:scenario==5 ? RELIC_SHIELD:RELIC_DECOY;
        g->relic_charge=GAME_SHIELD_PICKUPS;
        g->relic_zones[0]=(GameRelicZone){(int16_t)(cx+175),(int16_t)(cy+140),120};
        g->relic_zones[1]=(GameRelicZone){(int16_t)(cx+211),(int16_t)(cy+142),120};
    }
    if(scenario==3) {
        g->crown[0].slot=5;g->crown[0].fire_at=24;
        g->crown[1].slot=10;
        g->crown[1].bolt=(GameBolt){(cx+300)*32,(cy+175)*32,0,0,32,12,0};
    }
}
int main(int argc,char **argv){
    assert(argc==2);int mode=atoi(argv[1]),baseline=mode==1;test_caps=baseline?0:mode==2?1:7;
    assert(VirtualAlloc((void*)(uintptr_t)(ASSET_BASE-65536),ASSET_BYTES+131072,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    assert(VirtualAlloc((void*)(uintptr_t)(FRAMEBUFFER-65536),2*FRAMEBUFFER_BYTES+131072,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    FILE *rom=fopen("assets/ui/magic_book_v5/runtime/reference/ui_stream.bin","rb");assert(rom);
    assert(fread(book_native_rom,1,sizeof(book_native_rom),rom)>0);fclose(rom);
    init_game_assets();
    verify_enemy_sizes();
    verify_zone_art();
    FILE *frames=fopen("software/build/game_batch/baseline_frames.bin",baseline?"wb":"rb");assert(frames);
    unsigned compared=0,seen_positions=0,seen_mixed=0;
    for(unsigned scenario=0;scenario<12;++scenario){
        memset((void*)(uintptr_t)ASSET_BASE,0,ASSET_BYTES);
        for(unsigned j=0;j<2*FRAMEBUFFER_BYTES;++j)((uint8_t*)(uintptr_t)FRAMEBUFFER)[j]=(uint8_t)((j*37+scenario*11)^(j>>8));
        book_assets_ready=0;book_init_assets();book_load(BOOK_GAME_ORNAMENT);init_game_assets();
        game_hud_pages=0;memset(game_hud_number_valid,0,sizeof(game_hud_number_valid));
        memset(game_hud_bar_valid,0,sizeof(game_hud_bar_valid));memset(game_page_valid,0,sizeof(game_page_valid));
        memset(game_page_playing,0,sizeof(game_page_playing));memset(game_dirty_valid,0,sizeof(game_dirty_valid));
        memset(game_gem_selected,0,sizeof(game_gem_selected));game_ui_key[0]=game_ui_key[1]=0xffffffff;
        SurvivorGame g;fixture(&g,scenario);game_max60.maximum=37;
        for(unsigned frame=0;frame<8;++frame){
            draw_buffer=frame&1?FRAMEBUFFER_B:FRAMEBUFFER;
            g.ticks=frame*7;g.walk_frame=frame&3;g.direction=frame&3;g.invincible=frame%3==1?12:0;
            if(scenario==8)g.state=frame<2?GAME_PLAY:frame<5?GAME_PAUSED:GAME_PLAY;
            if(scenario==11){static const unsigned states[]={GAME_PLAY,GAME_PAUSED,GAME_PAUSED,GAME_PLAY,GAME_UPGRADE,GAME_PLAY,GAME_OVER,GAME_PLAY};g.state=states[frame];g.options[0]=0;g.options[1]=1;g.options[2]=2;}
            if(scenario==10)game_tick(&g,frame&1?1:2);
            memcpy(front_before,(void*)(uintptr_t)(frame&1?FRAMEBUFFER:FRAMEBUFFER_B),FRAMEBUFFER_BYTES);
            submissions=mixed_commands=position_objects=single_draws=0;test_cpu_pixels=0;
            if(frame==1 && ((mode==0 && (scenario==3 || scenario==5 || scenario==6 || scenario==10)) ||
                            (mode==3 && (scenario==3 || scenario==10)))) {
                char path[160];
                capture_id=mode==3 ? (scenario==3 ? 4:5):scenario==3 ? 0:scenario==5 ? 1:scenario==6 ? 2:3;
                snprintf(path,sizeof(path),"software/build/game_batch/calls_%u.bin",capture_id);
                capture=fopen(path,"wb");assert(capture);capture_started=0;
            }
            unsigned drawn=game_draw(&g,60,123,0,0);
            if(capture){fclose(capture);capture=0;}
            assert(!memcmp(front_before,(void*)(uintptr_t)(frame&1?FRAMEBUFFER:FRAMEBUFFER_B),FRAMEBUFFER_BYTES));
            if(baseline)assert(fwrite((void*)(uintptr_t)FRAMEBUFFER,1,2*FRAMEBUFFER_BYTES,frames)==2*FRAMEBUFFER_BYTES);
            else {
                assert(fread(expected_frame,1,sizeof(expected_frame),frames)==sizeof(expected_frame));
                if(memcmp(expected_frame,(void*)(uintptr_t)FRAMEBUFFER,sizeof(expected_frame))){
                    for(unsigned j=0;j<sizeof(expected_frame);++j)if(expected_frame[j]!=((uint8_t*)(uintptr_t)FRAMEBUFFER)[j]){
                        fprintf(stderr,"GAME mismatch scenario=%u frame=%u byte=%u got=%02x expected=%02x\n",scenario,frame,j,((uint8_t*)(uintptr_t)FRAMEBUFFER)[j],expected_frame[j]);return 3;}}
                ++compared;seen_positions+=position_objects!=0;seen_mixed+=mixed_commands!=0;
            }
            printf("FRAME %u %u %u %u %u %u %u %llu\n",scenario,frame,drawn,single_draws,submissions,mixed_commands,position_objects,(unsigned long long)test_cpu_pixels);
        }
    }
    fclose(frames);
    if(!baseline){assert(compared==96&&(!(test_caps&2)||seen_positions)&&seen_mixed);printf("GAME BATCH C PASSED frames=%u positions_frames=%u mixed_frames=%u; equal single-command pixels, both pages and order\n",compared,seen_positions,seen_mixed);}
    return 0;
}
'''
env=dict(os.environ,PATH=str(a.cc.parent)+os.pathsep+os.environ.get('PATH',''))
def run(cmd,label):
 r=subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,capture_output=True,text=True,errors='replace')
 (ROOT/f'reports/game_batch_{label}.log').write_text(r.stdout+r.stderr,encoding='utf-8')
 if r.returncode:print(r.stdout+r.stderr);r.check_returncode()
 return r.stdout+r.stderr
for variant,mode,source in (('baseline',1,ROOT/'software/game_view.h'),('current',0,ROOT/'software/game_view.h'),
                            ('before_cache',3,a.before_view)):
 if source is None:continue
 view=source.read_text(encoding='utf-8')
 view=re.sub(r'__asm__ volatile\s*\(.*?\);','',view,flags=re.S)
 (OUT/f'view_{variant}.h').write_text(view,encoding='utf-8')
 c=OUT/f'{variant}.c';c.write_text(template.replace('"game_view_host.h"',f'"view_{variant}.h"')+main,encoding='utf-8')
 binary=OUT/f'{variant}.exe'
 run([a.cc,'-std=c99','-O2','-Isoftware',c,'software/survivor_game.c','-o',binary],variant+'_compile')
 log=run([binary,str(mode)],variant)
 if variant=='current':print(log.splitlines()[-1],flush=True)
compat=run([OUT/'current.exe','2'],'batch_only');print(compat.splitlines()[-1],flush=True)

def translate(address):
 if 0x10000000<=address<0x10100000:return address-0x10000000+0x01200000
 if 0x11000000<=address<0x11000000+1228800:return address-0x11000000+0x01000000
 assert address==0,address
 return 0
stream=[];requests=[]
fixture_count=6 if a.before_view else 4
for fixture in range(fixture_count):
 data=(OUT/f'calls_{fixture}.bin').read_bytes();at=0;frame_words=[];frame_requests=[]
 while at<len(data):
  mode,count,source,side,alpha,flags=struct.unpack_from('<6I',data,at);at+=24
  n=count*(8 if mode==2 else 1);words=list(struct.unpack_from('<'+'I'*n,data,at));at+=n*4
  if mode==2:
   for i in range(count):words[i*8]=translate(words[i*8]);words[i*8+1]=translate(words[i*8+1])
  else:source=translate(source);words=list(map(translate,words))
  frame_words.extend([mode,count,source,side,alpha,flags,*words]);frame_requests.append({'mode':mode,'count':count})
 stream.extend([len(frame_words),*frame_words]);requests.append(frame_requests)
 for name in ('initial','gpu_expected','assets'):
  b=(OUT/f'{name}_{fixture}.bin').read_bytes()
  (OUT/f'{name}_{fixture}.hex').write_text(''.join(f'{v:02x}\n' for v in b),encoding='ascii')
crowded_pixels=(OUT/'gpu_expected_0.bin').read_bytes()
for x,y in ((156,149),(308,255)): # Warning and travelling gold bolt at the top of the sprite layers.
    offset=614400+((y-3)*640+x-3)*2
    assert struct.unpack_from('<H',crowded_pixels,offset)[0]==0xfbe0,(x,y)
(OUT/'calls.hex').write_text(''.join(f'{v:08x}\n' for v in stream),encoding='ascii')
original=(ROOT/'sim/tb_render.sv').read_text();prefix=original[:original.index('    reg [31:0] status;\n    integer old_writes')]
prefix=prefix.replace('module tb_render;','module tb_game_batch;').replace('always #5 clk=~clk;','always #3.333333 clk=~clk;')
tail=r'''
    localparam LIST=32'h012b0000;
    reg [31:0] commands[0:__WORDS__-1],status;
    integer at=0,end_at,mode,count,source,side,alpha,flags,words,start_clock,frame_clock=0,start_ar,start_aw;
    always @(posedge clk)frame_clock++;
    initial begin
        for(integer j=0;j<MEM_BYTES;++j)mem[j]=0;
        $readmemh("software/build/game_batch/calls.hex",commands);
        repeat(10)@(negedge clk);reset=0;draw_base=BASE+PAGE_BYTES;write_reg(56,1);
        for(integer fixture=0;fixture<__FIXTURES__;fixture++)begin
        $readmemh($sformatf("software/build/game_batch/initial_%0d.hex",fixture),mem,0,2*PAGE_BYTES-1);
        $readmemh($sformatf("software/build/game_batch/assets_%0d.hex",fixture),mem,ASSET_BASE-BASE,MEM_BYTES-1);
        $readmemh($sformatf("software/build/game_batch/gpu_expected_%0d.hex",fixture),golden,0,2*PAGE_BYTES-1);
        // Use the same deterministic AXI delay sequence at each submission set.
        #1 rng=32'h7ba59e3d;
        start_clock=frame_clock;start_ar=read_bursts;start_aw=bursts;end_at=at+1+commands[at];at++;
        while(at<end_at)begin
            mode=commands[at];count=commands[at+1];source=commands[at+2];side=commands[at+3];alpha=commands[at+4];flags=commands[at+5];at+=6;
            words=count*(mode==2?8:1);
            for(integer i=0;i<words;++i)begin
                for(integer b=0;b<4;++b)mem[LIST-BASE+i*4+b]=commands[at+i][b*8+:8];
            end
            at+=words;
            if(mode==2)begin write_reg(52,LIST);write_reg(16,count);end
            else begin
                write_reg(52,source);write_reg(12,LIST);write_reg(16,count);write_reg(20,side);
                write_reg(76,side*2);write_reg(80,flags);write_reg(84,alpha);write_reg(88,0);
            end
            write_reg(8,mode);status=0;while((status&3)!=2)read_reg(4,status);
            if(status&4)$fatal(1,"Actual game DMA error %h",status);
            read_reg(120,status);if(status!=count)$fatal(1,"Actual game completion count");
        end
        for(integer j=0;j<2*PAGE_BYTES;++j)if(mem[j]!==golden[j])$fatal(1,"Actual game RTL pixel %0d got=%h expected=%h",j,mem[j],golden[j]);
        $display("GAME BATCH FIXTURE %0d cycles=%0d AR=%0d AW=%0d",fixture,frame_clock-start_clock,read_bursts-start_ar,bursts-start_aw);
        end
        $display("GAME BATCH RTL PASSED: 4 real C mixed/normal/piercing/crowded scenes, original pixels and front-page protection");$finish;
    end
    initial begin #1000000000;$fatal(1,"Game batch watchdog");end
endmodule
'''.replace('__WORDS__',str(len(stream))).replace('__FIXTURES__',str(fixture_count))
tb=OUT/'tb.sv';tb.write_text(prefix+tail,encoding='utf-8');lib='sim/work_game_batch'
if not (ROOT/lib).exists():run([a.modelsim/'vlib.exe',lib],'vlib')
run([a.modelsim/'vlog.exe','-sv','-work',lib,'rtl/sync_fifo.v','rtl/fill_engine.v','rtl/render_batch.v','rtl/tile_renderer.v',
     'rtl/ui_compositor.v','rtl/ui_asset_rom.v','rtl/render_regs.v','rtl/framebuffer_video.v','rtl/video_mode_measure.v','rtl/render_subsystem.v',tb],'vlog')
log=run([a.modelsim/'vsim.exe','-batch','-t','1ps','-lib',lib,'tb_game_batch','-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'run')
assert 'GAME BATCH RTL PASSED' in log and 'Errors: 0, Warnings: 0' in log,log[-3500:]
assert hashes=={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in inputs},'Game source changed during test'
old_frames=[list(map(int,line.split()[1:])) for line in (ROOT/'reports/game_batch_baseline.log').read_text().splitlines() if line.startswith('FRAME ')]
new_frames=[list(map(int,line.split()[1:])) for line in (ROOT/'reports/game_batch_current.log').read_text().splitlines() if line.startswith('FRAME ')]
assert len(old_frames)==len(new_frames)==96
for b,c in zip(old_frames,new_frames):assert b[:3]==c[:3]
report={'scope':'192 real-C complete-frame comparisons to single-command rendering, full/batch-only capabilities; exact atlas and clipping tests across 24/32/40; C lists replayed in modeled RTL',
        'source_sha256':hashes,'requests':requests[:4],'full_frame_cases':192,
        'enemy_sizes':{'sides':[24,32,40],'fixed_side_by_kind':[24,32,24,32,40],
                       'frames_per_side':10,'clipped_pixel_fixtures_per_capability':180},
        'zone_art':{'ice_side':48,'decoy_side':24,'ice':'static rune','decoy':'circle','alpha_samples':[80,235,155],'complete_frames_per_capability':30},
        'frame_fields':['scenario','frame','drawn','single_calls','batch_calls','mixed_commands','position_objects','CPU_fill_pixels'],
        'baseline_frames':old_frames,'current_frames':new_frames,
        'RTL':log[log.index('GAME BATCH RTL PASSED'):].splitlines()[0]}
if a.before_view:
    metrics={int(f):{'cycles':int(c),'AR':int(r),'AW':int(w)} for f,c,r,w in
             re.findall(r'GAME BATCH FIXTURE (\d+) cycles=(\d+) AR=(\d+) AW=(\d+)',log)}
    comparisons={name:{'before':metrics[before],'after':metrics[after]} for name,before,after in
                 (('mixed_full_pool',4,0),('crowd_three_bolts',5,3))}
    report['enemy_cache_comparison']={
        'before_view_sha256':hashlib.sha256(a.before_view.read_bytes()).hexdigest(),
        'scope':'same production draws and framebuffer pixels; RTL AXI model, excludes CPU and scanout timing',
        'scenes':comparisons}
    print(json.dumps(comparisons,indent=2),flush=True)
(ROOT/'reports/game_batch.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(report['RTL'],flush=True)
