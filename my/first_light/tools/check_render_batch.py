"""Real C driver/benchmark lists -> scalar pixels -> shared-bus RTL regression.

Host timing is not board FPS. RTL reuses the existing randomized AXI memory
model; new cases cover mixed order, errors, empty lists and HDMI contention.
"""
from pathlib import Path
import argparse,os,re,struct,subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'software/build/render_batch';OUT.mkdir(parents=True,exist_ok=True)
p=argparse.ArgumentParser();p.add_argument('--cc',default='C:/mingw64/bin/gcc.exe')
p.add_argument('--modelsim',type=Path,default=Path('D:/modelsim/win64'));args=p.parse_args()
main=(ROOT/'software/main.c').read_text(encoding='utf-8')
def function(name):
    m=re.search(r'^static [^;{]*\b'+name+r'\([^;{]*\)\s*\{|^int '+name+r'\([^;{]*\)\s*\{',main,re.M)
    assert m,name
    depth=0
    for t in re.finditer(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*|[{}]',main[m.end()-1:],re.S):
        if t[0]=='{':depth+=1
        if t[0]=='}':depth-=1
        if not depth:return main[m.start():m.end()-1+t.end()]
c=r'''
#include <windows.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "render.h"
static uint32_t draw_buffer=FRAMEBUFFER_B,clock_value,registers[34],writes,submits,capture;
static uint32_t bad_completion,forced_error,bench_batch_size,sprite_count=513,bench_size_index=1;
static uint32_t bench_tile_cursor[180];
static uint32_t bench_strategy_count,bench_strategy_size,bench_strategy_trials,bench_strategy_peak[2],bench_strategy_tile;
static uint32_t tile_cost,position_cost,positions_drawn;
static const uint8_t bench_sizes[]={4,16,24,32};
static const uint32_t bench_sources[]={ASSET_BASE+0x2e80,ASSET_BASE+0x2800,ASSET_BASE+0x2a00,ASSET_BASE+0x3000};
static uint16_t scalar[640*480];
static uint32_t draw_page(void){return draw_buffer==FRAMEBUFFER_B;}
static uint32_t cycle_now(void){return clock_value+=100;}
static void publish_pixels(void){}
static void paint(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t color,uint32_t hw){
    (void)hw;uint16_t *p=(void*)(uintptr_t)draw_buffer;
    for(unsigned row=y;row<y+h;++row)for(unsigned col=x;col<x+w;++col)p[row*640+col]=color;
}
static void fail(const char *s){fprintf(stderr,"%s\n",s);exit(3);}
static uint16_t blend(uint16_t f,uint16_t b,unsigned a,unsigned flags,uint16_t key){
    if((flags&2)&&f==key)return b;if(!(flags&1))return f;
    unsigned r=((f>>11)*a+(b>>11)*(255-a)+127)/255;
    unsigned g=(((f>>5)&63)*a+((b>>5)&63)*(255-a)+127)/255;
    unsigned bl=((f&31)*a+(b&31)*(255-a)+127)/255;return (r<<11)|(g<<5)|bl;
}
static void execute(uint32_t source,uint32_t dst,uint32_t extent,uint32_t pitch,uint32_t colors,uint32_t ctrl){
    assert((ctrl&3)==2);
    for(unsigned y=0;y<(extent>>16);++y)for(unsigned x=0;x<(extent&65535);++x){
        uint16_t f=*(uint16_t*)(uintptr_t)(source+y*pitch+x*2);
        uint16_t *b=(void*)(uintptr_t)(dst+y*1280+x*2);
        *b=blend(f,*b,(ctrl>>8)&255,(ctrl>>2)&3,colors>>16);
    }
}
static uint32_t host_read(uint32_t address){return registers[(address-GFX_BASE)/4];}
static void host_write(uint32_t address,uint32_t value){
    unsigned r=address-GFX_BASE;++writes;registers[r/4]=value;
    if(r!=GFX_COMMAND)return;
    if(value==1){
        execute(registers[GFX_SRC/4],registers[GFX_DST/4],registers[GFX_WIDTH/4]|(registers[GFX_HEIGHT/4]<<16),
            registers[GFX_SRC_STRIDE/4],registers[GFX_COLOR_KEY/4]<<16,
            registers[GFX_OPERATION/4]|(registers[GFX_BLEND_CTRL/4]<<2)|(registers[GFX_ALPHA/4]<<8));
    }else if(value==3){
        clock_value+=position_cost;
        unsigned side=registers[GFX_HEIGHT/4],n=registers[GFX_WIDTH/4];
        positions_drawn+=n;
        const uint32_t *list=(void*)(uintptr_t)registers[GFX_DST/4];
        for(unsigned i=0;i<n;++i)execute(registers[GFX_SRC/4],list[i],side|(side<<16),side*2,
            registers[GFX_COLOR_KEY/4]<<16,2|(registers[GFX_BLEND_CTRL/4]<<2)|(registers[GFX_ALPHA/4]<<8));
        registers[GFX_BATCH_COMPLETED/4]=bad_completion?n-1:n;
    }else if(value==4){
        clock_value+=tile_cost;
        unsigned side=registers[GFX_WIDTH/4];uint16_t *target=(void*)(uintptr_t)draw_buffer;
        const uint32_t *offsets=(void*)(uintptr_t)registers[GFX_DST/4];
        const uint32_t *list=(void*)(uintptr_t)(registers[GFX_DST/4]+GFX_TILE_POSITIONS);
        const uint16_t *texture=(void*)(uintptr_t)registers[GFX_SRC/4];
        assert(offsets[0]==0&&offsets[180]==registers[GFX_HEIGHT/4]);
        for(unsigned y=152;y<408;++y)for(unsigned x=0;x<640;++x)target[y*640+x]=(uint16_t)registers[GFX_COLOR/4];
        for(unsigned b=0;b<180;++b){
            assert(offsets[b]<=offsets[b+1]);unsigned tx=(b%20)*32,ty=(b/20+4)*32;
            for(unsigned i=offsets[b];i<offsets[b+1];++i){
                unsigned x=list[i]&65535,y=list[i]>>16;
                for(unsigned row=0;row<side;++row)for(unsigned col=0;col<side;++col)
                    if(x+col>=tx&&x+col<tx+32&&y+row>=ty&&y+row<ty+32){
                        uint16_t *p=&target[(y+row)*640+x+col];
                        *p=blend(texture[row*side+col],*p,registers[GFX_ALPHA/4],registers[GFX_BLEND_CTRL/4],registers[GFX_COLOR_KEY/4]);
                    }
            }
        }
        registers[GFX_BATCH_COMPLETED/4]=bad_completion?offsets[180]-1:offsets[180];
    }else{
        assert(value==2);uint32_t n=registers[GFX_WIDTH/4];
        const GfxBatchCommand *list=(void*)(uintptr_t)registers[GFX_SRC/4];
        if(capture){
            char name[160];snprintf(name,sizeof(name),"software/build/render_batch/native_list_%u.hex",submits);
            FILE *f=fopen(name,"wb");assert(f);
            const uint32_t *words=(void*)list;for(unsigned i=0;i<n*8;++i)fprintf(f,"%08x\n",words[i]);fclose(f);
        }
        for(unsigned i=0;i<n;++i){assert(!list[i].reserved0&&!list[i].reserved1);
            execute(list[i].source,list[i].destination,list[i].extent,list[i].source_stride,list[i].colors,list[i].control);}
        registers[GFX_BATCH_COMPLETED/4]=bad_completion?n-1:n;
    }
    ++submits;registers[GFX_STATUS/4]=forced_error?GFX_DONE|GFX_ERROR:GFX_DONE;
}
#define mmio_read host_read
#define mmio_write host_write
'''
for name in ('select_draw_page','wait_render','blend_image','gfx_batch_submit','gfx_positions_submit','gfx_tile_submit',
             'sprite_pixel_sized','bounce','sprite_seed','bench_batch_frame','bench_compact_frame','bench_tile_positions','bench_tile_frame','bench_render_frame'):
    c+='\n'+function(name)
c+=r'''
static void initialize(void){
    uint8_t *memory=(void*)(uintptr_t)FRAMEBUFFER;
    for(unsigned n=0;n<ASSET_BASE+ASSET_BYTES-FRAMEBUFFER;++n)memory[n]=(uint8_t)((n*73u)^(n>>8));
    for(unsigned v=0;v<4;++v){uint16_t *p=(void*)(uintptr_t)bench_sources[v];unsigned side=bench_sizes[v];
        for(unsigned y=0;y<side;++y)for(unsigned x=0;x<side;++x)p[y*side+x]=sprite_pixel_sized(side,y,x);}
    memset(registers,0,sizeof(registers));registers[GFX_CAPABILITIES/4]=GFX_CAP_BATCH;
    writes=submits=bench_batch_size=positions_drawn=0;
}
int main(void){
    assert(sizeof(GfxBatchCommand)==32);
    assert(VirtualAlloc((void*)(uintptr_t)FRAMEBUFFER,ASSET_BASE+ASSET_BYTES-FRAMEBUFFER,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    initialize();
    for(unsigned n=0;n<sprite_count;++n){unsigned seed=sprite_seed(n),size=16,frame=37;
        unsigned x=8+bounce((seed&65535u)+frame*(1+((seed>>16)&7u)),632u-size);
        unsigned y=160+bounce((seed>>16)+frame*(1+((seed>>24)&3u)),240u-size);
        assert(!blend_image(bench_sources[1],size*2,x,y,size,size,128,0,3));}
    memcpy(scalar,(void*)(uintptr_t)draw_buffer,sizeof(scalar));unsigned single_writes=writes,single_submits=submits;
    initialize();capture=1;bench_batch_frame(37);capture=0;
    assert(!memcmp(scalar,(void*)(uintptr_t)draw_buffer,sizeof(scalar)));
    assert(single_submits==513&&submits==2&&single_writes==6156&&writes==8);
    printf("BATCH C DRIVER PASSED: 513 actual benchmark Sprites; same complete scalar framebuffer; submissions %u->%u, APB writes %u->%u (host IO model, not board FPS).\n",single_submits,submits,single_writes,writes);
    FILE *f=fopen("software/build/render_batch/native_expected.bin","wb");assert(f);fwrite(scalar,1,sizeof(scalar),f);fclose(f);
    f=fopen("software/build/render_batch/native_assets.bin","wb");assert(f);fwrite((void*)(uintptr_t)(ASSET_BASE+0x2800),1,0x1000,f);fclose(f);
    unsigned cases=0;static const unsigned loads[]={0,1,7,512,513,1025};
    for(unsigned v=0;v<4;++v)for(unsigned page=0;page<2;++page)for(unsigned k=0;k<6;++k){
        draw_buffer=page?FRAMEBUFFER_B:FRAMEBUFFER;sprite_count=loads[k];bench_size_index=v;initialize();
        for(unsigned n=0;n<sprite_count;++n){unsigned seed=sprite_seed(n),side=bench_sizes[v],frame=91;
            unsigned x=8+bounce((seed&65535u)+frame*(1+((seed>>16)&7u)),632u-side);
            unsigned y=160+bounce((seed>>16)+frame*(1+((seed>>24)&3u)),240u-side);
            assert(!blend_image(bench_sources[v],side*2,x,y,side,side,128,0,3));}
        memcpy(scalar,(void*)(uintptr_t)draw_buffer,sizeof(scalar));initialize();bench_batch_frame(91);
        assert(!memcmp(scalar,(void*)(uintptr_t)draw_buffer,sizeof(scalar)));
        assert(submits==(sprite_count+511)/512);++cases;
    }
    printf("BATCH BENCH CASES PASSED: %u complete scalar-frame comparisons; four sizes, both pages, loads 0/1/7/512/513/1025 and multiple chunks.\n",cases);
    unsigned new_cases=0,tile_cases=0,packed_cases=0;static const unsigned new_loads[]={0,1,7,511,512,1024,2048,4096,4097};
    for(unsigned v=0;v<4;++v)for(unsigned page=0;page<2;++page)for(unsigned k=0;k<9;++k){
        draw_buffer=page?FRAMEBUFFER_B:FRAMEBUFFER;sprite_count=new_loads[k];bench_size_index=v;initialize();
        unsigned side=bench_sizes[v];uint16_t *pixels=(void*)(uintptr_t)draw_buffer;
        for(unsigned y=152;y<408;++y)for(unsigned x=0;x<640;++x)pixels[y*640+x]=0x0843;
        for(unsigned i=0;i<sprite_count;++i){unsigned seed=sprite_seed(i);
            unsigned x=8+bounce((seed&65535u)+37*(1+((seed>>16)&7u)),632u-side);
            unsigned y=160+bounce((seed>>16)+37*(1+((seed>>24)&3u)),240u-side);
            assert(!blend_image(bench_sources[v],side*2,x,y,side,side,128,0,3));}
        memcpy(scalar,pixels,sizeof(scalar));initialize();registers[GFX_CAPABILITIES/4]=7;
        if(bench_tile_frame(37))++tile_cases;
        else {
            for(unsigned y=152;y<408;++y)for(unsigned x=0;x<640;++x)pixels[y*640+x]=0x0843;
            bench_compact_frame(37);++packed_cases;
        }
        assert(!memcmp(scalar,pixels,sizeof(scalar)));++new_cases;
        if(v==3&&page==1&&sprite_count==1024){
            f=fopen("software/build/render_batch/native_tile_list.hex","wb");assert(f);
            const uint32_t *words=(void*)(uintptr_t)GFX_TILE_BASE;
            for(unsigned i=0;i<GFX_TILE_BYTES/4;++i)fprintf(f,"%08x\n",words[i]);fclose(f);
            f=fopen("software/build/render_batch/native_tile_expected.hex","wb");assert(f);
            for(unsigned i=0;i<640*480;++i)fprintf(f,"%04x\n",scalar[i]);fclose(f);
            f=fopen("software/build/render_batch/native_tile_texture.hex","wb");assert(f);
            words=(void*)(uintptr_t)bench_sources[v];for(unsigned i=0;i<512;++i)fprintf(f,"%08x\n",words[i]);fclose(f);
        }
    }
    printf("TILE/POSITIONS C PASSED: %u full-frame comparisons, %u tile and %u compact; actual firmware dispatch, bins, drivers, both pages, chunk boundary and count preserved.\n",new_cases,tile_cases,packed_cases);
    // Synthetic clocks validate selection only, never used as a speed claim.
    for(unsigned prefer=0;prefer<2;++prefer){
        draw_buffer=FRAMEBUFFER_B;sprite_count=1024;bench_size_index=3;initialize();registers[GFX_CAPABILITIES/4]=7;
        bench_strategy_count=0xffffffff;tile_cost=prefer?10000:50000;position_cost=prefer?50000:10000;
        for(unsigned frame=0;frame<10;++frame){
            memcpy(scalar,(void*)(uintptr_t)draw_buffer,sizeof(scalar));
            for(unsigned y=152;y<408;++y)for(unsigned x=0;x<640;++x)scalar[y*640+x]=0x0843;
            const uint16_t *texture=(void*)(uintptr_t)bench_sources[3];
            for(unsigned i=0;i<sprite_count;++i){unsigned s=sprite_seed(i);
                unsigned x=8+bounce((s&65535)+frame*(1+((s>>16)&7)),600);
                unsigned y=160+bounce((s>>16)+frame*(1+((s>>24)&3)),208);
                for(unsigned yy=0;yy<32;++yy)for(unsigned xx=0;xx<32;++xx){unsigned at=(y+yy)*640+x+xx;
                    scalar[at]=blend(texture[yy*32+xx],scalar[at],128,3,0);}}
            bench_render_frame(frame);assert(!memcmp(scalar,(void*)(uintptr_t)draw_buffer,sizeof(scalar)));
        }
        assert(bench_strategy_trials==8&&bench_strategy_tile==prefer);
    }
    tile_cost=position_cost=0;puts("BENCH SELECTOR PASSED: both synthetic cost orderings; 20 exact frames, no workload changes");
    // Oversized bins must fall back with all objects retained.
    sprite_count=20000;bench_size_index=3;initialize();registers[GFX_CAPABILITIES/4]=7;
    assert(!bench_tile_frame(37));paint(0,152,640,256,0x0843,1);bench_compact_frame(37);
    assert(submits==5&&positions_drawn==20000);puts("TILE OVERFLOW FALLBACK PASSED: 20000 objects, no tile truncation, five compact chunks");
    registers[GFX_STATUS/4]=0;registers[GFX_CAPABILITIES/4]=7;
    assert(gfx_positions_submit(bench_sources[3],8,GFX_BATCH_BASE,1,128,0,3)==-1);
    assert(gfx_positions_submit(bench_sources[3],32,GFX_BATCH_BASE+1,1,128,0,3)==-1);
    assert(gfx_positions_submit(bench_sources[3],32,GFX_BATCH_BASE,65536,128,0,3)==-1);
    assert(gfx_tile_submit(bench_sources[3]+1,32,GFX_TILE_BASE,1,128,0,3,0)==-1);
    assert(gfx_tile_submit(bench_sources[3],32,ASSET_BASE+ASSET_BYTES-32,1,128,0,3,0)==-1);
    registers[GFX_STATUS/4]=GFX_BUSY;
    assert(gfx_positions_submit(bench_sources[3],32,GFX_BATCH_BASE,1,128,0,3)==-2);
    assert(gfx_tile_submit(bench_sources[3],32,GFX_TILE_BASE,1,128,0,3,0)==-2);
    registers[GFX_STATUS/4]=GFX_SWAP_PENDING;
    assert(gfx_positions_submit(bench_sources[3],32,GFX_BATCH_BASE,1,128,0,3)==-2);
    registers[GFX_STATUS/4]=0;registers[GFX_CAPABILITIES/4]=0;
    assert(gfx_positions_submit(bench_sources[3],32,GFX_BATCH_BASE,1,128,0,3)==-5);
    assert(gfx_tile_submit(bench_sources[3],32,GFX_TILE_BASE,1,128,0,3,0)==-5);
    puts("TILE/POSITIONS GUARDS PASSED: source/list/size/count boundaries, busy/swap and capabilities");
    sprite_count=1;bench_size_index=0;initialize();bench_batch_frame(0);
    unsigned before=writes;
    assert(!gfx_batch_submit(1,0));assert(gfx_batch_submit(GFX_BATCH_BASE+4,1)==-1);
    assert(gfx_batch_submit(ASSET_BASE-32,1)==-1);assert(gfx_batch_submit(ASSET_BASE+ASSET_BYTES-32,2)==-1);
    assert(gfx_batch_submit(GFX_BATCH_BASE,65536)==-1&&writes==before);
    registers[GFX_STATUS/4]=GFX_BUSY;assert(gfx_batch_submit(GFX_BATCH_BASE,1)==-2);
    registers[GFX_STATUS/4]=GFX_SWAP_PENDING;assert(gfx_batch_submit(GFX_BATCH_BASE,1)==-2);
    registers[GFX_STATUS/4]=0;registers[GFX_CAPABILITIES/4]=0;assert(gfx_batch_submit(GFX_BATCH_BASE,1)==-1);
    registers[GFX_CAPABILITIES/4]=1;bad_completion=1;assert(gfx_batch_submit(GFX_BATCH_BASE,1)==-3);
    bad_completion=0;forced_error=1;assert(gfx_batch_submit(GFX_BATCH_BASE,1)==-3);
    puts("BATCH DRIVER GUARDS PASSED: empty, alignment, range/overflow, busy/swap ownership, capability, incomplete prefix and error status.");return 0;
}
'''
source=OUT/'native.c';source.write_text(c,encoding='utf-8')
env=dict(os.environ);env['PATH']=str(Path(args.cc).parent)+os.pathsep+env.get('PATH','')
def run(command,log):
    r=subprocess.run(list(map(str,command)),cwd=ROOT,env=env,capture_output=True,text=True,errors='replace')
    (ROOT/'reports'/log).write_text(r.stdout+r.stderr,encoding='utf-8')
    if r.returncode:print(r.stdout+r.stderr);r.check_returncode()
    return r.stdout+r.stderr
run([args.cc,'-std=c99','-O2','-Isoftware',source,'-o',OUT/'native.exe'],'render_batch_host_compile.log')
print(run([OUT/'native.exe'],'render_batch_host.log'),flush=True)
for name in ('native_expected','native_assets'):
    values=struct.unpack('<'+'H'*((OUT/(name+'.bin')).stat().st_size//2),(OUT/(name+'.bin')).read_bytes())
    (OUT/(name+'.hex')).write_text(''.join(f'{v:04x}\n' for v in values),encoding='ascii')
original=(ROOT/'sim/tb_render.sv').read_text()
prefix=original[:original.index('    reg [31:0] status;\n    integer old_writes')]
prefix=prefix.replace('module tb_render;','module tb_render_batch;').replace('always #5 clk=~clk;','always #3.333333 clk=~clk;')
prefix=prefix.replace('rlast=rb==rl;','rlast=(rb==rl) ^ (inject_bad_last && dut.batch_read_active && (rb==1 || rb==7));')
prefix=prefix.replace('if(rlast) reading=0;','if(rb>rl) reading=0;')
prefix=prefix.replace('reg inject_bg_error=0;','reg inject_bg_error=0,inject_bad_last=0,inject_tile_error=0,inject_prefetch_error=0,hold_prefetch_address=0;')
prefix=prefix.replace('arready=!reading && !rvalid && (force_bus_ready||rng[3]);',
    'arready=!reading && !rvalid && (force_bus_ready||rng[3]) && !(hold_prefetch_address && dut.fill.pf_state==dut.fill.PF_ADDR);')
prefix=prefix.replace('rresp=(inject_read_error ||','rresp=(inject_read_error || (inject_prefetch_error && dut.fill.pf_state==dut.fill.PF_DATA) || (inject_tile_error && dut.fill.cache_loading && dut.fill.state==dut.fill.C_RDATA) ||')
bench=OUT/'tb.sv';bench.write_text(prefix+(ROOT/'sim/tb_render_batch_cases.svh').read_text(),encoding='utf-8')
library='sim/work_batch'
if not (ROOT/library).exists():run([args.modelsim/'vlib.exe',library],'render_batch_vlib.log')
print(run([args.modelsim/'vlog.exe','-sv','-work',library,'rtl/sync_fifo.v','rtl/fill_engine.v','rtl/render_batch.v','rtl/tile_renderer.v',
           'rtl/ui_compositor.v','rtl/ui_asset_rom.v','rtl/render_regs.v','rtl/framebuffer_video.v',
           'rtl/video_mode_measure.v','rtl/render_subsystem.v',bench],'render_batch_vlog.log')[-500:],flush=True)
result=run([args.modelsim/'vsim.exe','-batch','-t','1ps','-lib',library,'tb_render_batch',
            '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'render_batch_run.log')
assert 'BATCH RTL PASSED' in result and 'Errors: 0, Warnings: 0' in result,result[-4000:]
print(result[-3500:])
