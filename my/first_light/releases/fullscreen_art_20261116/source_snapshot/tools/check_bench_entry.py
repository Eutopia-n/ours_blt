"""Verify continuous real RTL scanout during a menu -> pressure -> menu swap.

check_book_menu.py checks the actual C entry/drawing/control path. This focused
RTL test uses its captured pixels and stresses the same retired-page handover
with full-frame AXI copies, under independent randomized bus backpressure.
"""
from pathlib import Path
import argparse
import subprocess
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--modelsim',type=Path,default=Path('S:/ModelSim/win64'))
args=parser.parse_args()
out=ROOT/'software/build/bench_entry';out.mkdir(exist_ok=True)
for name,source in (('menu','book_menu_2_2.png'),('pressure','book_pressure_entry.png')):
    im=Image.open(ROOT/'reports'/source).convert('RGB')
    data=im.get_flattened_data() if hasattr(im,'get_flattened_data') else im.getdata()
    values=[((round(r*31/255)<<11)|(round(g*63/255)<<5)|round(b*31/255)) for r,g,b in data]
    (out/(name+'.hex')).write_text(''.join(f'{v:04x}\n' for v in values),encoding='ascii')
original=(ROOT/'sim/tb_render.sv').read_text()
prefix=original[:original.index('    reg repainted_a=')]
prefix=prefix.replace('module tb_render;','module tb_bench_entry;').replace('always #5 clk=~clk;','always #3.333333 clk=~clk;')
tail=r'''
    reg [15:0] menu_pixels[0:307199],pressure_pixels[0:307199];
    integer page_kind[0:1],x=0,y=0,kind=0,menu_frames=0,pressure_frames=0;
    reg monitor=0,previous_de=0,started=0,check_front=0;
    reg [31:0] status;
    always @(posedge clk)if(!reset)begin
        if(started && psel && penable && pwrite && paddr==32 && pwdata==0)
            $fatal(1,"Display disabled during transition");
        if(check_front && awvalid && awready && ((awaddr>=BASE+PAGE_BYTES)==dut.display_page_sync[1]))
            $fatal(1,"Pressure entry overwrote the front page");
    end
    always @(posedge pixel_clk)begin
        #3;
        if(monitor)begin
            if(de)begin
                if(x==0 && y==0)kind=page_kind[dut.display_page_sync[1]];
                if(pixel!==(kind ? pressure_pixels[y*640+x]:menu_pixels[y*640+x]))
                    $fatal(1,"Blank/mixed scanout kind=%0d x=%0d y=%0d pixel=%h",kind,x,y,pixel);
                x=x+1;
            end
            if(previous_de && !de)begin
                if(x!=640)$fatal(1,"Bad scan width");
                x=0;y=y+1;
                if(y==480)begin y=0;if(kind)pressure_frames++;else menu_frames++;end
            end
        end
        previous_de=de;
    end
    task pace(input bit page);
        integer tries;reg [31:0] value;
        write_reg(60,page);write_reg(64,1);tries=0;value=128;
        while(value&128)begin
            repeat(100)@(posedge clk);read_reg(4,value);tries++;
            if(tries>50000)$fatal(1,"Swap timeout");
        end
        if(((value>>6)&1)!=page || (value&48))$fatal(1,"Scanout error %h",value);
    endtask
    task upload(input bit pressure);
        for(integer n=0;n<307200;n++)begin
            {mem[ASSET_BASE-BASE+n*2+1],mem[ASSET_BASE-BASE+n*2]}=pressure ? pressure_pixels[n]:menu_pixels[n];
        end
    endtask
    task compose(input bit pressure);
        bit back;
        back=!dut.display_page_sync[1];draw_base=back ? BASE+PAGE_BYTES:BASE;
        write_reg(56,back);
        // A whole-frame copy overlaps active scanout and exceeds the texture
        // read load of entry's solid fills. The C text/HUD path is host-checked.
        raw_copy(ASSET_BASE,1280,draw_base,640,480);
        page_kind[back]=pressure;pace(back);
    endtask
    initial begin
        $readmemh("software/build/bench_entry/menu.hex",menu_pixels);
        $readmemh("software/build/bench_entry/pressure.hex",pressure_pixels);
        for(integer n=0;n<MEM_BYTES;n++)mem[n]=0;
        for(integer n=0;n<307200;n++)begin
            {mem[n*2+1],mem[n*2]}=menu_pixels[n];
            {mem[PAGE_BYTES+n*2+1],mem[PAGE_BYTES+n*2]}=menu_pixels[n];
        end
        page_kind[0]=0;page_kind[1]=0;
        repeat(10)@(negedge clk);reset=0;
        write_reg(32,1);started=1;pace(0);monitor=1;check_front=1;
        upload(1);compose(1);compose(1);
        pace(dut.display_page_sync[1]);
        upload(0);compose(0);compose(0);
        pace(dut.display_page_sync[1]);
        read_reg(4,status);if(status&48)$fatal(1,"Final underflow/read error");
        if(menu_frames<2 || pressure_frames<2 || !contentions)$fatal(1,"Coverage missing");
        $display("BENCH ENTRY RTL PASSED: %0d menu + %0d pressure full HDMI frames, no blank/mixed pixels, continuous display, no front writes/underflow/read errors; AXI contention=%0d",menu_frames,pressure_frames,contentions);
        $finish;
    end
    initial begin #220000000;$fatal(1,"Bench entry timeout");end
endmodule
'''
bench=out/'tb_bench_entry.sv';bench.write_text(prefix+tail,encoding='utf-8')
library='sim/work_bench_entry'
commands=[]
if not (ROOT/library).exists():commands.append(([args.modelsim/'vlib.exe',library],'vlib'))
commands.extend([([args.modelsim/'vlog.exe','-sv','-work',library,'rtl/sync_fifo.v','rtl/fill_engine.v',
    'rtl/render_regs.v','rtl/framebuffer_video.v','rtl/video_mode_measure.v','rtl/render_subsystem.v',bench],'vlog'),
    ([args.modelsim/'vsim.exe','-batch','-t','1ps','-lib',library,'tb_bench_entry','-do',
      'onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'run')])
for command,label in commands:
    print('Bench entry RTL:',label,flush=True)
    result=subprocess.run(list(map(str,command)),cwd=ROOT,capture_output=True,text=True)
    log=result.stdout+result.stderr;(ROOT/f'reports/bench_entry_{label}.log').write_text(log,encoding='utf-8')
    print(log[-2200:],flush=True)
    if result.returncode:raise SystemExit(result.returncode)
    if label=='run' and 'BENCH ENTRY RTL PASSED' not in log:raise SystemExit('Missing success marker')
