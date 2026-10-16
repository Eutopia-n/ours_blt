`timescale 1ns/1ps
module tb_button_input;
    reg clk=0,reset=1,ack=0;
    reg [4:0] key_n=31;
    wire [4:0] pending;
    wire [4:0] pending_once;
    wire [4:0] held;
    always #5 clk=~clk;
    button_input #(.KEY_COUNT(5),.DEBOUNCE_CYCLES(4),.REPEAT_CYCLES(24)) dut(
        .clk(clk),.reset(reset),.key_n(key_n),.ack_toggle(ack),.pending(pending),.held(held));
    button_input #(.KEY_COUNT(5),.DEBOUNCE_CYCLES(4),.REPEAT_CYCLES(24),.ENABLE_REPEAT(0)) menu_keys(
        .clk(clk),.reset(reset),.key_n(key_n),.ack_toggle(ack),.pending(pending_once),.held());
    task ticks(input integer n);
        repeat(n) begin @(posedge clk); #1; end
    endtask
    task expect_mask(input reg [4:0] mask);
        if(pending!==mask) $fatal(1,"Button mask %h != %h",pending,mask);
    endtask
    task consume;
        begin @(negedge clk); ack=~ack; ticks(1); expect_mask(0); end
    endtask
    task release_keys;
        begin @(negedge clk); key_n=31; ticks(10);
            if(held!==0) $fatal(1,"Live button held after release"); end
    endtask
    initial begin
        ticks(3); @(negedge clk); reset=0; ticks(3); expect_mask(0);
        // Short pulses and changing candidates must restart qualification.
        @(negedge clk); key_n=30; ticks(3);
        @(negedge clk); key_n=31; ticks(8); expect_mask(0);
        @(negedge clk); key_n=30; ticks(3);
        @(negedge clk); key_n=29; ticks(3); expect_mask(0);
        ticks(6); expect_mask(2); release_keys();
        ticks(60); expect_mask(2); consume(); // Retained after a short press/release.
        for(integer bitno=0;bitno<4;bitno=bitno+1) begin
            @(negedge clk); key_n=~(5'b00001<<bitno);
            ticks(10); expect_mask(5'b00001<<bitno);
            if(held!==(5'b00001<<bitno)) $fatal(1,"Live movement mask missing");
            if(pending_once!==(5'b00001<<bitno)) $fatal(1,"One-shot key missing");
            consume();
            if(held!==(5'b00001<<bitno)) $fatal(1,"Acknowledgement cleared live movement");
            ticks(24); expect_mask(4'b0001<<bitno);
            if(pending_once!==0) $fatal(1,"Menu key repeated while held");
            consume();
            release_keys(); ticks(30); expect_mask(0);
        end
        @(negedge clk); key_n=28; ticks(10); expect_mask(3); consume();
        ticks(80); expect_mask(0); // A held chord changes the load only once.
        @(negedge clk); key_n=30; ticks(40); expect_mask(0);
        release_keys();
        @(negedge clk); key_n=19; ticks(10); expect_mask(12); consume();
        ticks(80); expect_mask(0); release_keys();
        // Pending commands cannot be overwritten while the CPU is busy.
        @(negedge clk); key_n=30; ticks(10); expect_mask(1); release_keys();
        @(negedge clk); key_n=29; ticks(10); expect_mask(1); release_keys();
        consume(); ticks(30); expect_mask(0);
        @(negedge clk); key_n=21; ticks(10); expect_mask(10);
        if(held!==10) $fatal(1,"Diagonal game movement lost");
        consume(); release_keys();
        // J28 key 5 has an event for menus and an independent live held bit.
        @(negedge clk); key_n=15; ticks(10); expect_mask(16);
        if(held!==16 || pending_once!==16) $fatal(1,"J28 key 5 action state missing");
        consume(); if(held!==16) $fatal(1,"Acknowledgement cleared key 5 live state");
        release_keys(); expect_mask(0);
        @(negedge clk); reset=1; ticks(2); expect_mask(0);
        $display("ALL BUTTON TESTS PASSED: bounce, five keys, short-press retention, hold repeat, one-shot chords, pending protection, reset");
        $finish;
    end
    initial begin #100000; $fatal(1,"Button test timeout"); end
endmodule
