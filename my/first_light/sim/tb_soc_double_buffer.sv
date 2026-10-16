`timescale 1ns/1ps
module tb_soc;
    reg clk=0,pixel_clk=0,reset=1;
    reg uart_rx=1;
    wire [3:0] button_pending=0,button_ack;
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
        .button_held(4'd0),
        .paddr(paddr),.psel(psel),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),
        .prdata(prdata),.pready(pready),.pslverror(pslverror),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wlast(wlast),.wvalid(wvalid),.wready(wready),
        .bresp(bresp),.bvalid(bvalid),.bready(bready),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rresp(rresp),.rlast(rlast),.rvalid(rvalid),.rready(rready),
        .pixel(pixel),.hs(hs),.vs(vs),.de(de)
    );
    localparam BASE=32'h01000000, PAGE_BYTES=614400, MEM_BYTES=1228800;
    reg [7:0] mem[0:MEM_BYTES-1];
    reg writing=0,reading=0;
    integer wa,ra,wl,rl,wb,rb,ws,rs;
    reg [7:0] wid,rid;
    integer commands=0,fill_commands=0,copy_commands=0;
    integer cpu_reads=0,cpu_read_bytes=0,copy_reads=0,progress_file;
    integer swap_commands=0,swap_acks=0,page_frames[0:1];
    reg pass_uart=0;
    // DDR is modeled at the controller's 128-bit AXI port. Real Sapphire
    // arbitration, cache and 32-to-128-bit conversion are all in simulation.
    always @(negedge clk) begin
        m_awready=!writing&&!m_bvalid;
        m_wready=writing;
        m_arready=!reading&&!m_rvalid;
        if(reading&&!m_rvalid) begin
            for(integer b=0;b<16;b=b+1) m_rdata[b*8+:8]=mem[(ra&~15)+b];
            m_rid=rid; m_rresp=0; m_rlast=rb==rl; m_rvalid=1;
        end
    end
    always @(posedge clk) if(!reset) begin
        if(m_awvalid&&m_awready) begin
            if(m_awaddr<BASE || m_awaddr+(m_awlen+1)*(1<<m_awsize)>BASE+MEM_BYTES)
                $fatal(1,"SoC write outside framebuffer: %h",m_awaddr);
            if(m_awburst!=1 || m_awsize>4) $fatal(1,"Unsupported AW burst");
            wa=m_awaddr-BASE; wl=m_awlen; wb=0; ws=1<<m_awsize;
            wid=m_awid; writing=1;
        end
        if(m_wvalid&&m_wready) begin
            if(m_wlast!=(wb==wl)) $fatal(1,"SoC WLAST mismatch");
            for(integer b=0;b<16;b=b+1)
                if(m_wstrb[b]) mem[(wa&~15)+b]=m_wdata[8*b+:8];
            wa=wa+ws; wb=wb+1;
            if(m_wlast) begin writing=0; m_bvalid<=1; m_bid<=wid; m_bresp<=0; end
        end
        if(m_bvalid&&m_bready) m_bvalid<=0;
        if(m_arvalid&&m_arready) begin
            if(m_araddr<BASE || m_araddr+(m_arlen+1)*(1<<m_arsize)>BASE+MEM_BYTES)
                $fatal(1,"SoC read outside framebuffer: %h",m_araddr);
            if(m_arburst!=1 || m_arsize>4) $fatal(1,"Unsupported AR burst");
            ra=m_araddr-BASE; rl=m_arlen; rb=0; rs=1<<m_arsize;
            rid=m_arid; reading=1;
            // Sapphire appends the selected master as ID bit 7: CPU=0,
            // external graphics=1. Count CPU verification independently.
            if(!m_arid[7]) begin
                cpu_reads=cpu_reads+1;
                cpu_read_bytes=cpu_read_bytes+((m_arlen+1)<<m_arsize);
            end else if(!graphics.display_enable) copy_reads=copy_reads+1;
        end
        if(m_rvalid&&m_rready) begin
            ra=ra+rs; rb=rb+1; m_rvalid<=0;
            if(m_rlast) reading=0;
        end
        if(psel&&penable&&pready) begin
            if(pslverror) $fatal(1,"Firmware APB error at %h",paddr);
            if(pwrite&&paddr==16'h8) begin
                commands=commands+1;
                if(graphics.operation==0) fill_commands=fill_commands+1;
                else copy_commands=copy_commands+1;
                $display("CPU command %0d operation=%0d at %0t",commands,graphics.operation,$time);
            end
            if(pwrite&&paddr==16'h40) swap_commands=swap_commands+1;
        end
        if(graphics.display_enable && m_awvalid && m_awready &&
           ((m_awaddr>=BASE+PAGE_BYTES)==graphics.display_page_sync[1]))
            $fatal(1,"Firmware rendered to the front page");
    end
    // Decode the real UART pin using the firmware's 100 MHz / 115200 divider.
    reg [7:0] uart_char;
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
            if(uart_line.substr(0,17)=="PASS DOUBLE BUFFER") pass_uart=1;
            uart_line="";
        end
    end
    function automatic [15:0] expected(input integer x,y,page);
        integer local_y;
        if((x>=31&&x<160&&y>=301&&y<398) || (x>=211&&x<340&&y>=321&&y<418)) begin
            local_y=x<160 ? y-301 : y-321;
            expected=local_y<32 ? 16'h07ff : local_y<64 ? 16'hf81f : 16'hffe0;
        end
        else if(x>=64&&x<256&&y>=60&&y<180) expected=16'hf800;
        else if(x>=301&&x<428&&y>=161&&y<260) expected=16'h07e0;
        else if(x>=501&&x<602&&y>=351&&y<424) expected=16'h001f;
        else expected=page ? 16'h18c3 : 16'h1082;
    endfunction
    integer px=0,py=0;
    reg prev_de=0,scan_page=0,prev_page=0,prev_ack=0,safe_boundary;
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
                if(px==0 && py==0) scan_page=graphics.display_page_active;
                if(scan_page!=graphics.display_page_active || pixel!==expected(px,py,scan_page))
                    $fatal(1,"SoC scanout page %0d pixel (%0d,%0d) mismatch",scan_page,px,py);
                px=px+1;
            end
            if(prev_de && !de) begin
                if(px!=640) $fatal(1,"SoC invalid line length %0d",px);
                px=0; py=py+1;
                if(py==480) begin page_frames[scan_page]=page_frames[scan_page]+1; py=0; end
            end
            prev_de=de;
        end
    end
    initial begin
        page_frames[0]=0; page_frames[1]=0;
        progress_file=$fopen("reports/soc_progress.log","w");
        if(progress_file==0) $fatal(1,"Cannot create SoC progress log");
        for(integer n=0;n<MEM_BYTES;n=n+1) mem[n]=8'ha5;
        repeat(50) @(negedge clk); reset=0;
        wait(graphics.display_enable===1'b1);
        wait(graphics.display_page_active===1'b1);
        if(commands!=16 || fill_commands!=14 || copy_commands!=2 || copy_reads==0 || cpu_read_bytes!=2*PAGE_BYTES)
            $fatal(1,"Missing double-buffer commands or CPU readback: fills=%0d copies=%0d bytes=%0d",fill_commands,copy_commands,cpu_read_bytes);
        for(integer page=0;page<2;page=page+1)
            for(integer n=0;n<307200;n=n+1)
                if({mem[page*PAGE_BYTES+n*2+1],mem[page*PAGE_BYTES+n*2]}!==expected(n%640,n/640,page))
                    $fatal(1,"SoC page %0d pixel mismatch at %0d",page,n);
        $display("\nPASS: real RISC-V double buffer: 14 fills, 2 copies, page swap at frame boundary; CPU verified %0d bytes (%0d bursts)",cpu_read_bytes,cpu_reads);
        wait(page_frames[1]>=2 && pass_uart);
        if(page_frames[0]==0 || swap_commands!=2 || swap_acks!=2)
            $fatal(1,"Missing page or acknowledgement coverage");
        if(graphics.underflow||graphics.read_error) $fatal(1,"SoC scanout error");
        $display("PASS: %0d complete A frames, %0d complete B frames, 2 acknowledged presents, UART PASS, no front-page writes",page_frames[0],page_frames[1]);
        $display("SOC TEST PASSED"); $fclose(progress_file); $finish;
    end
    initial forever begin
        #10000000;
        $fdisplay(progress_file,"time=%0t commands=%0d CPU read bytes=%0d display=%b",
            $time,commands,cpu_read_bytes,graphics.display_enable);
        $fflush(progress_file);
    end
    initial begin #500000000; $fatal(1,"SoC firmware timeout"); end
endmodule
