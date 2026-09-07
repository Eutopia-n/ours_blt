`timescale 1ns/1ps

module blt_solid_fill_tb;

    reg         clk;
    reg         rst;
    reg         start;
    wire        cmd_ready;
    reg  [31:0] base_addr;
    reg  [31:0] line_stride_bytes;
    reg  [15:0] width_px;
    reg  [15:0] height_px;
    reg  [31:0] color;

    wire        busy;
    wire        done;
    wire        invalid_cmd;
    wire        wr_valid;
    reg         wr_ready;
    wire [31:0] wr_addr;
    wire [31:0] wr_data;
    wire        wr_last;

    integer errors;
    integer writes;
    integer exp_x;
    integer exp_y;
    integer exp_width;
    integer exp_height;
    reg [31:0] exp_base;
    reg [31:0] exp_stride;
    reg [31:0] exp_color;
    reg        checking;
    reg        stalled_last_cycle;
    reg [31:0] held_addr;
    reg [31:0] held_data;
    reg        held_last;

    blt_solid_fill dut (
        .clk               (clk),
        .rst               (rst),
        .start             (start),
        .cmd_ready         (cmd_ready),
        .base_addr         (base_addr),
        .line_stride_bytes (line_stride_bytes),
        .width_px          (width_px),
        .height_px         (height_px),
        .color             (color),
        .busy              (busy),
        .done              (done),
        .invalid_cmd       (invalid_cmd),
        .wr_valid          (wr_valid),
        .wr_ready          (wr_ready),
        .wr_addr           (wr_addr),
        .wr_data           (wr_data),
        .wr_last           (wr_last)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    task begin_case;
        input [31:0] case_base;
        input [31:0] case_stride;
        input [15:0] case_width;
        input [15:0] case_height;
        input [31:0] case_color;
        begin
            exp_base   = case_base;
            exp_stride = case_stride;
            exp_width  = case_width;
            exp_height = case_height;
            exp_color  = case_color;
            exp_x      = 0;
            exp_y      = 0;
            writes     = 0;
            checking   = 1'b1;

            @(negedge clk);
            base_addr         = case_base;
            line_stride_bytes = case_stride;
            width_px          = case_width;
            height_px         = case_height;
            color             = case_color;
            start             = 1'b1;
            @(negedge clk);
            start             = 1'b0;
        end
    endtask

    task finish_case;
        input integer expected_writes;
        begin
            @(posedge done);
            #2;
            checking = 1'b0;
            if (writes !== expected_writes) begin
                $display("ERROR: expected %0d writes, got %0d", expected_writes, writes);
                errors = errors + 1;
            end
        end
    endtask

    always @(posedge clk) begin
        if (rst) begin
            stalled_last_cycle = 1'b0;
        end else begin
            if (wr_valid && !wr_ready) begin
                if (stalled_last_cycle) begin
                    if ((wr_addr !== held_addr) ||
                        (wr_data !== held_data) ||
                        (wr_last !== held_last)) begin
                        $display("ERROR: write request changed while stalled");
                        errors = errors + 1;
                    end
                end
                held_addr          = wr_addr;
                held_data          = wr_data;
                held_last          = wr_last;
                stalled_last_cycle = 1'b1;
            end else begin
                stalled_last_cycle = 1'b0;
            end

            if (checking && wr_valid && wr_ready) begin
                if (wr_addr !== (exp_base + exp_y * exp_stride + exp_x * 4)) begin
                    $display("ERROR: write %0d address %08x, expected %08x",
                             writes, wr_addr,
                             (exp_base + exp_y * exp_stride + exp_x * 4));
                    errors = errors + 1;
                end
                if (wr_data !== exp_color) begin
                    $display("ERROR: write %0d data %08x, expected %08x",
                             writes, wr_data, exp_color);
                    errors = errors + 1;
                end
                if (wr_last !== ((exp_x == exp_width - 1) &&
                                 (exp_y == exp_height - 1))) begin
                    $display("ERROR: write %0d has incorrect wr_last", writes);
                    errors = errors + 1;
                end

                writes = writes + 1;
                if (exp_x == exp_width - 1) begin
                    exp_x = 0;
                    exp_y = exp_y + 1;
                end else begin
                    exp_x = exp_x + 1;
                end
            end
        end
    end

    initial begin
        rst               = 1'b1;
        start             = 1'b0;
        base_addr         = 32'd0;
        line_stride_bytes = 32'd0;
        width_px          = 16'd0;
        height_px         = 16'd0;
        color             = 32'd0;
        wr_ready          = 1'b0;
        errors            = 0;
        writes            = 0;
        checking          = 1'b0;
        stalled_last_cycle = 1'b0;

        repeat (3) @(posedge clk);
        @(negedge clk);
        rst      = 1'b0;
        wr_ready = 1'b1;

        // Test 1: normal 3x2 rectangle with padding between rows.
        begin_case(32'h0000_0100, 32'h0000_0020, 16'd3, 16'd2,
                   32'hAABB_CCDD);
        finish_case(6);
        if (invalid_cmd) begin
            $display("ERROR: normal command marked invalid");
            errors = errors + 1;
        end

        // Test 2: boundary case, exactly one pixel.
        begin_case(32'h0000_0200, 32'h0000_0004, 16'd1, 16'd1,
                   32'h1234_5678);
        finish_case(1);

        // Test 3: empty width completes without issuing a write.
        exp_base   = 32'h0000_0300;
        exp_stride = 32'h0000_0040;
        exp_width  = 0;
        exp_height = 5;
        exp_color  = 32'hDEAD_BEEF;
        exp_x      = 0;
        exp_y      = 0;
        writes     = 0;
        checking   = 1'b1;
        @(negedge clk);
        base_addr         = exp_base;
        line_stride_bytes = exp_stride;
        width_px          = 16'd0;
        height_px         = 16'd5;
        color             = exp_color;
        start             = 1'b1;
        @(posedge clk);
        #2;
        start    = 1'b0;
        checking = 1'b0;
        if (!done || !invalid_cmd || (writes != 0) || wr_valid || busy) begin
            $display("ERROR: empty command behavior is incorrect");
            errors = errors + 1;
        end

        // Test 4: backpressure must hold the request and lose no pixels.
        wr_ready = 1'b0;
        begin_case(32'h0000_0400, 32'h0000_0010, 16'd2, 16'd2,
                   32'h55AA_00FF);
        repeat (3) @(negedge clk);
        wr_ready = 1'b1;
        repeat (1) @(negedge clk);
        wr_ready = 1'b0;
        repeat (2) @(negedge clk);
        wr_ready = 1'b1;
        finish_case(4);

        repeat (2) @(posedge clk);
        if (errors == 0)
            $display("ALL TESTS PASSED");
        else
            $display("TESTS FAILED: %0d error(s)", errors);

        $finish;
    end

endmodule
