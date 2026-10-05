`timescale 1ns/1ps
module tb_resolution_soc;
    reg clk=0,pixel_clk=0,reset=1,uart_rx=1;
    always #5 clk=~clk;
    reg [3:0] key_state=0;
    wire soc_reset,master_reset,uart_tx;
    wire [15:0] paddr,pixel;
    wire psel,penable,pwrite,pready,pslverror;
    wire [31:0] pwdata,prdata,awaddr,wdata,araddr,rdata;
    wire [7:0] awlen,arlen;
    wire [3:0] wstrb;
    wire [1:0] bresp,rresp;
    wire awvalid,awready,wvalid,wready,wlast,bvalid,bready;
    wire arvalid,arready,rvalid,rready,rlast,hs,vs,de;
    `include "soc_wiring.vh"
    wire mode_active,clock_hold,clock_ready,pll_reset_n;
    wire [1:0] clock_select;
    wire [7:0] clock_debug;
    reg pll_locked=0;
    integer lock_count=0;
    wire graphics_reset=soc_reset|master_reset;
    // Model-only fix for the vendor FIFO's invalid empty payload (same as
    // the established sprite77 SoC test). Valid UART bytes are untouched.
    wire [7:0] safe_uart_payload =
        cpu.u_EfxSapphireSoc.system_uart_0_io_logic.uartCtrl_1_io_read_queueWithOccupancy_io_pop_valid ?
        cpu.u_EfxSapphireSoc.system_uart_0_io_logic.uartCtrl_1_io_read_queueWithOccupancy_io_pop_payload : 8'h00;
    initial begin
        #1;
        force cpu.u_EfxSapphireSoc.system_uart_0_io_logic.bridge_read_streamBreaked_payload = safe_uart_payload;
    end
    video_clock_control #(.RESET_CYCLES(20),.LOCK_CYCLES(20),.DEFAULT_MODE(1),.FIXED_MODE(1)) clocks(
        .clk(clk),.reset(graphics_reset),.mode_active(mode_active),.pll_locked(pll_locked),
        .clock_select(clock_select),.pll_reset_n(pll_reset_n),.clock_hold(clock_hold),.clock_ready(clock_ready),
        .debug_status(clock_debug));
    always @(posedge clk)
        if(!pll_reset_n) begin pll_locked<=0; lock_count<=0; end
        else if(lock_count==10) pll_locked<=1;
        else lock_count<=lock_count+1;
    always begin
        #(clock_select[0] === 1'b1 ? 12.5 : 20.0);
        pixel_clk=pll_reset_n === 1'b1 ? ~pixel_clk : 0;
    end
    render_subsystem graphics(
        .clk(clk),.reset(graphics_reset),.pixel_clk(pixel_clk),.memory_ready(1'b1),.key2_down(1'b0),
        .clock_hold(clock_hold),.clock_ready(clock_ready),.mode_active(mode_active),
        .clock_debug(clock_debug),
        .paddr(paddr),.psel(psel),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),
        .prdata(prdata),.pready(pready),.pslverror(pslverror),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wlast(wlast),.wvalid(wvalid),.wready(wready),
        .bresp(bresp),.bvalid(bvalid),.bready(bready),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rresp(rresp),.rlast(rlast),.rvalid(rvalid),.rready(rready),
        .pixel(pixel),.hs(hs),.vs(vs),.de(de));
    localparam BASE=32'h01000000,PAGE_BYTES=960000,ASSET_BASE=32'h01200000,
               APP_HEAD=32'h013ffff0,APP_BASE=32'h01400000,MEM_BYTES=APP_BASE-BASE+65536;
    // DDR storage is explicitly initialized; two-state arrays avoid carrying
    // unknown-state bookkeeping across millions of byte writes.
    bit [7:0] mem[0:MEM_BYTES-1];
    bit [15:0] snapshot[0:959999];
    reg writing=0,reading=0;
    integer wa,ra,wl,rl,wb,rb,ws,rs;
    reg [7:0] wid,rid;
    integer presents=0,mode_writes=0,commands=0,stage=0,hw_fills=0;
    integer frames[0:1];
    integer progress_file,axi_reads=0,axi_write_beats=0;
    integer saved_page;
    reg [31:0] scene_signature=0,transparency_percent=0;
    always @(negedge clk) begin
        m_awready=!writing&&!m_bvalid; m_wready=writing;
        m_arready=!reading&&!m_rvalid;
        if(reading&&!m_rvalid) begin
            for(integer b=0;b<16;b=b+1) m_rdata[b*8+:8]=mem[(ra&~15)+b];
            m_rid=rid; m_rresp=0; m_rlast=rb==rl; m_rvalid=1;
        end
    end
    always @(posedge clk) if(!reset) begin
        if(m_awvalid&&m_awready) begin
            if(m_awaddr<BASE || (m_awaddr&~15)+(m_awlen+1)*(1<<m_awsize)>BASE+MEM_BYTES)
                $fatal(1,"DDR AW range");
            if(graphics.display_enable && m_awaddr<BASE+2*PAGE_BYTES &&
               ((m_awaddr>=BASE+PAGE_BYTES)==graphics.display_page_sync[1]))
                $fatal(1,"Write to displayed page");
            wa=m_awaddr-BASE; wl=m_awlen; wb=0; ws=1<<m_awsize; wid=m_awid; writing=1;
        end
        if(m_wvalid&&m_wready) begin
            axi_write_beats=axi_write_beats+1;
            if(m_wlast!=(wb==wl)) $fatal(1,"WLAST");
            for(integer b=0;b<16;b=b+1) if(m_wstrb[b]) mem[(wa&~15)+b]=m_wdata[8*b+:8];
            // Watch the firmware's diagnostics when DDR writes commit. A
            // wait on a function reading an array has no direct event source.
            if((wa&~15)==32'h013fff00-BASE)
                scene_signature={mem[(wa&~15)+3],mem[(wa&~15)+2],mem[(wa&~15)+1],mem[wa&~15]};
            if((wa&~15)==32'h013fff10-BASE)
                transparency_percent={mem[(wa&~15)+15],mem[(wa&~15)+14],mem[(wa&~15)+13],mem[(wa&~15)+12]};
            wa=(wa&~(ws-1))+ws; wb=wb+1;
            if(m_wlast) begin writing=0; m_bvalid<=1; m_bid<=wid; m_bresp<=0; end
        end
        if(m_bvalid&&m_bready) m_bvalid<=0;
        if(m_arvalid&&m_arready) begin
            axi_reads=axi_reads+1;
            if(m_araddr<BASE || (m_araddr&~15)+(m_arlen+1)*(1<<m_arsize)>BASE+MEM_BYTES)
                $fatal(1,"DDR AR range");
            ra=m_araddr-BASE; rl=m_arlen; rb=0; rs=1<<m_arsize; rid=m_arid; reading=1;
        end
        if(m_rvalid&&m_rready) begin
            ra=(ra&~(rs-1))+rs; rb=rb+1; m_rvalid<=0;
            if(m_rlast) reading=0;
        end
        if(psel&&penable&&pready) begin
            if(pslverror) $fatal(1,"Firmware APB error %h",paddr);
            if(pwrite&&paddr==16'h5c) begin
                if(stage<1 || stage>4) $fatal(1,"Resolution changed outside BASIC");
                mode_writes=mode_writes+1;
            end
            if(pwrite&&paddr==8) begin
                commands=commands+1;
                if(mode_active && graphics.operation==0 && graphics.width==800 && graphics.height==600)
                    hw_fills=hw_fills+1;
            end
            if(pwrite&&paddr==16'h40) begin
                if(writing || m_bvalid) $fatal(1,"PRESENT before writes drained");
                saved_page=graphics.swap_page;
                for(integer n=0;n<480000;n=n+1)
                    snapshot[saved_page*480000+n]={mem[saved_page*PAGE_BYTES+n*2+1],mem[saved_page*PAGE_BYTES+n*2]};
                presents=presents+1;
                $display("PRESENT %0d mode=%0d stage=%0d",presents,mode_active,stage);
            end
        end
    end
    integer px=0,py=0;
    reg prev_de=0,scan_page=0;
    always @(posedge pixel_clk) begin
        #1;
        if(!reset) begin
            if(clock_hold || !graphics.display_enable) begin px=0; py=0; prev_de=0; end
            else begin
                if(de) begin
                    if(px==0 && py==0) scan_page=graphics.display_page_active;
                    if(scan_page!=graphics.display_page_active ||
                       pixel!==snapshot[scan_page*480000+py*800+px])
                        $fatal(1,"Real CPU scanout mismatch (%0d,%0d) mode=%0d",px,py,mode_active);
                    px=px+1;
                end
                if(prev_de&&!de) begin
                    if(px!=(mode_active ? 800 : 640)) $fatal(1,"Active width");
                    px=0; py=py+1;
                    if(py==(mode_active ? 600 : 480)) begin
                        frames[mode_active]=frames[mode_active]+1; py=0;
                    end
                end
                prev_de=de;
            end
        end
    end
    string uart_line="";
    reg [7:0] uart_char;
    reg advanced_seen=0;
    reg new_app_seen=0;
    reg underflow_warning_seen=0;
    string expected_banner="Ti60 FIXED 800X600 20261005";
    reg [7:0] expected_app[0:65551];
    integer expected_app_bytes;
    initial forever begin
        @(negedge uart_tx); #13020;
        for(integer bitno=0;bitno<8;bitno=bitno+1) begin uart_char[bitno]=uart_tx; #8680; end
        uart_line={uart_line,uart_char};
        if(uart_char==10) begin
            $display("UART: %s",uart_line);
            if(uart_line.substr(0,3)=="FAIL" || uart_line.substr(0,3)=="TRAP") $fatal(1,"Firmware failure");
            if(uart_line.substr(0,12)=="ADVANCED DEMO") advanced_seen=1;
            if(uart_line.substr(0,19)=="WARN video underflow") underflow_warning_seen=1;
            if(uart_line.substr(0,expected_banner.len()-1)==expected_banner) new_app_seen=1;
            uart_line="";
        end
    end
    task press(input integer key);
        @(negedge clk); key_state[key]=~key_state[key];
    endtask
    integer target,old_mode_writes,old_frames;
    initial begin
        progress_file=$fopen("reports/resolution_soc_progress.log","w");
        frames[0]=0; frames[1]=0;
        for(integer n=0;n<MEM_BYTES;n=n+1) mem[n]=8'ha5;
        $readmemh("sim/sprite77_compact.memh",mem,ASSET_BASE-BASE);
        $readmemh("sim/app_image_compact.memh",mem,APP_HEAD-BASE);
        if($test$plusargs("BOOT_ROM_ONLY")) begin
            $readmemh("sim/app_image_compact.memh",expected_app);
            expected_app_bytes={expected_app[7],expected_app[6],expected_app[5],expected_app[4]};
            // A stale/unusable DDR program must be replaced by the ROM.
            for(integer n=0;n<65536;n=n+1) mem[APP_BASE-BASE+n]=8'ha5;
        end
        repeat(50) @(negedge clk); reset=0;
        if($test$plusargs("BOOT_ROM_ONLY")) begin
            wait(new_app_seen);
            if(!mode_active || !clock_ready || clock_select!=1 || !graphics.mode_request)
                $fatal(1,"Embedded app did not start with fixed 800x600 clocks");
            for(integer n=0;n<expected_app_bytes;n=n+1)
                if(mem[APP_BASE-BASE+n]!==expected_app[16+n])
                    $fatal(1,"Embedded application mismatch at byte %0d",n);
            for(integer n=0;n<12;n=n+1)
                if(mem[APP_HEAD-BASE+n]!==expected_app[n]) $fatal(1,"Embedded header mismatch");
            $display("EMBEDDED BOOT TEST PASSED: stale DDR app overwritten, APB ROM copied byte-for-byte, real CPU entered new application");
            $fclose(progress_file); $finish;
        end
        wait(presents==1); press(2); // Menu ENTER.
        wait(presents==2);
        if($test$plusargs("BASIC_HW_ONLY")) begin
            stage=3; press(0);
            wait(hw_fills>0);
            // A recorded late line must not permanently halt the application.
            if($test$plusargs("VIDEO_UNDERFLOW")) force graphics.underflow=1'b1;
            target=presents+2; wait(presents>=target);
            if(graphics.error || (!$test$plusargs("VIDEO_UNDERFLOW") && graphics.underflow) || graphics.read_error)
                $fatal(1,"BASIC hardware switch error");
            if($test$plusargs("VIDEO_UNDERFLOW") && !underflow_warning_seen)
                $fatal(1,"Scanout warning was not reported");
            $display("BASIC HW SWITCH TEST PASSED: two hardware frames with active 800x600 scanout");
            $fclose(progress_file); $finish;
        end
        stage=1; target=presents+1; press(2); wait(presents>=target);
        if(mode_writes || !mode_active || clock_select!=1)
            $fatal(1,"BASIC KEY2 changed fixed resolution");
        stage=3; target=presents+1; press(0); wait(presents>=target);
        wait(hw_fills>0);
        stage=4; target=presents+1; press(3); wait(presents>=target);
        stage=5; target=presents+1; press(1); wait(presents>=target); press(2);
        wait(advanced_seen); wait(scene_signature[31:24]==8'h77);
        if(transparency_percent!=0) $fatal(1,"Initial advanced transparency");
        press(2); wait(transparency_percent==2);
        if(mode_writes || !mode_active || graphics.underflow || graphics.read_error)
            $fatal(1,"Fixed-mode scanout/controls error");
        $display("FIXED800 SOC TEST PASSED: menu, BASIC KEY2 ignored, CPU/HW, return, advanced Alpha");
        $fclose(progress_file);
        $finish;
    end
    initial forever begin
        #10000000;
        $fdisplay(progress_file,"time=%0t reset=%b ready=%b stage=%0d presents=%0d reads=%0d writes=%0d mode=%b display=%b PC=%h APB=%h",
                  $time,graphics_reset,clock_ready,stage,presents,axi_reads,axi_write_beats,mode_active,
                  graphics.display_enable,cpu.u_EfxSapphireSoc.system_cores_0_logic_cpu.IBusCachedPlugin_fetchPc_pcReg,paddr);
        $fflush(progress_file);
    end
    initial begin #1000000000; $fatal(1,"Resolution SoC timeout stage=%0d presents=%0d",stage,presents); end
    initial if($test$plusargs("BOOT_ROM_ONLY")) begin
        #30000000; $fatal(1,"Embedded application did not start within 30 ms");
    end
endmodule
