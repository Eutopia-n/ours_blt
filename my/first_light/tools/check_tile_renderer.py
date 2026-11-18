"""Fused tile RTL vs unchanged scalar Alpha/Key frames and legacy batch+clear.

Measures modeled renderer cycles including APB setup, not CPU work or MAX60.
"""
from pathlib import Path
import argparse, hashlib, json, re, subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--modelsim',type=Path,default=Path('D:/modelsim/win64'));a=p.parse_args()
out=ROOT/'software/build/tile_renderer';out.mkdir(parents=True,exist_ok=True)
inputs=('rtl/fill_engine.v','rtl/render_batch.v','rtl/tile_renderer.v','rtl/render_regs.v','rtl/render_subsystem.v','tools/check_tile_renderer.py')
input_hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in inputs}
source=(ROOT/'sim/tb_render.sv').read_text()
prefix=source[:source.index('    reg [31:0] status;\n    integer old_writes')]
prefix=prefix.replace('module tb_render;','module tb_tiles;').replace('always #5 clk=~clk;','always #3.333333 clk=~clk;')
prefix=prefix.replace('reg inject_bg_error=0;','reg inject_bg_error=0,inject_tile_bad_last=0;')
prefix=prefix.replace('rlast=rb==rl;','rlast=(rb==rl) ^ (inject_tile_bad_last && dut.tile_selected && (rb==0 || rb==rl));')
prefix=prefix.replace('if(rlast) reading=0;','if(rb>rl) reading=0;')
tail=r'''
    localparam LIST=32'h012b0000,LEGACY=32'h012a0000,TEXTURE=32'h01203000;
    reg [31:0] status;
    integer xs[0:8191],ys[0:8191],counts[0:179],offsets[0:180],cursor[0:179];
    integer fragments,frame_clock=0,old_clock,legacy_cycles,tile_cycles,old_aw,old_ar;
    integer checked=0,failed_checks=0,target_read=-1;
    reg [15:0] test_key=0;
    reg [31:0] native_list[0:65535],native_texture[0:511];
    reg [15:0] native_pixels[0:307199];
    reg scan_check=0,previous_vs=1,seen_pixels=0;
    integer scanned_frames=0;
    always @(posedge pixel_clk)begin
        #2;
        if(scan_check)begin
            if(de)begin seen_pixels=1;if(pixel!==16'h1082)$fatal(1,"Tile modified front page");end
            if(previous_vs && !vs && seen_pixels)begin scanned_frames++;seen_pixels=0;end
        end
        previous_vs=vs;
    end
    always @(posedge clk)begin
        frame_clock=frame_clock+1;
        if(!reset && dut.tiles.awvalid && dut.tiles.load_count!=16)$fatal(1,"Tile row was not fully staged before AW");
        if(dut.tiles.state==dut.tiles.RADDR && dut.tiles.read_kind==target_read)inject_read_error=1;
    end
    function automatic [31:0] seed(input [31:0] n);
        reg [31:0] v;
        begin v=(n+1)*32'h9e3779b9;v=v^(v<<13);v=v^(v>>17);v=v^(v<<5);seed=v;end
    endfunction
    function automatic integer bounce(input [31:0] phase,input integer limit);
        reg [31:0] v;begin v=phase%(limit*2);bounce=v>limit ? limit*2-v:v;end
    endfunction
    task put(input integer address,input [31:0] value);
        for(integer j=0;j<4;j=j+1)mem[address-BASE+j]=value[j*8+:8];
    endtask
    task wait_done(input bit expected_error);
        status=0;while((status&3)!=2)read_reg(4,status);
        if(((status&4)!=0)!=expected_error)$fatal(1,"Tile/legacy error mismatch %h state=%0d",status,dut.tiles.state);
        if(((reading || rvalid) && dut.read_owner_copy) || writing || bvalid)$fatal(1,"DONE with outstanding renderer AXI transaction");
    endtask
    task fixture(input integer side,n,frame,input bit edges=0);
        integer x,y,at,b;reg [31:0] s;reg [15:0] pixel_value;
        begin
            for(integer row=0;row<side;row=row+1)for(integer col=0;col<side;col=col+1)begin
                x=col*2-(side-1);if(x<0)x=-x;y=row*2-(side-1);if(y<0)y=-y;
                pixel_value=x+y>(side*13+15)/16 ? 0:row*32<side*10 ? 16'h07ff:row*32<side*20 ? 16'hf800:16'hffe0;
                {mem[TEXTURE-BASE+(row*side+col)*2+1],mem[TEXTURE-BASE+(row*side+col)*2]}=pixel_value;
            end
            for(integer i=0;i<180;i=i+1)counts[i]=0;
            for(integer i=0;i<n;i=i+1)begin
                s=seed(i);xs[i]=8+bounce((s&65535)+frame*(1+((s>>16)&7)),632-side);
                ys[i]=160+bounce((s>>16)+frame*(1+((s>>24)&3)),240-side);
                if(edges)begin
                    case(i%4)
                    0:begin xs[i]=0;ys[i]=152;end
                    1:begin xs[i]=640-side;ys[i]=408-side;end
                    2:begin xs[i]=609-side;ys[i]=377-side;end
                    3:begin xs[i]=31;ys[i]=159;end
                    endcase
                end
                for(integer ty=ys[i]/32;ty<=(ys[i]+side-1)/32;ty=ty+1)
                    for(integer tx=xs[i]/32;tx<=(xs[i]+side-1)/32;tx=tx+1)counts[(ty-4)*20+tx]++;
            end
            offsets[0]=0;
            for(integer b=0;b<180;b=b+1)begin offsets[b+1]=offsets[b]+counts[b];cursor[b]=offsets[b];put(LIST+b*4,offsets[b]);end
            fragments=offsets[180];put(LIST+720,fragments);
            for(integer i=0;i<n;i=i+1)
                for(integer ty=ys[i]/32;ty<=(ys[i]+side-1)/32;ty=ty+1)
                    for(integer tx=xs[i]/32;tx<=(xs[i]+side-1)/32;tx=tx+1)begin
                        b=(ty-4)*20+tx;put(LIST+768+cursor[b]*4,(ys[i]<<16)|xs[i]);cursor[b]++;
                    end
        end
    endtask
    task prepare_golden(input integer side,n,alpha,flags);
        integer s,d;
        begin
            for(integer j=0;j<PAGE_BYTES;j=j+1)mem[draw_base-BASE+j]=(j*37)^(j>>8);
            for(integer j=0;j<2*PAGE_BYTES;j=j+1)golden[j]=mem[j];
            for(integer y=152;y<408;y=y+1)for(integer x=0;x<640;x=x+1)begin
                d=draw_base-BASE+y*1280+x*2;{golden[d+1],golden[d]}=16'h0843;
            end
            for(integer i=0;i<n;i=i+1)for(integer y=0;y<side;y=y+1)for(integer x=0;x<side;x=x+1)begin
                s=TEXTURE-BASE+(y*side+x)*2;d=draw_base-BASE+(ys[i]+y)*1280+(xs[i]+x)*2;
                {golden[d+1],golden[d]}=reference_blend({mem[s+1],mem[s]},{golden[d+1],golden[d]},alpha,flags,test_key);
            end
        end
    endtask
    task compare_pixels;
        for(integer j=0;j<2*PAGE_BYTES;j=j+1)if(mem[j]!==golden[j])
            $fatal(1,"Tile pixel mismatch at (%0d,%0d) byte=%0d got=%h expected=%h state=%0d",(j%1280)/2,(j/1280)%480,j,mem[j],golden[j],dut.tiles.state);
    endtask
    task launch_tile(input integer side,alpha,flags,input bit expected_error=0);
        write_reg(52,TEXTURE);write_reg(12,LIST);write_reg(16,side);write_reg(20,fragments);
        write_reg(28,16'h0843);write_reg(80,flags);write_reg(84,alpha);write_reg(88,test_key);write_reg(8,4);
        if(!expected_error)begin write_reg(16,side,1);write_reg(64,1,1);end
        wait_done(expected_error);
    endtask
    task checked_positions(input integer side,n,ready);
        integer d;
        begin
            force_bus_ready=ready;fixture(side,n,37);prepare_golden(side,n,128,3);
            old_clock=frame_clock;fill(0,152,640,256,16'h0843);
            for(integer i=0;i<n;i=i+1)put(LIST+i*4,draw_base+ys[i]*1280+xs[i]*2);
            write_reg(52,TEXTURE);write_reg(12,LIST);write_reg(16,n);write_reg(20,side);
            write_reg(76,side*2);write_reg(80,3);write_reg(84,128);write_reg(88,0);write_reg(8,3);
            wait_done(0);compare_pixels();read_reg(120,status);if(status!=n)$fatal(1,"Packed completion count");
            $display("POSITIONS side=%0d count=%0d ready=%0d cycles=%0d",side,n,ready,frame_clock-old_clock);
        end
    endtask
    task checked_tile(input integer side,n,frame,alpha,flags,ready,input bit baseline=0,edges=0);
        integer at,c;
        begin
            force_bus_ready=ready;fixture(side,n,frame,edges);prepare_golden(side,n,alpha,flags);
            if(baseline)begin
                old_clock=frame_clock;fill(0,152,640,256,16'h0843);
                for(integer first=0;first<n;first=first+512)begin
                    c=n-first;if(c>512)c=512;
                    for(integer i=0;i<c;i=i+1)begin
                        at=LEGACY+i*32;put(at,TEXTURE);put(at+4,draw_base+ys[first+i]*1280+xs[first+i]*2);
                        put(at+8,(side<<16)|side);put(at+12,side*2);put(at+16,0);
                        put(at+20,2|(flags<<2)|(alpha<<8));put(at+24,0);put(at+28,0);
                    end
                    write_reg(52,LEGACY);write_reg(16,c);write_reg(8,2);wait_done(0);
                end
                legacy_cycles=frame_clock-old_clock;compare_pixels();
                for(integer j=0;j<PAGE_BYTES;j=j+1)mem[draw_base-BASE+j]=(j*37)^(j>>8);
            end
            old_clock=frame_clock;old_ar=read_bursts;old_aw=bursts;
            launch_tile(side,alpha,flags);tile_cycles=frame_clock-old_clock;
            compare_pixels();read_reg(120,status);if(status!=fragments)$fatal(1,"Tile completion count");
            if(bursts-old_aw!=5120)$fatal(1,"Tile viewport must be written exactly once");
            checked++;
            $display("TILE side=%0d count=%0d ready=%0d alpha=%0d flags=%0d frame=%0d fragments=%0d legacy_cycles=%0d tile_cycles=%0d AR=%0d AW=%0d",
                side,n,ready,alpha,flags,frame,fragments,baseline?legacy_cycles:0,tile_cycles,read_bursts-old_ar,bursts-old_aw);
        end
    endtask
    task bad_job(input integer side);
        launch_tile(side,128,3,1);failed_checks++;
    endtask
    task rejected_job(input [31:0] src,address,input integer size,frags);
        integer ar,aw;
        begin
            ar=read_bursts;aw=bursts;write_reg(52,src);write_reg(12,address);
            write_reg(16,size);write_reg(20,frags);write_reg(8,4);wait_done(1);
            if(ar!=read_bursts || aw!=bursts)$fatal(1,"Invalid tile geometry accessed DDR");failed_checks++;
        end
    endtask
    initial begin
        for(integer n=0;n<MEM_BYTES;n=n+1)mem[n]=(n*73)^(n>>8);
        repeat(10)@(negedge clk);reset=0;draw_base=BASE+PAGE_BYTES;write_reg(56,1);
        checked_tile(32,0,0,128,3,0);
        checked_tile(4,1,0,128,3,0,0,1);checked_tile(16,7,37,128,3,0,0,1);
        checked_tile(24,7,37,128,3,0,0,1);checked_tile(32,7,37,128,3,0,0,1);
        for(integer ready=0;ready<2;ready=ready+1)begin
            checked_tile(4,1024,0,128,3,ready,1);
            checked_tile(16,1024,0,128,3,ready,1);
            checked_tile(24,1024,0,128,3,ready,1);
            checked_tile(32,1024,0,128,3,ready,1);
            checked_tile(32,512,0,128,3,ready,1);
            checked_tile(16,2048,0,128,3,ready,1);
            checked_positions(4,1024,ready);checked_positions(16,128,ready);
        end
        checked_positions(32,0,0);checked_positions(32,7,0);
        checked_tile(32,4096,36000,128,3,0,1);
        for(integer a=0;a<3;a=a+1)checked_tile(32,7,37,a==0?0:a==1?1:255,3,0,0,1);
        checked_tile(32,7,37,128,1,0,0,1);checked_tile(32,7,37,128,2,0,0,1);
        test_key=16'h07ff;checked_tile(32,7,37,254,3,0,0,1);test_key=0;
        fixture(32,7,0);for(integer i=0;i<512;i=i+1)put(TEXTURE+i*4,0);
        prepare_golden(32,7,128,3);launch_tile(32,128,3);compare_pixels();
        draw_base=BASE;write_reg(56,0);checked_tile(32,128,37,128,3,0,0,1);
        // Invalid shape and table records, then clean recovery.
        fixture(32,7,0);bad_job(3);
        rejected_job(TEXTURE+2,LIST,32,fragments);
        rejected_job(TEXTURE,LIST+4,32,fragments);
        rejected_job(TEXTURE,ASSET_BASE+ASSET_BYTES-32,32,1);
        rejected_job(ASSET_BASE+ASSET_BYTES-4,LIST,32,1);
        put(LIST,1);bad_job(32);fixture(32,7,0);
        put(LIST+4,fragments+1);bad_job(32);fixture(32,7,0);
        put(LIST+768,0);bad_job(32);fixture(32,7,0);
        for(integer k=0;k<3;k=k+1)begin target_read=k;bad_job(32);target_read=-1;inject_read_error=0;fixture(32,7,0);end
        inject_tile_bad_last=1;bad_job(32);inject_tile_bad_last=0;
        inject_write_error=1;bad_job(32);inject_write_error=0;
        checked_tile(32,7,37,128,3,0,0,1);
        // Actual C-generated stable bins, texture and independent scalar frame.
        $readmemh("software/build/render_batch/native_tile_list.hex",native_list);
        $readmemh("software/build/render_batch/native_tile_texture.hex",native_texture);
        $readmemh("software/build/render_batch/native_tile_expected.hex",native_pixels);
        draw_base=BASE+PAGE_BYTES;write_reg(56,1);
        for(integer i=0;i<65536;i=i+1)put(LIST+i*4,native_list[i]);
        for(integer i=0;i<512;i=i+1)put(TEXTURE+i*4,native_texture[i]);
        for(integer i=0;i<PAGE_BYTES;i=i+1)mem[PAGE_BYTES+i]=((PAGE_BYTES+i)*73)^((PAGE_BYTES+i)>>8);
        fragments=native_list[180];launch_tile(32,128,3);
        for(integer i=0;i<307200;i=i+1)if({mem[PAGE_BYTES+i*2+1],mem[PAGE_BYTES+i*2]}!==native_pixels[i])$fatal(1,"Actual C tile pixels %0d",i);
        $display("TILE C LIST RTL PASSED: actual 1024-Sprite C bins and scalar C full frame");
        // Display owns A; tiled writes and position/texture DMA must preserve it.
        for(integer i=0;i<PAGE_BYTES;i=i+2){mem[i+1],mem[i]}=16'h1082;
        fixture(32,512,0);write_reg(32,1);scan_check=1;
        while(scanned_frames<3)launch_tile(32,128,3);
        read_reg(4,status);if(status&48 || video_read_bursts==0 || contentions==0)$fatal(1,"Tile/HDMI contention failed %h",status);
        $display("TILE RTL PASSED checked=%0d errors=%0d: original pixels/order, one viewport write, AXI faults drained",checked,failed_checks);$finish;
    end
    initial begin #2000000000;$fatal(1,"Tile watchdog");end
endmodule
'''
bench=out/'tb.sv';bench.write_text(prefix+tail,encoding='utf-8');lib='sim/work_tiles'
def run(cmd,tag):
 r=subprocess.run(list(map(str,cmd)),cwd=ROOT,capture_output=True,text=True,errors='replace')
 (ROOT/f'reports/tile_{tag}.log').write_text(r.stdout+r.stderr,encoding='utf-8')
 if r.returncode:print(r.stdout+r.stderr);r.check_returncode()
 return r.stdout+r.stderr
