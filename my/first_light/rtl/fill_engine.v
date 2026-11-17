// RGB565 fill, block copy and DDR Sprite composition (Alpha + Color Key).
// One outstanding AXI read or write burst, at most 16 beats.
// Byte strobes preserve neighbouring pixels for odd X / odd rectangle widths.
`default_nettype none
module fill_engine #(
    parameter [31:0] FB_BASE = 32'h01000000,
    parameter [31:0] FB_BYTES = 32'd614400,
    parameter [31:0] ASSET_BASE = 32'h01200000,
    parameter [31:0] ASSET_BYTES = 32'h00100000
) (
    input wire clk, input wire reset,
    input wire start, input wire memory_ready,
    input wire [1:0] operation, input wire [31:0] src,
    input wire [31:0] frame_base,
    input wire [31:0] dst, input wire [15:0] width, height,
    input wire [31:0] stride, src_stride, input wire [15:0] color,
    input wire [1:0] blend_ctrl, input wire [7:0] blend_alpha,
    input wire [15:0] color_key,
    output wire busy, output reg done, output reg error,
    output reg [31:0] cycles,
    output reg [31:0] burst_reads, output reg [31:0] burst_writes,
    output reg [31:0] ddr_read_wait_cycles, output reg [31:0] ddr_write_wait_cycles,
    output reg [31:0] awaddr, output wire [7:0] awlen,
    output wire awvalid, input wire awready,
    output wire [31:0] wdata, output wire [3:0] wstrb,
    output wire wlast, output wire wvalid, input wire wready,
    input wire [1:0] bresp, input wire bvalid, output wire bready,
    output reg [31:0] araddr, output wire [7:0] arlen,
    output wire arvalid, input wire arready,
    input wire [31:0] rdata, input wire [1:0] rresp,
    input wire rlast, input wire rvalid, output wire rready
);
    localparam IDLE=0, F_PREP=1, F_FIFO=2, F_ADDR=3, F_DATA=4, F_RESP=5,
               C_RPREP=6, C_RADDR=7, C_RDATA=8,
               C_WPREP=9, C_WPRIME=10, C_WFIFO=11,
               C_WADDR=12, C_WDATA=13, C_WRESP=14,
               B_RPREP=15, B_RADDR=16, B_RDATA=17;
    reg [4:0] state;
    reg copy_mode, blend_mode;
    reg [31:0] source_row_addr;
    reg [31:0] source_row_step;
    reg [9:0] copy_width;
    reg [31:0] row_step;
    reg [31:0] row_addr;
    reg [15:0] rows_left;
    reg [15:0] fill_color;
    reg [9:0] words_left, row_words, word_index;
    reg [4:0] burst_words, beat;
    reg first_high, last_low;
    reg [9:0] copy_read_words_left, copy_read_row_words, copy_read_word_index;
    reg [4:0] copy_read_burst_words, copy_read_beat;
    reg [9:0] copy_write_words_left, copy_write_row_words, copy_write_word_index;
    reg [4:0] copy_write_burst_words, copy_write_beat;
    reg [4:0] fifo_load_count;
    reg [9:0] fifo_base_word_index;
    reg [9:0] copy_prefetch_index;
    reg copy_src_half, copy_dst_half;
    // Raw source words are stored before any destination writes. Two banks
    // allow synchronous block RAM inference and halfword realignment.
    reg [15:0] copy_buf_lo [0:511];
    reg [15:0] copy_buf_hi [0:511];
    reg [15:0] copy_qlo, copy_qhi;
    reg [15:0] bg_buf_lo [0:511];
    reg [15:0] bg_buf_hi [0:511];
    reg [15:0] bg_qlo, bg_qhi;
    reg [9:0] bg_read_words_left, bg_read_row_words, bg_read_word_index;
    reg [4:0] bg_read_burst_words, bg_read_beat;
    wire [8:0] copy_lo_index = copy_prefetch_index[8:0] +
        ((copy_src_half && !copy_dst_half) ? 9'd1 : 9'd0);
    wire [8:0] copy_hi_index = copy_prefetch_index[8:0] -
        ((!copy_src_half && copy_dst_half) ? 9'd1 : 9'd0);
    wire [31:0] copy_data = copy_src_half == copy_dst_half ?
        {copy_qhi,copy_qlo} : {copy_qlo,copy_qhi};
    wire [31:0] bg_data = {bg_qhi,bg_qlo};
    // Each component is at most 63. The weighted sum plus rounding fits
    // in 14 bits. For this range, floor(t/255) == (t+1+(t>>8))>>8.
    // Keep multipliers narrow and avoid a general-purpose divider.
    function [5:0] blend_channel;
        input [5:0] fg_component, bg_component;
        input [7:0] alpha_value;
        reg [7:0] inverse_alpha;
        reg [13:0] weighted;
        reg [14:0] normalized;
        begin
            inverse_alpha = 8'd255-alpha_value;
            weighted = fg_component*alpha_value + bg_component*inverse_alpha + 14'd127;
            normalized = {1'b0,weighted} + 15'd1 + {9'd0,weighted[13:8]};
            blend_channel = normalized[13:8];
        end
    endfunction
    function [15:0] blend_pixel;
        input [15:0] fg_pixel;
        input [15:0] bg_pixel;
        input [7:0] alpha_value;
        input [1:0] ctrl_value;
        input [15:0] key_value;
        reg [5:0] out_r, out_g, out_b;
        begin
            if (ctrl_value[1] && fg_pixel == key_value) begin
                blend_pixel = bg_pixel;
            end else if (!ctrl_value[0]) begin
                blend_pixel = fg_pixel;
            end else if (alpha_value == 8'hff) begin
                // Opaque foreground pixels do not depend on the background.
                blend_pixel = fg_pixel;
            end else if (alpha_value == 8'h00) begin
                blend_pixel = bg_pixel;
            end else begin
                out_r = blend_channel({1'b0,fg_pixel[15:11]},{1'b0,bg_pixel[15:11]},alpha_value);
                out_g = blend_channel(fg_pixel[10:5],bg_pixel[10:5],alpha_value);
                out_b = blend_channel({1'b0,fg_pixel[4:0]},{1'b0,bg_pixel[4:0]},alpha_value);
                blend_pixel = {out_r[4:0],out_g[5:0],out_b[4:0]};
            end
        end
    endfunction
    wire [31:0] blend_data = {
        blend_pixel(copy_data[31:16],bg_data[31:16],blend_alpha,blend_ctrl,color_key),
        blend_pixel(copy_data[15:0],bg_data[15:0],blend_alpha,blend_ctrl,color_key)
    };
    wire copy_read_beat_error = rresp != 0 || rlast != (copy_read_beat == copy_read_burst_words-1);
    wire bg_read_beat_error = rresp != 0 || rlast != (bg_read_beat == bg_read_burst_words-1);
    wire [32:0] row_offset = (({17'd0,height}-33'd1) << 10) +
                            (({17'd0,height}-33'd1) << 8);
    // Limit source pitch to 16 bits before multiplying. Check the full APB
    // value too, so a large/overflowing stride cannot wrap into a valid range.
    // Keep the subtraction explicitly 16 bits too. A 32-bit expression here
    // inferred a cascaded multiplier on the command validation critical path.
    wire [15:0] source_rows = height - 16'd1;
    wire [31:0] source_offset = source_rows * src_stride[15:0];
    wire [32:0] source_end = {1'b0,src} + {1'b0,source_offset} + ({17'd0,width} << 1);
    wire source_in_frame = src >= frame_base &&
        source_end <= {1'b0,frame_base}+{1'b0,FB_BYTES} && src_stride == 1280;
    wire source_in_assets = src >= ASSET_BASE &&
        source_end <= {1'b0,ASSET_BASE}+{1'b0,ASSET_BYTES};
    wire reverse_copy = source_in_frame && dst > src;
    wire [31:0] next_source_row = source_row_addr + source_row_step;
    wire [9:0] next_read_words =
        ({1'b0,copy_width} + {10'd0,next_source_row[1]} + 11'd1) >> 1;
    wire [32:0] end_address = {1'b0,dst} +
        (({17'd0,height}-33'd1) << 10) +
        (({17'd0,height}-33'd1) << 8) + ({17'd0,width} << 1);
    wire [10:0] words_to_4k = 11'd1024 - {1'b0,awaddr[11:2]};
    wire [9:0] proposed_words = words_left > 16 ? 10'd16 : words_left;
    wire [10:0] read_words_to_4k = 11'd1024 - {1'b0,araddr[11:2]};
    wire [9:0] copy_read_proposed = copy_read_words_left > 16 ? 10'd16 : copy_read_words_left;
    wire [9:0] bg_read_proposed = bg_read_words_left > 16 ? 10'd16 : bg_read_words_left;
    wire [10:0] write_words_to_4k = 11'd1024 - {1'b0,awaddr[11:2]};
    wire [9:0] copy_write_proposed = copy_write_words_left > 16 ? 10'd16 : copy_write_words_left;
    // The FIFO can hold one complete AXI write burst. Its first entries are
    // cached before AWVALID and the rest are prefetched while W data drains,
    // keeping WVALID continuous when WREADY is asserted.
    wire [36:0] fifo_input;
    wire [36:0] fifo_output;
    wire [4:0] fifo_level;
    wire fifo_full, fifo_empty, fifo_overflow, fifo_underflow;
    wire fifo_clear = state == IDLE;
    wire fifo_loading =
        (!copy_mode && (state == F_FIFO || state == F_ADDR || state == F_DATA) &&
         fifo_load_count < burst_words) ||
        (copy_mode && (state == C_WFIFO || state == C_WADDR || state == C_WDATA) &&
         fifo_load_count < copy_write_burst_words);
    wire fifo_push = fifo_loading && !fifo_full;
    wire fifo_pop = (state == F_DATA || state == C_WDATA) && !fifo_empty && wready;
    wire [9:0] fifo_word_index = fifo_base_word_index + {5'd0,fifo_load_count};
    wire [9:0] fifo_row_words = copy_mode ? copy_write_row_words : row_words;
    wire [4:0] fifo_burst_words = copy_mode ? copy_write_burst_words : burst_words;
    wire [3:0] fifo_entry_strb =
        ((fifo_word_index == 0 && first_high) ? 4'b1100 : 4'b1111) &
        ((fifo_word_index == fifo_row_words-10'd1 && last_low) ? 4'b0011 : 4'b1111) &
        ((blend_mode && blend_ctrl[1] && copy_data[15:0] == color_key) ? 4'b1100 : 4'b1111) &
        ((blend_mode && blend_ctrl[1] && copy_data[31:16] == color_key) ? 4'b0011 : 4'b1111);
    // A masked neighbour may be outside the loaded row. Zero inactive lanes
    // before caching the word so simulation never exposes uninitialised data.
    wire [31:0] fifo_entry_mask =
        {{16{fifo_entry_strb[2]}},{16{fifo_entry_strb[0]}}};
    wire [31:0] fifo_entry_data = copy_mode ?
        ((blend_mode ? blend_data : copy_data) & fifo_entry_mask) : {fill_color,fill_color};
    wire fifo_entry_last = fifo_load_count == fifo_burst_words-1'b1;
    assign fifo_input = {fifo_entry_last,fifo_entry_strb,fifo_entry_data};

    sync_fifo write_fifo (
        .clk(clk),.reset(reset),.clear(fifo_clear),
        .push(fifo_push),.push_data(fifo_input),
        .pop(fifo_pop),.pop_data(fifo_output),
        .full(fifo_full),.empty(fifo_empty),.level(fifo_level),
        .overflow(fifo_overflow),.underflow(fifo_underflow)
    );

    assign busy = state != IDLE;
    assign awlen = {3'd0,(copy_mode ? copy_write_burst_words : burst_words)} - 8'd1;
    assign awvalid = state == F_ADDR || state == C_WADDR;
    assign wvalid = (state == F_DATA || state == C_WDATA) && !fifo_empty;
    assign arlen = {3'd0,(state == B_RADDR ? bg_read_burst_words : copy_read_burst_words)} - 8'd1;
    assign arvalid = state == C_RADDR || state == B_RADDR;
    assign rready = state == C_RDATA || state == B_RDATA;
    assign wdata = fifo_output[31:0];
    assign wstrb = fifo_output[35:32];
    assign wlast = fifo_output[36];
    assign bready = state == F_RESP || state == C_WRESP;

    always @(posedge clk) begin
        copy_qlo <= copy_buf_lo[copy_lo_index];
        copy_qhi <= copy_buf_hi[copy_hi_index];
        bg_qlo <= bg_buf_lo[copy_prefetch_index[8:0]];
        bg_qhi <= bg_buf_hi[copy_prefetch_index[8:0]];
        if (rvalid && rready) begin
            if (state == B_RDATA) begin
                bg_buf_lo[bg_read_word_index[8:0]] <= rdata[15:0];
                bg_buf_hi[bg_read_word_index[8:0]] <= rdata[31:16];
            end else begin
                copy_buf_lo[copy_read_word_index[8:0]] <= rdata[15:0];
                copy_buf_hi[copy_read_word_index[8:0]] <= rdata[31:16];
            end
        end
    end
    always @(posedge clk) begin
        if (reset) begin
            state <= IDLE; done <= 0; error <= 0; cycles <= 0;
            burst_reads <= 0; burst_writes <= 0;
            ddr_read_wait_cycles <= 0; ddr_write_wait_cycles <= 0;
            awaddr <= 0; araddr <= 0; row_addr <= 0; source_row_addr <= 0;
            source_row_step <= 1280; copy_width <= 0;
            rows_left <= 0; row_step <= 1280; copy_mode <= 0; blend_mode <= 0;
            fill_color <= 0; words_left <= 0; row_words <= 0;
            word_index <= 0; burst_words <= 0; beat <= 0;
            first_high <= 0; last_low <= 0;
            copy_read_words_left <= 0; copy_read_row_words <= 0;
            copy_read_word_index <= 0; copy_read_burst_words <= 0; copy_read_beat <= 0;
            copy_write_words_left <= 0; copy_write_row_words <= 0; copy_write_word_index <= 0;
            copy_write_burst_words <= 0; copy_write_beat <= 0;
            bg_read_words_left <= 0; bg_read_row_words <= 0; bg_read_word_index <= 0;
            bg_read_burst_words <= 0; bg_read_beat <= 0;
            fifo_load_count <= 0; fifo_base_word_index <= 0; copy_prefetch_index <= 0;
            copy_src_half <= 0; copy_dst_half <= 0;
        end else begin
            if (busy) cycles <= cycles + 1'b1;
            if (arvalid && arready) burst_reads <= burst_reads + 1'b1;
            if (awvalid && awready) burst_writes <= burst_writes + 1'b1;
            // Count only cycles where a valid AXI phase is waiting for the
            // memory/interconnect response, not internal raster work.
            if (((state == C_RADDR || state == B_RADDR) && !arready) ||
                ((state == C_RDATA || state == B_RDATA) && !rvalid))
                ddr_read_wait_cycles <= ddr_read_wait_cycles + 1'b1;
            if (((state == F_ADDR || state == C_WADDR) && !awready) ||
                ((state == F_DATA || state == C_WDATA) && wvalid && !wready) ||
                ((state == F_RESP || state == C_WRESP) && !bvalid))
                ddr_write_wait_cycles <= ddr_write_wait_cycles + 1'b1;
            case (state)
            IDLE: if (start) begin
                done <= 0; error <= 0; cycles <= 0;
                if (!memory_ready || (operation > 2) || dst[0] || width == 0 || height == 0 ||
                    width > 640 || height > 480 || stride != 1280 ||
                    dst < frame_base || end_address > {1'b0,frame_base}+{1'b0,FB_BYTES} ||
                    (operation != 0 && (src[0] || src_stride[0] ||
                     src_stride > 65534 || src_stride < ({16'd0,width} << 1) ||
                     !(source_in_frame || source_in_assets))) ||
                    (operation == 2 && !source_in_assets)) begin
                    error <= 1; done <= 1;
                end else begin
                    copy_mode <= operation != 0;
                    blend_mode <= operation == 2;
                    row_addr <= dst; awaddr <= {dst[31:2],2'b00};
                    rows_left <= height; fill_color <= color;
                    first_high <= dst[1]; last_low <= dst[1] ^ width[0];
                    if (operation == 0) begin
                        row_words <= ({1'b0,width[9:0]} + {10'd0,dst[1]} + 11'd1) >> 1;
                        words_left <= ({1'b0,width[9:0]} + {10'd0,dst[1]} + 11'd1) >> 1;
                        word_index <= 0; state <= F_PREP;
                    end else begin
                        // Same-page copies retain equal strides and bottom-up
                        // traversal when dst follows src, preserving overlap.
                        // Assets never overlap the destination and read top-down.
                        row_step <= reverse_copy ? -32'd1280 : 32'd1280;
                        source_row_step <= reverse_copy ? -src_stride : src_stride;
                        copy_width <= width[9:0];
                        row_addr <= dst + (reverse_copy ? row_offset[31:0] : 32'd0);
                        source_row_addr <= src + (reverse_copy ? source_offset : 32'd0);
                        awaddr <= {dst[31:2],2'b00} + (reverse_copy ? row_offset[31:0] : 32'd0);
                        araddr <= {src[31:2],2'b00} + (reverse_copy ? source_offset : 32'd0);
                        copy_src_half <= src[1]; copy_dst_half <= dst[1];
                        copy_read_row_words <= ({1'b0,width[9:0]} + {10'd0,src[1]} + 11'd1) >> 1;
                        copy_write_row_words <= ({1'b0,width[9:0]} + {10'd0,dst[1]} + 11'd1) >> 1;
                        bg_read_row_words <= ({1'b0,width[9:0]} + {10'd0,dst[1]} + 11'd1) >> 1;
                        copy_read_words_left <= ({1'b0,width[9:0]} + {10'd0,src[1]} + 11'd1) >> 1;
                        copy_write_words_left <= ({1'b0,width[9:0]} + {10'd0,dst[1]} + 11'd1) >> 1;
                        copy_read_word_index <= 0; copy_write_word_index <= 0;
                        state <= C_RPREP;
                    end
                end
            end
            F_PREP: begin
                burst_words <= words_to_4k < proposed_words ? words_to_4k[4:0] : proposed_words[4:0];
                beat <= 0; fifo_load_count <= 0;
                fifo_base_word_index <= word_index;
                state <= F_FIFO;
            end
            F_FIFO: if (fifo_push) begin
                fifo_load_count <= fifo_load_count + 1'b1;
                state <= F_ADDR;
            end
            F_ADDR: begin
                if (fifo_push) fifo_load_count <= fifo_load_count + 1'b1;
                if (awready) state <= F_DATA;
            end
            F_DATA: begin
                if (fifo_push) fifo_load_count <= fifo_load_count + 1'b1;
                if (fifo_pop) begin
                    beat <= beat + 1'b1;
                    word_index <= word_index + 1'b1;
                    if (wlast) state <= F_RESP;
                end
            end
            F_RESP: if (bvalid) begin
                if (bresp != 0) begin error <= 1; done <= 1; state <= IDLE; end
                else if (words_left == {5'd0,burst_words}) begin
                    if (rows_left == 1) begin done <= 1; state <= IDLE; end
                    else begin
                        row_addr <= row_addr + 1280;
                        awaddr <= {row_addr[31:2],2'b00} + 1280;
                        rows_left <= rows_left - 1'b1;
                        words_left <= row_words; word_index <= 0; state <= F_PREP;
                    end
                end else begin
                    awaddr <= awaddr + ({27'd0,burst_words} << 2);
                    words_left <= words_left - {5'd0,burst_words}; state <= F_PREP;
                end
            end
            C_RPREP: begin
                copy_read_burst_words <= read_words_to_4k < copy_read_proposed ? read_words_to_4k[4:0] : copy_read_proposed[4:0];
                copy_read_beat <= 0; state <= C_RADDR;
            end
            C_RADDR: if (arready) state <= C_RDATA;
            C_RDATA: if (rvalid) begin
                // Drain the accepted burst on RRESP error; returning early
                // would leave unread beats on the shared scanout/copy channel.
                if (copy_read_beat_error) error <= 1;
                copy_read_word_index <= copy_read_word_index + 1'b1;
                if (copy_read_beat == copy_read_burst_words-1) begin
                    if (error || copy_read_beat_error) begin
                        done <= 1; state <= IDLE;
                    end else if (copy_read_words_left == {5'd0,copy_read_burst_words}) begin
                        copy_write_word_index <= 0;
                        if (blend_mode && blend_ctrl[0] && blend_alpha != 8'hff) begin
                            araddr <= {row_addr[31:2],2'b00};
                            bg_read_words_left <= bg_read_row_words;
                            bg_read_word_index <= 0;
                            state <= B_RPREP;
                        end else state <= C_WPREP;
                    end else begin
                        araddr <= araddr + ({27'd0,copy_read_burst_words} << 2);
                        copy_read_words_left <= copy_read_words_left - {5'd0,copy_read_burst_words};
                        state <= C_RPREP;
                    end
                end else copy_read_beat <= copy_read_beat + 1'b1;
            end
            // Compositing reads the destination row before any writes. Keep
            // background lanes aligned to destination words, including edges.
            B_RPREP: begin
                bg_read_burst_words <= read_words_to_4k < bg_read_proposed ? read_words_to_4k[4:0] : bg_read_proposed[4:0];
                bg_read_beat <= 0; state <= B_RADDR;
            end
            B_RADDR: if (arready) state <= B_RDATA;
            B_RDATA: if (rvalid) begin
                if (bg_read_beat_error) error <= 1;
                bg_read_word_index <= bg_read_word_index + 1'b1;
                if (bg_read_beat == bg_read_burst_words-1) begin
                    if (error || bg_read_beat_error) begin
                        done <= 1; state <= IDLE;
                    end else if (bg_read_words_left == {5'd0,bg_read_burst_words}) begin
                        state <= C_WPREP;
                    end else begin
                        araddr <= araddr + ({27'd0,bg_read_burst_words} << 2);
                        bg_read_words_left <= bg_read_words_left - {5'd0,bg_read_burst_words};
                        state <= B_RPREP;
                    end
                end else bg_read_beat <= bg_read_beat + 1'b1;
            end
            C_WPREP: begin
                copy_write_burst_words <= write_words_to_4k < copy_write_proposed ? write_words_to_4k[4:0] : copy_write_proposed[4:0];
                copy_write_beat <= 0; fifo_load_count <= 0;
                fifo_base_word_index <= copy_write_word_index;
                copy_prefetch_index <= copy_write_word_index;
                state <= C_WPRIME;
            end
            // Prime the synchronous row RAM, then issue one read per cycle
            // while the corresponding previous result enters the FIFO.
            C_WPRIME: begin
                copy_prefetch_index <= copy_prefetch_index + 1'b1;
                state <= C_WFIFO;
            end
            C_WFIFO: if (fifo_push) begin
                fifo_load_count <= fifo_load_count + 1'b1;
                if (fifo_load_count != copy_write_burst_words-1'b1)
                    copy_prefetch_index <= copy_prefetch_index + 1'b1;
                state <= C_WADDR;
            end
            C_WADDR: begin
                if (fifo_push) begin
                    fifo_load_count <= fifo_load_count + 1'b1;
                    if (fifo_load_count != copy_write_burst_words-1'b1)
                        copy_prefetch_index <= copy_prefetch_index + 1'b1;
                end
                if (awready) state <= C_WDATA;
            end
            C_WDATA: begin
                if (fifo_push) begin
                    fifo_load_count <= fifo_load_count + 1'b1;
                    if (fifo_load_count != copy_write_burst_words-1'b1)
                        copy_prefetch_index <= copy_prefetch_index + 1'b1;
                end
                if (fifo_pop) begin
                    copy_write_beat <= copy_write_beat + 1'b1;
                    copy_write_word_index <= copy_write_word_index + 1'b1;
                    if (wlast) state <= C_WRESP;
                end
            end
            C_WRESP: if (bvalid) begin
                if (bresp != 0) begin error <= 1; done <= 1; state <= IDLE; end
                else if (copy_write_words_left == {5'd0,copy_write_burst_words}) begin
                    if (rows_left == 1) begin done <= 1; state <= IDLE; end
                    else begin
                        row_addr <= row_addr + row_step;
                        source_row_addr <= next_source_row;
                        awaddr <= {row_addr[31:2],2'b00} + row_step;
                        araddr <= {next_source_row[31:2],2'b00};
                        // A pitch of 2 mod 4 alternates the source halfword
                        // alignment each row (e.g. tightly packed odd widths).
                        copy_src_half <= next_source_row[1];
                        rows_left <= rows_left - 1'b1;
                        copy_read_row_words <= next_read_words;
                        copy_read_words_left <= next_read_words;
                        copy_write_words_left <= copy_write_row_words;
                        copy_read_word_index <= 0; copy_write_word_index <= 0;
                        state <= C_RPREP;
                    end
                end else begin
                    awaddr <= awaddr + ({27'd0,copy_write_burst_words} << 2);
                    copy_write_words_left <= copy_write_words_left - {5'd0,copy_write_burst_words};
                    state <= C_WPREP;
                end
            end
            default: state <= IDLE;
            endcase
        end
    end
endmodule
`default_nettype wire
