"""Same-workload RTL cycle/traffic comparison, not measured board MAX60.

Run once with --label before before editing RTL, then --label after
--compare reports/bench_throughput_before.json. No FPS or workload changes.
"""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--label',default='after')
p.add_argument('--profile',action='store_true',help='Record exclusive renderer phase cycles; no RTL changes')
p.add_argument('--firmware-motion',action='store_true',help='Use real benchmark frame-zero positions instead of fixed test overlaps')
p.add_argument('--compare',type=Path);p.add_argument('--modelsim',type=Path,default=Path('D:/modelsim/win64'));a=p.parse_args()
assert re.fullmatch('[a-z_]+',a.label)
out=ROOT/'software/build/bench_throughput';out.mkdir(parents=True,exist_ok=True)
source=(ROOT/'sim/tb_render.sv').read_text();prefix=source[:source.index('    reg [31:0] status;\n    integer old_writes')]
prefix=prefix.replace('module tb_render;','module tb_bench_throughput;').replace('always #5 clk=~clk;','always #3.333333 clk=~clk;')
tail=r'''
    localparam LIST=32'h012b0000;
    reg [31:0] status,cycles_value;
    integer old_reads,old_writes,source_bursts=0,source_words=0;
    reg profiling=0;
    always @(posedge clk)if(profiling && arvalid && arready && araddr<LIST && araddr>=ASSET_BASE)begin
        source_bursts=source_bursts+1;source_words=source_words+arlen+1;
    end
    task put(input [31:0] address,input [31:0] value);
        for(integer j=0;j<4;j=j+1)mem[address-BASE+j]=value[j*8+:8];
    endtask
    task measure(input integer side,count,ready,input bit key_enabled);
        integer seed,x,y,at,s,d;reg [15:0] pixel_value;
        begin
            force_bus_ready=ready;
            for(integer row=0;row<side;row=row+1)for(integer col=0;col<side;col=col+1)begin
                x=col*2-(side-1);if(x<0)x=-x;y=row*2-(side-1);if(y<0)y=-y;
                pixel_value=x+y>(side*13+15)/16 ? 0:row*32<side*10 ? 16'h07ff:row*32<side*20 ? 16'hf800:16'hffe0;
                {mem[ASSET_BASE-BASE+(row*side+col)*2+1],mem[ASSET_BASE-BASE+(row*side+col)*2]}=pixel_value;
            end
            for(integer i=0;i<count;i=i+1)begin
                // Many overlaps and both destination alignments, fixed order.
                x=8+(i*37)%(632-side);y=160+(i*19)%(240-side);
                put(LIST+i*32,ASSET_BASE);put(LIST+i*32+4,draw_base+y*1280+x*2);
                put(LIST+i*32+8,(side<<16)|side);put(LIST+i*32+12,side*2);
                put(LIST+i*32+16,0);put(LIST+i*32+20,2|((key_enabled?3:1)<<2)|(128<<8));
                put(LIST+i*32+24,0);put(LIST+i*32+28,0);
            end
            for(integer n=0;n<MEM_BYTES;n=n+1)golden[n]=mem[n];
            for(integer i=0;i<count;i=i+1)begin
                x=8+(i*37)%(632-side);y=160+(i*19)%(240-side);
                for(integer row=0;row<side;row=row+1)for(integer col=0;col<side;col=col+1)begin
                    s=ASSET_BASE-BASE+(row*side+col)*2;d=draw_base-BASE+(y+row)*1280+(x+col)*2;
                    {golden[d+1],golden[d]}=reference_blend({golden[s+1],golden[s]},{golden[d+1],golden[d]},128,key_enabled?3:1,0);
                end
            end
            old_reads=read_bursts;old_writes=bursts;source_bursts=0;source_words=0;profiling=1;
            write_reg(52,LIST);write_reg(16,count);write_reg(8,2);
            status=0;while((status&3)!=2)read_reg(4,status);
            profiling=0;if(status&4)$fatal(1,"Throughput command failed %h",status);
            read_reg(36,cycles_value);
            for(integer n=0;n<MEM_BYTES;n=n+1)if(mem[n]!==golden[n])$fatal(1,"Throughput pixel mismatch byte=%0d",n);
            $display("THROUGHPUT side=%0d count=%0d ready=%0d key=%0d cycles=%0d AR=%0d AW=%0d source_bursts=%0d source_words=%0d",
                side,count,ready,key_enabled,cycles_value,read_bursts-old_reads,bursts-old_writes,source_bursts,source_words);
        end
    endtask
    initial begin
        for(integer n=0;n<MEM_BYTES;n=n+1)mem[n]=(n*73)^(n>>8);
        repeat(10)@(negedge clk);reset=0;draw_base=BASE+PAGE_BYTES;write_reg(56,1);
        for(integer ready=0;ready<2;ready=ready+1)begin
            measure(4,128,ready,1);measure(16,128,ready,1);measure(24,128,ready,1);measure(32,128,ready,1);
        end
        measure(32,8,0,0); // Key-disabled images must keep their black pixels.
        $display("THROUGHPUT PIXELS PASSED: identical Alpha128 workload, full DDR pixels");$finish;
    end
    initial begin #1000000000;$fatal(1,"Throughput watchdog");end
endmodule
'''
if a.firmware_motion:
 tail=tail.replace('    task put(',r'''
    function automatic [31:0] firmware_seed(input [31:0] n);
        reg [31:0] v;
        begin
            v=(n+32'd1)*32'h9e3779b9;
            v=v^(v<<13);v=v^(v>>17);v=v^(v<<5);firmware_seed=v;
        end
    endfunction
    function automatic [31:0] firmware_bounce(input [31:0] phase,limit);
        reg [31:0] v;
        begin v=phase%(limit*2);firmware_bounce=v>limit ? limit*2-v:v;end
    endfunction
    task put(''')
 tail=tail.replace('x=8+(i*37)%(632-side);y=160+(i*19)%(240-side);',
    'seed=firmware_seed(i);x=8+firmware_bounce(seed&65535,632-side);y=160+firmware_bounce((firmware_seed(i)>>16),240-side);')
