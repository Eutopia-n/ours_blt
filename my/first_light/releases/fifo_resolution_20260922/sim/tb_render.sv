`timescale 1ns/1ps
module tb_render;
    reg clk=0, pixel_clk=0, reset=1, memory_ready=1;
    always #5 clk=~clk;
    always #19.8347107 pixel_clk=~pixel_clk;
    reg [15:0] paddr=0;
    reg psel=0, penable=0, pwrite=0;
    reg [31:0] pwdata=0;
    wire [31:0] prdata;
    wire pready, pslverror;
    wire [31:0] awaddr,wdata,araddr;
    wire [7:0] awlen,arlen;
    wire [3:0] wstrb;
    wire awvalid,wvalid,wlast,bready,arvalid,rready;
    reg awready=0,wready=0,bvalid=0,arready=0,rvalid=0,rlast=0;
    reg [1:0] bresp=0,rresp=0;
    reg [31:0] rdata=0;
    wire [15:0] pixel;
    wire hs,vs,de;
    render_subsystem dut(.*);
    localparam BASE=32'h01000000, PAGE_BYTES=614400, MEM_BYTES=1228800;
    reg [31:0] draw_base=BASE;
    reg [7:0] mem[0:MEM_BYTES-1];
    reg [7:0] golden[0:MEM_BYTES-1];
    reg [15:0] snapshot[0:307199];
    reg [31:0] rng=32'h19a35b17;
    integer wa,ra,wl,rl,wb,rb;
    integer write_delay=0;
    reg writing=0,reading=0, inject_write_error=0,inject_read_error=0;
    reg force_bus_ready=0;
    integer bursts=0,read_bursts=0,crossings=0,read_crossings=0;
    integer copy_read_bursts=0,video_read_bursts=0,contentions=0,checked_copies=0;
    integer copy_16beat_bursts=0,ready_write_cycles=0;
    reg held_aw=0,held_ar=0,held_w=0;
    reg [39:0] last_aw,last_ar;
    reg [36:0] last_w;
    // All address/data/control signals must remain stable under backpressure.
    always @(posedge clk) if(!reset) begin
        if(held_aw && (!awvalid || {awaddr,awlen}!==last_aw)) $fatal(1,"AW changed while stalled");
        if(held_ar && (!arvalid || {araddr,arlen}!==last_ar)) $fatal(1,"AR changed while stalled");
        if(held_w && (!wvalid || {wdata,wstrb,wlast}!==last_w)) $fatal(1,"W changed while stalled");
        held_aw=awvalid&&!awready; last_aw={awaddr,awlen};
        held_ar=arvalid&&!arready; last_ar={araddr,arlen};
        held_w=wvalid&&!wready; last_w={wdata,wstrb,wlast};
        if(dut.fill_arvalid&&dut.video_arvalid) contentions=contentions+1;
        if(dut.fill.fifo_overflow||dut.fill.fifo_underflow)
            $fatal(1,"Write FIFO overflow/underflow");
        if(dut.fill.fifo_level>16) $fatal(1,"Write FIFO level exceeded its depth");
        // Once an AW burst has started, a ready slave must see a W beat every
        // cycle. This catches the old synchronous-row-RAM C_WLOAD bubbles.
        if(writing&&wready) begin
            ready_write_cycles=ready_write_cycles+1;
            if(!wvalid) $fatal(1,"WVALID bubble while WREADY was asserted");
        end
    end
    // Deterministic randomized AXI backpressure and independent read/write responses.
    always @(negedge clk) begin
        rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
        awready=!writing && !bvalid && write_delay==0 && (force_bus_ready||rng[0]);
        wready=writing && (force_bus_ready||rng[2]);
        arready=!reading && !rvalid && (force_bus_ready||rng[3]);
        if(reading && !rvalid && (force_bus_ready||rng[4])) begin
            rdata={mem[ra+3],mem[ra+2],mem[ra+1],mem[ra]};
            rlast=rb==rl; rresp=inject_read_error ? 2'b10 : 0; rvalid=1;
        end
    end
    always @(posedge clk) if(!reset) begin
        if(awvalid && awready) begin
            if(awlen>15 || awaddr[1:0]!=0 || awaddr[11:0]+(awlen+1)*4>4096)
                $fatal(1,"Illegal AXI AW burst");
            if(awaddr<BASE || awaddr+(awlen+1)*4>BASE+MEM_BYTES) $fatal(1,"AW outside framebuffer");
            if(awaddr[11:0]==0) crossings=crossings+1;
            if(dut.fill.copy_mode && awlen==15) copy_16beat_bursts=copy_16beat_bursts+1;
            wa=awaddr-BASE; wl=awlen; wb=0; writing=1; bursts=bursts+1;
        end
        if(wvalid && wready) begin
            if(wlast!=(wb==wl)) $fatal(1,"WLAST mismatch");
            for(integer b=0;b<4;b=b+1) if(wstrb[b]) mem[wa+b]=wdata[8*b+:8];
            wa=wa+4; wb=wb+1;
            if(wlast) begin writing=0; write_delay=4; end
        end
        if(write_delay>0) begin
            write_delay=write_delay-1;
            if(write_delay==0) begin bvalid<=1; bresp<=inject_write_error ? 2'b10 : 0; end
        end
        if(bvalid && bready) bvalid<=0;
        if(arvalid && arready) begin
            if(arlen>15 || araddr[1:0]!=0 || araddr[11:0]+(arlen+1)*4>4096)
                $fatal(1,"Illegal AXI AR burst");
            if(araddr<BASE || araddr+(arlen+1)*4>BASE+MEM_BYTES) $fatal(1,"AR outside framebuffer");
            if(araddr[11:0]==0) read_crossings=read_crossings+1;
            if(dut.read_owner_copy) copy_read_bursts=copy_read_bursts+1;
            else video_read_bursts=video_read_bursts+1;
            ra=araddr-BASE; rl=arlen; rb=0; reading=1; read_bursts=read_bursts+1;
        end
        if(rvalid && rready) begin
            ra=ra+4; rb=rb+1; rvalid<=0;
            if(rlast) reading=0;
        end
    end
    task write_reg(input [15:0] address,input [31:0] value,input bit expect_error=0);
        @(negedge clk); psel=1; penable=0; pwrite=1; paddr=address; pwdata=value;
        @(negedge clk); penable=1;
        @(posedge clk);
        if(pslverror!==expect_error) $fatal(1,"APB error mismatch at %h",address);
        @(negedge clk); psel=0; penable=0; pwrite=0;
    endtask
    task read_reg(input [15:0] address,output [31:0] value);
        @(negedge clk); psel=1; penable=0; pwrite=0; paddr=address;
        @(negedge clk); penable=1;
        @(posedge clk); value=prdata;
        if(pslverror) $fatal(1,"Unexpected APB read error");
        @(negedge clk); psel=0; penable=0;
    endtask
    task fill(input integer x,y,w,h,input [15:0] color,input bit expect_error=0);
        reg [31:0] status;
        integer tries;
        write_reg(48,0);
        write_reg(12,draw_base+y*1280+x*2); write_reg(16,w); write_reg(20,h);
        write_reg(24,1280); write_reg(28,color); write_reg(8,1);
        status=0; tries=0;
        while((status&3)!=2) begin
            read_reg(4,status); tries=tries+1;
            if(tries>1000000) $fatal(1,"Fill timeout");
        end
        if(((status&4)!=0)!=expect_error) $fatal(1,"Fill error mismatch: %h",status);
    endtask
    // Independent golden model snapshots all source pixels before any writes.
    // Checking the entire framebuffer also catches damaged edge neighbours.
    task checked_copy(input integer sx,sy,dx,dy,w,h);
        integer s,d;
        for(integer n=0;n<MEM_BYTES;n=n+1) golden[n]=mem[n];
        for(integer y=0;y<h;y=y+1) for(integer x=0;x<w;x=x+1) begin
            s=draw_base-BASE+(sy+y)*1280+(sx+x)*2;
            snapshot[y*w+x]={golden[s+1],golden[s]};
        end
        for(integer y=0;y<h;y=y+1) for(integer x=0;x<w;x=x+1) begin
            d=draw_base-BASE+(dy+y)*1280+(dx+x)*2;
            {golden[d+1],golden[d]}=snapshot[y*w+x];
        end
        copy_block(sx,sy,dx,dy,w,h);
        for(integer n=0;n<MEM_BYTES;n=n+1)
            if(mem[n]!==golden[n]) $fatal(1,"Copy (%0d,%0d)->(%0d,%0d) %0dx%0d byte %0d got %h expected %h",sx,sy,dx,dy,w,h,n,mem[n],golden[n]);
        checked_copies=checked_copies+1;
    endtask
    task copy_block(input integer sx,sy,dx,dy,w,h,input bit expect_error=0);
        reg [31:0] status;
        integer tries;
        write_reg(48,1); write_reg(52,draw_base+sy*1280+sx*2);
        write_reg(12,draw_base+dy*1280+dx*2); write_reg(16,w); write_reg(20,h);
        write_reg(24,1280); write_reg(8,1);
        status=0; tries=0;
        while((status&3)!=2) begin
            read_reg(4,status); tries=tries+1;
            if(tries>1000000) $fatal(1,"Copy timeout");
        end
        if(((status&4)!=0)!=expect_error) $fatal(1,"Copy error mismatch: %h",status);
    endtask
    function [15:0] expected(input integer x,y);
        integer local_y;
        if((x>=31&&x<160&&y>=301&&y<398) || (x>=211&&x<340&&y>=321&&y<418)) begin
            local_y=x<160 ? y-301 : y-321;
            expected=local_y<32 ? 16'h07ff : local_y<64 ? 16'hf81f : 16'hffe0;
        end
        else if(x>=64 && x<256 && y>=60 && y<180) expected=16'hf800;
        else if(x>=301 && x<428 && y>=161 && y<260) expected=16'h07e0;
        else if(x>=501 && x<602 && y>=351 && y<424) expected=16'h001f;
        else expected=16'h1082;
    endfunction
    reg repainted_a=0, frame_page=0, check_page_writes=0;
    function automatic [15:0] expected_page(input integer x,y,input bit page);
        if(page) begin
            if((x>=1&&x<34&&y>=7&&y<10)||(x>=101&&x<134&&y>=13&&y<16))
                expected_page=16'h07ff;
            else expected_page=16'h39e7;
        end else expected_page=repainted_a ? 16'h4a49 : expected(x,y);
    endfunction
    // Page changes and acknowledgements are legal only at the last blank line,
    // after the old page's outstanding line request has been drained.
    reg previous_page=0,previous_ack=0;
    reg boundary_safe;
    integer swap_acks=0;
    always @(posedge pixel_clk) begin
        boundary_safe=dut.video.h==0 && dut.video.v==524 &&
                      dut.video.req_toggle==dut.video.done_sync[1];
        #1;
        if(!reset) begin
            if(dut.display_page_active!=previous_page && !boundary_safe)
                $fatal(1,"Page changed outside safe frame boundary");
            if(dut.swap_ack_pixel!=previous_ack) begin
                if(!boundary_safe) $fatal(1,"Swap acknowledged before old reads drained");
                swap_acks=swap_acks+1;
            end
            previous_page=dut.display_page_active;
            previous_ack=dut.swap_ack_pixel;
        end
    end
    always @(posedge clk) if(check_page_writes && awvalid && awready)
        if((awaddr>=BASE+PAGE_BYTES)==dut.display_page_sync[1])
            $fatal(1,"Rendering wrote the front page");
    task await_swap(input bit page);
        reg [31:0] value;
        integer tries;
        value=128; tries=0;
        while(value&128) begin
            repeat(100) @(posedge clk);
            read_reg(4,value); tries=tries+1;
            if(tries>20000) $fatal(1,"Swap acknowledgement timeout");
        end
        if(((value>>6)&1)!=page || (value&48)) $fatal(1,"Swap status %h",value);
    endtask
    integer pixel_x=0,pixel_y=0,frames=0,frame_file;
    integer line_ticks=0,frame_ticks=0,hs_low=0,vs_low=0;
    reg prev_hs=1,prev_vs=1,seen_hs=0,seen_vs=0;
    reg previous_de=0, checking_video=0;
    always @(posedge pixel_clk) begin
        #1;
        if(!reset) begin
            if(prev_hs&&!hs) begin
                if(seen_hs&&line_ticks!=800) $fatal(1,"Horizontal period %0d",line_ticks);
                seen_hs=1; line_ticks=0;
            end
            if(prev_vs&&!vs) begin
                if(seen_vs&&frame_ticks!=420000) $fatal(1,"Vertical period %0d",frame_ticks);
                seen_vs=1; frame_ticks=0;
            end
            if(seen_hs) line_ticks=line_ticks+1;
            if(seen_vs) frame_ticks=frame_ticks+1;
            if(!hs) hs_low=hs_low+1;
            else if(!prev_hs) begin
                if(hs_low!=96) $fatal(1,"HS pulse width %0d",hs_low);
                hs_low=0;
            end
            if(!vs) vs_low=vs_low+1;
            else if(!prev_vs) begin
                if(vs_low!=1600) $fatal(1,"VS pulse width %0d",vs_low);
                vs_low=0;
            end
            prev_hs=hs; prev_vs=vs;
        end
        if(checking_video) begin
            if(de) begin
                if(pixel_x==0 && pixel_y==0) frame_page=dut.display_page_active;
                if(frame_page!=dut.display_page_active) $fatal(1,"Mixed pages in one frame");
                if(pixel!==expected_page(pixel_x,pixel_y,frame_page))
                    $fatal(1,"Video page %0d pixel (%0d,%0d): got %h expected %h",frame_page,pixel_x,pixel_y,pixel,expected_page(pixel_x,pixel_y,frame_page));
                if(frames==0) $fwrite(frame_file,"%c%c%c",
                    {pixel[15:11],pixel[15:13]}, {pixel[10:5],pixel[10:9]},
                    {pixel[4:0],pixel[4:2]});
                pixel_x=pixel_x+1;
            end
            if(previous_de && !de) begin
                if(pixel_x!=640) $fatal(1,"Line pixel count %0d",pixel_x);
                pixel_x=0; pixel_y=pixel_y+1;
                if(pixel_y==480) begin
                    pixel_y=0; frames=frames+1;
                    if(frames==1) $fclose(frame_file);
                end
            end
        end
        previous_de=de;
    end
    reg [31:0] status;
    integer old_writes,old_reads,test_width,frame_target,old_acks;
    initial begin
        frame_file=$fopen("reports/sim_frame.ppm","wb");
        if(frame_file==0) $fatal(1,"Cannot create simulation frame");
        $fwrite(frame_file,"P6\n640 480\n255\n");
        for(integer i=0;i<MEM_BYTES;i=i+1) mem[i]=8'ha5;
        repeat(10) @(negedge clk); reset=0;
        read_reg(0,status); if(status!==32'h32444631) $fatal(1,"ID mismatch");
        fill(1,0,0,1,16'hffff,1);
        fill(639,479,2,1,16'hffff,1);
        if(bursts!=0) $fatal(1,"Invalid command issued AXI transaction");
        fill(1,0,1,1,16'h1234);
        if({mem[1],mem[0]}!==16'ha5a5 || {mem[3],mem[2]}!==16'h1234 ||
           {mem[5],mem[4]}!==16'ha5a5) $fatal(1,"Odd single pixel strobe failed");
        inject_write_error=1; fill(0,0,2,1,16'h9999,1); inject_write_error=0;
        // Nonuniform data exposes byte order, halfword and row alignment bugs.
        for(integer n=0;n<307200;n=n+1)
            {mem[2*n+1],mem[2*n]}=((n*73)^(n/640)*911)^16'ha59b;
        old_writes=bursts; old_reads=read_bursts;
        copy_block(0,0,0,0,0,1,1);
        copy_block(639,479,0,0,2,1,1);
        copy_block(0,0,639,479,2,1,1);
        copy_block(-1,0,0,0,1,1,1);
        if(bursts!=old_writes||read_bursts!=old_reads) $fatal(1,"Invalid copy generated AXI");
        for(integer parity=0;parity<4;parity=parity+1)
            for(integer size=0;size<6;size=size+1) begin
                case(size)
                    0:test_width=1; 1:test_width=2; 2:test_width=31;
                    3:test_width=32; 4:test_width=33; 5:test_width=639;
                endcase
                checked_copy(parity&1,20,(parity>>1)&1,250,test_width,3);
            end
        checked_copy(125,3,127,19,129,7); // reads and writes cross 4K boundaries
        // With an always-ready memory, two complete rows must be faster than
        // the previous alternate C_WDATA/C_WLOAD implementation.
        force_bus_ready=1;
        checked_copy(0,100,0,350,640,2);
        read_reg(36,status);
        force_bus_ready=0;
        if(status>=1900) $fatal(1,"FIFO copy did not remove write bubbles: %0d cycles",status);
        $display("PASS: FIFO copy uses continuous W beats, 640x2 in %0d core cycles",status);
        checked_copy(51,101,52,101,121,11); // same-row overlap, right
        checked_copy(52,101,51,101,121,11); // same-row overlap, left
        checked_copy(51,101,50,102,121,19); // vertical overlap, bottom-up
        checked_copy(50,102,51,101,121,19); // vertical overlap, top-down
        checked_copy(0,0,0,0,640,480);      // maximum size, identity
        // A read error must drain the current burst and avoid writing that row.
        old_writes=bursts;
        inject_read_error=1; copy_block(31,3,41,19,129,2,1); inject_read_error=0;
        if(bursts!=old_writes||reading||rvalid) $fatal(1,"Copy read error did not drain/abort");
        checked_copy(31,3,41,19,129,2);
        inject_write_error=1; copy_block(31,3,41,19,129,2,1); inject_write_error=0;
        checked_copy(31,3,41,19,129,2);
        if(copy_read_bursts==0||read_crossings==0||copy_16beat_bursts==0||ready_write_cycles==0)
            $fatal(1,"Missing copy read/boundary/FIFO coverage");
        $display("PASS: %0d patterned copies, all alignments, sizes, overlap, read/write error recovery",checked_copies);
        fill(0,0,640,480,16'h1082);
        fill(64,60,192,120,16'hf800);
        fill(301,161,127,99,16'h07e0);
        fill(501,351,101,73,16'h001f);
        fill(31,301,129,32,16'h07ff);
        fill(31,333,129,32,16'hf81f);
        fill(31,365,129,33,16'hffe0);
        checked_copy(31,301,211,321,129,97);
        for(integer y=0;y<480;y=y+1) for(integer x=0;x<640;x=x+1)
            if({mem[y*1280+x*2+1],mem[y*1280+x*2]}!==expected(x,y))
                $fatal(1,"DDR pixel mismatch at %0d,%0d",x,y);
        $display("PASS: fill, odd pixel strobes, invalid command, write error, all 307200 DDR pixels");
        checking_video=1; write_reg(32,1);
        wait(de);
        // Keep the image unchanged while both read masters compete for DDR.
        // The comparison stays active throughout concurrent scanout and copy.
        checked_copy(0,0,0,0,640,480);
        wait(frames==2);
        read_reg(68,status);
        if(status!=={16'd480,16'd640}) $fatal(1,"Measured video size %h",status);
        read_reg(72,status);
        if(status!==1) $fatal(1,"Measured video mode not valid: %h",status);
        write_reg(68,0,1); write_reg(72,0,1);
        $display("PASS: measured HDMI active raster is 640x480; registers are read-only");
        read_reg(4,status);
        if(status&48) $fatal(1,"Video error status %h",status);
        if(crossings==0||contentions==0||video_read_bursts==0) $fatal(1,"Missing boundary/arbitration coverage");
        $display("PASS: two complete HDMI raster frames, random AXI stalls, 4K boundaries (%0d bursts)",bursts);
        $display("PASS: concurrent scanout/copy, %0d arbitration contention cycles; AXI stable under stalls",contentions);
        check_page_writes=1;
        // Fill and copy into B while every scanned A pixel is still checked.
        draw_base=BASE+PAGE_BYTES; write_reg(56,1);
        fill(639,479,2,1,16'hffff,1);
        fill(0,0,640,480,16'h39e7);
        fill(1,7,33,3,16'h07ff); checked_copy(1,7,101,13,33,3);
        wait(dut.video.v==100 && dut.video.h==100);
        write_reg(60,1); write_reg(64,1);
        read_reg(4,status);
        if((status&192)!=128) $fatal(1,"Active-frame submission was not deferred");
        write_reg(64,1,1); write_reg(60,0,1); write_reg(8,1,1);
        frame_target=frames+2; await_swap(1); wait(frames>=frame_target);
        // Retire A, repaint it, and switch back. No front-page writes allowed.
        draw_base=BASE; write_reg(56,0);
        fill(0,0,640,480,16'h4a49); repainted_a=1;
        wait(dut.video.v==200 && dut.video.h==200);
        write_reg(60,0); write_reg(64,1);
        frame_target=frames+2; await_swap(0); wait(frames>=frame_target);
        // Same-page presents still require a distinct acknowledgement.
        wait(dut.video.v==300 && dut.video.h==300);
        old_acks=swap_acks; write_reg(60,0); write_reg(64,1);
        read_reg(4,status); if(!(status&128)) $fatal(1,"Same-page present completed early");
        await_swap(0); if(swap_acks!=old_acks+1) $fatal(1,"Missing same-page acknowledgement");
        // A request submitted after the boundary must wait one more frame.
        wait(dut.video.v==524 && dut.video.h==10);
        old_acks=swap_acks; write_reg(60,1); write_reg(64,1);
        wait(dut.video.v==1);
        read_reg(4,status); if((status&192)!=128 || swap_acks!=old_acks)
            $fatal(1,"Late submission changed the page in the current frame");
        frame_target=frames+2; await_swap(1); wait(frames>=frame_target);
        // With display disabled, raster boundaries still acknowledge requests.
        write_reg(32,0); wait(!dut.video.running);
        write_reg(60,0); write_reg(64,1); await_swap(0);
        write_reg(32,1); frame_target=frames+1; wait(frames>=frame_target);
        $display("PASS: double buffer: %0d complete frames, %0d swap acknowledgements; A/B repaint, repeated/same-page/late/disabled swaps, no mixed pixels or front-page writes",frames,swap_acks);
        checking_video=0; inject_read_error=1;
        // End of frame is followed by vertical blanking before the next read.
        repeat(200000) @(posedge clk);
        read_reg(4,status); if(!(status&32)) $fatal(1,"Read error not reported");
        $display("PASS: AXI read error reporting");
        $display("ALL TESTS PASSED"); $finish;
    end
    initial begin #400000000; $fatal(1,"Global timeout"); end
endmodule
