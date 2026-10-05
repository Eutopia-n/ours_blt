`timescale 1ns/1ps
module tb_resolution #(parameter integer FIXED_SVGA=0);
    reg clk=0,pixel_clk=0,reset=0;
    // Drive an actual assertion edge while the PLL's pixel clock is stopped.
    initial #1 reset=1;
    always #5 clk=~clk;
    wire [1:0] clock_select;
    wire pll_reset_n,clock_hold,clock_ready,mode_active;
    wire [7:0] debug_status;
    wire [7:0] clock_debug=debug_status;
    reg pll_locked=0;
    integer lock_count=0;
    always @(posedge clk) begin
        if (!pll_reset_n) begin pll_locked<=0; lock_count<=0; end
        else if (lock_count==10) pll_locked<=1;
        else lock_count<=lock_count+1;
    end
    // Model both pixel frequencies and a stopped clock during PLL reset.
    always begin
        #(clock_select[0] === 1'b1 ? 12.5 : 20.0);
        pixel_clk = pll_reset_n === 1'b1 ? ~pixel_clk : 0;
    end
    video_clock_control #(.RESET_CYCLES(20),.LOCK_CYCLES(20),
        .DEFAULT_MODE(FIXED_SVGA),.FIXED_MODE(FIXED_SVGA)) clocks(.*);
    reg memory_ready=1,key2_down=0;
    reg [15:0] paddr=0;
    reg psel=0,penable=0,pwrite=0;
    reg [31:0] pwdata=0;
    wire [31:0] prdata,awaddr,wdata,araddr;
    wire [7:0] awlen,arlen;
    wire [3:0] wstrb;
    wire pready,pslverror,awvalid,wvalid,wlast,bready,arvalid,rready;
    reg awready=0,wready=0,bvalid=0,arready=0,rvalid=0,rlast=0;
    reg [1:0] bresp=0,rresp=0;
    reg [31:0] rdata=0;
    wire [15:0] pixel;
    wire hs,vs,de;
    render_subsystem #(.FIXED_SVGA(FIXED_SVGA)) dut(.*);
    localparam BASE=32'h01000000,PAGE_BYTES=960000,PITCH=1600;
    reg [15:0] mem[0:959999];
    reg reading=0,writing=0,stall_reads=0;
    integer ra,rb,rl,wa,wb,wl,tick=0;
    reg held_ar=0;
    reg [39:0] old_ar;
    integer writes=0,reads=0;
    always @(negedge clk) begin
        arready=!reading && !rvalid && !stall_reads && tick%3!=0;
        awready=!writing && !bvalid;
        wready=writing && tick%4!=0;
        if(reading && !rvalid && !stall_reads && tick%3!=0) begin
            rdata={mem[ra+1],mem[ra]}; rlast=rb==rl; rvalid=1;
        end
    end
    always @(posedge clk) if(!reset) begin
        tick=tick+1;
        if(held_ar && (!arvalid || {araddr,arlen}!==old_ar)) $fatal(1,"AR lost under backpressure");
        held_ar=arvalid&&!arready; old_ar={araddr,arlen};
        if(arvalid&&arready) begin
            if(araddr<BASE || araddr+(arlen+1)*4>BASE+2*PAGE_BYTES ||
               araddr[11:0]+(arlen+1)*4>4096 || arlen>63) $fatal(1,"Illegal video AR");
            ra=(araddr-BASE)/2; rb=0; rl=arlen; reading=1; reads=reads+1;
        end
        if(rvalid&&rready) begin
            ra=ra+2; rb=rb+1; rvalid<=0;
            if(rlast) reading=0;
        end
        if(awvalid&&awready) begin
            if(awaddr<BASE || awaddr+(awlen+1)*4>BASE+PAGE_BYTES ||
               awaddr[11:0]+(awlen+1)*4>4096) $fatal(1,"Illegal fill AW");
            wa=(awaddr-BASE)/2; wb=0; wl=awlen; writing=1;
        end
        if(wvalid&&wready) begin
            if(wlast!=(wb==wl)) $fatal(1,"WLAST");
            if(wstrb[0]) mem[wa]=wdata[15:0];
            if(wstrb[2]) mem[wa+1]=wdata[31:16];
            wa=wa+2; wb=wb+1; writes=writes+1;
            if(wlast) begin writing=0; bvalid<=1; end
        end
        if(bvalid&&bready) bvalid<=0;
    end
    function automatic [15:0] pattern(input integer x,y,page);
        pattern=16'h1234 ^ x ^ (y*17) ^ (page*16'h8000);
    endfunction
    integer px=0,py=0,frames[0:1],width_now,height_now;
    reg prev_de=0,old_mode=FIXED_SVGA;
    reg safe_change;
    always @(posedge pixel_clk) begin
        safe_change=dut.video.frame_boundary && dut.video.fetch_idle;
        #1;
        if(!reset) begin
            if(mode_active!=old_mode && (!safe_change || de)) $fatal(1,"Mode changed before reads drained");
            old_mode=mode_active;
            width_now=mode_active ? 800 : 640; height_now=mode_active ? 600 : 480;
            if(clock_hold || !dut.display_enable) begin px=0; py=0; prev_de=0; end
            else begin
                if(de) begin
                    if(pixel!==pattern(px,py,dut.display_page_active))
                        $fatal(1,"Pixel mismatch mode=%0d (%0d,%0d): %h",mode_active,px,py,pixel);
                    px=px+1;
                end
                if(prev_de&&!de) begin
                    if(px!=width_now) $fatal(1,"Wrong active line width %0d",px);
                    px=0; py=py+1;
                    if(py==height_now) begin frames[mode_active]=frames[mode_active]+1; py=0; end
                end
                prev_de=de;
            end
        end
    end
    task apb_write(input [15:0] address,input [31:0] value,input expected_error);
        @(negedge clk); paddr=address; pwdata=value; psel=1; pwrite=1;
        @(negedge clk); penable=1; #1;
        if(pslverror!==expected_error) $fatal(1,"APB write error %h err=%b busy=%b pending=%b ack=%b resetpipe=%b h=%d v=%d",
            address,pslverror,dut.busy,dut.regs.swap_pending,dut.swap_ack_pixel,
            dut.video.pixel_reset_pipe,dut.video.h,dut.video.v);
        @(negedge clk); psel=0; penable=0; pwrite=0;
    endtask
    task select_mode(input mode);
        apb_write(16'h20,0,0); apb_write(16'h5c,mode,0);
        wait(mode_active==mode && clock_ready && clock_select[0]==mode);
        apb_write(16'h20,1,0);
    endtask
    integer before_writes, startup_wait;
    integer hs_count=0,vs_count=0,hs_checks=0,vs_checks=0;
    reg prev_hs_active=0,prev_vs_active=0;
    reg hs_active,vs_active;
    always @(posedge pixel_clk) begin
        #2;
        hs_active=mode_active ? hs : !hs;
        vs_active=mode_active ? vs : !vs;
        if(!reset && dut.video.running && dut.display_enable && clock_ready) begin
            if(hs_active) hs_count=hs_count+1;
            else if(prev_hs_active) begin
                if(hs_count!=(mode_active ? 128 : 96)) $fatal(1,"HS width/polarity");
                hs_count=0; hs_checks=hs_checks+1;
            end
            if(vs_active) vs_count=vs_count+1;
            else if(prev_vs_active) begin
                if(vs_count!=(mode_active ? 4*1056 : 2*800)) $fatal(1,"VS width/polarity");
                vs_count=0; vs_checks=vs_checks+1;
            end
            prev_hs_active=hs_active; prev_vs_active=vs_active;
        end else begin
            hs_count=0; vs_count=0; prev_hs_active=0; prev_vs_active=0;
        end
    end
    initial begin
        frames[0]=0; frames[1]=0;
        for(integer n=0;n<960000;n=n+1) mem[n]=pattern(n%800,(n%480000)/800,n/480000);
        if($test$plusargs("STARTUP_ONLY")) begin $display("STARTUP: memory initialized"); $fflush(); end
        repeat(10) @(negedge clk); reset=0;
        wait(clock_ready);
        // Menu submits A->A while display is off after pixel-domain reset.
        // This is legal; acknowledge at the next blanking boundary.
        apb_write(16'h3c,0,0); apb_write(16'h40,1,0);
        startup_wait=0;
        while(dut.regs.swap_pending && startup_wait<2000000) begin
            @(negedge clk); startup_wait=startup_wait+1;
        end
        if(dut.regs.swap_pending || dut.display_page_active || dut.display_enable)
            $fatal(1,"Initial disabled-display A-to-A swap failed");
        wait(clock_ready);
        $display("PASS initial menu A-to-A swap with display disabled");
        if($test$plusargs("STARTUP_ONLY")) begin
            if(dut.heartbeat_count==0) $fatal(1,"Pixel clock heartbeat missing");
            $display("MENU STARTUP PASSED: PLL ready, pixel heartbeat, same-page acknowledgement");
            $finish;
        end
        apb_write(16'h20,1,0);
        if(FIXED_SVGA) begin
            wait(frames[1]==4);
            if(!mode_active || clock_select!=1 || dut.video_width!=800 ||
               dut.video_height!=600 || !dut.video_mode_valid || dut.underflow)
                $fatal(1,"Fixed 800x600 startup/scanout");
            apb_write(16'h5c,0,1);
            apb_write(16'h20,0,0);
            apb_write(16'h5c,0,1); // Even while blanked, timing cannot change.
            $display("PASS fixed 800x600 startup, complete pixels, HS/VS, rejected mode writes");
        end else begin
        wait(frames[0]==2);
        $display("PASS 640x480 pixels and complete frames");
        apb_write(16'h5c,1,1); // Active display cannot be reconfigured directly.
        wait(dut.video.v==20 && reading); @(negedge clk); stall_reads=1;
        apb_write(16'h20,0,0);
        apb_write(16'h5c,1,0);
        repeat(1800000) @(negedge clk);
        if(mode_active!=0 || !reading) $fatal(1,"Mode did not wait for stalled AXI burst");
        stall_reads=0;
        wait(mode_active && clock_ready && clock_select==1);
        apb_write(16'h20,1,0);
        wait(frames[1]==2);
        if(dut.video_width!=800 || dut.video_height!=600 || !dut.video_mode_valid)
            $fatal(1,"SVGA measured dimensions invalid");
        $display("PASS 800x600, rows above 511, stalled read drain, 40 MHz select");
        select_mode(0); wait(frames[0]==4);
        $display("PASS return to 640x480");
        end
        apb_write(16'h20,0,0); wait(!dut.video.running && !reading && !rvalid);
        force pll_locked=0; wait(clock_hold); repeat(30) @(negedge clk);
        if(mode_active!=FIXED_SVGA || clock_ready) $fatal(1,"Lock loss did not hold video");
        release pll_locked; wait(clock_ready);
        apb_write(16'h5c,2,1);
        apb_write(16'hc,BASE,0); apb_write(16'h18,PITCH,0); apb_write(16'h1c,16'h07e0,0);
        apb_write(16'h10,800,0); apb_write(16'h14,600,0); apb_write(16'h8,1,0);
        wait(dut.done); #1;
        if(dut.error) $fatal(1,"Full 800x600 fill rejected");
        for(integer n=0;n<480000;n=n+1) if(mem[n]!==16'h07e0) $fatal(1,"Fill missed pixel %0d",n);
        before_writes=writes;
        apb_write(16'h10,801,0); apb_write(16'h8,1,0); repeat(3) @(posedge clk); #1;
        if(!dut.error || writes!=before_writes) $fatal(1,"Oversized fill issued AXI");
        apb_write(16'h10,800,0); apb_write(16'h14,601,0); apb_write(16'h8,1,0);
        repeat(3) @(posedge clk); #1;
        if(!dut.error || writes!=before_writes) $fatal(1,"Oversized height issued AXI");
        apb_write(16'h14,600,0);
        apb_write(16'h10,0,0); apb_write(16'h8,1,0); repeat(3) @(posedge clk); #1;
        if(!dut.error || writes!=before_writes) $fatal(1,"Empty fill issued AXI");
        if(dut.read_error) $fatal(1,"Read error");
        if(!FIXED_SVGA && dut.underflow_count==0)
            $fatal(1,"Stalled scanline was not counted");
        if(hs_checks<100 || vs_checks<3) $fatal(1,"Missing sync pulse coverage");
        // The deliberately stalled line latches UNDERFLOW; normal frames above
        // are checked pixel-by-pixel before and after that display-off stall.
        $display("PASS full 800x600 fill, width boundary and empty operations");
        if(FIXED_SVGA) $display("FIXED800 TEST PASSED");
        else $display("ALL RESOLUTION TESTS PASSED");
        $finish;
    end
    initial begin #200000000; $fatal(1,"Resolution timeout ready=%b mode=%b resetpipe=%b h=%d v=%d frames=%0d/%0d req=%b done=%b",
        clock_ready,mode_active,dut.video.pixel_reset_pipe,dut.video.h,dut.video.v,frames[0],frames[1],dut.video.req_toggle,dut.video.done_toggle); end
endmodule

module tb_fixed800;
    tb_resolution #(.FIXED_SVGA(1)) test();
endmodule