if a.profile:
 tail=tail.replace('    task put(',r'''
    integer descriptor_cycles,frontend_cycles,texture_cycles,background_cycles,write_cycles,span_cycles;
    integer payload_read_words,payload_write_words;
    always @(posedge clk)if(profiling)begin
        if(arvalid && arready && dut.read_owner_copy)payload_read_words=payload_read_words+arlen+1;
        if(awvalid && awready)payload_write_words=payload_write_words+awlen+1;
    end
    always @(posedge clk)if(profiling && dut.batch_busy)begin
        if(dut.batch_read_active)descriptor_cycles=descriptor_cycles+1;
        else if(!dut.fill.busy)frontend_cycles=frontend_cycles+1;
        else case(dut.fill.state)
            6,7,8:texture_cycles=texture_cycles+1;
            15,16,17:background_cycles=background_cycles+1;
            9,10,11,12,13,14,22:write_cycles=write_cycles+1;
            default:span_cycles=span_cycles+1;
        endcase
    end
    task put(''')
 tail=tail.replace('old_reads=read_bursts;old_writes=bursts;',
    'descriptor_cycles=0;frontend_cycles=0;texture_cycles=0;background_cycles=0;write_cycles=0;span_cycles=0;payload_read_words=0;payload_write_words=0;\n'
    '            old_reads=read_bursts;old_writes=bursts;')
 tail=tail.replace('profiling=0;if(status&4)',r'''
            profiling=0;
            $display("PHASE side=%0d count=%0d ready=%0d key=%0d descriptor=%0d frontend=%0d texture=%0d background=%0d write=%0d span=%0d read_words=%0d write_words=%0d",
                side,count,ready,key_enabled,descriptor_cycles,frontend_cycles,texture_cycles,background_cycles,write_cycles,span_cycles,payload_read_words,payload_write_words);
            if(status&4)''')
