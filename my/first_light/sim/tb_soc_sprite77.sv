`timescale 1ns/1ps
module tb_soc_sprite77;
    reg clk=0,pixel_clk=0,reset=1;
    reg uart_rx=1;
    reg boot_uart_only=0;
    initial boot_uart_only=$test$plusargs("BOOT_UART_ONLY");
    reg menu_smoke=0;
    initial menu_smoke=$test$plusargs("MENU_SMOKE");
    reg basic_random_test=0;
    initial basic_random_test=$test$plusargs("BASIC_RANDOM");
    reg moving_test=0;
    initial moving_test=$test$plusargs("BASIC_MOVING");
    reg perf_test=0;
    initial perf_test=$test$plusargs("BASIC_PERF");
    reg controls_test=0;
    initial controls_test=$test$plusargs("BASIC_CONTROLS");
    reg alpha_test=0,key2_down=0;
    initial alpha_test=$test$plusargs("ALPHA_TEST");
    integer alpha_expected=0,alpha_mode_expected=0,alpha_key_expected=1;
    integer alpha_commands=0;
    reg stress_test=0,stress_in_basic=0,stress_in_advanced=0,stress_menu_right=0;
    initial stress_test=$test$plusargs("BASIC_STRESS") || $test$plusargs("BASIC_MOVING") ||
                        $test$plusargs("BASIC_PERF") || $test$plusargs("BASIC_CONTROLS");
    integer stress_count=16,stress_mode=0;
    integer basic_frames=0,basic_last_commands=0,basic_last_fills=0,basic_last_copies=0;
    reg [15:0] basic_reference[0:307199];
    reg [31:0] motion_reference[0:255][0:2];
    integer basic_previous_count=0;
    reg [31:0] basic_previous_remainder=0;
    integer perf_engine_cycles=0,perf_config_writes=0,perf_present_mode=0,perf_present_count=0;
    time perf_first_command=0,perf_previous_ack=0;
    integer perf_previous_mode=0,perf_previous_count=0;
    integer perf_samples[0:2];
    time perf_elapsed[0:2],perf_max_period[0:2];
    always @(posedge clk) if(perf_test && graphics.busy) perf_engine_cycles=perf_engine_cycles+1;
    integer smoke_stage=0;
    wire [7:0] safe_uart_payload =
        cpu.u_EfxSapphireSoc.system_uart_0_io_logic.uartCtrl_1_io_read_queueWithOccupancy_io_pop_valid ?
        cpu.u_EfxSapphireSoc.system_uart_0_io_logic.uartCtrl_1_io_read_queueWithOccupancy_io_pop_payload : 8'h00;
    // The generated Sapphire model exposes X on the empty FIFO data bus.
    // Real hardware has a defined 0/1 value there; make only that invalid
    // payload deterministic, including firmware that compiles UART dispatch
    // into speculative arithmetic before testing the valid bit.
    initial begin
        #1;
        force cpu.u_EfxSapphireSoc.system_uart_0_io_logic.bridge_read_streamBreaked_payload = safe_uart_payload;
    end
    reg [3:0] key_state=0; // Debounced KEY0..KEY3 event toggles.
    always #5 clk=~clk;
    always #19.8347107 pixel_clk=~pixel_clk;
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
    render_subsystem graphics(
        .clk(clk),.reset(soc_reset|master_reset),.pixel_clk(pixel_clk),.memory_ready(1'b1),.key2_down(key2_down),.clock_hold(1'b0),.clock_ready(1'b1),
        .clock_debug(8'h0d),
        .paddr(paddr),.psel(psel),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),
        .prdata(prdata),.pready(pready),.pslverror(pslverror),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wlast(wlast),.wvalid(wvalid),.wready(wready),
        .bresp(bresp),.bvalid(bvalid),.bready(bready),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rresp(rresp),.rlast(rlast),.rvalid(rvalid),.rready(rready),
        .pixel(pixel),.hs(hs),.vs(vs),.de(de)
    );
    localparam BASE=32'h01000000, PAGE_BYTES=960000;
    localparam ASSET_BASE=32'h01200000, ASSET_BYTES=1048576;
    localparam APP_HEAD=32'h013ffff0, APP_BASE=32'h01400000;
    localparam MEM_BYTES=APP_BASE-BASE+65536;
    integer asset_length;
    reg [7:0] mem[0:MEM_BYTES-1];
    reg writing=0,reading=0;
    integer wa,ra,wl,rl,wb,rb,ws,rs;
    reg [7:0] wid,rid;
    integer commands=0,fill_commands=0,copy_commands=0;
    integer opaque_copy_commands=0,keyed_copy_commands=0;
    integer cpu_reads=0,cpu_read_bytes=0,copy_reads=0,progress_file;
    integer swap_commands=0,demo_swaps=0,swap_acks=0,page_frames[0:1];
    integer reports_cpu=0,reports_hw=0,mode_frames[0:1];
    integer last_commands=0,last_fills=0,last_copies=0,last_mode=-1,scene_frame=-1;
    integer page_present[0:1],bus_cycle=0,cpu_writes=0;
    integer video_status_reads=0,video_size_reads=0;
    integer asset_write_bytes=0,cpu_asset_reads=0,hw_asset_reads=0;
    integer keyed_zero_beats=0,keyed_partial_beats=0;
    integer uart_ready=0,uart_error=0,uart_ok=0,uart_cached=0;
    integer uart_rx_bytes=0,uart_pop_bytes=0;
    always @(posedge clk) if(boot_uart_only && cpu.u_EfxSapphireSoc.system_uart_0_io_logic.uartCtrl_1_io_read_valid &&
                           cpu.u_EfxSapphireSoc.system_uart_0_io_logic.uartCtrl_1_io_read_queueWithOccupancy_io_push_ready) begin
        uart_rx_bytes=uart_rx_bytes+1;
    end
    always @(posedge clk) if(boot_uart_only &&
                           cpu.u_EfxSapphireSoc.system_uart_0_io_logic.uartCtrl_1_io_read_queueWithOccupancy_io_pop_valid &&
                           cpu.u_EfxSapphireSoc.system_uart_0_io_logic.uartCtrl_1_io_read_queueWithOccupancy_io_pop_ready) begin
        uart_pop_bytes=uart_pop_bytes+1;
    end
    reg seen_pose0=0,seen_pose38=0,seen_pose76=0,seen_wrap=0;
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
                 (m_awaddr>=32'h013fff00 && (m_awaddr&~((1<<m_awsize)-1))+(m_awlen+1)*(1<<m_awsize)<=APP_BASE) ||
                 (m_awaddr>=APP_BASE && (m_awaddr&~((1<<m_awsize)-1))+(m_awlen+1)*(1<<m_awsize)<=APP_BASE+65536) ||
                 (boot_uart_only && m_awaddr>=ASSET_BASE &&
                  (m_awaddr&~((1<<m_awsize)-1))+(m_awlen+1)*(1<<m_awsize)<=ASSET_BASE+ASSET_BYTES) ||
                 (m_awaddr>=ASSET_BASE+32'hf0000 &&
                  (m_awaddr&~((1<<m_awsize)-1))+(m_awlen+1)*(1<<m_awsize)<=ASSET_BASE+32'hf0800)))
                $fatal(1,"SoC write outside framebuffer/mailbox: %h",m_awaddr);
            if(m_awburst!=1 || m_awsize>4) $fatal(1,"Unsupported AW burst");
            wa=m_awaddr-BASE; wl=m_awlen; wb=0; ws=1<<m_awsize;
            wid=m_awid; writing=1;
            if(!m_awid[7]) cpu_writes=cpu_writes+1;
        end
        if(m_wvalid&&m_wready) begin
            if(m_wlast!=(wb==wl)) $fatal(1,"SoC WLAST mismatch");
            if(wid[7] && graphics.operation==2) begin
                if(m_wstrb==0) keyed_zero_beats=keyed_zero_beats+1;
                else if(m_wstrb!=16'hffff) keyed_partial_beats=keyed_partial_beats+1;
            end
            for(integer b=0;b<16;b=b+1)
                if(m_wstrb[b]) begin
                    mem[(wa&~15)+b]=m_wdata[8*b+:8];
                    if(wa>=ASSET_BASE-BASE && wa<ASSET_BASE-BASE+ASSET_BYTES)
                        asset_write_bytes=asset_write_bytes+1;
                end
            wa=(wa&~(ws-1))+ws; wb=wb+1;
            if(m_wlast) begin writing=0; m_bvalid<=1; m_bid<=wid; m_bresp<=0; end
        end
        if(m_bvalid&&m_bready) m_bvalid<=0;
        if(m_arvalid&&m_arready) begin
            if(!((m_araddr>=BASE && (m_araddr&~((1<<m_arsize)-1))+(m_arlen+1)*(1<<m_arsize)<=BASE+2*PAGE_BYTES) ||
                 (m_araddr>=ASSET_BASE && (m_araddr&~((1<<m_arsize)-1))+(m_arlen+1)*(1<<m_arsize)<=ASSET_BASE+ASSET_BYTES) ||
                 (m_araddr>=32'h013f0000 && (m_araddr&~((1<<m_arsize)-1))+(m_arlen+1)*(1<<m_arsize)<=APP_BASE+65536)))
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
                if(perf_test && perf_first_command==0) perf_first_command=$time;
                commands=commands+1;
                if(alpha_test) begin
                    $fdisplay(progress_file,"CMD op=%0d src=%h dst=%h a=%0d time=%0t",
                        graphics.operation,graphics.src,graphics.dst,graphics.alpha_opacity,$time);
                    $fflush(progress_file);
                end
                if(graphics.operation==0) fill_commands=fill_commands+1;
                else if(stress_test && stress_in_basic || basic_random_test && (smoke_stage==2 || smoke_stage==5)) begin
                    if(graphics.operation!=1 || graphics.src!=ASSET_BASE+32'hf0000 ||
                       graphics.src_stride!=64 || graphics.width!=32 || graphics.height!=32)
                        $fatal(1,"BASIC hardware copy must read the 32x32 DDR resource");
                    copy_commands=copy_commands+1;
                end else if(alpha_test) begin
                    if(graphics.operation!=(alpha_expected ? 3 : (alpha_key_expected ? 2 : 1)) ||
                       graphics.src<ASSET_BASE || graphics.src>=ASSET_BASE+asset_length ||
                       graphics.src_stride!=graphics.width*2)
                        $fatal(1,"Alpha firmware used wrong command/source");
                    if(graphics.operation==3) begin
                        if(graphics.alpha_opacity!=((100-alpha_expected)*256+50)/100 ||
                           graphics.alpha_key_enable!=alpha_key_expected || graphics.color!=16'hf81f)
                            $fatal(1,"Alpha coefficient/key mismatch");
                        alpha_commands=alpha_commands+1;
                    end
                    copy_commands=copy_commands+1;
                end else begin
                    if((graphics.operation!=1 && graphics.operation!=2) ||
                       graphics.src<ASSET_BASE || graphics.src>=ASSET_BASE+asset_length ||
                       graphics.src_stride!=graphics.width*2)
                        $fatal(1,"Demo copy did not use the DDR image");
                    if(graphics.operation==2) begin
                        if(graphics.color!=16'hf81f || demo_swaps==5)
                            $fatal(1,"Unexpected keyed copy or transparent color");
                        keyed_copy_commands=keyed_copy_commands+1;
                    end else begin
                        if(demo_swaps!=5) $fatal(1,"Opaque copy outside KEY OFF frame");
                        opaque_copy_commands=opaque_copy_commands+1;
                    end
                    copy_commands=copy_commands+1;
                end
            end
            if(perf_test && pwrite && paddr!=16'h40 && paddr!=16'h3c && paddr!=16'h20)
                perf_config_writes=perf_config_writes+1;
            if(pwrite&&paddr==16'h40) begin
                swap_commands=swap_commands+1;
                if(alpha_test) begin
                    if(swap_commands<=2 || swap_commands==11) check_menu();
                    else begin demo_swaps=demo_swaps+1; check_scene(); end
                end else if(stress_test) begin
                    if(stress_in_basic) check_basic();
                    else if(stress_in_advanced) begin
                        last_commands=commands; last_fills=fill_commands; last_copies=copy_commands;
                        demo_swaps=demo_swaps+1; check_scene();
                    end else check_menu();
                end else if(basic_random_test) begin
                    case(smoke_stage)
                        0,3,6,7: check_menu();
                        1,2,4,5: check_basic();
                        8: begin
                            last_commands=commands; last_fills=fill_commands; last_copies=copy_commands;
                            demo_swaps=demo_swaps+1; check_scene();
                        end
                        default: $fatal(1,"Unexpected BASIC random stage");
                    endcase
                end else if(menu_smoke) begin
                    case(smoke_stage)
                        0,2,3: check_menu();
                        1: check_basic();
                        4: begin demo_swaps=demo_swaps+1; check_scene(); end
                        default: $fatal(1,"Unexpected menu smoke stage");
                    endcase
                end else if(swap_commands<=2) check_menu();
                else begin demo_swaps=demo_swaps+1; check_scene(); end
            end
        end
        if(graphics.display_enable && m_awvalid && m_awready && m_awaddr<BASE+2*PAGE_BYTES &&
           ((m_awaddr>=BASE+PAGE_BYTES)==graphics.display_page_sync[1]))
            $fatal(1,"Firmware rendered to the front page");
    end
    // Decode the real UART pin using the firmware's 100 MHz / 115200 divider.
    reg [7:0] uart_char;
    integer metric_fps,metric_us,metric_fields;
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
            if(uart_line.substr(0,10)=="ASSET READY") uart_ready=uart_ready+1;
            if(uart_line.substr(0,8)=="ASSET ERR") uart_error=uart_error+1;
            if(uart_line.substr(0,7)=="ASSET OK") uart_ok=uart_ok+1;
            if(uart_line.substr(0,11)=="ASSET CACHED") uart_cached=uart_cached+1;
            if(uart_line.substr(0,3)=="FAIL" || uart_line.substr(0,3)=="TRAP")
                $fatal(1,"Firmware reported: %s",uart_line);
            if(uart_line.substr(0,6)=="CPU FPS" || uart_line.substr(0,5)=="HW FPS") begin
                if(uart_line.substr(0,6)=="CPU FPS") begin
                    reports_cpu=reports_cpu+1;
                    metric_fields=$sscanf(uart_line,"CPU FPS %d US %d",metric_fps,metric_us);
                end else begin
                    reports_hw=reports_hw+1;
                    metric_fields=$sscanf(uart_line,"HW FPS %d US %d",metric_fps,metric_us);
                end
                if(metric_fields!=2 || metric_fps<1 || metric_fps>61 || metric_us<1)
                    $fatal(1,"Invalid measured UART metrics: %s",uart_line);
            end
            uart_line="";
        end
    end
    function automatic integer bounce(input integer phase,limit);
        integer p;
        p=phase%(2*limit); bounce=p>limit ? 2*limit-p : p;
    endfunction
    function automatic [31:0] word_at(input integer a);
        word_at={mem[a+3],mem[a+2],mem[a+1],mem[a]};
    endfunction
    function automatic integer signed8(input reg [7:0] value);
        signed8=value[7] ? value-256 : value;
    endfunction
    function automatic [15:0] sprite(input integer frame,x,y);
        integer entry,offset,width,at;
        begin
            entry=ASSET_BASE-BASE+16+frame*8;
            offset=word_at(entry);
            width=mem[entry+4];
            at=ASSET_BASE-BASE+offset+(y*width+x)*2;
            sprite={mem[at+1],mem[at]};
        end
    endfunction
    function automatic [7:0] resolution_char(input integer index,input bit measured);
        begin
            if(measured) case(index)
                0:resolution_char="R"; 1:resolution_char="E"; 2:resolution_char="S";
                3:resolution_char=" "; 4:resolution_char="6"; 5:resolution_char="4";
                6:resolution_char="0"; 7:resolution_char="X"; 8:resolution_char="4";
                9:resolution_char="8"; default:resolution_char="0";
            endcase else case(index)
                0:resolution_char="R"; 1:resolution_char="E"; 2:resolution_char="S";
                3:resolution_char=" "; 4:resolution_char="W"; 5:resolution_char="A";
                6:resolution_char="I"; default:resolution_char="T";
            endcase
        end
    endfunction
    function automatic [34:0] glyph_bits(input [7:0] character);
        begin
            case(character)
                "0":glyph_bits={5'he,5'h11,5'h13,5'h15,5'h19,5'h11,5'he};
                "1":glyph_bits={5'h4,5'hc,5'h4,5'h4,5'h4,5'h4,5'he};
                "2":glyph_bits={5'he,5'h11,5'h1,5'h2,5'h4,5'h8,5'h1f};
                "3":glyph_bits={5'h1e,5'h1,5'h1,5'he,5'h1,5'h1,5'h1e};
                "4":glyph_bits={5'h2,5'h6,5'ha,5'h12,5'h1f,5'h2,5'h2};
                "5":glyph_bits={5'h1f,5'h10,5'h10,5'h1e,5'h1,5'h1,5'h1e};
                "6":glyph_bits={5'h6,5'h8,5'h10,5'h1e,5'h11,5'h11,5'he};
                "7":glyph_bits={5'h1f,5'h1,5'h2,5'h4,5'h8,5'h8,5'h8};
                "8":glyph_bits={5'he,5'h11,5'h11,5'he,5'h11,5'h11,5'he};
                "9":glyph_bits={5'he,5'h11,5'h11,5'hf,5'h1,5'h2,5'h1c};
                "A":glyph_bits={5'he,5'h11,5'h11,5'h1f,5'h11,5'h11,5'h11};
                "B":glyph_bits={5'h1e,5'h11,5'h11,5'h1e,5'h11,5'h11,5'h1e};
                "C":glyph_bits={5'hf,5'h10,5'h10,5'h10,5'h10,5'h10,5'hf};
                "D":glyph_bits={5'h1e,5'h11,5'h11,5'h11,5'h11,5'h11,5'h1e};
                "E":glyph_bits={5'h1f,5'h10,5'h10,5'h1e,5'h10,5'h10,5'h1f};
                "F":glyph_bits={5'h1f,5'h10,5'h10,5'h1e,5'h10,5'h10,5'h10};
                "G":glyph_bits={5'he,5'h11,5'h10,5'h17,5'h11,5'h11,5'he};
                "H":glyph_bits={5'h11,5'h11,5'h11,5'h1f,5'h11,5'h11,5'h11};
                "I":glyph_bits={5'he,5'h4,5'h4,5'h4,5'h4,5'h4,5'he};
                "J":glyph_bits={5'h7,5'h2,5'h2,5'h2,5'h2,5'h12,5'hc};
                "K":glyph_bits={5'h11,5'h12,5'h14,5'h18,5'h14,5'h12,5'h11};
                "L":glyph_bits={5'h10,5'h10,5'h10,5'h10,5'h10,5'h10,5'h1f};
                "M":glyph_bits={5'h11,5'h1b,5'h15,5'h15,5'h11,5'h11,5'h11};
                "N":glyph_bits={5'h11,5'h19,5'h15,5'h13,5'h11,5'h11,5'h11};
                "O":glyph_bits={5'he,5'h11,5'h11,5'h11,5'h11,5'h11,5'he};
                "P":glyph_bits={5'h1e,5'h11,5'h11,5'h1e,5'h10,5'h10,5'h10};
                "Q":glyph_bits={5'he,5'h11,5'h11,5'h11,5'h15,5'h12,5'hd};
                "R":glyph_bits={5'h1e,5'h11,5'h11,5'h1e,5'h14,5'h12,5'h11};
                "S":glyph_bits={5'hf,5'h10,5'h10,5'he,5'h1,5'h1,5'h1e};
                "T":glyph_bits={5'h1f,5'h4,5'h4,5'h4,5'h4,5'h4,5'h4};
                "U":glyph_bits={5'h11,5'h11,5'h11,5'h11,5'h11,5'h11,5'he};
                "V":glyph_bits={5'h11,5'h11,5'h11,5'h11,5'h11,5'ha,5'h4};
                "W":glyph_bits={5'h11,5'h11,5'h11,5'h15,5'h15,5'h15,5'ha};
                "X":glyph_bits={5'h11,5'h11,5'ha,5'h4,5'ha,5'h11,5'h11};
                "Y":glyph_bits={5'h11,5'h11,5'ha,5'h4,5'h4,5'h4,5'h4};
                "Z":glyph_bits={5'h1f,5'h1,5'h2,5'h4,5'h8,5'h10,5'h1f};
                "%":glyph_bits={5'h11,5'h2,5'h4,5'h8,5'h11,5'h0,5'h0};
                "+":glyph_bits={5'h0,5'h4,5'h4,5'h1f,5'h4,5'h4,5'h0};
                "-":glyph_bits={5'h0,5'h0,5'h0,5'h1f,5'h0,5'h0,5'h0};
                ".":glyph_bits={5'h0,5'h0,5'h0,5'h0,5'h0,5'h6,5'h6};
                "/":glyph_bits={5'h1,5'h2,5'h4,5'h8,5'h10,5'h0,5'h0};
                default:glyph_bits=0;
            endcase
        end
    endfunction
    function automatic [7:0] key_char(input integer index,input bit keyed);
        begin
            case(index)
                0:key_char="K"; 1:key_char="E"; 2:key_char="Y";
                3:key_char=" "; 4:key_char="O";
                5:key_char=keyed ? "N" : "F";
                default:key_char=keyed ? " " : "F";
            endcase
        end
    endfunction
    task check_menu;
        integer page,base,n;
        reg [15:0] left_edge,right_edge;
        begin
            page=graphics.swap_page;
            base=page*PAGE_BYTES;
            left_edge={mem[base+(145*800+112)*2+1],mem[base+(145*800+112)*2]};
            right_edge={mem[base+(145*800+348)*2+1],mem[base+(145*800+348)*2]};
            if((!stress_test && (!basic_random_test && (!menu_smoke && swap_commands==1 || menu_smoke && smoke_stage!=3) ||
                basic_random_test && smoke_stage!=7) || stress_test && !stress_menu_right) &&
               (left_edge!==16'h07ff || right_edge!==16'h8410))
                $fatal(1,"Menu selection is not BASIC");
            if((!stress_test && (!basic_random_test && (!menu_smoke && swap_commands==2 || menu_smoke && smoke_stage==3) ||
                basic_random_test && smoke_stage==7) || stress_test && stress_menu_right) &&
               (left_edge!==16'h8410 || right_edge!==16'h07ff))
                $fatal(1,"KEY1 did not select ADVANCED");
            for(n=0;n<307200;n=n+1)
                snapshot[page*307200+n]={mem[base+(n/640*800+n%640)*2+1],mem[base+(n/640*800+n%640)*2]};
            page_present[page]=0;
            $display("PASS menu selection %0d",swap_commands);
        end
    endtask
    function automatic [34:0] screen_glyph(input integer base,x,y);
        reg [34:0] bits;
        reg [15:0] px;
        begin
            bits=0;
            for(integer r=0;r<7;r=r+1) for(integer c=0;c<5;c=c+1) begin
                px={mem[base+((y+r*2)*800+x+c*2)*2+1],mem[base+((y+r*2)*800+x+c*2)*2]};
                if(px!=16'h1082) bits[34-r*5-c]=1;
            end
            screen_glyph=bits;
        end
    endfunction
    task read_number(input integer base,x,y,output integer value,digits);
        integer digit,found;
        reg done;
        begin
            value=0; digits=0; done=0;
            for(integer c=0;c<8 && !done;c=c+1) begin
                found=-1;
                for(digit=0;digit<10;digit=digit+1)
                    if(screen_glyph(base,x+c*12,y)==glyph_bits(8'd48+digit)) found=digit;
                if(found<0) done=1;
                else begin value=value*10+found; digits=digits+1; end
            end
            if(digits==0) $fatal(1,"Missing numeric HUD at (%0d,%0d)",x,y);
        end
    endtask
    task check_basic;
        integer page,base,n,side,x,y,row,col,mode,different,count,descriptors,at;
        integer cpu_us,hw_us,ops,digits,ratio,frac,total,fill_count,copy_count;
        integer motion_ptr,phase_x,phase_y,speed_x,speed_y,folded,idx;
        integer left_fill,right_fill,left_copy,right_copy;
        longint unsigned scaled,steps;
        reg [31:0] state;
        reg [15:0] actual,color,expected;
        begin
            page=graphics.swap_page;
            base=page*PAGE_BYTES;
            mode=commands!=basic_last_commands;
            state=word_at(32'h013fff00-BASE); count=state[15:0];
            if(state[31:24]!=8'hba || state[20]!=mode || !(count inside {16,64,128}))
                $fatal(1,"BASIC missing/invalid workload descriptor");
            if(stress_test && (count!=stress_count || mode!=stress_mode))
                $fatal(1,"BASIC load/mode transition mismatch: count=%0d mode=%0d",count,mode);
            if(basic_random_test && mode!=(basic_frames%2))
                $fatal(1,"BASIC CPU/HW transition failed");
            if(mode && (fill_commands-basic_last_fills!=count+1 || copy_commands-basic_last_copies!=count))
                $fatal(1,"BASIC did not execute all Fill/Copy operations");
            if(writing || m_bvalid) $fatal(1,"BASIC present before DDR writes drained");
            if(perf_test) begin
                perf_present_mode=mode; perf_present_count=count;
                if(mode) begin
                    $fdisplay(progress_file,"PROFILE blocks=%0d engine_us=%0d submit_to_ready_us=%0d register_writes=%0d",
                        count*2,perf_engine_cycles/100,($time-perf_first_command)/1000,perf_config_writes);
                    $fflush(progress_file);
                end
                perf_engine_cycles=0; perf_config_writes=0; perf_first_command=0;
            end
            basic_last_commands=commands;
            basic_last_fills=fill_commands; basic_last_copies=copy_commands;
            for(n=0;n<307200;n=n+1) golden[n]=16'h1082;
            left_fill=0; right_fill=0; left_copy=0; right_copy=0;
            scaled=word_at(32'h013fff14-BASE);
            scaled=scaled*256+basic_previous_remainder;
            steps=scaled/100000000;
            // Independently rasterize every descriptor in order. Overlapped
            // operations still count; later rectangles overwrite earlier ones.
            for(n=0;n<count;n=n+1) for(side=0;side<2;side=side+1) begin
                descriptors=word_at(32'h013fff04+side*4-BASE);
                if(descriptors<APP_BASE || descriptors+count*12>APP_BASE+65536)
                    $fatal(1,"Invalid BASIC descriptor pointer");
                at=descriptors-BASE+n*12;
                x=word_at(at); y=word_at(at+4); color=word_at(at+8);
                if(x<12 || x+32>628 || y<160 || y+32>424)
                    $fatal(1,"BASIC moving block touches HUD or leaves shared area");
                if(side==0) begin
                    if(x<320) left_fill=left_fill+1; else right_fill=right_fill+1;
                end else begin
                    if(x<320) left_copy=left_copy+1; else right_copy=right_copy+1;
                end
                motion_ptr=word_at(32'h013fff0c+side*4-BASE);
                if(motion_ptr<APP_BASE || motion_ptr+count*12>APP_BASE+65536)
                    $fatal(1,"Invalid BASIC motion pointer");
                idx=side*128+n;
                phase_x=word_at(motion_ptr-BASE+n*12);
                phase_y=word_at(motion_ptr-BASE+n*12+4);
                speed_x=word_at(motion_ptr-BASE+n*12+8)&65535;
                speed_y=word_at(motion_ptr-BASE+n*12+8)>>16;
                if(phase_x<0 || phase_x>=299008 || phase_y<0 || phase_y>=118784 ||
                   speed_x<24 || speed_x>96 || speed_y<24 || speed_y>96)
                    $fatal(1,"Invalid BASIC position/direction/speed state");
                folded=phase_x>149504 ? 299008-phase_x : phase_x;
                if(x!=12+folded/256) $fatal(1,"BASIC X does not follow reflected phase");
                folded=phase_y>59392 ? 118784-phase_y : phase_y;
                if(y!=160+folded/256) $fatal(1,"BASIC Y does not follow reflected phase");
                if(stress_test && count==basic_previous_count) begin
                    if(word_at(motion_ptr-BASE+n*12+8)!=motion_reference[idx][2] ||
                       phase_x!=(motion_reference[idx][0]+speed_x*steps)%299008 ||
                       phase_y!=(motion_reference[idx][1]+speed_y*steps)%118784)
                        $fatal(1,"BASIC clamp/renderer switch reset or broke trajectory");
                end
                motion_reference[idx][0]=phase_x;
                motion_reference[idx][1]=phase_y;
                motion_reference[idx][2]=word_at(motion_ptr-BASE+n*12+8);
                if(side==0 && !(color inside {16'hf800,16'h07e0,16'h001f,16'hffe0,
                                             16'h07ff,16'hf81f,16'hfd20,16'hffff}))
                    $fatal(1,"BASIC invalid fill color");
                for(row=0;row<32;row=row+1) for(col=0;col<32;col=col+1) begin
                    expected=color;
                    if(side==1) begin
                        if(row==0 || row==31 || col==0 || col==31) expected=16'hffff;
                        else expected=((row/8+col/8)%2) ? 16'h07ff : 16'hf81f;
                    end
                    golden[(y+row)*640+x+col]=expected;
                end
            end
            different=0;
            for(n=156*640;n<432*640;n=n+1) begin
                actual={mem[base+(n/640*800+n%640)*2+1],mem[base+(n/640*800+n%640)*2]};
                if(actual!==golden[n]) $fatal(1,"BASIC pixel mismatch at (%0d,%0d)",n%640,n/640);
                if(basic_frames>0 && actual!==basic_reference[n]) different=different+1;
            end
            if(left_fill==0 || right_fill==0 || left_copy==0 || right_copy==0)
                $fatal(1,"BASIC Fill/Copy are still partitioned");
            if(basic_random_test && (basic_frames%2)==1 && different==0)
                $fatal(1,"BASIC blocks did not move between CPU/HW frames");
            if(basic_random_test && basic_frames==2 && different==0)
                $fatal(1,"BASIC re-entry did not generate a new layout");
            if(stress_test && count==basic_previous_count) begin
                if(word_at(32'h013fff18-BASE)!=scaled%100000000)
                    $fatal(1,"BASIC discarded fractional motion time");
                if(steps>0 && different==0) $fatal(1,"BASIC same-load frames did not move");
            end
            basic_previous_count=count;
            basic_previous_remainder=word_at(32'h013fff18-BASE);
            read_number(base,96,80,total,digits);
            read_number(base,268,80,fill_count,digits);
            read_number(base,448,80,copy_count,digits);
            if(total!=count*2 || fill_count!=count || copy_count!=count)
                $fatal(1,"BASIC HUD operation counts are not the executed workload");
            if(screen_glyph(base,48,56)!=glyph_bits("/") || screen_glyph(base,48,104)!=glyph_bits("/"))
                $fatal(1,"BASIC metric separator glyph is incorrect");
            if(stress_test && ((controls_test && (basic_frames==0 || basic_frames==2 || basic_frames==3 ||
                                basic_frames==4 || basic_frames==6)) ||
                               (!controls_test && !perf_test && (basic_frames==0 || basic_frames==2 || basic_frames==3 ||
                               basic_frames==8)) ||
                               (perf_test && (basic_frames==0 ||
                                basic_frames==8 || basic_frames==15 || basic_frames==23)))) begin
                if(screen_glyph(base,112,8)!=glyph_bits("-") || screen_glyph(base,432,8)!=glyph_bits("-") ||
                   screen_glyph(base,88,56)!=glyph_bits("-") || screen_glyph(base,408,56)!=glyph_bits("-") ||
                   screen_glyph(base,108,104)!=glyph_bits("-"))
                    $fatal(1,"BASIC reused statistics after load change");
            end
            if(controls_test) begin
                // KEY0 changes only the renderer. Previously measured data
                // remains visible, while KEY1's new workload clears it above.
                if(basic_frames==1) begin
                    read_number(base,48,32,cpu_us,digits);
                    if(cpu_us<1) $fatal(1,"KEY0 discarded CPU statistics");
                end
                if(basic_frames==5 || basic_frames==7) begin
                    read_number(base,368,32,hw_us,digits);
                    if(hw_us<1) $fatal(1,"Renderer change discarded HW statistics");
                end
            end
            if(stress_test && ((controls_test && basic_frames==8) ||
                              (!controls_test && !perf_test && basic_frames==7) ||
                              (perf_test && basic_frames==22))) begin
                read_number(base,48,32,cpu_us,digits);
                read_number(base,368,32,hw_us,digits);
                if(cpu_us<1 || hw_us<1) $fatal(1,"Missing BASIC measured render time");
                read_number(base,88,56,ops,digits);
                if(ops<1 || ops>256*61) $fatal(1,"Invalid CPU operation throughput");
                read_number(base,408,56,ops,digits);
                if(ops<1 || ops>256*61) $fatal(1,"Invalid HW operation throughput");
                read_number(base,108,104,ratio,digits);
                if(screen_glyph(base,108+digits*12,104)!=glyph_bits(".")) $fatal(1,"Missing ratio decimal point");
                read_number(base,120+digits*12,104,frac,digits);
                if(ratio*10+frac!=cpu_us*10/hw_us) $fatal(1,"Incorrect displayed CPU/HW ratio");
                $display("PASS measured %0d-block HUD: CPU=%0d us HW=%0d us ratio10=%0d",count*2,cpu_us,hw_us,ratio*10+frac);
            end
            for(n=156*640;n<432*640;n=n+1) basic_reference[n]=golden[n];
            if(asset_write_bytes!=2048) $fatal(1,"BASIC sprite upload size mismatch");
            for(n=0;n<307200;n=n+1)
                snapshot[page*307200+n]={mem[base+(n/640*800+n%640)*2+1],mem[base+(n/640*800+n%640)*2]};
            basic_frames=basic_frames+1;
            page_present[page]=stress_test ? 200+basic_frames : (basic_random_test ? 100+basic_frames : 0);
            $display("PASS BASIC scene %0d: mode=%0d, %0d fills + %0d copies, changed pixels=%0d",
                     basic_frames,mode,count,count,different);
            $fdisplay(progress_file,"PASS BASIC scene %0d: mode=%0d count=%0d changed=%0d",basic_frames,mode,count,different);
            $fflush(progress_file);
        end
    endtask
    // Independently rasterize the scene, then compare every non-HUD pixel
    // at submission. Save the entire page for subsequent scanout checks.
    task golden_text(input integer x,y,input string label);
        reg [34:0] bits;
        for(integer c=0;c<label.len();c++) begin
            bits=glyph_bits(label.getc(c));
            for(integer r=0;r<7;r++) for(integer k=0;k<5;k++)
                if(bits&(35'd1<<(34-r*5-k)))
                    for(integer dy=0;dy<2;dy++) for(integer dx=0;dx<2;dx++)
                        golden[(y+r*2+dy)*640+x+c*12+k*2+dx]=16'hffff;
        end
    endtask
    function automatic [15:0] alpha_reference(input [15:0] f,b,input integer t);
        integer a,r,g,v;
        a=((100-t)*256+50)/100;
        r=((f>>11)*a+(b>>11)*(256-a)+128)/256;
        g=(((f>>5)&63)*a+((b>>5)&63)*(256-a)+128)/256;
        v=((f&31)*a+(b&31)*(256-a)+128)/256;
        alpha_reference=(r<<11)|(g<<5)|v;
    endfunction
    task check_scene;
        integer mode,page,x,y,base,offset,res_x,res_len,char_index,row,col,dx,dy,key_len;
        integer number_len,frame_number,digit,transparency;
        integer pose,entry,width,height,dst_x,dst_y;
        reg [31:0] state;
        reg [15:0] actual;
        reg [34:0] bits;
        reg [7:0] character;
        reg keyed;
        begin
            mode=commands!=last_commands; page=graphics.swap_page;
            state=word_at(32'h013fff00-BASE);
            if(state[31:24]!=8'h77) $fatal(1,"Missing animation state mailbox");
            pose=state[7:0];x=state[17:8];keyed=state[20];
            transparency=word_at(32'h013fff1c-BASE);
            if(transparency>100 || transparency%2 || transparency!=(alpha_test ? alpha_expected : 0))
                $fatal(1,"Wrong KEY2 transparency: got %0d expected %0d",transparency,alpha_expected);
            if(pose>76 || x<120 || x>520 || state[21]!=mode ||
               keyed!=(alpha_test ? alpha_key_expected : (demo_swaps!=2 && demo_swaps!=6)))
                $fatal(1,"Unexpected animation state: %h present=%0d",state,demo_swaps);
            if(pose==0) seen_pose0=1;
            if(pose==38) seen_pose38=1;
            if(pose==76) seen_pose76=1;
            if(seen_pose76 && pose==0) seen_wrap=1;
            if(mode!=(alpha_test ? alpha_mode_expected : (demo_swaps>=5 && demo_swaps<=8)))
                $fatal(1,"Unexpected renderer mode: present=%0d mode=%0d state=%h commands=%0d last=%0d",demo_swaps,mode,state,commands,last_commands);
            if(mode && (fill_commands-last_fills!=3 || copy_commands-last_copies!=1))
                $fatal(1,"Incomplete hardware scene");
            if(writing || m_bvalid) $fatal(1,"Present before DDR writes completed");
            if(mode!=last_mode) begin
                scene_frame=0;
                if(mode==0 && last_mode==1) returned_to_cpu=1;
            end else scene_frame=scene_frame+1;
            last_mode=mode; last_commands=commands;
            last_fills=fill_commands; last_copies=copy_commands;
            mode_frames[mode]=mode_frames[mode]+1;
            for(integer n=0;n<307200;n=n+1) golden[n]=16'h1082;
            if(asset_write_bytes!=2048 || word_at(ASSET_BASE-BASE)!=32'h37375341)
                $fatal(1,"DDR asset was altered");
            for(y=277;y<297;y=y+1) for(x=0;x<640;x=x+1) golden[y*640+x]=16'h07e0;
            for(y=321;y<341;y=y+1) for(x=0;x<640;x=x+1) golden[y*640+x]=16'h001f;
            entry=ASSET_BASE-BASE+16+pose*8;
            width=mem[entry+4];height=mem[entry+5];
            dst_x=state[17:8]+signed8(mem[entry+6]);
            dst_y=320+signed8(mem[entry+7]);
            if(dst_x<0 || dst_y<64 || dst_x+width>640 || dst_y+height>480)
                $fatal(1,"Sprite outside screen, pose=%0d",pose);
            if(mode && (graphics.src!=ASSET_BASE+word_at(entry) ||
                        graphics.src_stride!=width*2 || graphics.width!=width ||
                        graphics.height!=height || graphics.operation!=(transparency ? 3 : (keyed ? 2 : 1))))
                $fatal(1,"Hardware used wrong frame metadata");
            for(row=0;row<height;row=row+1)
                for(col=0;col<width;col=col+1)
                    if(!keyed || sprite(pose,col,row)!=16'hf81f)
                        golden[(dst_y+row)*640+dst_x+col]=alpha_reference(sprite(pose,col,row),
                            golden[(dst_y+row)*640+dst_x+col],transparency);
            golden_text(12,80,$sformatf("TRANSPARENCY %0d%%",transparency));
            golden_text(98,448,"KEY1 KEY  KEY2 +2 HOLD  KEY3 BACK");
            if(last_video_valid && last_video_size!=={16'd480,16'd640})
                $fatal(1,"Firmware read invalid measured size %h",last_video_size);
            res_x=last_video_valid ? 496 : 532;
            res_len=last_video_valid ? 11 : 8;
            for(char_index=0;char_index<res_len;char_index=char_index+1) begin
                character=resolution_char(char_index,last_video_valid);
                bits=glyph_bits(character);
                for(row=0;row<7;row=row+1) for(col=0;col<5;col=col+1)
                    if(bits&(35'd1<<(34-row*5-col)))
                        for(dy=0;dy<2;dy=dy+1) for(dx=0;dx<2;dx=dx+1)
                            golden[(56+row*2+dy)*640+res_x+char_index*12+col*2+dx]=16'hffff;
            end
            key_len=keyed ? 6 : 7;
            for(char_index=0;char_index<key_len;char_index=char_index+1) begin
                character=key_char(char_index,keyed);
                bits=glyph_bits(character);
                for(row=0;row<7;row=row+1) for(col=0;col<5;col=col+1)
                    if(bits&(35'd1<<(34-row*5-col)))
                        for(dy=0;dy<2;dy=dy+1) for(dx=0;dx<2;dx=dx+1)
                            golden[(56+row*2+dy)*640+12+char_index*12+col*2+dx]=16'hffff;
            end
            for(char_index=0;char_index<5;char_index=char_index+1) begin
                case(char_index)
                    0:character="F"; 1:character="R"; 2:character="A";
                    3:character="M"; default:character="E";
                endcase
                bits=glyph_bits(character);
                for(row=0;row<7;row=row+1) for(col=0;col<5;col=col+1)
                    if(bits&(35'd1<<(34-row*5-col)))
                        for(dy=0;dy<2;dy=dy+1) for(dx=0;dx<2;dx=dx+1)
                            golden[(56+row*2+dy)*640+164+char_index*12+col*2+dx]=16'hffff;
            end
            frame_number=pose+1;
            number_len=frame_number>=10 ? 2 : 1;
            for(char_index=0;char_index<number_len;char_index=char_index+1) begin
                digit=number_len==2 && char_index==0 ? frame_number/10 : frame_number%10;
                character=8'd48+digit;
                bits=glyph_bits(character);
                for(row=0;row<7;row=row+1) for(col=0;col<5;col=col+1)
                    if(bits&(35'd1<<(34-row*5-col)))
                        for(dy=0;dy<2;dy=dy+1) for(dx=0;dx<2;dx=dx+1)
                            golden[(56+row*2+dy)*640+236+char_index*12+col*2+dx]=16'hffff;
            end
            base=page*PAGE_BYTES;
            for(integer n=0;n<307200;n=n+1) begin
                actual={mem[base+(n/640*800+n%640)*2+1],mem[base+(n/640*800+n%640)*2]};
                if(n>=640*72 && actual!==golden[n])
                    $fatal(1,"Mode %0d frame %0d pixel (%0d,%0d): %h != %h",mode,scene_frame,n%640,n/640,actual,golden[n]);
                snapshot[page*307200+n]=actual;
            end
            // Rows 56..63 are above the old comparison boundary: verify the
            // complete RES WAIT / measured RES 640X480 label explicitly.
            for(y=56;y<72;y=y+1) for(x=res_x;x<628;x=x+1) begin
                actual={mem[base+(y*800+x)*2+1],mem[base+(y*800+x)*2]};
                if(actual!==golden[y*640+x])
                    $fatal(1,"Resolution HUD pixel (%0d,%0d): %h != %h",x,y,actual,golden[y*640+x]);
            end
            for(y=56;y<72;y=y+1) for(x=12;x<96;x=x+1) begin
                actual={mem[base+(y*800+x)*2+1],mem[base+(y*800+x)*2]};
                if(actual!==golden[y*640+x])
                    $fatal(1,"Key HUD pixel (%0d,%0d): %h != %h",x,y,actual,golden[y*640+x]);
            end
            for(y=56;y<72;y=y+1) for(x=164;x<260;x=x+1) begin
                actual={mem[base+(y*800+x)*2+1],mem[base+(y*800+x)*2]};
                if(actual!==golden[y*640+x])
                    $fatal(1,"Frame HUD pixel (%0d,%0d): %h != %h",x,y,actual,golden[y*640+x]);
            end
            // The top-left pixel of C/H must identify the active column.
            offset=base+8*1600+12*2;
            if({mem[offset+1],mem[offset]}!==(mode ? 16'h8410 : 16'hffff))
                $fatal(1,"CPU HUD active color mismatch");
            offset=base+8*1600+332*2;
            if({mem[offset+1],mem[offset]}!==(mode ? 16'hffff : 16'h8410))
                $fatal(1,"HW HUD active color mismatch");
            page_present[page]=demo_swaps;
            $fdisplay(progress_file,"PASS scene: present=%0d mode=%0d keyed=%0d pose=%0d x=%0d page=%0d time=%0t",
                      demo_swaps,mode,keyed,pose,state[17:8],page,$time); $fflush(progress_file);
        end
    endtask
    task send_char(input reg [7:0] value);
        begin
            uart_rx=0; #8680;
            for(integer bitno=0;bitno<8;bitno=bitno+1) begin uart_rx=value[bitno]; #8680; end
            uart_rx=1; #8680;
        end
    endtask
    task send_word(input reg [31:0] value);
        for(integer n=0;n<4;n=n+1) send_char(value[n*8+:8]);
    endtask
    task send_tiny_packet(input bit wrong_crc);
        begin
            // One RGB565 key pixel shared by 77 one-pixel entries. The DDR
            // boot path sees a real S77B app followed by a real S77U asset.
            send_char("S");send_char("7");send_char("7");send_char("B");
            send_word(4);send_word(32'h42013849); // CRC of jal x0,0
            send_char(8'h6f);send_char(0);send_char(0);send_char(0);
            send_char("S");send_char("7");send_char("7");send_char("U");
            send_word(634);send_word(1);
            send_word(wrong_crc ? 32'hd2ea4035 : 32'hd2ea4034);
            for(integer n=0;n<77;n=n+1) begin
                send_word(632);send_char(1);send_char(1);send_char(0);send_char(0);
            end
            send_char(8'h80);
        end
    endtask
    initial begin
        #1;
        if(alpha_test) begin
        wait(swap_commands==1); @(negedge clk); key_state[1]=~key_state[1];
        wait(swap_commands==2); @(negedge clk); key2_down=1; key_state[2]=~key_state[2];
        wait(demo_swaps==2); @(negedge clk); key2_down=0; // Held ENTER ignored.
        wait(demo_swaps==3); @(negedge clk); key2_down=1; key_state[2]=~key_state[2]; alpha_expected=2;
        wait(demo_swaps==4); @(negedge clk); key2_down=0; alpha_mode_expected=1; send_char("h");
        wait(demo_swaps==5); @(negedge clk); key2_down=1; key_state[2]=~key_state[2]; alpha_expected=4;
        wait(demo_swaps==6); @(negedge clk); key2_down=0; key_state[1]=~key_state[1]; alpha_key_expected=0;
        wait(demo_swaps==7); @(negedge clk); alpha_mode_expected=0; send_char("c");
        wait(demo_swaps==8); @(negedge clk); key_state[3]=~key_state[3];
        wait(swap_commands==11); @(negedge clk); key_state[2]=~key_state[2]; alpha_expected=0;
        end else if(controls_test) begin
        wait(swap_commands==1); @(negedge clk); stress_in_basic=1; key_state[2]=~key_state[2];
        wait(basic_frames==1); @(negedge clk); stress_mode=1; key_state[0]=~key_state[0]; // 32 CPU -> HW.
        wait(basic_frames==2); @(negedge clk); stress_count=64; key_state[1]=~key_state[1]; // 128 HW.
        wait(basic_frames==3); @(negedge clk); stress_count=128; key_state[1]=~key_state[1]; // 256 HW.
        wait(basic_frames==4); @(negedge clk); stress_count=16; key_state[1]=~key_state[1]; // 256 -> 32 HW.
        wait(basic_frames==5); @(negedge clk); stress_mode=0; key_state[0]=~key_state[0]; // 32 CPU.
        wait(basic_frames==6); @(negedge clk); stress_mode=1; stress_count=64;
        key_state[1:0]=~key_state[1:0]; // Simultaneous KEY0 + KEY1 -> 128 HW.
        wait(basic_frames==7); @(negedge clk); stress_mode=0; send_char("c"); // UART still selects CPU.
        wait(basic_frames==8); @(negedge clk); stress_mode=1; send_char("h"); // UART still selects HW.
        wait(basic_frames==9); @(negedge clk); stress_in_basic=0; key_state[3]=~key_state[3];
        wait(swap_commands==11); @(negedge clk); stress_menu_right=1; key_state[1]=~key_state[1];
        wait(swap_commands==12); @(negedge clk); stress_in_advanced=1; key_state[2]=~key_state[2];
        end else if(perf_test) begin
        wait(swap_commands==1); @(negedge clk); stress_in_basic=1; key_state[2]=~key_state[2];
        // Leave two initial CPU frames before each six-frame HW sample.
        for(integer group=0;group<3;group=group+1) begin
            wait(basic_frames==2+group*7); @(negedge clk); stress_mode=1; send_char("h");
            wait(basic_frames==8+group*7); @(negedge clk);
            if(group<2) begin
                stress_mode=0; stress_count=(group==0 ? 64 : stress_count*2);
                key_state[1]=~key_state[1]; send_char("c");
            end
        end
        // An extra 256 HW frame checks uninterrupted motion/statistics.
        wait(basic_frames==23); @(negedge clk); stress_mode=0; stress_count=16; key_state[1:0]=~key_state[1:0];
        wait(basic_frames==24); @(negedge clk);
        stress_in_basic=0; key_state[3]=~key_state[3];
        wait(swap_commands==26); @(negedge clk); stress_menu_right=1; key_state[1]=~key_state[1];
        wait(swap_commands==27); @(negedge clk); stress_in_advanced=1; key_state[2]=~key_state[2];
        end else if(stress_test) begin
        wait(swap_commands==1); @(negedge clk); stress_in_basic=1; key_state[2]=~key_state[2];
        wait(basic_frames==2); @(negedge clk); stress_count=64; key_state[1]=~key_state[1];
        wait(basic_frames==3); @(negedge clk); stress_count=128; key_state[1]=~key_state[1];
        wait(basic_frames==6); @(negedge clk); stress_mode=1; send_char("h");
        wait(basic_frames==8); @(negedge clk); stress_mode=0; stress_count=16; key_state[1:0]=~key_state[1:0];
        wait(basic_frames==9); @(negedge clk); stress_in_basic=0; key_state[3]=~key_state[3];
        wait(swap_commands==11); @(negedge clk); stress_menu_right=1; key_state[1]=~key_state[1];
        wait(swap_commands==12); @(negedge clk); stress_in_advanced=1; key_state[2]=~key_state[2];
        end else if(basic_random_test) begin
        wait(swap_commands==1); @(negedge clk); smoke_stage=1; key_state[2]=~key_state[2];
        wait(basic_frames==1); @(negedge clk); smoke_stage=2; send_char("h");
        wait(basic_frames==2); @(negedge clk); smoke_stage=3; key_state[3]=~key_state[3];
        wait(swap_commands==4); @(negedge clk); smoke_stage=4; key_state[2]=~key_state[2];
        wait(basic_frames==3); @(negedge clk); smoke_stage=5; send_char("h");
        wait(basic_frames==4); @(negedge clk); smoke_stage=6; key_state[3]=~key_state[3];
        wait(swap_commands==7); @(negedge clk); smoke_stage=7; key_state[1]=~key_state[1];
        wait(swap_commands==8); @(negedge clk); smoke_stage=8; key_state[2]=~key_state[2];
        end else if(menu_smoke) begin
        wait(swap_commands==1); @(negedge clk); smoke_stage=1; key_state[2]=~key_state[2];
        wait(swap_commands==2); @(negedge clk); smoke_stage=2; key_state[3]=~key_state[3];
        wait(swap_commands==3); @(negedge clk); smoke_stage=3; key_state[1]=~key_state[1];
        wait(swap_commands==4); @(negedge clk); smoke_stage=4; key_state[2]=~key_state[2];
        end else if(!boot_uart_only) begin
        wait(swap_commands==1); key_state[1]=~key_state[1];
        wait(swap_commands==2); key_state[2]=~key_state[2];
        // Send before acknowledgement so production firmware sees the
        // character on its next loop; no fake timers or test-only firmware.
        wait(mode_frames[0]==1); key_state[1]=~key_state[1];
        wait(mode_frames[0]==2); key_state[1]=~key_state[1];
        wait(mode_frames[0]==3); send_char("m");
        wait(mode_frames[0]==4); send_char("h");
        wait(mode_frames[1]==1); key_state[1]=~key_state[1];
        wait(mode_frames[1]==2); key_state[1]=~key_state[1];
        wait(mode_frames[1]==3); send_char("z");
        wait(mode_frames[1]==4); send_char("c");
        end
    end
    integer px=0,py=0;
    reg prev_de=0,scan_page=0,prev_page=0,prev_ack=0,safe_boundary;
    integer preview_file=0,scan_present=0,return_frames=0;
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
                if(perf_test && stress_in_basic) begin
                    if(perf_present_mode && perf_previous_mode && perf_present_count==perf_previous_count) begin
                        for(integer g=0;g<3;g=g+1) if(perf_present_count==(g==0 ? 16 : 32<<g)) begin
                            perf_samples[g]=perf_samples[g]+1;
                            perf_elapsed[g]=perf_elapsed[g]+$time-perf_previous_ack;
                            if($time-perf_previous_ack>perf_max_period[g]) perf_max_period[g]=$time-perf_previous_ack;
                            $fdisplay(progress_file,"PRESENT blocks=%0d interval_us=%0d",perf_present_count*2,($time-perf_previous_ack)/1000);
                            $fflush(progress_file);
                        end
                    end
                    perf_previous_ack=$time; perf_previous_mode=perf_present_mode; perf_previous_count=perf_present_count;
                end
            end
            prev_page=graphics.display_page_active; prev_ack=graphics.swap_ack_pixel;
            if(de) begin
                if(px==0 && py==0) begin
                    scan_page=graphics.display_page_active;
                    scan_present=page_present[scan_page];
                    if(alpha_test && (scan_present==4 || scan_present==6)) begin
                        preview_file=$fopen($sformatf("reports/alpha_%0d.ppm",scan_present),"wb");
                        $fwrite(preview_file,"P6\n640 480\n255\n");
                    end else if(controls_test && (scan_present==202 || scan_present==204)) begin
                        preview_file=$fopen($sformatf("reports/basic_controls_%0d.ppm",scan_present-200),"wb");
                        $fwrite(preview_file,"P6\n640 480\n255\n");
                    end else if(perf_test && (scan_present==208 || scan_present==215 || scan_present==223)) begin
                        preview_file=$fopen($sformatf("reports/basic_perf_%0d.ppm",scan_present-200),"wb");
                        $fwrite(preview_file,"P6\n640 480\n255\n");
                    end else if(!controls_test && stress_test && (scan_present==202 || scan_present==208)) begin
                        preview_file=$fopen($sformatf(moving_test ? "reports/basic_moving_%0d.ppm" :
                            "reports/basic_stress_%0d.ppm",scan_present-200),"wb");
                        $fwrite(preview_file,"P6\n640 480\n255\n");
                    end else if(basic_random_test && scan_present>=101 && scan_present<=104) begin
                        preview_file=$fopen($sformatf("reports/basic_random_%0d.ppm",scan_present-100),"wb");
                        $fwrite(preview_file,"P6\n640 480\n255\n");
                    end else if(scan_present==1 || scan_present==2 || scan_present==5 ||
                       scan_present==6 || scan_present==9) begin
                        preview_file=$fopen($sformatf("reports/motion_%0d.ppm",scan_present),"wb");
                        $fwrite(preview_file,"P6\n640 480\n255\n");
                    end
                end
                if(scan_page!=graphics.display_page_active || pixel!==snapshot[scan_page*307200+py*640+px])
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
                    if(preview_file) begin $fclose(preview_file); preview_file=0; end
                    if(returned_to_cpu && scan_present>=9) return_frames=return_frames+1;
                end
            end
            prev_de=de;
        end
    end
    initial begin
        page_frames[0]=0; page_frames[1]=0;
        mode_frames[0]=0; mode_frames[1]=0;
        page_present[0]=0; page_present[1]=0;
        for(integer g=0;g<3;g=g+1) begin perf_samples[g]=0; perf_elapsed[g]=0; perf_max_period[g]=0; end
        progress_file=$fopen("reports/soc_progress.log","w");
        if(progress_file==0) $fatal(1,"Cannot create SoC progress log");
        for(integer n=0;n<MEM_BYTES;n=n+1) mem[n]=8'ha5;
        #1;
        if(!boot_uart_only) begin
            if(stress_test || alpha_test) begin
                $readmemh("sim/sprite77_compact.memh",mem,ASSET_BASE-BASE);
                $readmemh("sim/app_image_compact.memh",mem,APP_HEAD-BASE);
            end else begin
                $readmemh("sim/sprite77.memh",mem,ASSET_BASE-BASE);
                $readmemh("sim/app_image.memh",mem,APP_HEAD-BASE);
            end
            asset_length=word_at(ASSET_BASE-BASE+8);
            if(asset_length<=632 || asset_length>ASSET_BYTES)
                $fatal(1,"Invalid preloaded asset length");
        end
        repeat(50) @(negedge clk); reset=0;
        if(boot_uart_only) begin
            wait(uart_ready>=1);
            send_tiny_packet(1);
            wait(uart_error>=1 && uart_ready>=2);
            if(word_at(ASSET_BASE-BASE)==32'h37375341)
                $fatal(1,"Corrupted upload was marked valid");
            send_tiny_packet(0);
            wait(uart_ok>=1);
            if(word_at(ASSET_BASE-BASE)!=32'h37375341 ||
               word_at(ASSET_BASE-BASE+8)!=634 ||
               word_at(APP_HEAD-BASE)!=32'h37505041 ||
               word_at(APP_BASE-BASE)!=32'h0000006f ||
               asset_write_bytes<618 || uart_rx_bytes<1298 ||
               uart_rx_bytes!=uart_pop_bytes)
                $fatal(1,"UART upload did not install validated DDR data");
            reset=1; repeat(50) @(negedge clk); reset=0;
            wait(uart_cached>=1);
            $display("PASS: Sapphire UART rejects bad CRC, accepts retry, verifies DDR and boots cached asset");
            $display("BOOT UART TEST PASSED"); $fclose(progress_file); $finish;
        end
        if(alpha_test) begin
            wait(demo_swaps>=9); @(negedge clk);
            if(alpha_commands!=3 || mode_frames[0]!=6 || mode_frames[1]!=3 ||
               swap_commands!=12 || graphics.underflow || graphics.read_error)
                $fatal(1,"Missing Alpha/key/menu coverage");
            wait(swap_acks>=12); wait(page_frames[0]+page_frames[1]>=12);
            $display("ALPHA SOC TEST PASSED: real firmware, KEY2 0/2/4, held ENTER isolation, CPU/HW, keying, return/reset, pixels and scanout");
            $fclose(progress_file); $finish;
        end else if(controls_test) begin
            wait(mode_frames[0]>=1); @(negedge clk);
            if(swap_commands!=13 || basic_frames!=9 || swap_acks<12 ||
               fill_commands!=358 || copy_commands!=352 || cpu_asset_reads==0 || hw_asset_reads==0 ||
               graphics.underflow || graphics.read_error)
                $fatal(1,"BASIC controls/menu/advanced integration failed");
            $display("BASIC CONTROLS SOC TEST PASSED"); $fclose(progress_file); $finish;
        end else if(perf_test) begin
            wait(mode_frames[0]>=1); @(negedge clk);
            if(swap_commands!=28 || basic_frames!=24 || swap_acks<27 ||
               fill_commands!=1395 || copy_commands!=1376 || graphics.underflow || graphics.read_error)
                $fatal(1,"BASIC performance integration failed");
            for(integer g=0;g<3;g=g+1) begin
                // The final hardware acknowledgement may occur after the
                // stimulus marks the next stage; at least 4 steady periods.
                if(perf_samples[g]<4) $fatal(1,"Insufficient steady performance frames");
                if(perf_max_period[g]>16667000) $fatal(1,"BASIC HW missed 60 FPS frame budget at group %0d",g);
                $display("PERFORMANCE blocks=%0d samples=%0d fps=%0.3f worst_us=%0d",g==0 ? 32 : 64<<g,
                    perf_samples[g],1.0e9*perf_samples[g]/perf_elapsed[g],perf_max_period[g]/1000);
                $fdisplay(progress_file,"PERFORMANCE blocks=%0d samples=%0d fps=%0.3f worst_us=%0d",g==0 ? 32 : 64<<g,
                    perf_samples[g],1.0e9*perf_samples[g]/perf_elapsed[g],perf_max_period[g]/1000);
            end
            $display("BASIC PERF SOC TEST PASSED"); $fclose(progress_file); $finish;
        end else if(stress_test) begin
            wait(mode_frames[0]>=1); @(negedge clk);
            if(swap_commands!=13 || basic_frames!=9 || swap_acks<12 ||
               fill_commands!=258 || copy_commands!=256 || cpu_asset_reads==0 || hw_asset_reads==0 ||
               graphics.underflow || graphics.read_error)
                $fatal(1,"BASIC load/menu/advanced integration failed");
            if(moving_test) $display("BASIC MOVING SOC TEST PASSED");
            else $display("BASIC STRESS SOC TEST PASSED");
            $fclose(progress_file); $finish;
        end
        if(basic_random_test) begin
            wait(mode_frames[0]>=1); @(negedge clk);
            if(swap_commands!=9 || basic_frames!=4 || swap_acks<8 ||
               fill_commands!=34 || copy_commands!=32 || cpu_asset_reads==0 || hw_asset_reads==0 ||
               graphics.underflow || graphics.read_error)
                $fatal(1,"BASIC random/menu/advanced integration failed");
            $display("BASIC RANDOM SOC TEST PASSED"); $fclose(progress_file); $finish;
        end
        if(menu_smoke) begin
            wait(mode_frames[0]>=1); @(negedge clk);
            if(swap_commands!=5 || mode_frames[0]!=1 ||
               graphics.underflow || graphics.read_error)
                $fatal(1,"Menu navigation or basic/advanced transition failed");
            $display("MENU SOC TEST PASSED"); $fclose(progress_file); $finish;
        end
        wait(return_frames>=1 && reports_cpu>=1 && reports_hw>=1 && seen_wrap);
        if(mode_frames[0]<5 || mode_frames[1]!=4 || swap_acks<9 || cpu_reads==0 || cpu_writes==0 ||
           video_status_reads==0 || video_size_reads==0 || !last_video_valid ||
           cpu_asset_reads==0 || hw_asset_reads==0 || asset_write_bytes!=2048 ||
           keyed_zero_beats==0 || keyed_partial_beats==0 ||
           opaque_copy_commands!=1 || keyed_copy_commands!=3 ||
           !seen_pose0 || !seen_pose38 || !seen_pose76)
            $fatal(1,"Missing CPU/HW mode, UART or double-buffer coverage");
        if(graphics.underflow||graphics.read_error) $fatal(1,"SoC scanout error");
        $display("PASS: real CPU/HW/CPU, %0d CPU frames, %0d HW frames, %0d swaps; same scene pixels; UART metrics; no front writes",
                 mode_frames[0],mode_frames[1],swap_acks);
        $display("PASS: %0d complete A frames, %0d complete B frames, no scanout mismatch",page_frames[0],page_frames[1]);
        $display("PASS: %0d DDR asset bytes preloaded and immutable across A/B clears; CPU resource bursts=%0d, HW resource bursts=%0d",
                 asset_length,cpu_asset_reads,hw_asset_reads);
        $display("PASS: Sapphire 32-to-128-bit bridge propagated %0d all-key and %0d partial key write masks",
                 keyed_zero_beats,keyed_partial_beats);
        $display("PASS: KEY1 switched both CPU and HW before/after views; poses 0/38/76/wrap; opaque copies=%0d, keyed copies=%0d",
                 opaque_copy_commands,keyed_copy_commands);
        $display("SOC TEST PASSED"); $fclose(progress_file); $finish;
    end
    initial forever begin
        #10000000;
        $fdisplay(progress_file,"time=%0t commands=%0d CPU read bytes=%0d display=%b",
            $time,commands,cpu_read_bytes,graphics.display_enable);
        $fflush(progress_file);
    end
    // The boot ROM verifies the complete 965 KiB DDR asset before drawing.
    // Sapphire's DDR simulation model makes those CPU reads much slower than
    // board time, so this guard must cover both verification and the scenes.
    initial begin #(64'd3000000000); $fatal(1,"SoC firmware timeout"); end
endmodule
