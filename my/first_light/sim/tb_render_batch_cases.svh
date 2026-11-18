// Appended to tb_render.sv's shared randomized AXI memory model by
// tools/check_render_batch.py. Independent scalar order and full-DDR checks.
    localparam LIST=32'h012b0000;
    reg [31:0] status,native_words[0:4095];
    reg [15:0] native_pixels[0:307199],native_assets[0:2047];
    integer batch_cases=0,before_reads,before_writes;
    integer first_reads,first_writes;
    task put32(input [31:0] address,input [31:0] value);
        for(integer j=0;j<4;j=j+1)mem[address-BASE+j]=value[j*8+:8];
    endtask
    function automatic [31:0] get32(input [31:0] address);
        integer a;
        begin a=address-BASE;get32={mem[a+3],mem[a+2],mem[a+1],mem[a]};end
    endfunction
    task descriptor(input integer i,input [31:0] source,destination,
                    input integer w,h,pitch,input [15:0] color,key,
                    input integer op,alpha,flags);
        put32(LIST+i*32,source);put32(LIST+i*32+4,destination);
        put32(LIST+i*32+8,(h<<16)|w);put32(LIST+i*32+12,pitch);
        put32(LIST+i*32+16,{key,color});put32(LIST+i*32+20,op|(flags<<2)|(alpha<<8));
        put32(LIST+i*32+24,0);put32(LIST+i*32+28,0);
    endtask
    task model_command(input integer index);
        reg [31:0] source,destination,size,pitch,colors,control;
        integer s,d,w,h,op;
        begin
            source=get32(LIST+index*32);destination=get32(LIST+index*32+4);
            size=get32(LIST+index*32+8);pitch=get32(LIST+index*32+12);
            colors=get32(LIST+index*32+16);control=get32(LIST+index*32+20);
            w=size&65535;h=size>>16;op=control&3;
            if(op!=0)for(integer y=0;y<h;y=y+1)for(integer x=0;x<w;x=x+1)begin
                s=source-BASE+y*pitch+x*2;snapshot[y*w+x]={golden[s+1],golden[s]};
            end
            for(integer y=0;y<h;y=y+1)for(integer x=0;x<w;x=x+1)begin
                d=destination-BASE+y*1280+x*2;
                if(op==0){golden[d+1],golden[d]}=colors[15:0];
                else if(op==1){golden[d+1],golden[d]}=snapshot[y*w+x];
                else {golden[d+1],golden[d]}=reference_blend(snapshot[y*w+x],{golden[d+1],golden[d]},(control>>8)&255,(control>>2)&3,colors[31:16]);
            end
        end
    endtask
    task batch_run(input [31:0] address,input integer count,
                   input bit expected_error,input integer completed,input bit lock_check=0);
        integer tries;reg [31:0] value;
        begin
            write_reg(52,address);write_reg(16,count);write_reg(8,2);
            if(lock_check)begin
                read_reg(4,value);if(!(value&1))$fatal(1,"Batch did not hold BUSY");
                write_reg(52,ASSET_BASE,1);write_reg(48,3,1);write_reg(56,1,1);
                write_reg(8,1,1);write_reg(8,2,1);write_reg(64,1,1);
            end
            status=0;tries=0;
            while((status&3)!=2)begin
                read_reg(4,status);tries=tries+1;
                if(tries>2000000)$fatal(1,"Batch timeout status=%h",status);
            end
            if(((status&4)!=0)!=expected_error)$fatal(1,"Batch error mismatch %h",status);
            read_reg(120,value);if(value!=completed)$fatal(1,"Batch prefix %0d expected %0d",value,completed);
            if(writing || bvalid)$fatal(1,"Batch finished before final B response");
        end
    endtask
    task compare_memory;
        for(integer n=0;n<MEM_BYTES;n=n+1)
            if(mem[n]!==golden[n])$fatal(1,"Batch full-DDR mismatch byte=%0d actual=%h expected=%h",n,mem[n],golden[n]);
    endtask
    task checked_batch(input integer count,input bit lock_check=0);
        begin
            for(integer n=0;n<MEM_BYTES;n=n+1)golden[n]=mem[n];
            for(integer n=0;n<count;n=n+1)model_command(n);
            batch_run(LIST,count,0,count,lock_check);compare_memory();batch_cases=batch_cases+1;
        end
    endtask
    task rejected_list(input [31:0] address,input integer count);
        begin
            before_reads=read_bursts;before_writes=bursts;
            batch_run(address,count,1,0);
            if(read_bursts!=before_reads || bursts!=before_writes)$fatal(1,"Rejected list touched DDR");
            batch_cases=batch_cases+1;
        end
    endtask
    task reset_pixels;
        begin
            for(integer n=0;n<MEM_BYTES;n=n+1)mem[n]=(n*73)^(n>>8);
            for(integer n=0;n<2048;n=n+1){mem[ASSET_BASE-BASE+'h2800+n*2+1],mem[ASSET_BASE-BASE+'h2800+n*2]}=native_assets[n];
        end
    endtask
    reg scan_check=0,previous_vs=1,seen_pixels=0;
    integer scanned_frames=0;
    always @(posedge pixel_clk)begin
        #2;
        if(scan_check)begin
            if(de)begin
                seen_pixels=1;if(pixel!==16'h1082)$fatal(1,"Batch modified live HDMI page: %h",pixel);
            end
            if(previous_vs && !vs && seen_pixels)begin scanned_frames=scanned_frames+1;seen_pixels=0;end
        end
        previous_vs=vs;
    end
    initial begin
        $readmemh("software/build/render_batch/native_assets.hex",native_assets);
        $readmemh("software/build/render_batch/native_expected.hex",native_pixels);
        reset_pixels();repeat(10)@(negedge clk);reset=0;
        read_reg(124,status);if((status&7)!=7)$fatal(1,"Batch/positions/tiles capabilities missing");
        write_reg(120,1,1);write_reg(124,1,1);write_reg(8,5,1);
        before_reads=read_bursts;before_writes=bursts;
        batch_run(1,0,0,0);
        if(read_bursts!=before_reads || bursts!=before_writes)$fatal(1,"Empty batch touched DDR");
        rejected_list(LIST+4,1);rejected_list(ASSET_BASE-32,1);
        rejected_list(ASSET_BASE+ASSET_BYTES-32,2);rejected_list(LIST,65535);
        memory_ready=0;rejected_list(LIST,1);memory_ready=1;
        // A batch is selected by COMMAND=2 even if the previous op was UI.
        write_reg(48,3);
        for(integer page=0;page<2;page=page+1)begin
            draw_base=BASE+page*PAGE_BYTES;write_reg(56,page);
            descriptor(0,0,draw_base+120*1280+200,128,5,0,16'h03f0,0,0,255,0);
            descriptor(1,draw_base+120*1280+200,draw_base+121*1280+202,127,4,1280,0,0,1,255,0);
            descriptor(2,ASSET_BASE+'h2800,draw_base+123*1280+204,16,16,32,0,0,2,128,3);
            descriptor(3,ASSET_BASE+'h2800,draw_base+123*1280+206,16,16,32,0,0,2,255,2);
            descriptor(4,ASSET_BASE+'h2800,draw_base+125*1280+208,16,16,32,0,0,2,0,1);
            descriptor(5,ASSET_BASE+'h2802,draw_base+140*1280+210,15,5,32,0,0,1,255,0);
            descriptor(6,ASSET_BASE+'h2800,draw_base+479*1280+1278,1,1,32,0,0,2,64,3);
            checked_batch(7,1);
        end
        // Cached sparse tiles: empty rows, one-pixel odd spans, holes inside
        // a span, overlapping painter order, key changes and uncached fallback.
        for(integer i=0;i<512;i=i+1)mem[ASSET_BASE-BASE+'h10000+i]=0;
        put32(ASSET_BASE+'h10000,32'hf8000000); // row0, only x1
        put32(ASSET_BASE+'h10000+2*32+28,32'h000007e0); // row2, only x14
        put32(ASSET_BASE+'h10000+3*32+4,32'hf81f0000);
        put32(ASSET_BASE+'h10000+3*32+24,32'h0000001f);
        for(integer i=0;i<512;i=i+1)mem[ASSET_BASE-BASE+'h10400+i]=(i*31)^(i>>3);
        for(integer pass=0;pass<5;pass=pass+1)begin
            descriptor(0,ASSET_BASE+'h10000,draw_base+80*1280+16,16,16,32,0,0,2,pass==0?0:pass==1?1:pass==2?128:pass==3?254:255,3);
            descriptor(1,ASSET_BASE+'h10000,draw_base+81*1280+18,16,16,32,0,0,2,128,3);
            descriptor(2,ASSET_BASE+'h10000,draw_base+82*1280+20,16,16,32,0,16'hf81f,2,128,3);
            descriptor(3,ASSET_BASE+'h10000,draw_base+83*1280+22,16,16,32,0,0,2,128,1);
            descriptor(4,ASSET_BASE+'h10000,draw_base+84*1280+24,16,16,32,0,0,2,255,2);
            descriptor(5,ASSET_BASE+'h10400,draw_base+85*1280+26,16,16,32,0,0,2,128,3);
            descriptor(6,ASSET_BASE+'h10000,draw_base+86*1280+28,16,16,32,0,0,2,128,3);
            descriptor(7,ASSET_BASE+'h10002,draw_base+87*1280+30,15,16,32,0,0,2,128,3);
            checked_batch(8);
        end
        for(integer i=0;i<2048;i=i+1)mem[ASSET_BASE-BASE+'h20000+i]=0;
        descriptor(0,ASSET_BASE+'h20000,draw_base+100*1280+100,32,32,64,0,0,2,128,3);
        before_writes=bursts;checked_batch(1);
        if(bursts!=before_writes)$fatal(1,"Entirely keyed tile generated writes");
        descriptor(0,ASSET_BASE+'h20000,draw_base+100*1280+102,32,32,64,0,0,2,128,1);checked_batch(1);
        // Between lists the CPU may update a texture at the same address.
        put32(ASSET_BASE+'h20000+64,32'hf80007e0);
        descriptor(0,ASSET_BASE+'h20000,draw_base+101*1280+104,32,32,64,0,0,2,128,3);checked_batch(1);
        descriptor(0,ASSET_BASE+'h10000,draw_base+140*1280+10,16,16,32,0,0,2,128,3);
        before_reads=read_bursts;before_writes=bursts;inject_tile_error=1;
        batch_run(LIST,1,1,0);inject_tile_error=0;
        if(read_bursts!=before_reads+2 || bursts!=before_writes || reading || rvalid)$fatal(1,"Cache fill error did not drain");
        checked_batch(1); // partial cache must never become valid
        // Prefetch errors must drain while an independent write completes.
        descriptor(0,ASSET_BASE+'h3000,draw_base+160*1280+23*2,32,32,64,0,0,2,128,3);
        inject_prefetch_error=1;batch_run(LIST,1,1,0);inject_prefetch_error=0;
        if(reading || rvalid)$fatal(1,"Prefetch R error returned before draining");
        checked_batch(1);
        // A write can fail while next-row ARVALID is stalled. Keep BUSY and
        // hold that address until acceptance, then drain before reporting ERROR.
        hold_prefetch_address=1;inject_write_error=1;
        write_reg(52,LIST);write_reg(16,1);write_reg(8,2);
        wait(dut.fill.state==dut.fill.CACHE_ABORT && dut.fill.pf_state==dut.fill.PF_ADDR);
        repeat(6)begin read_reg(4,status);if((status&7)!=1)$fatal(1,"Early prefetch-abort completion %h",status);end
        hold_prefetch_address=0;status=0;while((status&3)!=2)read_reg(4,status);
        inject_write_error=0;
        if(!(status&4) || reading || rvalid || writing || bvalid)$fatal(1,"Write/prefetch abort did not drain");
        checked_batch(1);
        batch_cases=batch_cases+2;
        // Stop before a bad record; later commands must never run. The first
        // command's pixels stay committed. Exercise both frontend and engine
        // validation, including an immediate engine failure without BUSY.
        for(integer kind=0;kind<4;kind=kind+1)begin
            descriptor(0,0,draw_base+150*1280+400,8,3,0,16'hf800,0,0,255,0);
            descriptor(1,0,draw_base+155*1280+400,8,3,0,16'h07e0,0,0,255,0);
            descriptor(2,0,draw_base+160*1280+400,8,3,0,16'h001f,0,0,255,0);
            if(kind==0)put32(LIST+32+24,1);
            if(kind==1)put32(LIST+32+20,3);
            if(kind==2)put32(LIST+32+20,32'h0000ff10);
            if(kind==3)put32(LIST+32+8,0);
            for(integer n=0;n<MEM_BYTES;n=n+1)golden[n]=mem[n];model_command(0);
            before_reads=read_bursts;batch_run(LIST,3,1,1);compare_memory();
            if(read_bursts-before_reads!=2)$fatal(1,"Fetched command after failure");
            batch_cases=batch_cases+1;
        end
        descriptor(0,0,BASE,4,4,0,16'h1234,0,0,255,0);
        before_writes=bursts;batch_run(LIST,1,1,0); // active page is still B
        if(bursts!=before_writes)$fatal(1,"Cross-page destination was written");
        for(integer fault=0;fault<2;fault=fault+1)begin
            descriptor(0,0,draw_base+180*1280,8,3,0,16'hffff,0,0,255,0);
            before_reads=read_bursts;before_writes=bursts;
            inject_read_error=fault==0;inject_bad_last=fault==1;
            batch_run(LIST,1,1,0);inject_read_error=0;inject_bad_last=0;
            if(read_bursts!=before_reads+1 || bursts!=before_writes || reading || rvalid)
                $fatal(1,"Descriptor error did not drain exactly one burst");
            batch_cases=batch_cases+1;
        end
        // A failing raster write can modify its own rectangle, but must stop
        // before reading the next descriptor. Recovery uses a fresh command.
        descriptor(0,0,draw_base+190*1280,4,1,0,16'h1234,0,0,255,0);
        descriptor(1,0,draw_base+195*1280,4,1,0,16'h5678,0,0,255,0);
        before_reads=read_bursts;inject_write_error=1;batch_run(LIST,2,1,0);inject_write_error=0;
        if(read_bursts!=before_reads+1)$fatal(1,"Continued after B error");
        // Earliest legal APB read after a new legacy start: previous ERROR
        // must not leak through the one-cycle raster-parameter launch stage.
        write_reg(48,0);write_reg(12,draw_base+200*1280);write_reg(16,128);
        write_reg(20,8);write_reg(24,1280);write_reg(28,16'h19a3);
        @(negedge clk);psel=1;penable=0;pwrite=1;paddr=8;pwdata=1;
        @(negedge clk);penable=1;
        @(posedge clk);if(pslverror)$fatal(1,"Recovery start rejected");
        @(negedge clk);penable=0;pwrite=0;paddr=4;
        @(negedge clk);penable=1;
        @(posedge clk);if(prdata&4)$fatal(1,"Previous ERROR leaked into new legacy job");
        @(negedge clk);psel=0;penable=0;
        status=0;while((status&3)!=2)read_reg(4,status);
        if(status&4)$fatal(1,"Legacy recovery failed");
        fill(10,190,3,2,16'h0ff0);read_reg(120,status);if(status!=0)$fatal(1,"Legacy retained batch mode");
        // Run the actual C-generated benchmark list in two chunks (512 + 1).
        // Its final page must match the scalar C result, not just the SV model.
        reset_pixels();draw_base=BASE+PAGE_BYTES;write_reg(56,1);
        for(integer chunk=0;chunk<2;chunk=chunk+1)begin
            if(chunk==0)$readmemh("software/build/render_batch/native_list_0.hex",native_words,0,4095);
            else $readmemh("software/build/render_batch/native_list_1.hex",native_words,0,7);
            for(integer n=0;n<(chunk==0?4096:8);n=n+1)put32(LIST+n*4,native_words[n]);
            checked_batch(chunk==0?512:1,chunk==0);
        end
        for(integer n=0;n<307200;n=n+1)
            if({mem[PAGE_BYTES+n*2+1],mem[PAGE_BYTES+n*2]}!==native_pixels[n])$fatal(1,"Actual C list mismatch pixel=%0d",n);
        $display("BATCH C LIST RTL PASSED: actual driver/bench chunks 512+1, 513 Alpha/Key Sprites, exact scalar C pixels");
        // Keep the displayed page immutable while the batch shares DDR reads
        // with scanout. Frontend must not starve scanout or write its page.
        for(integer n=0;n<PAGE_BYTES;n=n+2){mem[n+1],mem[n]}=16'h1082;
        for(integer n=0;n<128;n=n+1)
            descriptor(n,ASSET_BASE+'h2800,draw_base+(160+n%12)*1280+(20+n%100)*2,16,16,32,0,0,2,128,3);
        write_reg(32,1);scan_check=1;
        while(scanned_frames<3)batch_run(LIST,128,0,128);
        read_reg(4,status);if(status&48)$fatal(1,"Batch scanout error %h",status);
        if(video_read_bursts==0 || contentions==0)$fatal(1,"No concurrent scanout contention");
        $display("BATCH RTL PASSED: %0d pixel/error/empty cases; ordered fill/copy/Alpha/Key, both pages, busy/swap lock, 4KiB-aligned fetch, RRESP/RLAST/B errors drained, C lists, %0d clean HDMI frames with randomized AXI stalls",batch_cases,scanned_frames);
        $finish;
    end
    initial begin #1000000000;$fatal(1,"Batch regression watchdog");end
endmodule