bench=out/'tb.sv';bench.write_text(prefix+tail,encoding='utf-8');lib='sim/work_throughput'
def run(cmd,tag):
 r=subprocess.run(list(map(str,cmd)),cwd=ROOT,capture_output=True,text=True,errors='replace')
 (ROOT/f'reports/bench_throughput_{a.label}_{tag}.log').write_text(r.stdout+r.stderr,encoding='utf-8')
 if r.returncode:print(r.stdout+r.stderr);r.check_returncode()
 return r.stdout+r.stderr
if not (ROOT/lib).exists():run([a.modelsim/'vlib.exe',lib],'vlib')
run([a.modelsim/'vlog.exe','-sv','-work',lib,'rtl/sync_fifo.v','rtl/fill_engine.v','rtl/render_batch.v','rtl/tile_renderer.v','rtl/ui_compositor.v',
     'rtl/ui_asset_rom.v','rtl/render_regs.v','rtl/framebuffer_video.v','rtl/video_mode_measure.v','rtl/render_subsystem.v',bench],'vlog')
log=run([a.modelsim/'vsim.exe','-batch','-t','1ps','-lib',lib,'tb_bench_throughput',
         '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'run')
assert 'THROUGHPUT PIXELS PASSED' in log and 'Errors: 0, Warnings: 0' in log,log[-3500:]
rows=[dict(zip(('side','count','ready','key','cycles','AR','AW','source_bursts','source_words'),map(int,m)))
      for m in re.findall(r'THROUGHPUT side=(\d+) count=(\d+) ready=(\d+) key=(\d+) cycles=(\d+) AR=(\d+) AW=(\d+) source_bursts=(\d+) source_words=(\d+)',log)]
assert len(rows)==9,log[-3500:]
result={'scope':'RTL modeled DDR cycles and pixels, not real-board FPS or MAX60','cases':rows,
        'source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
                         ('rtl/fill_engine.v','rtl/render_subsystem.v','rtl/render_batch.v','rtl/tile_renderer.v','sim/tb_render.sv')}}
if a.profile:
 phases=[dict(zip(('side','count','ready','key','descriptor','frontend','texture','background','write','span','read_words','write_words'),map(int,m)))
         for m in re.findall(r'PHASE side=(\d+) count=(\d+) ready=(\d+) key=(\d+) descriptor=(\d+) frontend=(\d+) texture=(\d+) background=(\d+) write=(\d+) span=(\d+) read_words=(\d+) write_words=(\d+)',log)]
 assert len(phases)==len(rows)
 for case,phase in zip(rows,phases):
  assert all(case[k]==phase[k] for k in ('side','count','ready','key'))
  assert sum(phase[k] for k in ('descriptor','frontend','texture','background','write','span'))==case['cycles']
 result['exclusive_phase_cycles']=phases
result['positions']='firmware frame zero' if a.firmware_motion else 'fixed overlapping test positions'
if a.compare:
 before=json.loads((ROOT/a.compare).read_text())['cases'];changes=[]
 for b,c in zip(before,rows):
  assert all(b[k]==c[k] for k in ('side','count','ready','key'))
  assert c['cycles']<b['cycles'] and c['source_words']<b['source_words'],(b,c)
  changes.append({'side':c['side'],'ready':c['ready'],'key':c['key'],'cycle_ratio_before_over_after':round(b['cycles']/c['cycles'],3),
                  'cycles_before':b['cycles'],'cycles_after':c['cycles'],'AR_before':b['AR'],'AR_after':c['AR'],'AW_before':b['AW'],'AW_after':c['AW']})
 result['comparison']=changes
(ROOT/f'reports/bench_throughput_{a.label}.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
