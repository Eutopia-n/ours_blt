"""Isolated basic-copy RTL regression and real AXI/FIFO waveform export.

Reuse the existing AXI memory model/assertions without editing shared RTL or its
regression. Generated bench uses CPU150 clock and leaves scanout disabled so
burst counts describe only the selected copy command. This is simulation data.
"""
from pathlib import Path
import argparse,csv,subprocess
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--modelsim',type=Path,default=Path('D:/modelsim/win64'))
args=parser.parse_args()
out=ROOT/'software/build/basic_bus';out.mkdir(exist_ok=True)
original=(ROOT/'sim/tb_render.sv').read_text()
prefix=original[:original.index('    reg [31:0] status;\n    integer old_writes')]
prefix=prefix.replace('module tb_render;','module tb_basic_bus;').replace('always #5 clk=~clk;','always #3.333333 clk=~clk;')
tail=r'''
    integer trace_file,trace_cycles=0;
    reg trace_enable=0,trace_started=0;
    always @(posedge clk) if(trace_enable && !reset) begin
        if(dut.fill.fifo_level!=0)trace_started=1;
        if(trace_started && trace_cycles<1024)begin
            $fwrite(trace_file,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d\n",
                trace_cycles,awvalid,awready,awlen,wvalid,wready,wlast,
                dut.fill.fifo_level,dut.fill.fifo_push,dut.fill.fifo_pop,
                arvalid,arready,arlen,rvalid,rready);
            trace_cycles=trace_cycles+1;
        end
    end
    reg [31:0] status,before_ar,before_aw,after_ar,after_aw;
    task checked_effect(input [31:0] source,input integer alpha,flags,input [15:0] key);
        integer s,d;
        for(integer n=0;n<MEM_BYTES;n=n+1)golden[n]=mem[n];
        for(integer y=0;y<128;y=y+1)for(integer x=0;x<128;x=x+1)begin
            s=source-BASE+y*256+x*2;d=draw_base-BASE+(224+y)*1280+(408+x)*2;
            {golden[d+1],golden[d]}=reference_blend({mem[s+1],mem[s]},{mem[d+1],mem[d]},alpha,flags,key);
        end
        raw_blend(source,256,draw_base+224*1280+408*2,128,128,alpha,flags,key);
        for(integer n=0;n<MEM_BYTES;n=n+1)if(mem[n]!==golden[n])$fatal(1,"Effect full-DDR mismatch byte %0d",n);
    endtask
    task basic_await_swap(input bit page);
        integer tries;reg [31:0] value;
        tries=0;value=128;
        while(value&128)begin
            repeat(100)@(posedge clk);read_reg(4,value);tries=tries+1;
            if(tries>50000)$fatal(1,"150MHz page handover timeout");
        end
        if(((value>>6)&1)!=page || (value&48))$fatal(1,"Handover error %h",value);
    endtask
    reg static_check=0,static_prev_vs=1,static_seen_pixels=0;
    integer static_frames=0;
    always @(posedge pixel_clk)begin
        #2;
        if(static_check)begin
            if(de)begin
                static_seen_pixels=1;
                if(pixel!==16'h1082)$fatal(1,"Static menu changed or blanked: pixel %h",pixel);
            end
            if(static_prev_vs && !vs && static_seen_pixels)begin
                static_frames=static_frames+1;static_seen_pixels=0;
            end
        end
        static_prev_vs=vs;
    end
    initial begin
        trace_file=$fopen("reports/basic_bus_trace.csv","w");
        $fwrite(trace_file,"cycle,awvalid,awready,awlen,wvalid,wready,wlast,fifo_level,push,pop,arvalid,arready,arlen,rvalid,rready\n");
        for(integer n=0;n<MEM_BYTES;n=n+1)mem[n]=(n*73)^(n>>8);
        repeat(10)@(negedge clk);reset=0;
        read_reg(0,status);if(status!==32'h32444631)$fatal(1,"ID mismatch");
        for(integer page=0;page<2;page=page+1)begin
            draw_base=BASE+page*PAGE_BYTES;write_reg(56,page);
            for(integer image=0;image<2;image=image+1)begin
                read_reg(92,before_ar);read_reg(96,before_aw);
                trace_enable=(page==0 && image==0);
                checked_asset(32'h012c0000+image*98304,512,352,176,256,192);
                trace_enable=0;
                read_reg(92,after_ar);read_reg(96,after_aw);
                if(after_ar-before_ar!=1536 || after_aw-before_aw!=1536)
                    $fatal(1,"Copy counters not isolated: AR %0d AW %0d",after_ar-before_ar,after_aw-before_aw);
            end
        end
        rejected_copy(32'h012c0000,512,draw_base+176*1280+352*2,0,192);
        rejected_copy(32'h012c0000,510,draw_base+176*1280+352*2,256,192);
        rejected_copy(32'h012ff000,512,draw_base+176*1280+352*2,256,192);
        if(trace_cycles<1000 || copy_16beat_bursts==0)$fatal(1,"Missing FIFO trace/burst coverage");
        $fclose(trace_file);
        $display("BASIC BUS RTL PASSED: two image addresses x two pages, 256x192/512-byte pitch, 1536 read/write bursts each, whole-DDR equality, empty/stride/range rejection; randomized stalls and FIFO/AXI assertions");
        for(integer image=0;image<2;image=image+1)for(integer y=0;y<128;y=y+1)for(integer x=0;x<128;x=x+1)begin
            integer d,dx,dy;reg [15:0] color;
            dx=x>63?x-63:63-x;dy=y>63?y-63:63-y;
            color=dx+dy>60 ? (image?16'hf81f:16'h0000) : y<43?16'h07ff:y<86?16'hf800:16'hffe0;
            d=32'h012b0000-BASE+image*32768+y*256+x*2;{mem[d+1],mem[d]}=color;
        end
        for(integer page=0;page<2;page=page+1)for(integer bg=0;bg<2;bg=bg+1)begin
            draw_base=BASE+page*PAGE_BYTES;write_reg(56,page);
            for(integer y=0;y<192;y=y+1)for(integer x=0;x<240;x=x+1)begin
                integer d,tile_alt;reg [15:0] color;
                tile_alt=((x/16)^(y/16))&1;color=bg?(tile_alt?16'h7bef:16'h2945):(tile_alt?16'h0514:16'hfca0);
                d=draw_base-BASE+(192+y)*1280+(352+x)*2;{mem[d+1],mem[d]}=color;
            end
            checked_effect(32'h012b0000,255,1,0);
            checked_effect(32'h012b0000,127,1,0);
            checked_effect(32'h012b0000,0,1,0);
            checked_effect(32'h012b0000,255,0,0);
            checked_effect(32'h012b0000,255,2,0);
            checked_effect(32'h012b8000,255,0,16'hf81f);
            checked_effect(32'h012b8000,255,2,16'hf81f);
        end
        $display("EFFECTS RTL PASSED: 28 full-DDR cases, 128x128 assets, Alpha endpoint/midpoint, black/magenta keys on/off, two pages/backgrounds");
        // Start with existing effect pixels visible on A. Draw the new menu
        // only into retired B, acknowledge it, then repaint retired A while B
        // remains visible. Keep scanout running for the entire handover.
        write_reg(32,1);wait(dut.video.running);check_page_writes=1;
        draw_base=BASE+PAGE_BYTES;write_reg(56,1);fill(0,0,640,480,16'h1082);
        write_reg(60,1);write_reg(64,1);basic_await_swap(1);static_check=1;
        draw_base=BASE;write_reg(56,0);fill(0,0,640,480,16'h1082);
        write_reg(60,0);write_reg(64,1);basic_await_swap(0);
        wait(static_frames>=6);read_reg(4,status);
        if(status&48)$fatal(1,"Static scanout underflow/error %h",status);
        $display("MENU HANDOVER RTL PASSED: six static HDMI frames, A/B handover and hold, no changed/blank pixels or underflow; physical display still requires board retest");
        $finish;
    end
    initial begin #200000000;$fatal(1,"Basic bus timeout");end
endmodule
'''
bench=out/'tb_basic_bus.sv';bench.write_text(prefix+tail)
library='sim/work_basic_bus'
commands=[]
if not (ROOT/library).exists():commands.append(([args.modelsim/'vlib.exe',library],'vlib'))
commands += [([args.modelsim/'vlog.exe','-sv','-work',library,'rtl/sync_fifo.v','rtl/fill_engine.v',
              'rtl/render_regs.v','rtl/framebuffer_video.v','rtl/video_mode_measure.v','rtl/render_subsystem.v',bench],'vlog'),
             ([args.modelsim/'vsim.exe','-batch','-t','1ps','-lib',library,'tb_basic_bus','-do',
              'onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'run')]
for command,label in commands:
    run=subprocess.run(list(map(str,command)),cwd=ROOT,capture_output=True,text=True)
    log=run.stdout+run.stderr;(ROOT/f'reports/basic_bus_{label}.log').write_text(log,encoding='utf-8')
    print(log[-2000:],flush=True)
    if run.returncode:raise SystemExit(run.returncode)
    if label=='run' and 'BASIC BUS RTL PASSED' not in log:raise SystemExit('Missing basic bus success marker')
    if label=='run':
        assert 'EFFECTS RTL PASSED' in log and 'MENU HANDOVER RTL PASSED' in log
rows=[{k:int(v) for k,v in r.items()} for r in csv.DictReader((ROOT/'reports/basic_bus_trace.csv').open())]
assert any(r['awvalid'] and r['awready'] and r['awlen']==15 for r in rows)
assert any(r['wvalid'] and not r['wready'] for r in rows)
assert any(r['wvalid'] and r['wready'] and r['wlast'] for r in rows)
assert all(0<=r['fifo_level']<=16 for r in rows)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
signals=[('awvalid','AWVALID'),('awready','AWREADY'),('awlen','AWLEN (15 = 16 beats)'),
         ('wvalid','WVALID'),('wready','WREADY'),('wlast','WLAST'),
         ('fifo_level','FIFO occupancy'),('push','FIFO push'),('pop','FIFO pop')]
window=rows[:96]
fig,axes=plt.subplots(len(signals),1,figsize=(12,8),sharex=True,layout='constrained')
for ax,(key,label) in zip(axes,signals):
    ax.step([r['cycle'] for r in window],[r[key] for r in window],where='post',color='#205c8c',linewidth=1.5)
    ax.set_ylabel(label,rotation=0,ha='right',va='center',fontsize=9)
    ax.set_yticks([0,16] if key=='fifo_level' else [0,15] if key=='awlen' else [0,1])
    ax.set_ylim(-0.15,16.5 if key=='fifo_level' else 15.5 if key=='awlen' else 1.15)
    ax.grid(axis='x',alpha=0.2);ax.spines[['top','right']].set_visible(False)
axes[-1].set_xlabel('Renderer clock cycles from first FIFO activity (CPU/renderer 150 MHz in simulation)')
fig.suptitle('Actual RTL simulation: AXI burst write and FIFO under randomized backpressure',fontsize=12)
fig.savefig(ROOT/'reports/basic_bus_waveform.png',dpi=150)
fig.savefig(ROOT/'reports/basic_bus_waveform.svg')
print('Exported actual simulation trace and AXI/FIFO waveform; no board performance claim.',flush=True)
