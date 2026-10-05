`timescale 1ns/1ps
module tb_video_clock_startup;
    reg clk=0, reset=1, mode_active=0, pll_locked=0;
    always #5 clk=~clk;
    wire [1:0] clock_select;
    wire pll_reset_n,clock_hold,clock_ready;
    wire [7:0] debug_status;
    video_clock_control #(.RESET_CYCLES(8),.LOCK_CYCLES(5),
        .LOCK_TIMEOUT_CYCLES(64),.DEFAULT_MODE(1),.FIXED_MODE(1)) dut(.*);

    integer releases=0, phase=0;
    reg previous_reset_n=0, permit_lock=0;
    // Emulate a PLL that cannot lock on the first release. A later reset
    // pulse must recover it without any software write or pixel-domain mode.
    always @(negedge clk) begin
        if(reset) begin
            releases=0; phase=0; previous_reset_n=0; pll_locked=0;
        end else begin
            if(pll_reset_n && !previous_reset_n) releases=releases+1;
            previous_reset_n=pll_reset_n;
            if(!pll_reset_n) begin phase=0; pll_locked=0; end
            else begin
                phase=phase+1;
                pll_locked=permit_lock && releases>=2 && phase>=10;
            end
        end
    end
    always @(posedge clk) if(!reset) begin
        if(clock_select!=1) $fatal(1,"Fixed PLL selected wrong mode before pixel startup");
        if(clock_ready && (!pll_reset_n || clock_hold || !dut.locked_sync[1]))
            $fatal(1,"Clock ready before qualified lock");
    end
    task await_ready;
        integer timeout;
        begin
            timeout=0;
            while(!clock_ready && timeout<500) begin @(negedge clk); timeout=timeout+1; end
            if(!clock_ready) $fatal(1,"PLL restart timeout debug=%h",debug_status);
        end
    endtask
    initial begin
        repeat(4) @(negedge clk); #1; reset=0; permit_lock=1;
        await_ready();
        if(releases<2 || debug_status[7:4]==0)
            $fatal(1,"Initial lock timeout never retried");
        // Pixel mode can be unknown or lag during reset; fixed clocks ignore it.
        mode_active=1'bx; repeat(20) @(negedge clk);
        if(!clock_ready || clock_select!=1) $fatal(1,"Pixel mode disturbed fixed clock");
        mode_active=1;
        permit_lock=0; repeat(8) @(negedge clk);
        if(!clock_hold || clock_ready) $fatal(1,"Lock loss did not hold video");
        permit_lock=1; await_ready();
        $display("CLOCK STARTUP PASSED: absent pixel mode, failed initial lock, retry, loss/relock");
        $finish;
    end
    initial begin #20000; $fatal(1,"Clock test timeout"); end
endmodule
