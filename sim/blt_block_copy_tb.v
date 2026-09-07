`timescale 1ns/1ps

module blt_block_copy_tb;

    reg         clk;
    reg         rst;
    reg         start;
    wire        cmd_ready;
    reg  [31:0] src_base_addr;
    reg  [31:0] dst_base_addr;
    reg  [31:0] src_stride_bytes;
    reg  [31:0] dst_stride_bytes;
    reg  [15:0] width_px;
    reg  [15:0] height_px;

    wire        busy;
    wire        done;
    wire        invalid_cmd;
    wire        rd_valid;
    reg         rd_ready;
    wire [31:0] rd_addr;
    reg         rd_data_valid;
    wire        rd_data_ready;
    reg  [31:0] rd_data;
    wire        wr_valid;
    reg         wr_ready;
    wire [31:0] wr_addr;
    wire [31:0] wr_data;
    wire        wr_last;

    reg [31:0] memory [0:1023];
    reg        read_pending;
    reg [31:0] pending_addr;
    integer    pending_delay;
    integer    reads;
    integer    writes;
    integer    errors;
    integer    i;

    reg        rd_stalled_last_cycle;
    reg [31:0] held_rd_addr;
    reg        wr_stalled_last_cycle;
    reg [31:0] held_wr_addr;
    reg [31:0] held_wr_data;
    reg        held_wr_last;

    blt_block_copy dut (
        .clk              (clk),
        .rst              (rst),
        .start            (start),
        .cmd_ready        (cmd_ready),
        .src_base_addr    (src_base_addr),
        .dst_base_addr    (dst_base_addr),
        .src_stride_bytes (src_stride_bytes),
        .dst_stride_bytes (dst_stride_bytes),
        .width_px         (width_px),
        .height_px        (height_px),
        .busy             (busy),
        .done             (done),
        .invalid_cmd      (invalid_cmd),
        .rd_valid         (rd_valid),
        .rd_ready         (rd_ready),
        .rd_addr          (rd_addr),
        .rd_data_valid    (rd_data_valid),
        .rd_data_ready    (rd_data_ready),
        .rd_data          (rd_data),
        .wr_valid         (wr_valid),
        .wr_ready         (wr_ready),
        .wr_addr          (wr_addr),
        .wr_data          (wr_data),
        .wr_last          (wr_last)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    task launch_copy;
        input [31:0] case_src_base;
        input [31:0] case_dst_base;
        input [31:0] case_src_stride;
        input [31:0] case_dst_stride;
        input [15:0] case_width;
        input [15:0] case_height;
        begin
            reads  = 0;
            writes = 0;
            @(negedge clk);
            src_base_addr    = case_src_base;
            dst_base_addr    = case_dst_base;
            src_stride_bytes = case_src_stride;
            dst_stride_bytes = case_dst_stride;
            width_px         = case_width;
            height_px        = case_height;
            start            = 1'b1;
            @(negedge clk);
            start            = 1'b0;
        end
    endtask

    task wait_for_copy;
        input integer expected_transfers;
        begin
            @(posedge done);
            #2;
            if ((reads !== expected_transfers) ||
                (writes !== expected_transfers)) begin
                $display("ERROR: expected %0d reads/writes, got %0d/%0d",
                         expected_transfers, reads, writes);
                errors = errors + 1;
            end
        end
    endtask

    task expect_word;
        input [31:0] address;
        input [31:0] expected;
        begin
            if (memory[address[11:2]] !== expected) begin
                $display("ERROR: memory[%08x] = %08x, expected %08x",
                         address, memory[address[11:2]], expected);
                errors = errors + 1;
            end
        end
    endtask

    // Ordered, single-outstanding read model with a two-cycle response delay.
    always @(posedge clk) begin
        if (rst) begin
            read_pending <= 1'b0;
            pending_addr <= 32'd0;
            pending_delay <= 0;
            rd_data_valid <= 1'b0;
            rd_data <= 32'd0;
        end else begin
            if (rd_valid && rd_ready) begin
                if (read_pending || rd_data_valid) begin
                    $display("ERROR: more than one read is outstanding");
                    errors = errors + 1;
                end
                read_pending <= 1'b1;
                pending_addr <= rd_addr;
                pending_delay <= 2;
                reads = reads + 1;
            end

            if (read_pending) begin
                if ((pending_delay == 0) && !rd_data_valid) begin
                    rd_data <= memory[pending_addr[11:2]];
                    rd_data_valid <= 1'b1;
                    read_pending <= 1'b0;
                end else begin
                    pending_delay <= pending_delay - 1;
                end
            end

            if (rd_data_valid && rd_data_ready)
                rd_data_valid <= 1'b0;

            if (wr_valid && wr_ready) begin
                memory[wr_addr[11:2]] = wr_data;
                writes = writes + 1;
            end
        end
    end

    // Stability checks for request-channel backpressure.
    always @(posedge clk) begin
        if (rst) begin
            rd_stalled_last_cycle = 1'b0;
            wr_stalled_last_cycle = 1'b0;
        end else begin
            if (rd_valid && !rd_ready) begin
                if (rd_stalled_last_cycle && (rd_addr !== held_rd_addr)) begin
                    $display("ERROR: read address changed while stalled");
                    errors = errors + 1;
                end
                held_rd_addr = rd_addr;
                rd_stalled_last_cycle = 1'b1;
            end else begin
                rd_stalled_last_cycle = 1'b0;
            end

            if (wr_valid && !wr_ready) begin
                if (wr_stalled_last_cycle &&
                    ((wr_addr !== held_wr_addr) ||
                     (wr_data !== held_wr_data) ||
                     (wr_last !== held_wr_last))) begin
                    $display("ERROR: write request changed while stalled");
                    errors = errors + 1;
                end
                held_wr_addr = wr_addr;
                held_wr_data = wr_data;
                held_wr_last = wr_last;
                wr_stalled_last_cycle = 1'b1;
            end else begin
                wr_stalled_last_cycle = 1'b0;
            end
        end
    end

    initial begin
        rst              = 1'b1;
        start            = 1'b0;
        src_base_addr    = 32'd0;
        dst_base_addr    = 32'd0;
        src_stride_bytes = 32'd0;
        dst_stride_bytes = 32'd0;
        width_px         = 16'd0;
        height_px        = 16'd0;
        rd_ready         = 1'b0;
        wr_ready         = 1'b0;
        rd_data_valid    = 1'b0;
        rd_data          = 32'd0;
        read_pending     = 1'b0;
        pending_addr     = 32'd0;
        pending_delay    = 0;
        reads            = 0;
        writes           = 0;
        errors           = 0;
        rd_stalled_last_cycle = 1'b0;
        wr_stalled_last_cycle = 1'b0;

        for (i = 0; i < 1024; i = i + 1)
            memory[i] = 32'hCAFE_0000 + i;

        repeat (3) @(posedge clk);
        @(negedge clk);
        rst      = 1'b0;
        rd_ready = 1'b1;
        wr_ready = 1'b1;

        // Test 1: normal 3x2 copy with different source/destination strides.
        memory[32'h040 >> 2] = 32'h1000_0001;
        memory[32'h044 >> 2] = 32'h1000_0002;
        memory[32'h048 >> 2] = 32'h1000_0003;
        memory[32'h060 >> 2] = 32'h1000_0004;
        memory[32'h064 >> 2] = 32'h1000_0005;
        memory[32'h068 >> 2] = 32'h1000_0006;
        launch_copy(32'h0000_0040, 32'h0000_0200,
                    32'h0000_0020, 32'h0000_0030, 16'd3, 16'd2);
        wait_for_copy(6);
        expect_word(32'h0000_0200, 32'h1000_0001);
        expect_word(32'h0000_0204, 32'h1000_0002);
        expect_word(32'h0000_0208, 32'h1000_0003);
        expect_word(32'h0000_0230, 32'h1000_0004);
        expect_word(32'h0000_0234, 32'h1000_0005);
        expect_word(32'h0000_0238, 32'h1000_0006);

        // Test 2: boundary case, exactly one pixel.
        memory[32'h100 >> 2] = 32'h1234_5678;
        launch_copy(32'h0000_0100, 32'h0000_0300,
                    32'h0000_0004, 32'h0000_0004, 16'd1, 16'd1);
        wait_for_copy(1);
        expect_word(32'h0000_0300, 32'h1234_5678);

        // Test 3: empty height completes without a read or write.
        reads  = 0;
        writes = 0;
        @(negedge clk);
        src_base_addr = 32'h0000_0100;
        dst_base_addr = 32'h0000_0300;
        width_px      = 16'd4;
        height_px     = 16'd0;
        start         = 1'b1;
        @(posedge clk);
        #2;
        start = 1'b0;
        if (!done || !invalid_cmd || busy || rd_valid || wr_valid ||
            (reads != 0) || (writes != 0)) begin
            $display("ERROR: empty command behavior is incorrect");
            errors = errors + 1;
        end

        // Test 4: stall both request and write channels.
        memory[32'h140 >> 2] = 32'hAA00_0001;
        memory[32'h144 >> 2] = 32'hAA00_0002;
        memory[32'h150 >> 2] = 32'hAA00_0003;
        memory[32'h154 >> 2] = 32'hAA00_0004;
        rd_ready = 1'b0;
        wr_ready = 1'b0;
        launch_copy(32'h0000_0140, 32'h0000_0340,
                    32'h0000_0010, 32'h0000_0020, 16'd2, 16'd2);
        repeat (3) @(negedge clk);
        rd_ready = 1'b1;
        repeat (6) @(negedge clk);
        wr_ready = 1'b1;
        @(negedge clk);
        rd_ready = 1'b0;
        repeat (2) @(negedge clk);
        rd_ready = 1'b1;
        wait_for_copy(4);
        expect_word(32'h0000_0340, 32'hAA00_0001);
        expect_word(32'h0000_0344, 32'hAA00_0002);
        expect_word(32'h0000_0360, 32'hAA00_0003);
        expect_word(32'h0000_0364, 32'hAA00_0004);

        repeat (2) @(posedge clk);
        if (errors == 0)
            $display("ALL BLOCK COPY TESTS PASSED");
        else
            $display("BLOCK COPY TESTS FAILED: %0d error(s)", errors);

        $finish;
    end

endmodule