if not (ROOT/lib).exists():run([a.modelsim/'vlib.exe',lib],'vlib')
run([a.modelsim/'vlog.exe','-sv','-work',lib,'rtl/sync_fifo.v','rtl/fill_engine.v','rtl/render_batch.v',
     'rtl/tile_renderer.v','rtl/ui_compositor.v','rtl/ui_asset_rom.v','rtl/render_regs.v','rtl/framebuffer_video.v',
     'rtl/video_mode_measure.v','rtl/render_subsystem.v',bench],'vlog')
log=run([a.modelsim/'vsim.exe','-batch','-t','1ps','-lib',lib,'tb_tiles',
         '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'run')
assert 'TILE RTL PASSED' in log and 'Errors: 0, Warnings: 0' in log,log[-4000:]
names=('side','count','ready','alpha','flags','frame','fragments','legacy_cycles','tile_cycles','AR','AW')
rows=[dict(zip(names,map(int,m))) for m in re.findall(r'TILE side=(\d+) count=(\d+) ready=(\d+) alpha=(\d+) flags=(\d+) frame=(\d+) fragments=(\d+) legacy_cycles=(\d+) tile_cycles=(\d+) AR=(\d+) AW=(\d+)',log)]
assert input_hashes=={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in inputs},'RTL changed during test'
result={'scope':'RTL modeled full viewport render including APB, excluding CPU binning, HUD and scanout; not MAX60',
        'cases':rows,'source_sha256':input_hashes,
        'actual_C_list_SHA256':{n:hashlib.sha256((ROOT/'software/build/render_batch'/n).read_bytes()).hexdigest()
                               for n in ('native_tile_list.hex','native_tile_texture.hex','native_tile_expected.hex')},
        'HDMI':'3 complete frames with tile traffic, no front-page changes/underflows',
        'pixel_and_error_checks':re.search(r'TILE RTL PASSED checked=(\d+) errors=(\d+)',log).groups()}
(ROOT/'reports/tile_renderer.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print('PASS tile RTL pixels and errors')
for row in rows:
 if row['legacy_cycles']:print(row)
