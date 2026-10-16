`timescale 1ns/1ps
module tb_soc;
    reg clk=0,pixel_clk=0,reset=1,uart_rx=1;
    reg [3:0] key_i=15;
    always #5 clk=~clk;
    always #19.8347107 pixel_clk=~pixel_clk;
    wire soc_reset,master_reset,uart_tx;
    wire [3:0] button_pending,button_ack,button_held;
    button_input #(.ENABLE_REPEAT(0),.DEBOUNCE_CYCLES(32)) buttons(
        .clk(clk),.reset(soc_reset),.key_n(key_i),.ack_toggle(button_ack[0]),.pending(button_pending),.held(button_held));
    wire [15:0] paddr,pixel;
    wire psel,penable,pwrite,pready,pslverror;
    wire [31:0] pwdata,prdata,awaddr,wdata,araddr,rdata;
    wire [7:0] awlen,arlen;
    wire [3:0] wstrb;
    wire [1:0] bresp,rresp;
    wire awvalid,awready,wvalid,wready,wlast,bvalid,bready;
    wire arvalid,arready,rvalid,rready,rlast,hs,vs,de;
    `include "soc_wiring.vh"
    render_subsystem graphics(
        .clk(clk),.reset(soc_reset|master_reset),.pixel_clk(pixel_clk),.memory_ready(1'b1),.button_held(button_held),
        .paddr(paddr),.psel(psel),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),
        .prdata(prdata),.pready(pready),.pslverror(pslverror),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wlast(wlast),.wvalid(wvalid),.wready(wready),
        .bresp(bresp),.bvalid(bvalid),.bready(bready),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rresp(rresp),.rlast(rlast),.rvalid(rvalid),.rready(rready),
        .pixel(pixel),.hs(hs),.vs(vs),.de(de));
    localparam BASE=32'h01000000,PAGE_BYTES=614400;
    localparam ASSET_BASE=32'h01200000,GAME_BASE=32'h01204000,BG=32'h01220000;
    localparam GAME_BYTES=51200,MEM_BYTES=3145728;
    reg [7:0] mem[0:MEM_BYTES-1],expected[0:MEM_BYTES-1];
    reg [15:0] game_expected[0:GAME_BYTES/2-1],player_expected[0:4095];
    integer bus_cycle=0,wa,ra,wl,rl,wb,rb,ws,rs;
    reg [7:0] wid,rid;
    reg writing=0,reading=0;
    integer present=0,acks=0,verified_scans=0,commands=0,blends=0,bg_copies=0,held_reads=0;
    integer asset_writes=0,bg_writes=0,map_copies=0,page_present[0:1],previewed[0:1];
    integer state_seen[0:6],game_frames=0,menu_count=0,state=-1,progress_file;
    integer game_fps=0,game_render_us=0,game_perf_samples=0;
    integer direction_mask=0,frame_mask=0,enemy_reads=0,orb_reads=0;
    integer floor_source_min=32'h7fffffff,floor_source_max=0;
    bit in_game=0,test_done=0;
    always @(negedge clk) begin
        m_awready=!writing&&!m_bvalid && bus_cycle%7!=0;
        m_wready=writing && bus_cycle%5!=0;
        m_arready=!reading&&!m_rvalid && bus_cycle%11!=0;
        if(reading&&!m_rvalid && bus_cycle%3!=0) begin
            for(integer b=0;b<16;b=b+1) m_rdata[b*8+:8]=mem[(ra&~15)+b];
            m_rid=rid; m_rresp=0; m_rlast=rb==rl; m_rvalid=1;
        end
    end
    function automatic [15:0] blend(input [15:0] f,b,input integer alpha,flags);
        integer r,g,bl;
        if((flags&2) && f==0) blend=b;
        else if(!(flags&1)) blend=f;
        else begin
            r=(((f>>11)&31)*alpha+((b>>11)&31)*(255-alpha)+127)/255;
            g=(((f>>5)&63)*alpha+((b>>5)&63)*(255-alpha)+127)/255;
            bl=((f&31)*alpha+(b&31)*(255-alpha)+127)/255;
            blend=(r<<11)|(g<<5)|bl;
        end
    endfunction
    task render_reference;
        integer dst,src,frame,x;
        reg [15:0] value,back;
        begin
            commands++;
            if(graphics.operation==1 && graphics.src==BG) bg_copies++;
            if(graphics.operation==1 && graphics.src>=BG+PAGE_BYTES && graphics.src<BG+PAGE_BYTES+131072) begin
                map_copies++;
                if(graphics.src<floor_source_min) floor_source_min=graphics.src;
                if(graphics.src>floor_source_max) floor_source_max=graphics.src;
            end
            if(graphics.operation==2) begin
                blends++;
                if(graphics.src>=GAME_BASE && graphics.src<GAME_BASE+GAME_BYTES) begin
                    frame=(graphics.src-GAME_BASE)/2048;
                    if(frame<16) begin
                        direction_mask=direction_mask|(1<<(frame/4)); frame_mask=frame_mask|(1<<(frame%4));
                    end
                    if(frame>=16 && frame<=18 || frame==24) enemy_reads++;
                    if(frame==21) orb_reads++;
                    if(graphics.blend_ctrl!=3 || graphics.color_key!=0) $fatal(1,"Game needs Alpha + Key");
                end
            end
            for(integer y=0;y<graphics.height;y++) for(integer c=0;c<graphics.width;c++) begin
                dst=graphics.dst-BASE+y*1280+c*2;
                if(dst<0 || dst+1>=2*PAGE_BYTES) $fatal(1,"Reference destination outside framebuffer");
                if(graphics.operation==0) value=graphics.color;
                else begin
                    src=graphics.src-BASE+y*graphics.src_stride+c*2;
                    if(src<0 || src+1>=MEM_BYTES) $fatal(1,"Reference source outside DDR");
                    value={expected[src+1],expected[src]};
                    if(graphics.operation==2) begin
                        back={expected[dst+1],expected[dst]}; value=blend(value,back,graphics.blend_alpha,graphics.blend_ctrl);
                    end
                end
                expected[dst]=value[7:0]; expected[dst+1]=value[15:8];
            end
        end
    endtask
    task check_assets;
        begin
        if(asset_writes!=61440) $fatal(1,"Game resources not uploaded once: %0d",asset_writes);
            for(integer n=0;n<4096;n++)
                if({mem[ASSET_BASE-BASE+2048+n*2+1],mem[ASSET_BASE-BASE+2048+n*2]}!==player_expected[n])
                    $fatal(1,"Menu player asset mismatch");
            for(integer n=0;n<GAME_BYTES/2;n++)
                if({mem[GAME_BASE-BASE+n*2+1],mem[GAME_BASE-BASE+n*2]}!==game_expected[n])
                    $fatal(1,"Game frame %0d pixel %0d decode mismatch",n/1024,n%1024);
        end
    endtask
    always @(posedge clk) if(!reset) begin
        bus_cycle++;
        if(m_awvalid&&m_awready) begin
            if(!((m_awaddr>=BASE && m_awaddr<BASE+2*PAGE_BYTES) ||
                 (m_awaddr>=ASSET_BASE && m_awaddr<ASSET_BASE+10240) ||
                 (m_awaddr>=GAME_BASE && m_awaddr<GAME_BASE+GAME_BYTES) ||
                 (m_awaddr>=BG && m_awaddr<BG+PAGE_BYTES+131072))) $fatal(1,"Unexpected DDR write %h",m_awaddr);
            if(m_awaddr>=ASSET_BASE && m_awid[7]) $fatal(1,"Hardware overwrote assets");
            if(graphics.display_enable && m_awaddr<BASE+2*PAGE_BYTES &&
               ((m_awaddr>=BASE+PAGE_BYTES)==graphics.display_page_sync[1])) $fatal(1,"Front page write");
            wa=m_awaddr-BASE; wl=m_awlen; wb=0; ws=1<<m_awsize; wid=m_awid; writing=1;
        end
        if(m_wvalid&&m_wready) begin
            if(m_wlast!=(wb==wl)) $fatal(1,"DDR WLAST mismatch");
            for(integer b=0;b<16;b++) if(m_wstrb[b]) begin
                if(!wid[7]) expected[(wa&~15)+b]=m_wdata[8*b+:8];
                else if(expected[(wa&~15)+b]!==m_wdata[8*b+:8]) $fatal(1,"Hardware pixel differs from independent blend/reference at %h",BASE+(wa&~15)+b);
                mem[(wa&~15)+b]=m_wdata[8*b+:8];
                if(wa>=BG-BASE) bg_writes++;
                else if(wa>=ASSET_BASE-BASE) asset_writes++;
            end
            wa=(wa&~(ws-1))+ws; wb++;
            if(m_wlast) begin writing=0; m_bvalid<=1; m_bid<=wid; m_bresp<=0; end
        end
        if(m_bvalid&&m_bready) m_bvalid<=0;
        if(m_arvalid&&m_arready) begin
            ra=m_araddr-BASE; if(ra<0 || ra>=MEM_BYTES) $fatal(1,"Unexpected DDR read");
            rl=m_arlen; rb=0; rs=1<<m_arsize; rid=m_arid; reading=1;
        end
        if(m_rvalid&&m_rready) begin ra=(ra&~(rs-1))+rs; rb++; m_rvalid<=0; if(m_rlast) reading=0; end
        if(psel&&penable&&pready) begin
            if(pslverror) $fatal(1,"Game APB error at %h",paddr);
            if(!pwrite && paddr==100) begin
                held_reads++; if(prdata[3:0]!==button_held) $fatal(1,"Live keys lost at APB");
            end
            if(pwrite&&paddr==8) render_reference();
            if(pwrite&&paddr==64) begin
                check_assets(); present++;
                page_present[graphics.swap_page]=present;
                if(in_game) game_frames++;
                $fdisplay(progress_file,"PASS present=%0d game=%b state=%0d game_frames=%0d",present,in_game,state,game_frames); $fflush(progress_file);
            end
        end
    end
    reg [7:0] uart_char;
    string uart_line="";
    initial forever begin
        @(negedge uart_tx); #13020;
        for(integer n=0;n<8;n++) begin uart_char[n]=uart_tx; #8680; end
        uart_line={uart_line,uart_char};
        if(uart_char==10) begin
            $fdisplay(progress_file,"UART: %s",uart_line); $fflush(progress_file);
            if(uart_line.substr(0,3)=="FAIL" || uart_line.substr(0,3)=="TRAP") $fatal(1,"Firmware %s",uart_line);
                if(uart_line.substr(0,8)=="GAME FPS ") begin
                    if($sscanf(uart_line,"GAME FPS %d RENDER_US %d",game_fps,game_render_us)!=2)
                        $fatal(1,"Malformed game performance report: %s",uart_line);
                    game_perf_samples++;
                end
            if(uart_line.substr(0,3)=="MENU") begin menu_count++; in_game=0; end
            if(uart_line.substr(0,3)=="GAME" && uart_line.len()<8) in_game=1;
            if(uart_line.substr(0,10)=="GAME STATE ") begin
                if($sscanf(uart_line,"GAME STATE %d",state)!=1 || state<0 || state>6) $fatal(1,"Bad game state");
                state_seen[state]++;
            end
            uart_line="";
        end
    end
    task tap(input reg [3:0] mask);
        key_i=~mask; #2000; key_i=15; #2000;
    endtask
    task menu_key(input reg [3:0] mask);
        integer previous_count; previous_count=present; tap(mask); wait(present>previous_count);
    endtask
    task hold_key(input reg [3:0] mask,input integer frames);
        integer previous_count; previous_count=game_frames; key_i=~mask;
        wait(game_frames>=previous_count+frames); key_i=15; #2000;
    endtask
    initial begin
        wait(present>=1 && verified_scans>=1);
        menu_key(2); menu_key(2); tap(4); // root game entry
        wait(state_seen[0]>=1); tap(4); wait(state_seen[1]>=1);
        hold_key(8,15); hold_key(1,6); hold_key(4,6); hold_key(2,6);
        tap(3); wait(state_seen[3]>=1); tap(4); wait(state_seen[1]>=2);
        hold_key(10,5); tap(12); wait(state_seen[3]>=2); tap(8);
        wait(menu_count>=4); // 3 root redraws, then returned root.
        wait(previewed[graphics.display_page_active]==present && acks==present);
        if(held_reads<15 || game_frames<20 || bg_copies<2 || map_copies<40 || floor_source_max<=floor_source_min || blends<20 || enemy_reads==0 || orb_reads==0 ||
           game_perf_samples==0 || game_fps<60 || game_render_us>=16667 ||
           direction_mask!=15 || frame_mask!=15 || bg_writes!=PAGE_BYTES+131072)
            $fatal(1,"Missing game input/animation/asset/pause/camera coverage: dirs=%h frames=%h floor=%h..%h",direction_mask,frame_mask,floor_source_min,floor_source_max);
        if(graphics.underflow||graphics.read_error) $fatal(1,"Game scanout error");
        $display("SOC GAME TEST PASSED: %0d pages, %0d game frames, %0d verified HDMI scans, %0d commands, live keys, all directions/walk frames, enemy/orbit Alpha+Key, pause/resume/menu, no front writes; %0d sprite asset bytes, %0d background bytes",present,game_frames,verified_scans,commands,asset_writes,bg_writes);
        $fclose(progress_file); $finish;
    end
    integer px=0,py=0,scan_present=0;
    bit prev_de=0,scan_page=0,prev_page=0,prev_ack=0,safe;
    always @(posedge pixel_clk) begin
        safe=graphics.video.h==0 && graphics.video.v==524 && graphics.video.req_toggle==graphics.video.done_sync[1]; #1;
        if(!reset) begin
            if(graphics.display_page_active!=prev_page && !safe) $fatal(1,"Game page switch mid-frame");
            if(graphics.swap_ack_pixel!=prev_ack) begin if(!safe) $fatal(1,"Game early swap"); acks++; end
            prev_ack=graphics.swap_ack_pixel; prev_page=graphics.display_page_active;
            if(de) begin
                if(px==0 && py==0) begin
                    scan_page=graphics.display_page_active; scan_present=page_present[scan_page];
                end
                if(scan_present && pixel!=={mem[scan_page*PAGE_BYTES+(py*640+px)*2+1],
                                            mem[scan_page*PAGE_BYTES+(py*640+px)*2]})
                    $fatal(1,"Game HDMI pixel mismatch at %0d,%0d",px,py);
                if(scan_page!=graphics.display_page_active) $fatal(1,"Mixed game page");
                px++;
            end
            if(prev_de&&!de) begin
                if(px!=640) $fatal(1,"Game HDMI line length"); px=0; py++;
                if(py==480) begin
                    py=0; if(scan_present) verified_scans++;
                    if(scan_present) begin
                        previewed[scan_page]=scan_present;
                        $fdisplay(progress_file,"VERIFIED HDMI game_%0d",scan_present); $fflush(progress_file);
                    end
                end
            end
            prev_de=de;
        end
    end
    initial begin
        progress_file=$fopen("reports/soc_game_progress.log","w");
        $readmemh("sim/game_expected.hex",game_expected); $readmemh("sim/player_expected.hex",player_expected);
        for(integer i=0;i<MEM_BYTES;i++) begin mem[i]=8'ha5; expected[i]=8'ha5; end
        for(integer i=0;i<7;i++) state_seen[i]=0;
        page_present[0]=0; page_present[1]=0; previewed[0]=0; previewed[1]=0;
        repeat(50) @(negedge clk); reset=0;
    end
    initial forever begin #10000000; $fdisplay(progress_file,"time=%0t present=%0d game_frames=%0d background=%0d",$time,present,game_frames,bg_writes); $fflush(progress_file); end
    initial begin #(64'd5000000000); $fatal(1,"Game SoC timeout"); end
endmodule
