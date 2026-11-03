`timescale 1ns/1ps
module tb_sync_fifo;
    reg clk = 0;
    reg reset = 1;
    reg clear = 0;
    reg push = 0;
    reg pop = 0;
    reg [36:0] push_data = 0;
    wire [36:0] pop_data;
    wire full, empty, overflow, underflow;
    wire [4:0] level;
    integer index;

    always #5 clk = ~clk;

    sync_fifo fifo (
        .clk(clk),.reset(reset),.clear(clear),
        .push(push),.push_data(push_data),.pop(pop),.pop_data(pop_data),
        .full(full),.empty(empty),.level(level),
        .overflow(overflow),.underflow(underflow)
    );

    task push_word(input [36:0] value);
        begin
            @(negedge clk); push_data = value; push = 1;
            @(negedge clk); push = 0;
        end
    endtask

    task pop_word(input [36:0] expected);
        begin
            if (empty || pop_data !== expected)
                $fatal(1,"FIFO order mismatch expected=%h actual=%h",expected,pop_data);
            @(negedge clk); pop = 1;
            @(negedge clk); pop = 0;
        end
    endtask

    initial begin
        repeat (3) @(posedge clk);
        reset = 0;
        @(posedge clk);
        if (!empty || full || level != 0) $fatal(1,"FIFO reset state is invalid");

        // Normal ordered operation.
        push_word(37'h1_12345678);
        push_word(37'h2_89abcdef);
        if (level != 2) $fatal(1,"FIFO level did not count pushes");
        pop_word(37'h1_12345678);
        pop_word(37'h2_89abcdef);
        if (!empty || level != 0) $fatal(1,"FIFO did not return to empty");

        // Empty read is rejected and reported without corrupting the count.
        @(negedge clk); pop = 1;
        @(negedge clk); pop = 0;
        if (!underflow || !empty || level != 0) $fatal(1,"FIFO underflow handling failed");
        @(posedge clk);

        // Boundary: exactly one complete 16-beat AXI burst.
        for (index=0; index<16; index=index+1)
            push_word({5'h0,index[31:0]});
        if (!full || empty || level != 16) $fatal(1,"FIFO full boundary failed");

        // Full write is rejected and reported.
        @(negedge clk); push_data = 37'h1_ffffffff; push = 1;
        @(negedge clk); push = 0;
        if (!overflow || !full || level != 16) $fatal(1,"FIFO overflow handling failed");
        @(posedge clk);

        for (index=0; index<16; index=index+1)
            pop_word({5'h0,index[31:0]});
        if (!empty || level != 0) $fatal(1,"FIFO boundary drain failed");

        // A simultaneous pop and push preserves the level and ordering.
        push_word(37'h3_11111111);
        @(negedge clk);
        if (pop_data !== 37'h3_11111111) $fatal(1,"FIFO simultaneous test head mismatch");
        push_data = 37'h4_22222222; push = 1; pop = 1;
        @(negedge clk); push = 0; pop = 0;
        if (level != 1 || pop_data !== 37'h4_22222222)
            $fatal(1,"FIFO simultaneous push/pop failed");
        pop_word(37'h4_22222222);

        // Clear discards queued entries and restores the empty state.
        push_word(37'h5_33333333);
        @(negedge clk); clear = 1;
        @(negedge clk); clear = 0;
        if (!empty || level != 0 || overflow || underflow)
            $fatal(1,"FIFO clear failed");

        $display("ALL FIFO TESTS PASSED");
        $finish;
    end
endmodule
