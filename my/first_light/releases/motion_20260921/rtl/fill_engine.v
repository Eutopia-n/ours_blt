// RGB565 solid fill and framebuffer block copy.
// One outstanding AXI read or write burst, at most 16 beats.
// Byte strobes preserve neighbouring pixels for odd X / odd rectangle widths.
`default_nettype none
module fill_engine #(
    parameter [31:0] FB_BASE = 32'h01000000,
    parameter [31:0] FB_BYTES = 32'd614400
) (
    input wire clk, input wire reset,
    input wire start, input wire memory_ready,
    input wire [1:0] operation, input wire [31:0] src,
    input wire [31:0] frame_base,
    input wire [31:0] dst, input wire [15:0] width, height,
    input wire [31:0] stride, input wire [15:0] color,
    output wire busy, output reg done, output reg error,
    output reg [31:0] cycles,
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
    localparam IDLE=0, F_PREP=1, F_ADDR=2, F_DATA=3, F_RESP=4,
               C_RPREP=5, C_RADDR=6, C_RDATA=7,
               C_WPREP=8, C_WADDR=9, C_WDATA=10, C_WRESP=11, C_WLOAD=12;
    reg [3:0] state;
    reg copy_mode;
    reg [31:0] source_row_addr;
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
    reg copy_src_half, copy_dst_half;
    // Raw source words are stored before any destination writes. Two banks
    // allow synchronous block RAM inference and halfword realignment.
    reg [15:0] copy_buf_lo [0:511];
    reg [15:0] copy_buf_hi [0:511];
    reg [15:0] copy_qlo, copy_qhi;
    wire [8:0] copy_lo_index = copy_write_word_index[8:0] +
        ((copy_src_half && !copy_dst_half) ? 9'd1 : 9'd0);
    wire [8:0] copy_hi_index = copy_write_word_index[8:0] -
        ((!copy_src_half && copy_dst_half) ? 9'd1 : 9'd0);
    wire [31:0] copy_data = copy_src_half == copy_dst_half ?
        {copy_qhi,copy_qlo} : {copy_qlo,copy_qhi};
    // A masked neighbour may be outside the loaded row; do not expose X data
    // on inactive byte lanes in simulation or sample uninitialised pixels.
    wire [31:0] copy_mask = {{16{wstrb[2]}},{16{wstrb[0]}}};
    wire [9:0] active_word_index = copy_mode ? copy_write_word_index : word_index;
    wire [9:0] active_row_words = copy_mode ? copy_write_row_words : row_words;
    wire read_beat_error = rresp != 0 || rlast != (copy_read_beat == copy_read_burst_words-1);
    wire [32:0] row_offset = (({17'd0,height}-33'd1) << 10) +
                            (({17'd0,height}-33'd1) << 8);
    wire [32:0] source_end = {1'b0,src} + row_offset + ({17'd0,width} << 1);
    wire [32:0] end_address = {1'b0,dst} +
        (({17'd0,height}-33'd1) << 10) +
        (({17'd0,height}-33'd1) << 8) + ({17'd0,width} << 1);
    wire [10:0] words_to_4k = 11'd1024 - {1'b0,awaddr[11:2]};
    wire [9:0] proposed_words = words_left > 16 ? 10'd16 : words_left;
    wire [10:0] read_words_to_4k = 11'd1024 - {1'b0,araddr[11:2]};
    wire [9:0] copy_read_proposed = copy_read_words_left > 16 ? 10'd16 : copy_read_words_left;
    wire [10:0] write_words_to_4k = 11'd1024 - {1'b0,awaddr[11:2]};
    wire [9:0] copy_write_proposed = copy_write_words_left > 16 ? 10'd16 : copy_write_words_left;
    assign busy = state != IDLE;
    assign awlen = {3'd0,(copy_mode ? copy_write_burst_words : burst_words)} - 8'd1;
    assign awvalid = state == F_ADDR || state == C_WADDR;
    assign wvalid = state == F_DATA || state == C_WDATA;
    assign arlen = {3'd0,copy_read_burst_words} - 8'd1;
    assign arvalid = state == C_RADDR;
    assign rready = state == C_RDATA;
    assign wdata = copy_mode ? (copy_data & copy_mask) : {fill_color,fill_color};
    assign wstrb = ((active_word_index == 0 && first_high) ? 4'b1100 : 4'b1111) &
                   ((active_word_index == active_row_words-10'd1 && last_low) ? 4'b0011 : 4'b1111);
    assign wlast = copy_mode ? copy_write_beat == copy_write_burst_words-1 : beat == burst_words-1;
    assign bready = state == F_RESP || state == C_WRESP;

    always @(posedge clk) begin
        copy_qlo <= copy_buf_lo[copy_lo_index];
        copy_qhi <= copy_buf_hi[copy_hi_index];
        if (rvalid && rready) begin
            copy_buf_lo[copy_read_word_index[8:0]] <= rdata[15:0];
            copy_buf_hi[copy_read_word_index[8:0]] <= rdata[31:16];
        end
    end
    always @(posedge clk) begin
        if (reset) begin
            state <= IDLE; done <= 0; error <= 0; cycles <= 0;
            awaddr <= 0; araddr <= 0; row_addr <= 0; source_row_addr <= 0;
            rows_left <= 0; row_step <= 1280; copy_mode <= 0;
            fill_color <= 0; words_left <= 0; row_words <= 0;
            word_index <= 0; burst_words <= 0; beat <= 0;
            first_high <= 0; last_low <= 0;
            copy_read_words_left <= 0; copy_read_row_words <= 0;
            copy_read_word_index <= 0; copy_read_burst_words <= 0; copy_read_beat <= 0;
            copy_write_words_left <= 0; copy_write_row_words <= 0; copy_write_word_index <= 0;
            copy_write_burst_words <= 0; copy_write_beat <= 0;
            copy_src_half <= 0; copy_dst_half <= 0;
        end else begin
            if (busy) cycles <= cycles + 1'b1;
            case (state)
            IDLE: if (start) begin
                done <= 0; error <= 0; cycles <= 0;
                if (!memory_ready || (operation > 1) || dst[0] || width == 0 || height == 0 ||
                    width > 640 || height > 480 || stride != 1280 ||
                    dst < frame_base || end_address > {1'b0,frame_base}+{1'b0,FB_BYTES} ||
                    (operation == 1 && (src[0] || src < frame_base ||
                     source_end > {1'b0,frame_base}+{1'b0,FB_BYTES}))) begin
                    error <= 1; done <= 1;
                end else begin
                    copy_mode <= operation == 1;
                    row_addr <= dst; awaddr <= {dst[31:2],2'b00};
                    rows_left <= height; fill_color <= color;
                    first_high <= dst[1]; last_low <= dst[1] ^ width[0];
                    if (operation == 0) begin
                        row_words <= ({1'b0,width[9:0]} + {10'd0,dst[1]} + 11'd1) >> 1;
                        words_left <= ({1'b0,width[9:0]} + {10'd0,dst[1]} + 11'd1) >> 1;
                        word_index <= 0; state <= F_PREP;
                    end else begin
                        // Same stride on both sides. Copy bottom-up when the
                        // destination follows the source, preserving overlap.
                        row_step <= dst > src ? -32'd1280 : 32'd1280;
                        row_addr <= dst + (dst > src ? row_offset[31:0] : 32'd0);
                        source_row_addr <= src + (dst > src ? row_offset[31:0] : 32'd0);
                        awaddr <= {dst[31:2],2'b00} + (dst > src ? row_offset[31:0] : 32'd0);
                        araddr <= {src[31:2],2'b00} + (dst > src ? row_offset[31:0] : 32'd0);
                        copy_src_half <= src[1]; copy_dst_half <= dst[1];
                        copy_read_row_words <= ({1'b0,width[9:0]} + {10'd0,src[1]} + 11'd1) >> 1;
                        copy_write_row_words <= ({1'b0,width[9:0]} + {10'd0,dst[1]} + 11'd1) >> 1;
                        copy_read_words_left <= ({1'b0,width[9:0]} + {10'd0,src[1]} + 11'd1) >> 1;
                        copy_write_words_left <= ({1'b0,width[9:0]} + {10'd0,dst[1]} + 11'd1) >> 1;
                        copy_read_word_index <= 0; copy_write_word_index <= 0;
                        state <= C_RPREP;
                    end
                end
            end
            F_PREP: begin
                burst_words <= words_to_4k < proposed_words ? words_to_4k[4:0] : proposed_words[4:0];
                beat <= 0; state <= F_ADDR;
            end
            F_ADDR: if (awready) state <= F_DATA;
            F_DATA: if (wready) begin
                beat <= beat + 1'b1;
                word_index <= word_index + 1'b1;
                if (wlast) state <= F_RESP;
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
                if (read_beat_error) error <= 1;
                copy_read_word_index <= copy_read_word_index + 1'b1;
                if (copy_read_beat == copy_read_burst_words-1) begin
                    if (error || read_beat_error) begin
                        done <= 1; state <= IDLE;
                    end else if (copy_read_words_left == {5'd0,copy_read_burst_words}) begin
                        copy_write_word_index <= 0; state <= C_WPREP;
                    end else begin
                        araddr <= araddr + ({27'd0,copy_read_burst_words} << 2);
                        copy_read_words_left <= copy_read_words_left - {5'd0,copy_read_burst_words};
                        state <= C_RPREP;
                    end
                end else copy_read_beat <= copy_read_beat + 1'b1;
            end
            C_WPREP: begin
                copy_write_burst_words <= write_words_to_4k < copy_write_proposed ? write_words_to_4k[4:0] : copy_write_proposed[4:0];
                copy_write_beat <= 0; state <= C_WADDR;
            end
            C_WADDR: if (awready) state <= C_WDATA;
            C_WLOAD: state <= C_WDATA; // one cycle for synchronous row RAM read
            C_WDATA: if (wready) begin
                copy_write_beat <= copy_write_beat + 1'b1;
                copy_write_word_index <= copy_write_word_index + 1'b1;
                if (wlast) state <= C_WRESP;
                else state <= C_WLOAD;
            end
            C_WRESP: if (bvalid) begin
                if (bresp != 0) begin error <= 1; done <= 1; state <= IDLE; end
                else if (copy_write_words_left == {5'd0,copy_write_burst_words}) begin
                    if (rows_left == 1) begin done <= 1; state <= IDLE; end
                    else begin
                        row_addr <= row_addr + row_step;
                        source_row_addr <= source_row_addr + row_step;
                        awaddr <= {row_addr[31:2],2'b00} + row_step;
                        araddr <= {source_row_addr[31:2],2'b00} + row_step;
                        rows_left <= rows_left - 1'b1;
                        copy_read_words_left <= copy_read_row_words;
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
