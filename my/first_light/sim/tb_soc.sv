`timescale 1ns/1ps
module tb_soc;
    reg clk=0,pixel_clk=0,reset=1;
    reg uart_rx=1;
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
        .clk(clk),.reset(soc_reset|master_reset),.pixel_clk(pixel_clk),.memory_ready(1'b1),
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
    localparam MEM_BYTES=ASSET_BASE-BASE+ASSET_BYTES;
    reg [7:0] mem[0:MEM_BYTES-1];
    reg writing=0,reading=0;
    integer wa,ra,wl,rl,wb,rb,ws,rs;
    reg [7:0] wid,rid;
    integer commands=0,fill_commands=0,copy_commands=0;
    integer cpu_reads=0,cpu_read_bytes=0,copy_reads=0,progress_file;
    integer swap_commands=0,swap_acks=0,page_frames[0:1];
    integer reports_cpu=0,reports_hw=0,mode_frames[0:1];
    integer last_commands=0,last_fills=0,last_copies=0,last_mode=-1,scene_frame=-1;
    integer page_present[0:1],bus_cycle=0,cpu_writes=0;
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
                 (m_awaddr>=ASSET_BASE && (m_awaddr&~((1<<m_awsize)-1))+(m_awlen+1)*(1<<m_awsize)<=ASSET_BASE+2048)))
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
                else begin
                    if(graphics.src!=ASSET_BASE || graphics.src_stride!=64)
                        $fatal(1,"Demo copy did not use the independent DDR image");
                    copy_commands=copy_commands+1;
                end
            end
            if(pwrite&&paddr==16'h40) begin
                swap_commands=swap_commands+1;
                check_scene();
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
    function automatic [15:0] stripe(input integer y);
        stripe=y<10 ? 16'h07ff : y<20 ? 16'hf81f : 16'hffe0;
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
    function automatic [15:0] glyph_bits(input [7:0] character);
        begin
            case(character)
                "0":glyph_bits=16'h7b6f; "4":glyph_bits=16'h5bc9;
                "6":glyph_bits=16'h79ef; "8":glyph_bits=16'h7bef;
                "A":glyph_bits=16'h2bed; "E":glyph_bits=16'h79a7;
                "I":glyph_bits=16'h7497; "R":glyph_bits=16'h7bac;
                "S":glyph_bits=16'h79cf; "T":glyph_bits=16'h7492;
                "W":glyph_bits=16'h5bfd; "X":glyph_bits=16'h5aad;
                default:glyph_bits=0;
            endcase
        end
    endfunction
    // Independently rasterize the scene, then compare every non-HUD pixel
    // at submission. Save the entire page for subsequent scanout checks.
    task check_scene;
        integer mode,page,x,y,base,offset,res_x,res_len,char_index,row,col,dx,dy;
        reg [15:0] actual,bits;
        reg [7:0] character;
        begin
            mode=commands!=last_commands; page=graphics.swap_page;
            if(mode!=(swap_commands>=5 && swap_commands<=8))
                $fatal(1,"Unexpected renderer mode: present=%0d mode=%0d",swap_commands,mode);
            if(mode && (fill_commands-last_fills!=1 || copy_commands-last_copies!=32))
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
            if(asset_write_bytes!=2048) $fatal(1,"Image was not uploaded exactly once: %0d bytes",asset_write_bytes);
            for(integer row=0;row<32;row=row+1)
                for(integer col=0;col<32;col=col+1) begin
                    offset=ASSET_BASE-BASE+row*64+col*2;
                    if({mem[offset+1],mem[offset]}!==stripe(row))
                        $fatal(1,"DDR resource changed or upload was not drained");
                end
            for(integer n=0;n<32;n=n+1) begin
                x=48+bounce(n*74+scene_frame*4,552);
                y=112+bounce(n*46+scene_frame*2,320);
                for(integer row=0;row<32;row=row+1)
                    for(integer col=0;col<32;col=col+1) golden[(y+row)*640+x+col]=stripe(row);
            end
            if(last_video_valid && last_video_size!=={16'd480,16'd640})
                $fatal(1,"Firmware read invalid measured size %h",last_video_size);
            res_x=last_video_valid ? 496 : 532;
            res_len=last_video_valid ? 11 : 8;
            for(char_index=0;char_index<res_len;char_index=char_index+1) begin
                character=resolution_char(char_index,last_video_valid);
                bits=glyph_bits(character);
                for(row=0;row<5;row=row+1) for(col=0;col<3;col=col+1)
                    if(bits&(1<<(14-row*3-col)))
                        for(dy=0;dy<3;dy=dy+1) for(dx=0;dx<3;dx=dx+1)
                            golden[(56+row*3+dy)*640+res_x+char_index*12+col*3+dx]=16'hffff;
            end
            base=page*PAGE_BYTES;
            for(integer n=0;n<307200;n=n+1) begin
                actual={mem[base+n*2+1],mem[base+n*2]};
                if(n>=640*64 && actual!==golden[n])
                    $fatal(1,"Mode %0d frame %0d pixel (%0d,%0d): %h != %h",mode,scene_frame,n%640,n/640,actual,golden[n]);
                snapshot[page*307200+n]=actual;
            end
            // Rows 56..63 are above the old comparison boundary: verify the
            // complete RES WAIT / measured RES 640X480 label explicitly.
            for(y=56;y<64;y=y+1) for(x=res_x;x<628;x=x+1) begin
                actual={mem[base+(y*640+x)*2+1],mem[base+(y*640+x)*2]};
                if(actual!==golden[y*640+x])
                    $fatal(1,"Resolution HUD pixel (%0d,%0d): %h != %h",x,y,actual,golden[y*640+x]);
            end
            // The top-left pixel of C/H must identify the active column.
            offset=base+8*1280+12*2;
            if({mem[offset+1],mem[offset]}!==(mode ? 16'h8410 : 16'hffff))
                $fatal(1,"CPU HUD active color mismatch");
            offset=base+8*1280+332*2;
            if({mem[offset+1],mem[offset]}!==(mode ? 16'hffff : 16'h8410))
                $fatal(1,"HW HUD active color mismatch");
            page_present[page]=swap_commands;
            $fdisplay(progress_file,"PASS scene: present=%0d mode=%0d frame=%0d page=%0d time=%0t",
                      swap_commands,mode,scene_frame,page,$time); $fflush(progress_file);
        end
    endtask
    task send_char(input reg [7:0] value);
        begin
            uart_rx=0; #8680;
            for(integer bitno=0;bitno<8;bitno=bitno+1) begin uart_rx=value[bitno]; #8680; end
            uart_rx=1; #8680;
        end
    endtask
    initial begin
        // Send before acknowledgement so production firmware sees the
        // character on its next loop; no fake timers or test-only firmware.
        wait(mode_frames[0]==4); send_char("h");
        wait(mode_frames[1]==4); send_char("c");
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
            end
            prev_page=graphics.display_page_active; prev_ack=graphics.swap_ack_pixel;
            if(de) begin
                if(px==0 && py==0) begin
                    scan_page=graphics.display_page_active;
                    scan_present=page_present[scan_page];
                    if(scan_present==1 || scan_present==5 || scan_present==9) begin
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
        progress_file=$fopen("reports/soc_progress.log","w");
        if(progress_file==0) $fatal(1,"Cannot create SoC progress log");
        for(integer n=0;n<MEM_BYTES;n=n+1) mem[n]=8'ha5;
        repeat(50) @(negedge clk); reset=0;
        wait(return_frames>=1 && reports_cpu>=1 && reports_hw>=1);
        if(mode_frames[0]<5 || mode_frames[1]!=4 || swap_acks<9 || cpu_reads==0 || cpu_writes==0 ||
           video_status_reads==0 || video_size_reads==0 || !last_video_valid ||
           cpu_asset_reads==0 || hw_asset_reads==0 || asset_write_bytes!=2048)
            $fatal(1,"Missing CPU/HW mode, UART or double-buffer coverage");
        if(graphics.underflow||graphics.read_error) $fatal(1,"SoC scanout error");
        $display("PASS: real CPU/HW/CPU, %0d CPU frames, %0d HW frames, %0d swaps; same scene pixels; UART metrics; no front writes",
                 mode_frames[0],mode_frames[1],swap_acks);
        $display("PASS: %0d complete A frames, %0d complete B frames, no scanout mismatch",page_frames[0],page_frames[1]);
        $display("PASS: DDR image uploaded once (%0d bytes), immutable across A/B clears; CPU resource bursts=%0d, HW resource bursts=%0d",
                 asset_write_bytes,cpu_asset_reads,hw_asset_reads);
        $display("SOC TEST PASSED"); $fclose(progress_file); $finish;
    end
    initial forever begin
        #10000000;
        $fdisplay(progress_file,"time=%0t commands=%0d CPU read bytes=%0d display=%b",
            $time,commands,cpu_read_bytes,graphics.display_enable);
        $fflush(progress_file);
    end
    initial begin #1000000000; $fatal(1,"SoC firmware timeout"); end
endmodule
