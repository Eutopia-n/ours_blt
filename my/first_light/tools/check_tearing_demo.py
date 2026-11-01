"""Capture genuine scanout tears versus acknowledged back-page rendering.

Production RTL is unchanged. C host tests check the actual application control;
this isolated bench checks the corresponding real APB/AXI/pixel transactions.
Images contain actual simulated HDMI pixels, not fabricated split pictures.
"""
from pathlib import Path
import argparse,re,subprocess
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--modelsim',type=Path,default=Path('D:/modelsim/win64'))
args=parser.parse_args()
source=(ROOT/'software/basic_demo_data.h').read_text(encoding='utf-8')
assert '#define BASIC_BUFFER_PHASE_CYCLES (8u*(SYSTEM_CLINT_HZ/1000u))' in source
app=(ROOT/'software/basic_demo.h').read_text(encoding='utf-8')
assert 'basic_bounce(frame*(8u<<basic_config.speed),360u)' in app
assert 'x+96u*n,184,24,208' in app
original=(ROOT/'sim/tb_render.sv').read_text()
prefix=original[:original.index('    reg [31:0] status;\n    integer old_writes')]
prefix=prefix.replace('module tb_render;','module tb_tearing_demo;').replace('always #5 clk=~clk;','always #3.333333 clk=~clk;')
tail=r"""
    reg [31:0] status;
    integer cap_file,cap_x=0,cap_y=0,cap_first[0:479],cap_white[0:479];
    integer torn_frames=0,whole_frames=0,menu_frames=0,front_bursts=0;
    reg cap_enable=0,cap_previous_de=0,cap_done=0,cap_protected=0,cap_menu=0;
    integer cap_old_x,cap_new_x;
    always @(posedge clk)if(!reset && awvalid && awready)
        if((awaddr>=BASE+PAGE_BYTES)==dut.display_page_sync[1])front_bursts=front_bursts+1;
    always @(posedge pixel_clk)begin
        #3;
        if(cap_enable)begin
            if(de)begin
                if(cap_menu && pixel!==16'h1082)$fatal(1,"Menu pixel changed/blanked");
                if(pixel===16'hffff)begin
                    if(cap_first[cap_y]<0)cap_first[cap_y]=cap_x;
                    cap_white[cap_y]=cap_white[cap_y]+1;
                end
                $fwrite(cap_file,"%c%c%c",{pixel[15:11],pixel[15:13]},
                    {pixel[10:5],pixel[10:9]},{pixel[4:0],pixel[4:2]});
                cap_x=cap_x+1;
            end
            if(cap_previous_de && !de)begin
                if(cap_x!=640)$fatal(1,"Capture line width %0d",cap_x);
                cap_x=0;cap_y=cap_y+1;
                if(cap_y==480)begin
                    $fclose(cap_file);cap_enable=0;cap_done=1;
                    if(cap_menu)menu_frames=menu_frames+1;
                    else if(cap_protected)begin
                        for(integer y=184;y<392;y=y+1)
                            if(cap_first[y]!=cap_old_x || cap_white[y]!=72)
                                $fatal(1,"Protected frame mixed at y=%0d x=%0d expected=%0d white=%0d",y,cap_first[y],cap_old_x,cap_white[y]);
                        whole_frames=whole_frames+1;
                    end else begin
                        if(cap_first[200]!=cap_old_x || cap_first[380]!=cap_new_x || cap_old_x==cap_new_x)
                            $fatal(1,"Expected actual scan/write tear, upper=%0d lower=%0d old=%0d new=%0d",cap_first[200],cap_first[380],cap_old_x,cap_new_x);
                        torn_frames=torn_frames+1;
                        $display("ACTUAL TEAR: upper x=%0d, lower x=%0d",cap_first[200],cap_first[380]);
                    end
                end
            end
        end
        cap_previous_de=de;
    end
    task pace(input bit page);
        integer tries;reg [31:0] value;
        write_reg(60,page);write_reg(64,1);tries=0;value=128;
        while(value&128)begin
            repeat(100)@(posedge clk);read_reg(4,value);tries=tries+1;
            if(tries>50000)$fatal(1,"Page acknowledgement timeout");
        end
        if(((value>>6)&1)!=page || (value&48))$fatal(1,"Page status %h",value);
    endtask
    task capture(input string name,input bit protected_mode,input integer old_x,new_x,input bit menu=0);
        cap_file=$fopen({"reports/tearing_",name,".ppm"},"wb");
        if(!cap_file)$fatal(1,"Capture file failed");
        $fwrite(cap_file,"P6\n640 480\n255\n");
        cap_x=0;cap_y=0;cap_done=0;cap_protected=protected_mode;cap_menu=menu;
        cap_old_x=old_x;cap_new_x=new_x;
        for(integer y=0;y<480;y=y+1)begin cap_first[y]=-1;cap_white[y]=0;end
        cap_enable=1;
    endtask
    function automatic integer bar_x(input integer frame,speed);
        integer phase;begin phase=(frame*speed)%720;bar_x=24+(phase>360?720-phase:phase);end
    endfunction
    integer old_x[0:1];
    task init_scene;
        fill(0,0,640,480,16'h10a6);fill(16,176,608,224,16'h084b);
        for(integer y=200;y<400;y=y+40)fill(16,y,608,2,16'h7bef);
        for(integer n=0;n<3;n=n+1)fill(24+n*96,184,24,208,16'hffff);
        old_x[draw_base==BASE?0:1]=24;
    endtask
    task update_scene(input integer x);
        integer p;begin
            p=draw_base==BASE?0:1;
            if(x!=old_x[p])begin
                for(integer n=0;n<3;n=n+1)begin
                    fill(old_x[p]+96*n,184,24,208,16'h084b);
                    for(integer y=200;y<392;y=y+40)fill(old_x[p]+96*n,y,24,2,16'h7bef);
                end
                for(integer n=0;n<3;n=n+1)fill(x+96*n,184,24,208,16'hffff);
                old_x[p]=x;
            end
        end
    endtask
    task prime_pair;
        bit back;
        for(integer page=0;page<2;page=page+1)begin
            back=!dut.display_page_sync[1];draw_base=back?BASE+PAGE_BYTES:BASE;
            write_reg(56,back);init_scene();pace(back);
        end
    endtask
    initial begin
        for(integer n=0;n<MEM_BYTES;n=n+1)mem[n]=0;
        repeat(10)@(negedge clk);reset=0;
        fill(0,0,0,1,16'hffff,1);
        if(bursts)$fatal(1,"Empty fill issued a write");
        init_scene();write_reg(32,1);wait(dut.video.running);
        // Explicit sequence 0 -> 1 -> 0 -> 1; no automatic mode controller.
        for(integer stage=0;stage<4;stage=stage+1)begin
            check_page_writes=1;prime_pair();
            for(integer frame=1;frame<=2;frame=frame+1)begin
                bit active,target;integer speed,previous,next;
                speed=stage<2 ? 8:stage==2 ? 32:16;
                active=dut.display_page_sync[1];target=stage[0] ? !active:active;
                draw_base=target?BASE+PAGE_BYTES:BASE;write_reg(56,target);
                previous=bar_x(frame-1,speed);next=bar_x(frame,speed);
                capture($sformatf("stage%0d_frame%0d",stage,frame),stage[0],previous,next);
                #8000000;
                check_page_writes=stage[0];update_scene(next);
                // Queue presentation at the same point as the application.
                // The scanout monitor finishes the current active frame before
                // the acknowledgement at v=524.
                pace(target);
                if(!cap_done)$fatal(1,"Capture not completed before acknowledgement");
                read_reg(4,status);if(status&48)$fatal(1,"Underflow/read error %h",status);
            end
        end
        // Paused comparison: no drawing, same-page pacing leaves a whole image.
        capture("paused",1,bar_x(2,16),0);pace(dut.display_page_sync[1]);
        if(!cap_done)$fatal(1,"Paused capture missing");
        // Exit through the existing retired-page handover, then hold the menu.
        check_page_writes=1;
        for(integer page=0;page<2;page=page+1)begin
            bit back;back=!dut.display_page_sync[1];
            draw_base=back?BASE+PAGE_BYTES:BASE;write_reg(56,back);
            fill(0,0,640,480,16'h1082);pace(back);
        end
        for(integer frame=0;frame<3;frame=frame+1)begin
            capture($sformatf("menu%0d",frame),1,0,0,1);pace(dut.display_page_sync[1]);
            if(!cap_done)$fatal(1,"Menu frame missing");
        end
        read_reg(4,status);if(status&48)$fatal(1,"Final display error %h",status);
        if(torn_frames!=4 || whole_frames!=5 || menu_frames!=3 || front_bursts==0)
            $fatal(1,"Coverage tears=%0d whole=%0d menus=%0d front=%0d",torn_frames,whole_frames,menu_frames,front_bursts);
        $display("TEARING RTL PASSED: 4 real torn frames, 4 complete double-buffer frames plus pause, explicit 0/1/0/1 paths, speeds 8/16/32, 3 stable exit-menu frames; no underflow, page-boundary/AXI/FIFO checks passed");
        $finish;
    end
    initial begin #400000000;$fatal(1,"Tearing demo timeout");end
endmodule
"""
out=ROOT/'software/build/tearing_demo';out.mkdir(exist_ok=True)
bench=out/'tb_tearing_demo.sv';bench.write_text(prefix+tail)
library='sim/work_tearing_demo'
commands=[]
if not (ROOT/library).exists():commands.append(([args.modelsim/'vlib.exe',library],'vlib'))
commands += [([args.modelsim/'vlog.exe','-sv','-work',library,'rtl/sync_fifo.v','rtl/fill_engine.v',
              'rtl/render_regs.v','rtl/framebuffer_video.v','rtl/video_mode_measure.v','rtl/render_subsystem.v',bench],'vlog'),
             ([args.modelsim/'vsim.exe','-batch','-t','1ps','-lib',library,'tb_tearing_demo','-do',
              'onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'run')]
for command,label in commands:
    print('Tearing RTL:',label,flush=True)
    run=subprocess.run(list(map(str,command)),cwd=ROOT,capture_output=True,text=True)
    log=run.stdout+run.stderr;(ROOT/f'reports/tearing_demo_{label}.log').write_text(log,encoding='utf-8')
    print(log[-3000:],flush=True)
    if run.returncode:raise SystemExit(run.returncode)
    if label=='run' and 'TEARING RTL PASSED' not in log:raise SystemExit('Missing success marker')
for path in (ROOT/'reports').glob('tearing_*.ppm'):
    with Image.open(path) as im:im.save(path.with_suffix('.png'))
print('Captured actual RTL scanout frames; physical-display retest still required.',flush=True)
