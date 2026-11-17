`timescale 1ns/1ps
module tb_soc;
    reg clk=0,pixel_clk=0,reset=1;
    reg uart_rx=1;
    reg [4:0] key_i=5'h1f;
    wire [4:0] button_pending,button_held;
    wire [3:0] button_ack;
    always #5 clk=~clk;
    always #19.8347107 pixel_clk=~pixel_clk;
    wire soc_reset,master_reset,uart_tx;
    // Debounce timing is tested separately; retain real CPU, DDR and HDMI clocks.
    button_input #(.KEY_COUNT(5),.ENABLE_REPEAT(0),.DEBOUNCE_CYCLES(32)) buttons(.clk(clk),.reset(soc_reset),.key_n(key_i),
                         .ack_toggle(button_ack[0]),.pending(button_pending),.held(button_held));
    wire [15:0] paddr,pixel;
    wire psel,penable,pwrite,pready,pslverror;
    wire [31:0] pwdata,prdata,awaddr,wdata,araddr,rdata;
    wire [7:0] awlen,arlen;
    wire [3:0] wstrb;
    wire [1:0] bresp,rresp;
    wire awvalid,awready,wvalid,wready,wlast,bvalid,bready;
    wire arvalid,arready,rvalid,rready,rlast,hs,vs,de;
    `include "soc_wiring.vh"
    render_subsystem #(.KEY_COUNT(5)) graphics(
        .clk(clk),.reset(soc_reset|master_reset),.pixel_clk(pixel_clk),.memory_ready(1'b1),
        .button_held(button_held),
        .button_enter_pending(button_pending[4]),
        .paddr(paddr),.psel(psel),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),
        .prdata(prdata),.pready(pready),.pslverror(pslverror),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wlast(wlast),.wvalid(wvalid),.wready(wready),
        .bresp(bresp),.bvalid(bvalid),.bready(bready),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rresp(rresp),.rlast(rlast),.rvalid(rvalid),.rready(rready),
        .pixel(pixel),.hs(hs),.vs(vs),.de(de)
    );
    localparam BASE=32'h01000000, PAGE_BYTES=614400;
    localparam ASSET_BASE=32'h01200000, ASSET_BYTES=1048576;
    localparam PLAYER_BASE=ASSET_BASE+2048, PLAYER_BYTES=8192;
    `include "game_asset_size.vh"
    localparam GAME_BASE=ASSET_BASE+'h4000, GAME_BYTES=`GAME_ASSET_BYTES;
    localparam ASSET_UPLOAD_BYTES=2048+8192+2*(16+256+576+1024)+GAME_BYTES;
    localparam MEM_BYTES=ASSET_BASE-BASE+ASSET_BYTES;
    reg [7:0] mem[0:MEM_BYTES-1];
    reg writing=0,reading=0;
    integer wa,ra,wl,rl,wb,rb,ws,rs;
    reg [7:0] wid,rid;
    integer commands=0,fill_commands=0,copy_commands=0,blend_commands=0;
    integer cpu_target=64;
    integer menu_level=0,menu_group=0,menu_item[0:1],demo=0,variant=0;
    integer variant_coverage[0:7][0:255],demo_hw[0:7],demo_cpu[0:7];
    bit test_done=0;
    bit ui_smoke=$test$plusargs("UI_SMOKE");
    // Chinese UI literals are UTF-8 octal escapes for ModelSim 10.6 source compatibility.
    string names[0:7]='{"\347\237\251\345\275\242\345\241\253\345\205\205","\345\233\276\345\203\217\345\244\215\345\210\266","\345\217\214\347\274\223\345\206\262","\350\247\206\351\242\221\346\250\241\345\274\217",
        "\351\242\234\350\211\262\351\224\256","\351\200\217\346\230\216\346\267\267\345\220\210","Sprite \345\216\213\345\212\233",""};
    string details[0:7]='{"RGB565 \347\241\254\344\273\266\345\241\253\345\205\205","DDR \345\233\276\345\203\217\345\244\215\345\210\266\345\210\260\346\230\276\345\255\230",
        "\345\236\202\347\233\264\346\266\210\351\232\220\344\272\244\346\215\242\351\241\265\351\235\242","\351\242\234\350\211\262\346\235\241\344\270\216\345\256\236\351\231\205\345\260\272\345\257\270",
        "\351\273\221\350\211\262\345\203\217\347\264\240\345\217\230\344\270\272\351\200\217\346\230\216","W\345\212\240\344\270\200 A\345\207\217\344\270\200","Alpha + Color Key / 64-4096",""};
    string actions[0:7]='{"W\346\224\271\345\217\230\351\242\234\350\211\262","W\346\224\271\345\217\230\344\275\215\347\275\256","W\346\224\271\345\217\230\351\200\237\345\272\246","W\346\224\271\345\217\230\345\233\276\346\241\210",
        "W\345\274\200\345\205\263\351\242\234\350\211\262\351\224\256","W\345\212\240\344\270\200 A\345\207\217\344\270\200","W\345\212\240\345\216\213 A\345\207\217\345\216\213",""};
    reg [15:0] colors[0:7]='{16'hffff,16'hffe0,16'h07ff,16'h07e0,16'hf81f,16'hf800,16'h001f,16'h0000};
    integer menu_choice=0,menu_count=0,menu_frames=0,demo_count=0;
    integer model_hw=0,model_auto=1,model_frame=0;
    integer measured_fps[0:1],measured_us[0:1],measured_ar[0:1],measured_aw[0:1],measured_valid[0:1];
    integer coverage_cpu[0:3],coverage_hw[0:3],scene_coverage_cpu[0:3],scene_coverage_hw[0:3];
    bit demo_active=0,reset_sample=0;
    integer manual_events=0,auto_events=0,alpha_decrements=0;
    integer sprite_best_60_model=0;
    reg [7:0] font_columns[0:179];
    reg [31:0] font_cn_records[0:4095];
    reg [15:0] player_expected[0:PLAYER_BYTES/2-1];
    reg [15:0] game_expected[0:GAME_BYTES/2-1];
    integer cpu_reads=0,cpu_read_bytes=0,copy_reads=0,progress_file;
    integer swap_commands=0,swap_acks=0,page_frames[0:1];
    integer reports_cpu=0,reports_hw=0,mode_frames[0:1];
    integer last_commands=0,last_fills=0,last_copies=0,last_blends=0,last_mode=-1,scene_frame=-1;
    integer last_scene_sprites=0;
    integer page_present[0:1],page_verified[0:1],verified_present[0:1],page_mode[0:1];
    integer previewed_present[0:1],bus_cycle=0,cpu_writes=0;
    integer sample_frames=0,sample_ar=0,sample_aw=0;
    integer last_burst_ar=0,last_burst_aw=0;
    integer expected_metric_ar=0,expected_metric_aw=0,expected_metric_sprites=0;
    integer verified_scenes=0,verified_scan_frames=0;
    integer video_status_reads=0,video_size_reads=0;
    integer asset_write_bytes=0,cpu_asset_reads=0,hw_asset_reads=0;
    reg last_video_valid=0;
    reg [31:0] last_video_size=0;
    reg [15:0] golden[0:307199],snapshot[0:614399];
    reg returned_to_cpu=0;
    // DDR is modeled at the controller's 128-bit AXI port. Real Sapphire
    // arbitration, cache and 32-to-128-bit conversion are all in simulation.
    always @(negedge clk) begin
        m_awready=!writing&&!m_bvalid && bus_cycle%7!=0;
        m_wready=writing && bus_cycle%5!=0;
        m_arready=!reading&&!m_rvalid && bus_cycle%11!=0;
        if(reading&&!m_rvalid && bus_cycle%3!=0) begin
            for(integer b=0;b<16;b=b+1) m_rdata[b*8+:8]=mem[(ra&~15)+b];
            m_rid=rid; m_rresp=0; m_rlast=rb==rl; m_rvalid=1;
        end
    end
    always @(posedge clk) if(!reset) begin
        bus_cycle=bus_cycle+1;
        if(m_awvalid&&m_awready) begin
            // The upsizer can retain an unaligned first address while WSTRB
            // selects only two bytes. Burst extent starts at the aligned beat.
            if(!((m_awaddr>=BASE && (m_awaddr&~((1<<m_awsize)-1))+(m_awlen+1)*(1<<m_awsize)<=BASE+2*PAGE_BYTES) ||
                 (m_awaddr>=ASSET_BASE && (m_awaddr&~((1<<m_awsize)-1))+(m_awlen+1)*(1<<m_awsize)<=ASSET_BASE+10240) ||
                 (m_awaddr>=GAME_BASE && (m_awaddr&~((1<<m_awsize)-1))+(m_awlen+1)*(1<<m_awsize)<=GAME_BASE+GAME_BYTES)))
                $fatal(1,"SoC write outside framebuffer/uploaded image: %h",m_awaddr);
            if(m_awaddr>=ASSET_BASE && (m_awid[7] || swap_commands!=0))
                $fatal(1,"Only startup CPU code may upload resources");
            if(m_awburst!=1 || m_awsize>4) $fatal(1,"Unsupported AW burst");
            wa=m_awaddr-BASE; wl=m_awlen; wb=0; ws=1<<m_awsize;
            wid=m_awid; writing=1;
            if(!m_awid[7]) cpu_writes=cpu_writes+1;
        end
        if(m_wvalid&&m_wready) begin
            if(m_wlast!=(wb==wl)) $fatal(1,"SoC WLAST mismatch");
            for(integer b=0;b<16;b=b+1)
                if(m_wstrb[b]) begin
                    mem[(wa&~15)+b]=m_wdata[8*b+:8];
                    if(wa>=ASSET_BASE-BASE) asset_write_bytes=asset_write_bytes+1;
                end
            wa=(wa&~(ws-1))+ws; wb=wb+1;
            if(m_wlast) begin writing=0; m_bvalid<=1; m_bid<=wid; m_bresp<=0; end
        end
        if(m_bvalid&&m_bready) m_bvalid<=0;
        if(m_arvalid&&m_arready) begin
            if(!((m_araddr>=BASE && (m_araddr&~((1<<m_arsize)-1))+(m_arlen+1)*(1<<m_arsize)<=BASE+2*PAGE_BYTES) ||
                 (m_araddr>=ASSET_BASE && (m_araddr&~((1<<m_arsize)-1))+(m_arlen+1)*(1<<m_arsize)<=ASSET_BASE+ASSET_BYTES)))
                $fatal(1,"SoC read outside framebuffer/resource pools: %h",m_araddr);
            if(m_araddr>=ASSET_BASE) begin
                if(m_arid[7]) hw_asset_reads=hw_asset_reads+1;
                else cpu_asset_reads=cpu_asset_reads+1;
            end
            if(m_arburst!=1 || m_arsize>4) $fatal(1,"Unsupported AR burst");
            ra=m_araddr-BASE; rl=m_arlen; rb=0; rs=1<<m_arsize;
            rid=m_arid; reading=1;
            // Sapphire appends the selected master as ID bit 7: CPU=0,
            // external graphics=1. Count CPU memory access independently.
            if(!m_arid[7]) begin
                cpu_reads=cpu_reads+1;
                cpu_read_bytes=cpu_read_bytes+((m_arlen+1)<<m_arsize);
            end else if(!graphics.display_enable) copy_reads=copy_reads+1;
        end
        if(m_rvalid&&m_rready) begin
            ra=(ra&~(rs-1))+rs; rb=rb+1; m_rvalid<=0;
            if(m_rlast) reading=0;
        end
        if(psel&&penable&&pready) begin
            if(pslverror) $fatal(1,"Firmware APB error at %h",paddr);
            if(!pwrite&&paddr==16'h48) begin
                last_video_valid=prdata[0];
                video_status_reads=video_status_reads+1;
            end
            if(!pwrite&&paddr==16'h44) begin
                last_video_size=prdata;
                video_size_reads=video_size_reads+1;
            end
            if(pwrite&&paddr==16'h8) begin
                commands=commands+1;
                if(graphics.operation==0) fill_commands=fill_commands+1;
                else if(graphics.operation==1) begin
                    if(demo_active && demo==1) begin
                        if(graphics.src!=BASE+graphics.draw_page*PAGE_BYTES+192*1280+128 || graphics.src_stride!=1280)
                            $fatal(1,"Block Copy source mismatch");
                    end else if(!demo_active && (graphics.src!=PLAYER_BASE || graphics.src_stride!=64))
                        $fatal(1,"Menu player copy source mismatch");
                    else if(demo_active && (graphics.src!=ASSET_BASE || graphics.src_stride!=64))
                        $fatal(1,"Demo copy did not use the independent DDR image");
                    copy_commands=copy_commands+1;
                end else if(graphics.operation==2) begin
                    if(!demo_active) begin
                        if(graphics.src!=PLAYER_BASE || graphics.src_stride!=64 || graphics.blend_ctrl!=2 ||
                           graphics.blend_alpha!=255 || graphics.color_key!=0)
                            $fatal(1,"Menu player blend controls/resource mismatch");
                    end else if(graphics.src!=ASSET_BASE || graphics.src_stride!=64 ||
                       graphics.blend_ctrl!=(demo==4 ? 2 : demo==5 ? 1 : 3) ||
                       graphics.blend_alpha!=(demo==6 ? 128 : alpha_value(variant)) || graphics.color_key!=0)
                        $fatal(1,"Demo blend controls/resource mismatch");
                    blend_commands=blend_commands+1;
                end else $fatal(1,"Unexpected graphics operation %0d",graphics.operation);
                end
            if(pwrite&&paddr==16'h40) begin
                swap_commands=swap_commands+1;
                if(demo_active) check_scene(); else check_menu();
            end
        end
        if(graphics.display_enable && m_awvalid && m_awready && m_awaddr<BASE+2*PAGE_BYTES &&
           ((m_awaddr>=BASE+PAGE_BYTES)==graphics.display_page_sync[1]))
            $fatal(1,"Firmware rendered to the front page");
    end
    // Decode the real UART pin using the firmware's 100 MHz / 115200 divider.
    reg [7:0] uart_char;
    integer metric_fps,metric_us,metric_sprites,metric_ar,metric_aw,metric_fields;
    integer scene_sprites;
    integer hw_seen_64=0,hw_seen_128=0,hw_seen_256=0;
    string uart_line="";
    initial forever begin
        @(negedge uart_tx); #13020;
        for(integer bitno=0;bitno<8;bitno=bitno+1) begin
            uart_char[bitno]=uart_tx; #8680;
        end
        $write("%c",uart_char);
        uart_line={uart_line,uart_char};
        if(uart_char==10) begin
            $fdisplay(progress_file,"UART: %s",uart_line); $fflush(progress_file);
            if(uart_line.substr(0,3)=="FAIL" || uart_line.substr(0,3)=="TRAP")
                $fatal(1,"Firmware reported: %s",uart_line);
            if(uart_line.substr(0,3)=="MENU") begin demo_active=0; menu_count=menu_count+1; end
            if(uart_line.substr(0,4)=="DEMO ") begin
                if($sscanf(uart_line,"DEMO %d",demo)!=1 || demo!=menu_group*4+menu_item[menu_group])
                    $fatal(1,"Wrong selected demo: %s",uart_line);
                demo_active=1; variant=demo==5 ? 128 : demo==4 ? 1 : 0;
                demo_count=demo_count+1; model_hw=1; model_auto=0; model_frame=0;
                last_mode=-1; sample_frames=0; sample_ar=0; sample_aw=0;
                for(integer i=0;i<2;i=i+1) measured_valid[i]=0;
            end
            if(uart_line.substr(0,6)=="CPU FPS" || uart_line.substr(0,5)=="HW FPS") begin
                if(uart_line.substr(0,6)=="CPU FPS") begin
                    reports_cpu=reports_cpu+1;
                    metric_fields=$sscanf(uart_line,"CPU FPS %d RENDER_US %d SPRITES %d DDR_AR %d DDR_AW %d",
                                          metric_fps,metric_us,metric_sprites,metric_ar,metric_aw);
                end else begin
                    reports_hw=reports_hw+1;
                    metric_fields=$sscanf(uart_line,"HW FPS %d RENDER_US %d SPRITES %d DDR_AR %d DDR_AW %d",
                                          metric_fps,metric_us,metric_sprites,metric_ar,metric_aw);
                end
                if(metric_fields!=5) begin
                    $write("UART metric bytes:");
                    for(integer k=0;k<uart_line.len();k=k+1) $write(" %02x",uart_line[k]);
                    $display("");
                end
                if(metric_fields!=5 || metric_fps<1 || metric_fps>61 || metric_us<1 ||
                   (metric_sprites!=0 && metric_sprites!=8 && metric_sprites<64) ||
                   metric_ar<0 || metric_aw<0)
                    $fatal(1,"Invalid measured UART metrics: %s",uart_line);
                if(metric_ar!=expected_metric_ar || metric_aw!=expected_metric_aw || metric_sprites!=expected_metric_sprites)
                    $fatal(1,"UART metrics mismatch: got AR/AW/SPRITES=%0d/%0d/%0d expected=%0d/%0d/%0d",
                        metric_ar,metric_aw,metric_sprites,expected_metric_ar,expected_metric_aw,expected_metric_sprites);
                begin
                    integer side,load_index;
                    side=uart_line.substr(0,5)=="HW FPS";
                    measured_fps[side]=metric_fps; measured_us[side]=metric_us;
                    measured_ar[side]=metric_ar/(demo==6 ? 30 : 4); measured_aw[side]=metric_aw/(demo==6 ? 30 : 4);
                    measured_valid[side]=1;
                    load_index=demo==6 ? (metric_sprites==64 ? 1 : metric_sprites==128 ? 2 : 3) : 0;
                    if(side) coverage_hw[load_index]=coverage_hw[load_index]+1;
                    else coverage_cpu[load_index]=coverage_cpu[load_index]+1;
                end
                if(uart_line.substr(0,5)=="HW FPS") begin
                    if(metric_sprites==64) hw_seen_64=1;
                    else if(metric_sprites==128) hw_seen_128=1;
                    else if(metric_sprites==256) hw_seen_256=1;
                    if(demo==6 && metric_fps>=59 && metric_sprites>sprite_best_60_model)
                        sprite_best_60_model=metric_sprites;
                end
                if(uart_line.substr(0,6)=="CPU FPS" && (metric_ar!=0 || metric_aw!=0))
                    $fatal(1,"CPU baseline must not increment renderer burst counters");
            if(uart_line.substr(0,5)=="HW FPS" && (metric_aw==0 || ((demo==1 || demo>=4) && metric_ar==0)))
                    $fatal(1,"FPGA blend pass did not report DDR read/write bursts");
            end
            uart_line="";
        end
    end
    function automatic integer bounce(input integer phase,limit);
        integer p;
        p=phase%(2*limit); bounce=p>limit ? 2*limit-p : p;
    endfunction
    function automatic [15:0] sprite_pixel(input integer y,input integer x);
        integer dx,dy;
        begin
            dx=x>15 ? x-15 : 15-x;
            dy=y>15 ? y-15 : 15-y;
            if(dx+dy>13) sprite_pixel=16'h0000;
            else sprite_pixel=y<10 ? 16'h07ff : y<20 ? 16'hf800 : 16'hffe0;
        end
    endfunction
    function automatic [31:0] sprite_seed(input integer n);
        reg [31:0] v;
        v=(n+1)*32'h9e3779b9; v=v^(v<<13); v=v^(v>>17); v=v^(v<<5);
        sprite_seed=v;
    endfunction
    function automatic integer alpha_value(input integer v);
        alpha_value=v;
    endfunction
    function automatic [15:0] blend_pixel(input [15:0] f,b,input integer flags,alpha);
        integer r,g,bl;
        if((flags&2)!=0 && f==0) blend_pixel=b;
        else if((flags&1)==0) blend_pixel=f;
        else begin
            r=(((f>>11)&31)*alpha+((b>>11)&31)*(255-alpha)+127)/255;
            g=(((f>>5)&63)*alpha+((b>>5)&63)*(255-alpha)+127)/255;
            bl=((f&31)*alpha+(b&31)*(255-alpha)+127)/255;
            blend_pixel=(r<<11)|(g<<5)|bl;
        end
    endfunction
    task golden_fill(input integer x,y,w,h,input reg [15:0] color);
        for(integer r=0;r<h;r=r+1) for(integer c=0;c<w;c=c+1)
            golden[(y+r)*640+x+c]=color;
    endtask
    task golden_text(input integer x,y,input string label,input reg [15:0] color);
        integer glyph, bits,codepoint,bytes_used,cursor_x;
        reg [7:0] c,b1,b2;
        cursor_x=x;
        for(integer k=0;k<label.len();k=k+1) begin
            c=label.getc(k); codepoint=c; bytes_used=1;
            if((c&8'he0)==8'hc0 && k+1<label.len()) begin
                b1=label.getc(k+1); codepoint=(c&8'h1f); codepoint=codepoint<<6;
                bits=(b1&8'h3f); codepoint=codepoint|bits; bytes_used=2;
            end else if((c&8'hf0)==8'he0 && k+2<label.len()) begin
                b1=label.getc(k+1); b2=label.getc(k+2);
                codepoint=(c&8'h0f); codepoint=codepoint<<12;
                bits=(b1&8'h3f); bits=bits<<6;
                codepoint=codepoint|bits|(b2&8'h3f); bytes_used=3;
            end
            if(codepoint>=128) begin
                glyph=-1;
                for(integer n=0;n<font_cn_records[0];n=n+1)
                    if(font_cn_records[1+n*15]==codepoint) glyph=n;
                if(glyph>=0) begin
                    for(integer row=0;row<14;row=row+1) begin
                        bits=font_cn_records[2+glyph*15+row] |
                             (font_cn_records[2+glyph*15+row]<<1);
                        for(integer column=0;column<13;column=column+1)
                            if((bits>>column)&1) golden_fill(cursor_x+column,y+row,1,1,color);
                    end
                    cursor_x=cursor_x+14;
                end else cursor_x=cursor_x+12;
                k=k+bytes_used-1;
            end else begin
                glyph=-1;
                if(c>="a" && c<="z") c=c-"a"+"A";
                if(c>="0" && c<="9") glyph=c-"0";
                if(c>="A" && c<="Z") glyph=c-"A"+10;
                for(integer column=0;column<5;column=column+1) begin
                    bits=glyph>=0 ? font_columns[glyph*5+column] : c=="-" ? 8 :
                         c=="/" ? (1<<(5-column)) : c=="+" ? (column==2 ? 62 : 8) :
                         c=="_" ? 64 : 0;
                    for(integer row=0;row<7;row=row+1)
                        if((bits>>row)&1) golden_fill(cursor_x+column*2,y+row*2,2,2,color);
                end
                cursor_x=cursor_x+12;
            end
        end
    endtask
    task golden_sprite(input integer x,y,flags,alpha);
        for(integer r=0;r<32;r=r+1) for(integer c=0;c<32;c=c+1)
            golden[(y+r)*640+x+c]=blend_pixel(sprite_pixel(r,c),golden[(y+r)*640+x+c],flags,alpha);
    endtask
    task golden_player(input integer x,y);
        begin
            for(integer r=0;r<32;r=r+1) for(integer c=0;c<32;c=c+1)
                golden[(y+r)*640+x+c]=blend_pixel(player_expected[r*32+c],golden[(y+r)*640+x+c],2,255);
        end
    endtask
    task check_player_assets;
        begin
            if(asset_write_bytes!=ASSET_UPLOAD_BYTES) $fatal(1,"Asset upload byte count mismatch");
            for(integer n=0;n<PLAYER_BYTES/2;n=n+1)
                if({mem[PLAYER_BASE-BASE+n*2+1],mem[PLAYER_BASE-BASE+n*2]}!==player_expected[n])
                    $fatal(1,"Player frame %0d pixel %0d upload/immutability mismatch",n/1024,n%1024);
            for(integer n=0;n<GAME_BYTES/2;n=n+1)
                if({mem[GAME_BASE-BASE+n*2+1],mem[GAME_BASE-BASE+n*2]}!==game_expected[n])
                    $fatal(1,"Game frame %0d pixel %0d upload mismatch",n/1024,n%1024);
        end
    endtask
    task compare_page(input integer mode);
        integer page,base;
        reg [15:0] actual;
        begin
            page=graphics.swap_page; base=page*PAGE_BYTES;
            if(writing || m_bvalid) $fatal(1,"Present before DDR writes completed");
            for(integer n=0;n<307200;n=n+1) begin
                actual={mem[base+n*2+1],mem[base+n*2]};
                if(actual!==golden[n])
                    $fatal(1,"Demo %0d mode %0d frame %0d pixel (%0d,%0d): %h != %h",
                        demo,mode,scene_frame,n%640,n/640,actual,golden[n]);
                snapshot[page*307200+n]=actual;
            end
            page_present[page]=swap_commands; page_mode[page]=mode;
            page_verified[page]=1; verified_present[page]=swap_commands;
            verified_scenes=verified_scenes+1;
            last_commands=commands; last_fills=fill_commands; last_copies=copy_commands; last_blends=blend_commands;
            $fdisplay(progress_file,"PASS page: present=%0d demo=%0d mode=%0d frame=%0d count=%0d variant=%0d level=%0d group=%0d time=%0t",
                swap_commands,demo,mode,scene_frame,cpu_target,variant,menu_level,menu_group,$time); $fflush(progress_file);
        end
    endtask
    task check_menu;
        integer y,count,choice;
        begin
            check_player_assets();
            golden_fill(0,0,640,480,16'h0843);
            golden_fill(24,18,592,64,16'h10a6);
            if(menu_level) begin
                if(menu_group) golden_text(40,30,"\351\253\230\351\230\266\346\274\224\347\244\272",16'hffff);
                else golden_text(40,30,"\345\237\272\347\241\200\346\274\224\347\244\272",16'hffff);
                golden_text(40,54,"\351\200\211\346\213\251\345\212\237\350\203\275",16'h07ff);
            end else begin
                golden_text(40,30,"TI60 \344\272\214\347\273\264\345\256\236\351\252\214\345\256\244",16'hffff);
                golden_text(40,54,"\351\200\211\346\213\251\346\265\213\350\257\225",16'h07ff);
            end
            golden_player(566,34);
            count=menu_level ? (menu_group ? 3 : 4) : 3; choice=menu_level ? menu_item[menu_group] : menu_group;
            if(!menu_level) begin
                for(integer n=0;n<3;n=n+1) begin
                    y=96+n*80;
                    golden_fill(32,y,576,68,n==choice ? 16'h22ae : 16'h10c7);
                    if(n==choice) golden_fill(32,y,4,68,16'h07ff);
                    if(n==2) begin
                        golden_text(52,y+12,"\345\206\260\351\234\234\345\271\270\345\255\230\350\200\205",16'hffff);
                        golden_text(52,y+40,"\350\207\252\345\212\250\346\226\275\346\263\225 \347\224\237\345\255\230180\347\247\222",16'h07ff);
                    end else if(n==1) begin
                        golden_text(52,y+12,"\351\253\230\351\230\266\346\274\224\347\244\272",16'hffff);
                        golden_text(52,y+40,"3\351\241\271\345\212\237\350\203\275",16'h07ff);
                    end else begin
                        golden_text(52,y+12,"\345\237\272\347\241\200\346\274\224\347\244\272",16'hffff);
                        golden_text(52,y+40,"4\351\241\271\345\212\237\350\203\275",16'h07ff);
                    end
                end
                golden_text(40,356,"W\344\270\212\344\270\200\351\241\271    S\344\270\213\344\270\200\351\241\271",16'hffff);
                golden_text(40,384,"ENTER\346\211\223\345\274\200      D\350\277\224\345\233\236",16'hffe0);
                golden_text(40,432,"7\351\241\271\346\274\224\347\244\272 + \345\271\270\345\255\230\350\200\205\346\270\270\346\210\217",16'h9cf3);
            end else begin
                for(integer n=0;n<count;n=n+1) begin
                    y=90+n*68;
                    golden_fill(32,y,576,58,n==choice ? 16'h22ae : 16'h10c7);
                    if(n==choice) golden_fill(32,y,4,58,16'h07ff);
                    golden_text(52,y+8,names[menu_group*4+n],16'hffff);
                    golden_text(52,y+32,details[menu_group*4+n],16'h07ff);
                end
                golden_text(40,374,"W\344\270\212\344\270\200\351\241\271    S\344\270\213\344\270\200\351\241\271",16'hffff);
                golden_text(40,402,"ENTER\345\274\200\345\247\213      D\350\277\224\345\233\236",16'hffe0);
                golden_text(40,442,"\347\242\260\346\222\236\344\270\216\347\247\273\345\212\250\350\256\241\347\256\227\345\234\250\346\270\270\346\210\217\344\270\255\350\277\220\350\241\214",16'h9cf3);
            end
            compare_page(0); menu_frames=menu_frames+1;
            last_burst_ar=graphics.burst_reads; last_burst_aw=graphics.burst_writes;
        end
    endtask
    // Independently model every framebuffer pixel, including menu, reference
    // composites, pseudo-random motion, numeric HUD and button instructions.
    task check_scene;
        integer mode,x,y,flags,nfill,ncopy,nblend,overlap;
        reg [31:0] seed;
        reg [15:0] color;
        begin
            mode=commands!=last_commands;
            if(mode!=model_hw) $fatal(1,"CPU/HW selection mismatch");
            scene_frame=model_frame; model_frame=model_frame+1;
            scene_sprites=demo==6 ? cpu_target : (demo==4 || demo==5) ? 8 : 0;
            nfill=1; ncopy=0; nblend=0;
            case(demo)
                0: nfill=4;
                1: begin nfill=5; ncopy=1; end
                2: nfill=4;
                3: nfill=variant ? 23 : 9;
                4: begin nfill=5; ncopy=variant ? 4 : 8; nblend=variant ? 4 : 0; end
                5: begin nfill=5; ncopy=4; nblend=4; end
                6: begin nfill=2; nblend=cpu_target; end
            endcase
            if(mode && (fill_commands-last_fills!=nfill || copy_commands-last_copies!=ncopy || blend_commands-last_blends!=nblend))
                $fatal(1,"Demo %0d includes unexpected or missing operations",demo);
            if(mode) demo_hw[demo]=demo_hw[demo]+1; else demo_cpu[demo]=demo_cpu[demo]+1;
            variant_coverage[demo][variant]=variant_coverage[demo][variant]+1;
            if(reset_sample || mode!=last_mode || scene_sprites!=last_scene_sprites) begin
                sample_frames=0; sample_ar=0; sample_aw=0; reset_sample=0;
            end
            if(mode==0 && last_mode==1) returned_to_cpu=1;
            last_mode=mode; last_scene_sprites=scene_sprites;
            mode_frames[mode]=mode_frames[mode]+1;
            begin
                integer load_index;
                load_index=demo==6 ? (cpu_target==64 ? 1 : cpu_target==128 ? 2 : 3) : 0;
                if(mode) scene_coverage_hw[load_index]=scene_coverage_hw[load_index]+1;
                else scene_coverage_cpu[load_index]=scene_coverage_cpu[load_index]+1;
            end
            golden_fill(0,0,640,480,16'h0862);
            case(demo)
                0: for(integer n=0;n<3;n=n+1)
                    golden_fill(48+n*184,176+bounce(scene_frame*(variant+1),80),128+n*16,72+n*16,colors[1+(n+variant)%3]);
                1: begin
                    for(integer n=0;n<4;n=n+1)
                        golden_fill(64+(n&1)*64,192+(n>>1)*48,64,48,colors[1+n]);
                    for(integer r=0;r<96;r=r+1) for(integer c=0;c<128;c=c+1)
                        golden[(192+variant*80+r)*640+384+c]=golden[(192+r)*640+64+c];
                end
                2: begin
                    golden_fill(32,160,576,240,graphics.swap_page ? 16'h2104 : 16'h084b);
                    golden_fill(40+bounce(scene_frame*(variant ? 24 : 8),520),184,24,160,16'hffff);
                    golden_fill(48,272,544,4,16'h07ff);
                end
                3: begin
                    for(integer n=0;n<8;n=n+1) golden_fill(32+n*72,160,72,240,colors[n]);
                    if(variant) begin
                        for(integer n=0;n<9;n=n+1) golden_fill(32+n*71,160,2,240,16'hffff);
                        for(integer n=0;n<5;n=n+1) golden_fill(32,160+n*59,576,2,16'hffff);
                    end
                end
                4,5: for(integer panel=0;panel<2;panel=panel+1) begin
                    x=40+panel*304;
                    golden_fill(x,176,128,216,16'h0514); golden_fill(x+128,176,128,216,16'hfca0);
                    flags=panel ? (demo==4 ? (variant ? 2 : 0) : 1) : 0;
                    for(integer n=0;n<4;n=n+1) golden_sprite(x+112+(n&1)*16,208+(n>>1)*96,flags,alpha_value(variant));
                end
                6: begin
                    golden_fill(0,152,640,256,16'h0843);
                    for(integer n=0;n<cpu_target;n=n+1) begin
                        seed=sprite_seed(n);
                        x=8+bounce((seed&65535)+scene_frame*(1+((seed>>16)&7)),600);
                        y=160+bounce((seed>>16)+scene_frame*(1+((seed>>24)&3)),208);
                        golden_sprite(x,y,3,128);
                    end
                end
            endcase
            golden_text(16,8,names[demo],16'h07ff);
            if(demo==6) begin
                golden_text(200,8,"SPRITES",16'hffff); golden_text(296,8,$sformatf("%0d",cpu_target),16'hffe0);
                golden_text(400,8,"BEST60",16'h07ff); golden_text(484,8,$sformatf("%0d",sprite_best_60_model),16'hffe0);
                golden_text(16,32,"FPGA FPS",16'hffe0); golden_text(124,32,measured_valid[1] ? $sformatf("%0d",measured_fps[1]) : "-",16'hffe0);
                golden_text(220,32,"RENDER_US",16'hffff); golden_text(340,32,measured_valid[1] ? $sformatf("%0d",measured_us[1]) : "-",16'hffff);
                golden_text(430,32,"DDR_RD",16'hffff); golden_text(510,32,measured_valid[1] ? $sformatf("%0d",measured_ar[1]) : "-",16'hffff);
                golden_text(16,56,"DDR_WR",16'hffff); golden_text(96,56,measured_valid[1] ? $sformatf("%0d",measured_aw[1]) : "-",16'hffff);
                golden_text(220,56,"30-FRAME STABLE WINDOW",16'h9cf3);
            end else begin
                if(model_auto) golden_text(400,8,"\350\207\252\345\212\250 CPU/FPGA",16'h07ff);
                else golden_text(400,8,"\346\211\213\345\212\250",16'h07ff);
                for(integer n=0;n<2;n=n+1) begin
                    x=16+n*320; color=n==mode ? 16'hffe0 : 16'hffff;
                    golden_text(x,32,n ? "FPGA FPS" : "RISC-V FPS",color);
                    golden_text(x+108,32,measured_valid[n] ? $sformatf("%0d",measured_fps[n]) : "-",color);
                    golden_text(x,54,"RENDER_US",color);
                    golden_text(x+120,54,measured_valid[n] ? $sformatf("%0d",measured_us[n]) : "-",color);
                    golden_text(x,76,"DDR_RD",color); golden_text(x+160,76,"DDR_WR",color);
                    if(measured_valid[n]) begin
                        golden_text(x+72,76,$sformatf("%0d",measured_ar[n]),color);
                        golden_text(x+184,76,$sformatf("%0d",measured_aw[n]),color);
                    end
                end
            end
            golden_text(16,102,"\346\257\217\345\270\247\347\252\201\345\217\221",16'h9cf3);
            if(last_video_valid) begin
                if(last_video_size!={16'd480,16'd640}) $fatal(1,"Wrong measured video size");
                golden_text(448,102,"640",16'h9cf3); golden_text(484,102,"\303\227",16'h9cf3);
                golden_text(496,102,"480",16'h9cf3);
            end
            case(demo)
                0: golden_text(32,128,"RGB565 \347\237\251\345\275\242\345\241\253\345\205\205",16'hffff);
                1: begin golden_text(64,152,"\346\272\220\345\233\276\345\203\217",16'hffff); golden_text(384,152,"\345\244\215\345\210\266 128\303\22796",16'hffff); end
                2: begin
                    // The label describes the page being rendered. SWAP_PAGE
                    // may still name the previously presented buffer while
                    // the CPU is preparing the next back page.
                    golden_text(32,128,graphics.draw_page ? "\351\241\265\351\235\242B" : "\351\241\265\351\235\242A",16'hffff);
                    golden_text(200,128,"\345\270\247",16'hffff); golden_text(272,128,$sformatf("%0d",scene_frame),16'hffff);
                    golden_text(48,372,"\345\217\252\345\234\250\345\236\202\347\233\264\346\266\210\351\232\220\346\227\266\344\272\244\346\215\242",16'hffff);
                end
                3: golden_text(32,128,"HDMI \351\242\234\350\211\262\344\270\216\345\257\271\351\275\220\346\265\213\350\257\225",16'hffff);
                4: begin golden_text(40,144,"\351\242\234\350\211\262\351\224\256\345\205\263",16'hffff); golden_text(344,144,variant ? "\351\242\234\350\211\262\351\224\256\345\274\200" : "\351\242\234\350\211\262\351\224\256\345\205\263",16'hffff); end
                5: begin
                    golden_text(40,144,"\345\217\202\350\200\203\344\270\215\351\200\217\346\230\216",16'hffff); golden_text(344,144,"FPGA \351\200\217\346\230\216\345\272\246",16'hffff);
                    golden_text(480,144,$sformatf("%0d",alpha_value(variant)),16'hffe0); golden_text(516,144,"/255",16'hffff);
                    golden_text(40,400,"\346\255\245\350\277\2331 \351\225\277\346\214\211\350\277\236\345\217\221 \351\242\234\350\211\262\351\224\256\345\205\263",16'h07ff);
                end
                6: golden_text(32,128,"ALPHA + COLOR KEY / GOAL 60 FPS",16'hffff);
            endcase
            golden_text(16,426,actions[demo],16'hffff);
            if(demo==6) golden_text(16,450,"FPGA \347\241\254\344\273\266\345\220\210\346\210\220  W\345\212\240\345\216\213 A\345\207\217\345\216\213  D\350\277\224\345\233\236",16'h07ff);
            else golden_text(16,450,"S\345\210\207\346\215\242 CPU/FPGA  D\350\277\224\345\233\236",16'h07ff);
            sample_ar=sample_ar+graphics.burst_reads-last_burst_ar;
            sample_aw=sample_aw+graphics.burst_writes-last_burst_aw;
            last_burst_ar=graphics.burst_reads; last_burst_aw=graphics.burst_writes;
            sample_frames=sample_frames+1;
            if(sample_frames==(demo==6 ? 30 : 4)) begin
                expected_metric_ar=sample_ar; expected_metric_aw=sample_aw;
                expected_metric_sprites=scene_sprites;
                sample_frames=0; sample_ar=0; sample_aw=0;
            end
            check_player_assets();
            for(integer r=0;r<32;r=r+1) for(integer c=0;c<32;c=c+1)
                if({mem[ASSET_BASE-BASE+r*64+c*2+1],mem[ASSET_BASE-BASE+r*64+c*2]}!==sprite_pixel(r,c))
                    $fatal(1,"Immutable Sprite resource changed");
            compare_page(mode);
        end
    endtask
    reg ack_seen=0;
    integer button_events=0;
    always @(posedge clk) if(!soc_reset && button_ack[0]!=ack_seen) begin
        ack_seen=button_ack[0]; button_events=button_events+1;
        if(!demo_active) begin
            if(button_pending==8) menu_level=0;
            if(button_pending==16) menu_level=1;
            if(button_pending==1 || button_pending==2) begin
                if(menu_level) menu_item[menu_group]=(menu_item[menu_group]+(button_pending==1 ? (menu_group ? 2 : 3) : 1))%(menu_group ? 3 : 4);
                else menu_group=(menu_group+(button_pending==1 ? 2 : 1))%3;
            end
        end else case(button_pending)
            1: begin
                if(demo==6) begin
                    case(cpu_target) 64:cpu_target=128; 128:cpu_target=256; 256:cpu_target=384;
                        384:cpu_target=512; 512:cpu_target=768; 768:cpu_target=1024;
                        1024:cpu_target=1536; 1536:cpu_target=2048; 2048:cpu_target=3072;
                        3072:cpu_target=4096; default:cpu_target=4096; endcase
                end
                else if(demo==5) variant=variant<255 ? variant+1 : 255;
                else if(demo==0) variant=(variant+1)%3;
                else variant=variant^1;
                model_frame=0; reset_sample=1;
                for(integer i=0;i<2;i=i+1) measured_valid[i]=0;
            end
            2: begin model_hw=model_hw^1; model_auto=0; model_frame=0; reset_sample=1; manual_events=manual_events+1; end
            4: if(demo==6) begin
                    case(cpu_target) 128:cpu_target=64; 256:cpu_target=128; 384:cpu_target=256;
                        512:cpu_target=384; 768:cpu_target=512; 1024:cpu_target=768;
                        1536:cpu_target=1024; 2048:cpu_target=1536; 3072:cpu_target=2048;
                        4096:cpu_target=3072; default:cpu_target=64; endcase
                    model_frame=0; reset_sample=1;
                end
                else if(demo==5) begin variant=variant>0 ? variant-1 : 0; alpha_decrements=alpha_decrements+1; model_frame=0; reset_sample=1; end
            8: demo_active=0;
            default: $fatal(1,"Unexpected button event %h",button_pending);
        endcase
    end
    task press_keys(input reg [4:0] mask);
        begin
            key_i=~mask; #2000;
            // Keep the fifth (Enter) key live long enough for the real CPU
            // polling loop, then let its debounced release settle as well.
            #20000; key_i=5'h1f; #2000;
        end
    endtask
    // Wait for each menu redraw and event acknowledgement so no key is lost.
    task menu_key(input reg [4:0] mask);
        integer before_frames;
        before_frames=menu_frames; press_keys(mask); wait(menu_frames>before_frames);
    endtask
    task leave_demo;
        integer before_frames;
        before_frames=menu_frames; press_keys(8); wait(menu_frames>before_frames);
    endtask
    initial begin
        wait(menu_frames>=1 && page_frames[0]+page_frames[1]>=1);
        menu_key(1); menu_key(2); // root wrap in both directions
        menu_key(16);
        if(ui_smoke) begin
            // Focus on changed UI/assets; exercise both HW and CPU scene access.
            press_keys(16); wait(demo_hw[0]>=1);
            press_keys(1); wait(variant_coverage[0][1]>=1); leave_demo();
            for(integer i=0;i<4;i=i+1) menu_key(2); // forward wrap of all basic entries
            menu_key(8); menu_key(2); menu_key(16);
            for(integer i=0;i<3;i=i+1) menu_key(1); // reverse wrap of all advanced entries
            menu_key(2); press_keys(16); wait(variant_coverage[5][128]>=1);
            press_keys(1); wait(variant_coverage[5][129]>=1);
            press_keys(2); wait(demo_cpu[5]>=1);
            leave_demo(); menu_key(8); test_done=1;
        end else begin
        for(integer d=0;d<4;d=d+1) begin
            press_keys(16); wait(demo_hw[d]>=1);
            press_keys(1); wait(variant_coverage[d][1]>=1);
            if(d==1) begin press_keys(2); wait(demo_cpu[d]>=1); end
            leave_demo();
            if(d<3) menu_key(2);
        end
        menu_key(8); menu_key(2); menu_key(16);
        press_keys(16); wait(variant_coverage[4][1]>=1);
        press_keys(1); wait(variant_coverage[4][0]>=1); leave_demo(); menu_key(2);
        press_keys(16); wait(variant_coverage[5][128]>=1);
        for(integer a=0;a<3;a=a+1) begin press_keys(1); wait(variant_coverage[5][129+a]>=1); end
        press_keys(4); wait(alpha_decrements==1 && variant==130);
        press_keys(2); wait(demo_cpu[5]>=1); leave_demo(); menu_key(2);
        press_keys(16); wait(demo_hw[6]>=1);
        wait(coverage_hw[1]>=1); press_keys(1);
        wait(coverage_hw[2]>=1); press_keys(1);
        wait(coverage_hw[3]>=1); leave_demo();
        leave_demo(); test_done=1;
        end
    end
    integer px=0,py=0;
    reg prev_de=0,scan_page=0,prev_page=0,prev_ack=0,safe_boundary,scan_verified=0;
    integer preview_file=0,scan_present=0,scan_mode=0,return_frames=0;
    always @(posedge pixel_clk) begin
        safe_boundary=graphics.video.h==0 && graphics.video.v==524 &&
                      graphics.video.req_toggle==graphics.video.done_sync[1];
        #1;
        if(!reset) begin
            if(graphics.display_page_active!=prev_page && !safe_boundary)
                $fatal(1,"SoC changed display page mid-frame");
            if(graphics.swap_ack_pixel!=prev_ack) begin
                if(!safe_boundary) $fatal(1,"SoC acknowledged before old reads drained");
                swap_acks=swap_acks+1;
            end
            prev_page=graphics.display_page_active; prev_ack=graphics.swap_ack_pixel;
            if(de) begin
                if(px==0 && py==0) begin
                    scan_page=graphics.display_page_active;
                    scan_present=page_present[scan_page];
                    scan_mode=page_mode[scan_page];
                    scan_verified=page_verified[scan_page] && verified_present[scan_page]==scan_present;
                    if(scan_verified && previewed_present[scan_page]!=scan_present) begin
                        if(ui_smoke) preview_file=$fopen($sformatf("reports/menu_player_%0d.ppm",scan_present),"wb");
                        else preview_file=$fopen($sformatf("reports/motion_%0d.ppm",scan_present),"wb");
                        if(preview_file==0) $fatal(1,"Cannot open scanout preview");
                        $fwrite(preview_file,"P6\n640 480\n255\n");
                    end
                end
                if(scan_page!=graphics.display_page_active ||
                   (scan_verified && pixel!==snapshot[scan_page*307200+py*640+px]))
                    $fatal(1,"SoC scanout page %0d pixel (%0d,%0d) mismatch",scan_page,px,py);
                if(preview_file) $fwrite(preview_file,"%c%c%c",{pixel[15:11],pixel[15:13]},
                    {pixel[10:5],pixel[10:9]},{pixel[4:0],pixel[4:2]});
                px=px+1;
            end
            if(prev_de && !de) begin
                if(px!=640) $fatal(1,"SoC invalid line length %0d",px);
                px=0; py=py+1;
                if(py==480) begin
                    page_frames[scan_page]=page_frames[scan_page]+1; py=0;
                    if(scan_verified) verified_scan_frames=verified_scan_frames+1;
                    if(preview_file) begin
                        $fclose(preview_file); preview_file=0;
                        if(ui_smoke) $fdisplay(progress_file,"PREVIEW menu_player_%0d",scan_present);
                        else $fdisplay(progress_file,"PREVIEW motion_%0d",scan_present);
                        $fflush(progress_file);
                        previewed_present[scan_page]=scan_present;
                    end
                    if(returned_to_cpu && scan_mode==0 && scan_present>=3)
                        return_frames=return_frames+1;
                end
            end
            prev_de=de;
        end
    end
    initial begin
        $readmemh("sim/font5x7.hex",font_columns);
        $readmemh("sim/font_cn.hex",font_cn_records);
        $readmemh("sim/player_expected.hex",player_expected);
        $readmemh("sim/game_expected.hex",game_expected);
        for(integer i=0;i<4;i=i+1) begin coverage_cpu[i]=0; coverage_hw[i]=0; scene_coverage_cpu[i]=0; scene_coverage_hw[i]=0; end
        for(integer i=0;i<2;i=i+1) measured_valid[i]=0;
        menu_item[0]=0; menu_item[1]=0;
        for(integer d=0;d<8;d=d+1) begin
            demo_hw[d]=0; demo_cpu[d]=0;
            for(integer a=0;a<256;a=a+1) variant_coverage[d][a]=0;
        end
        page_frames[0]=0; page_frames[1]=0;
        mode_frames[0]=0; mode_frames[1]=0;
        page_present[0]=0; page_present[1]=0;
        page_verified[0]=0; page_verified[1]=0;
        verified_present[0]=0; verified_present[1]=0;
        page_mode[0]=0; page_mode[1]=0;
        previewed_present[0]=0; previewed_present[1]=0;
        progress_file=$fopen(ui_smoke ? "reports/soc_ui_progress.log" : "reports/soc_progress.log","w");
        if(progress_file==0) $fatal(1,"Cannot create SoC progress log");
        for(integer n=0;n<MEM_BYTES;n=n+1) mem[n]=8'ha5;
        repeat(50) @(negedge clk); reset=0;
        wait(test_done);
        wait(swap_acks==swap_commands && previewed_present[graphics.display_page_active]==swap_commands);
        check_player_assets();
        if(ui_smoke) begin
            if(menu_frames<15 || demo_hw[0]<1 || variant_coverage[0][1]<1 || demo_hw[5]<1 ||
           variant_coverage[5][129]<1 || demo_cpu[5]<1 || manual_events!=1 || auto_events!=0 ||
               hw_asset_reads==0 || cpu_asset_reads==0 || verified_scan_frames<12)
                $fatal(1,"Missing menu/player/HW/CPU smoke coverage");
            $display("PASS UI: %0d menu frames, %0d verified pages, %0d complete verified scan frames, %0d swaps",
                     menu_frames,verified_scenes,verified_scan_frames,swap_acks);
            $display("PASS UI: all four direction frames match source-derived RGB565; %0d bytes uploaded once; forward/reverse menu wrap; Fill and Alpha HW/CPU; no front-page writes",
                     asset_write_bytes);
        end else begin
        for(integer d=0;d<7;d=d+1)
            if(demo_hw[d]<1) $fatal(1,"Missing independent demo %0d",d);
        if(variant_coverage[5][128]<1 || variant_coverage[5][129]<1 || variant_coverage[5][130]<1)
            $fatal(1,"Missing alpha levels 128/129/130");
        for(integer i=1;i<4;i=i+1)
            if(coverage_hw[i]<1) $fatal(1,"Missing HW load/metric coverage %0d",i);
        if(coverage_cpu[1]<1 || demo_cpu[1]<1 || demo_cpu[5]<1 || variant_coverage[4][0]<1 || variant_coverage[4][1]<1)
            $fatal(1,"Missing CPU baseline or isolated Color Key coverage");
        if(hw_asset_reads==0 || cpu_asset_reads==0 || asset_write_bytes!=ASSET_UPLOAD_BYTES ||
           verified_scenes<50 || verified_scan_frames<40 ||
           manual_events!=2 || auto_events!=0 || video_size_reads==0)
            $fatal(1,"Missing UI/mode/button/asset coverage");
        $display("PASS: real CPU/HW/CPU, %0d CPU frames, %0d HW frames, %0d swaps; same scene pixels; UART metrics; no front writes",
                 mode_frames[0],mode_frames[1],swap_acks);
        $display("PASS: %0d complete A frames, %0d complete B frames, no scanout mismatch",page_frames[0],page_frames[1]);
        $display("PASS: DDR image uploaded once (%0d bytes), immutable across A/B clears; CPU resource bursts=%0d, HW resource bursts=%0d",
                 asset_write_bytes,cpu_asset_reads,hw_asset_reads);
        $display("PASS: hardware burst counters read=%0d write=%0d; Sprite targets 64/128/256; 7 independent demos, FPGA Alpha+Key stress, Alpha 1-step levels, Color Key toggle, Chinese two-level menu and full HUD covered",
                 graphics.burst_reads,graphics.burst_writes);
        end
        if(graphics.underflow||graphics.read_error) $fatal(1,"SoC scanout error");
        if(ui_smoke) $display("SOC UI TEST PASSED"); else $display("SOC TEST PASSED");
        $fclose(progress_file); $finish;
    end
    initial forever begin
        #10000000;
        $fdisplay(progress_file,"time=%0t commands=%0d CPU read bytes=%0d display=%b",
            $time,commands,cpu_read_bytes,graphics.display_enable);
        $fflush(progress_file);
    end
    initial begin #(64'd10000000000); $fatal(1,"SoC firmware timeout"); end
endmodule
