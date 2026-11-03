`timescale 1ns/1ps
module tb_cpu120;
    reg clk=0,mem_clk=0,pixel_clk=0,reset=1,uart_rx=1;
    always #4.166667 clk=~clk;
    // Deliberate phase offset: do not depend on coincident clock edges.
    initial begin #1.37; forever #5 mem_clk=~mem_clk; end
    always #19.8347107 pixel_clk=~pixel_clk;
    wire soc_reset,master_reset,uart_tx;
    wire [3:0] button_ack;
`ifdef CPU120_GAME
    wire [4:0] button_pending,button_held;
    reg [4:0] key_i=31;
    button_input #(.KEY_COUNT(5),.ENABLE_REPEAT(0),.DEBOUNCE_CYCLES(32)) buttons(
        .clk(clk),.reset(soc_reset),.key_n(key_i),.ack_toggle(button_ack[0]),
        .pending(button_pending),.held(button_held));
    integer presents=0,game_frames=0,state=-1,menus=0,alpha_draws=0;
`else
    wire [4:0] button_pending=0;
    wire [4:0] button_held=0;
`endif
    wire [15:0] paddr,pixel;
    wire psel,penable,pwrite,pready,pslverror;
    wire [31:0] pwdata,prdata,awaddr,wdata,araddr,rdata;
    wire [7:0] awlen,arlen;
    wire [3:0] wstrb;
    wire [1:0] bresp,rresp;
    wire awvalid,awready,wvalid,wready,wlast,bvalid,bready;
    wire arvalid,arready,rvalid,rready,rlast,hs,vs,de;
    `define SOC_MEMORY_CLK mem_clk
    `include "soc_wiring.vh"
    render_subsystem graphics(
        .clk(clk),.reset(soc_reset|master_reset),.pixel_clk(pixel_clk),.memory_ready(1'b1),
        .button_held(button_held),.button_enter_pending(button_pending[4]),
        .paddr(paddr),.psel(psel),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),
        .prdata(prdata),.pready(pready),.pslverror(pslverror),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wlast(wlast),.wvalid(wvalid),.wready(wready),
        .bresp(bresp),.bvalid(bvalid),.bready(bready),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rresp(rresp),.rlast(rlast),.rvalid(rvalid),.rready(rready),
        .pixel(pixel),.hs(hs),.vs(vs),.de(de));
    localparam BASE=32'h01000000,MEM_BYTES=3145728;
    reg [7:0] mem[0:MEM_BYTES-1];
    integer wa=0,ra=0,wl=0,rl=0,wb=0,rb=0,ws=0,rs=0,cycle=0;
    reg [7:0] wid=0,rid=0;
    reg writing=0,reading=0;
    integer cpu_writes=0,gfx_writes=0,stalls=0,verified_scans=0,px=0,py=0;
    reg prev_de=0;
    time timer_start=0;
    reg timer_ok=0;
`ifdef CPU120_GAME
    initial forever begin
        #20000000;
        $display("CPU120 GAME progress time=%0t presents=%0d state=%0d scans=%0d",$time,presents,state,verified_scans);
        $fflush();
    end
    always @(posedge clk) if(!soc_reset && psel && penable && pready) begin
        if(pslverror) $fatal(1,"APB error in game firmware");
        if(state==1 && pwrite && paddr==8 && graphics.operation==2) begin
            if(graphics.blend_ctrl!=3) $fatal(1,"Alpha/key disabled");
            alpha_draws++;
        end
        if(pwrite && paddr==64) begin
            presents++;
            if(state==1) game_frames++;
            $display("CPU120 GAME present=%0d state=%0d game_frames=%0d",presents,state,game_frames);
        end
    end
    task tap(input [4:0] mask);
        key_i=~mask;#2000;key_i=31;#2000;
    endtask
    task menu_key(input [4:0] mask);
        integer last;last=presents;tap(mask);wait(presents>last);
    endtask
    initial begin
        wait(presents>=1 && verified_scans>=1);
        menu_key(2);menu_key(2);tap(16);wait(state==0);
        tap(16);wait(state==1);key_i=~5'd8;wait(game_frames>=4);key_i=31;
        tap(16);wait(state==3);tap(4);wait(menus>=4);wait(verified_scans>=5);
        if(alpha_draws<10 || graphics.underflow || graphics.read_error) $fatal(1,"Game coverage/scanout error");
        $display("CPU120 GAME SMOKE PASSED: actual game firmware; menu/start/movement/pause/return; Alpha+Key=%0d; HDMI_scans=%0d; DDR stalls=%0d",alpha_draws,verified_scans,stalls);
        $finish;
    end
`endif
    // DDR controller is modeled at its 128-bit / 100 MHz AXI interface.
    always @(negedge mem_clk) begin
        m_awready=!reset&&!writing&&!m_bvalid&&(cycle%7!=0);
        m_wready=!reset&&writing&&(cycle%5!=0);
        m_arready=!reset&&!reading&&!m_rvalid&&(cycle%11!=0);
        if(!reset&&reading&&!m_rvalid&&(cycle%3!=0)) begin
            for(integer b=0;b<16;b++) m_rdata[b*8+:8]=mem[(ra&~15)+b];
            m_rid=rid; m_rresp=0; m_rlast=rb==rl; m_rvalid=1;
        end
    end
    always @(posedge mem_clk) begin
        if(reset) begin
            writing=0; reading=0; m_bvalid<=0; m_rvalid<=0;
            timer_start=0; timer_ok=0;
        end else begin
            cycle++;
            if((m_awvalid&&!m_awready)||(m_wvalid&&!m_wready)||(m_arvalid&&!m_arready)) stalls++;
            if(m_awvalid&&m_awready) begin
`ifdef CPU120_GAME
                if(graphics.display_enable && m_awaddr<BASE+2*614400 &&
                   ((m_awaddr>=BASE+614400)==graphics.display_page_sync[1]))
                    $fatal(1,"Game wrote to visible framebuffer");
`endif
                wa=m_awaddr-BASE; wl=m_awlen; wb=0; ws=1<<m_awsize; wid=m_awid; writing=1;
                if(wa<0||wa+16>=MEM_BYTES) $fatal(1,"DDR write out of range");
            end
            if(m_wvalid&&m_wready) begin
                if(m_wlast!=(wb==wl)) $fatal(1,"WLAST changed across CDC");
                for(integer b=0;b<16;b++) if(m_wstrb[b]) mem[(wa&~15)+b]=m_wdata[8*b+:8];
                if(wid[7]) gfx_writes++; else cpu_writes++;
                if(BASE+wa==32'h012e0400 && m_wdata[31:0]==32'h11111111) timer_start=$time;
                if(BASE+wa==32'h012e0400 && m_wdata[31:0]==32'h22222222) begin
                    if($time-timer_start<999000 || $time-timer_start>1010000) $fatal(1,"CLINT timebase mismatch: %t",$time-timer_start);
                    timer_ok=1;
                end
                wa=(wa&~(ws-1))+ws; wb++;
                if(m_wlast) begin writing=0; m_bvalid<=1; m_bid<=wid; m_bresp<=0; end
            end
            if(m_bvalid&&m_bready) m_bvalid<=0;
            if(m_arvalid&&m_arready) begin
                ra=m_araddr-BASE; rl=m_arlen; rb=0; rs=1<<m_arsize; rid=m_arid; reading=1;
                if(ra<0||ra+16>=MEM_BYTES) $fatal(1,"DDR read out of range");
            end
            if(m_rvalid&&m_rready) begin ra=(ra&~(rs-1))+rs; rb++; m_rvalid<=0; if(m_rlast) reading=0; end
        end
    end
    always @(posedge pixel_clk) begin
        if(reset || !graphics.display_enable) begin px=0;py=0;prev_de=0; if(reset) verified_scans=0; end
        else begin
            #0.01;
            if(de && graphics.display_enable) begin
                if(pixel!=={mem[graphics.display_page_active*614400+(py*640+px)*2+1],
                             mem[graphics.display_page_active*614400+(py*640+px)*2]})
                    $fatal(1,"HDMI pixel mismatch %0d,%0d",px,py);
                px++;
            end
            if(prev_de&&!de && graphics.display_enable) begin
                if(px!=640) $fatal(1,"HDMI line width %0d",px);
                px=0;py++;
                if(py==480) begin py=0;verified_scans++;end
            end
            prev_de=de&&graphics.display_enable;
        end
    end
    reg [7:0] ch;
    string line="";
    initial forever begin
        @(negedge uart_tx); #13000;
        for(integer n=0;n<8;n++) begin ch[n]=uart_tx; #8666.667;end
        line={line,ch};
        if(ch==10) begin
            $display("PROBE UART: %s",line);
`ifdef CPU120_GAME
            if(line=="MENU\015\012") menus++;
            if(line.substr(0,10)=="GAME STATE ") begin
                if($sscanf(line,"GAME STATE %d",state)!=1) $fatal(1,"Bad game state");
            end
            if(line.substr(0,3)=="FAIL" || line.substr(0,3)=="TRAP") $fatal(1,"Game firmware failed: %s",line);
`else
            if(line=="CPU120 CROSS-CLOCK PASS\015\012") begin
                if(!timer_ok || cpu_writes<256 || gfx_writes<38400 || stalls<10 || verified_scans<1)
                    $fatal(1,"Missing coverage timer=%d cpu=%d gfx=%d stalls=%d scans=%d",timer_ok,cpu_writes,gfx_writes,stalls,verified_scans);
                if({mem[12822+1],mem[12822]}!==16'h800f || {mem[12820+1],mem[12820]}!==16'h001f)
                    $fatal(1,"Alpha/key pixel result wrong");
                $display("CPU120 CDC TEST PASSED: CPU120/DDR100/HDMI25.208; reset during traffic; byte masks; CLINT1ms; alpha/key; stalls=%0d cpu_writes=%0d gfx_writes=%0d HDMI_scans=%0d",stalls,cpu_writes,gfx_writes,verified_scans);
                $finish;
            end
            if(line=="CPU120 PROBE FAIL\015\012") $fatal(1,"Probe firmware failed");
`endif
            line="";
        end
    end
    initial begin
        for(integer i=0;i<MEM_BYTES;i++) mem[i]=8'ha5;
        repeat(50) @(negedge clk);reset=0;
`ifndef CPU120_GAME
        wait(cpu_writes>10); @(negedge clk);reset=1;
        repeat(50) @(negedge clk);reset=0;
`endif
    end
    initial begin #500000000;$fatal(1,"CPU120 test timeout");end
endmodule
