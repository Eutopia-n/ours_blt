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
    input wire cache_session,
    // Mutually exclusive tile renderer reuses these four existing RAM banks.
    input wire tile_mode,tile_source_write,tile_background_write,tile_span_write,
    input wire [8:0] tile_source_address,tile_source_lo_address,tile_source_hi_address,
    input wire [8:0] tile_background_address,tile_background_read_address,
    input wire [31:0] tile_source_data,tile_background_data,
    input wire [4:0] tile_span_row,
    input wire [5:0] tile_span_left,tile_span_right,
    output wire [31:0] tile_source_q,tile_background_q,
    output wire [191:0] tile_left_bits,tile_right_bits,
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
    output wire [31:0] araddr, output wire [7:0] arlen,
    output wire arvalid, input wire arready,
    input wire [31:0] rdata, input wire [1:0] rresp,
    input wire rlast, input wire rvalid, output wire rready
);
    localparam IDLE=0, F_PREP=1, F_FIFO=2, F_ADDR=3, F_DATA=4, F_RESP=5,
               C_RPREP=6, C_RADDR=7, C_RDATA=8,
               C_WPREP=9, C_WPRIME=10, C_WFIFO=11,
               C_WADDR=12, C_WDATA=13, C_WRESP=14,
               B_RPREP=15, B_RADDR=16, B_RDATA=17,
               CACHE_CHECK=18,CACHE_SPAN=19,CACHE_ROW=20,CACHE_ABORT=21,C_WALIGN=22;
    reg [31:0] main_araddr;
    localparam PF_IDLE=0,PF_SPAN=1,PF_ROW=2,PF_PREP=3,PF_ADDR=4,PF_DATA=5;
    reg [2:0] pf_state;
    reg pf_ready,pf_bad,pf_failed,cache_abort;
    reg [4:0] pf_row,pf_count,pf_beat;
    reg [5:0] pf_left,pf_right;
    reg [9:0] pf_words,pf_index;
    reg [31:0] pf_address,pf_destination;
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
    // Reuse the existing two 512x16 source-row banks as one <=32x32 compact
    // tile during a batch. Session ownership excludes CPU texture changes.
    // Ordinary commands retain the original uncached path and invalidation.
    reg cache_use,cache_loading,cache_valid;
    reg [31:0] cache_tag_source;
    reg [5:0] cache_tag_side,cache_side,cache_row_words;
    reg [15:0] cache_span_key;
    reg [8:0] cache_row_base,cache_source_base;
    reg [4:0] cache_row,cache_load_row,cache_load_word;
    reg [5:0] cache_first,cache_last,cache_left,cache_right;
    // Small row metadata stays in flops, not a new memory block.
    wire [191:0] cache_span_left_bits,cache_span_right_bits;
    wire cache_eligible=cache_session && operation==2 && src[1:0]==0 &&
        src_stride==({16'd0,width}<<1) && height==width &&
        (width==4 || width==16 || width==24 || width==32);
    wire [9:0] cache_tile_words=width==32 ? 10'd512:width==24 ? 10'd288:width==16 ? 10'd128:10'd8;
    wire [5:0] load_x={cache_load_word[4:0],1'b0};
    wire load_low=rdata[15:0]!=color_key,load_high=rdata[31:16]!=color_key;
    wire [5:0] load_first=cache_first!=63 ? cache_first:load_low ? load_x:load_high ? load_x+6'd1:6'd63;
    wire [5:0] load_last=load_high ? load_x+6'd1:load_low ? load_x:cache_last;
    genvar span_row;
    generate for(span_row=0;span_row<32;span_row=span_row+1)begin:cached_span_registers
        reg [5:0] left_value,right_value;
        always @(posedge clk)if(tile_mode && tile_span_write && tile_span_row==span_row)begin
            left_value<=tile_span_left;right_value<=tile_span_right;
        end else if(state==C_RDATA && rvalid && rready && cache_loading &&
            {1'b0,cache_load_word}==cache_row_words-1'b1 && cache_load_row==span_row)begin
            left_value<=load_first;right_value<=load_last;
        end
        assign cache_span_left_bits[span_row*6+:6]=left_value;
        assign cache_span_right_bits[span_row*6+:6]=right_value;
    end endgenerate
    assign tile_source_q={copy_qhi,copy_qlo};
    assign tile_background_q={bg_qhi,bg_qlo};
    assign tile_left_bits=cache_span_left_bits;
    assign tile_right_bits=cache_span_right_bits;
    wire trim_row=blend_ctrl[1] && color_key==cache_span_key;
    wire [5:0] pf_x0=trim_row ? pf_left:6'd0;
    wire [5:0] pf_x1=trim_row ? pf_right:cache_side-6'd1;
    wire [5:0] pf_width=pf_x1-pf_x0+6'd1;
    wire [31:0] pf_start=pf_destination+{25'd0,pf_x0,1'b0};
    wire [9:0] pf_row_words=({4'd0,pf_width}+{9'd0,pf_start[1]}+10'd1)>>1;
    wire [10:0] pf_boundary=11'd1024-{1'b0,pf_address[11:2]};
    wire [4:0] pf_proposed=pf_words>16 ? 5'd16:pf_words[4:0];
    wire pf_active=pf_state==PF_ADDR || pf_state==PF_DATA;
    wire pf_consumed=state==CACHE_ROW && pf_ready && pf_row==cache_row;
    wire pf_failure=rresp!=0 || rlast!=(pf_beat==pf_count-1'b1);
    wire [8:0] bg_prefetch_index=copy_prefetch_index[8:0]+(cache_use && cache_row[0] ? 9'd32:9'd0);
    wire [5:0] row_left=trim_row ? cache_left:6'd0;
    wire [5:0] row_right=trim_row ? cache_right:cache_side-6'd1;
    wire [5:0] row_width=row_right-row_left+6'd1;
    wire [31:0] cached_row_destination=row_addr+{25'd0,row_left,1'b0};
    wire [9:0] cached_write_words=({4'd0,row_width}+{9'd0,cached_row_destination[1]}+10'd1)>>1;
    wire [8:0] source_prefetch=copy_prefetch_index[8:0]+(cache_use ? cache_source_base:9'd0);
    wire [8:0] copy_lo_index = source_prefetch +
        ((copy_src_half && !copy_dst_half) ? 9'd1 : 9'd0);
    wire [8:0] copy_hi_index = source_prefetch -
        ((!copy_src_half && copy_dst_half) ? 9'd1 : 9'd0);
    wire [31:0] copy_data = copy_src_half == copy_dst_half ?
        {copy_qhi,copy_qlo} : {copy_qlo,copy_qhi};
    wire [31:0] bg_data = {bg_qhi,bg_qlo};
    // Isolate BRAM read/halfword alignment from the multiply/normalize/FIFO
    // path. Once primed, this extra stage still supplies one word per clock.
    reg [31:0] aligned_source,aligned_background;
    always @(posedge clk)begin aligned_source<=copy_data;aligned_background<=bg_data;end
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
        blend_pixel(aligned_source[31:16],aligned_background[31:16],blend_alpha,blend_ctrl,color_key),
        blend_pixel(aligned_source[15:0],aligned_background[15:0],blend_alpha,blend_ctrl,color_key)
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
    wire [10:0] read_words_to_4k = 11'd1024 - {1'b0,main_araddr[11:2]};
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
        ((blend_mode && blend_ctrl[1] && aligned_source[15:0] == color_key) ? 4'b1100 : 4'b1111) &
        ((blend_mode && blend_ctrl[1] && aligned_source[31:16] == color_key) ? 4'b0011 : 4'b1111);
    // A masked neighbour may be outside the loaded row. Zero inactive lanes
    // before caching the word so simulation never exposes uninitialised data.
    wire [31:0] fifo_entry_mask =
        {{16{fifo_entry_strb[2]}},{16{fifo_entry_strb[0]}}};
    wire [31:0] fifo_entry_data = copy_mode ?
        ((blend_mode ? blend_data : aligned_source) & fifo_entry_mask) : {fill_color,fill_color};
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
    assign araddr=pf_active ? pf_address:main_araddr;
    assign arlen = {3'd0,(pf_active ? pf_count:state == B_RADDR ? bg_read_burst_words : copy_read_burst_words)} - 8'd1;
    assign arvalid = pf_state==PF_ADDR || state == C_RADDR || state == B_RADDR;
    assign rready = pf_state==PF_DATA || state == C_RDATA || state == B_RDATA;
    assign wdata = fifo_output[31:0];
    assign wstrb = fifo_output[35:32];
    assign wlast = fifo_output[36];
    assign bready = state == F_RESP || state == C_WRESP;

    // Present exactly one physical write port per bank. Separate conditional
    // array assignments made Efinity infer multiwrite logic memories.
    wire source_ram_write=tile_mode ? tile_source_write:(rvalid && rready && state==C_RDATA);
    wire [8:0] source_ram_address=tile_mode ? tile_source_address:copy_read_word_index[8:0];
    wire [31:0] source_ram_data=tile_mode ? tile_source_data:rdata;
    wire background_ram_write=tile_mode ? tile_background_write:
        (rvalid && rready && (state==B_RDATA || pf_state==PF_DATA));
    wire [8:0] background_ram_address=tile_mode ? tile_background_address:
        pf_state==PF_DATA ? pf_index[8:0]:bg_read_word_index[8:0];
    wire [31:0] background_ram_data=tile_mode ? tile_background_data:rdata;

    always @(posedge clk) begin
        copy_qlo <= copy_buf_lo[tile_mode ? tile_source_lo_address:copy_lo_index];
        copy_qhi <= copy_buf_hi[tile_mode ? tile_source_hi_address:copy_hi_index];
        bg_qlo <= bg_buf_lo[tile_mode ? tile_background_read_address:bg_prefetch_index];
        bg_qhi <= bg_buf_hi[tile_mode ? tile_background_read_address:bg_prefetch_index];
        if(source_ram_write)begin
            copy_buf_lo[source_ram_address]<=source_ram_data[15:0];
            copy_buf_hi[source_ram_address]<=source_ram_data[31:16];
        end
        if(background_ram_write)begin
            bg_buf_lo[background_ram_address]<=background_ram_data[15:0];
            bg_buf_hi[background_ram_address]<=background_ram_data[31:16];
        end
    end
    // A next-row read overlaps the current row's write. The two rows occupy
    // separate 32-word windows of the existing background RAM. No second AR
    // may be issued until the first response burst has completely retired.
    always @(posedge clk)begin
        if(reset)begin
            pf_state<=PF_IDLE;pf_ready<=0;pf_bad<=0;pf_failed<=0;
            pf_row<=0;pf_count<=0;pf_beat<=0;pf_left<=0;pf_right<=0;
            pf_words<=0;pf_index<=0;pf_address<=0;pf_destination<=0;
        end else begin
            if(state==IDLE && start)begin pf_ready<=0;pf_failed<=0;end
            if(pf_consumed)pf_ready<=0;
            case(pf_state)
            PF_IDLE:if(state==C_WPREP && cache_use && rows_left>1 &&
                blend_ctrl[0] && blend_alpha!=255 && !pf_ready && !pf_failed && !cache_abort)begin
                pf_row<=cache_row+1'b1;pf_destination<=row_addr+32'd1280;pf_state<=PF_SPAN;
            end
            PF_SPAN:begin
                pf_left<=cache_span_left_bits[pf_row*6+:6];pf_right<=cache_span_right_bits[pf_row*6+:6];pf_state<=PF_ROW;
            end
            PF_ROW:if(cache_abort)pf_state<=PF_IDLE;
                else if(trim_row && pf_left==63)begin pf_ready<=1;pf_state<=PF_IDLE;end
                else begin
                    pf_address<={pf_start[31:2],2'd0};pf_words<=pf_row_words;
                    pf_index<=pf_row[0] ? 10'd32:10'd0;pf_state<=PF_PREP;
                end
            PF_PREP:if(cache_abort)pf_state<=PF_IDLE;
                else begin
                    pf_count<=pf_boundary<pf_proposed ? pf_boundary[4:0]:pf_proposed;
                    pf_beat<=0;pf_bad<=0;pf_state<=PF_ADDR;
                end
            PF_ADDR:if(arready)pf_state<=PF_DATA;
            PF_DATA:if(rvalid)begin
                if(pf_failure)pf_bad<=1;
                pf_index<=pf_index+1'b1;
                if(pf_beat==pf_count-1'b1)begin
                    if(pf_bad || pf_failure)begin pf_failed<=1;pf_state<=PF_IDLE;end
                    else if(pf_words=={5'd0,pf_count})begin pf_ready<=1;pf_state<=PF_IDLE;end
                    else begin
                        pf_address<=pf_address+{25'd0,pf_count,2'd0};pf_words<=pf_words-{5'd0,pf_count};pf_state<=PF_PREP;
                    end
                end else pf_beat<=pf_beat+1'b1;
            end
            default:pf_state<=PF_IDLE;
            endcase
        end
    end
    always @(posedge clk) begin
        if (reset) begin
            state <= IDLE; done <= 0; error <= 0; cycles <= 0;
            burst_reads <= 0; burst_writes <= 0;
            ddr_read_wait_cycles <= 0; ddr_write_wait_cycles <= 0;
            awaddr <= 0; main_araddr <= 0; row_addr <= 0; source_row_addr <= 0;cache_abort<=0;
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
            cache_use<=0;cache_loading<=0;cache_valid<=0;cache_tag_source<=0;cache_tag_side<=0;
            cache_side<=0;cache_row_words<=0;cache_span_key<=0;cache_row_base<=0;cache_source_base<=0;
            cache_row<=0;cache_load_row<=0;cache_load_word<=0;
            cache_first<=63;cache_last<=0;cache_left<=63;cache_right<=0;
        end else begin
            if(!cache_session)cache_valid<=0;
            if (busy) cycles <= cycles + 1'b1;
            if (arvalid && arready) burst_reads <= burst_reads + 1'b1;
            if (awvalid && awready) burst_writes <= burst_writes + 1'b1;
            // Count only cycles where a valid AXI phase is waiting for the
            // memory/interconnect response, not internal raster work.
            if ((arvalid && !arready) || (rready && !rvalid))
                ddr_read_wait_cycles <= ddr_read_wait_cycles + 1'b1;
            if (((state == F_ADDR || state == C_WADDR) && !awready) ||
                ((state == F_DATA || state == C_WDATA) && wvalid && !wready) ||
                ((state == F_RESP || state == C_WRESP) && !bvalid))
                ddr_write_wait_cycles <= ddr_write_wait_cycles + 1'b1;
            case (state)
            IDLE: if (start) begin
                done <= 0; error <= 0; cycles <= 0;cache_abort<=0;
                cache_use<=cache_eligible;cache_loading<=0;
                if(!cache_eligible)cache_valid<=0;
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
                        main_araddr <= {src[31:2],2'b00} + (reverse_copy ? source_offset : 32'd0);
                        copy_src_half <= src[1]; copy_dst_half <= dst[1];
                        copy_read_row_words <= ({1'b0,width[9:0]} + {10'd0,src[1]} + 11'd1) >> 1;
                        copy_write_row_words <= ({1'b0,width[9:0]} + {10'd0,dst[1]} + 11'd1) >> 1;
                        bg_read_row_words <= ({1'b0,width[9:0]} + {10'd0,dst[1]} + 11'd1) >> 1;
                        copy_read_words_left <= ({1'b0,width[9:0]} + {10'd0,src[1]} + 11'd1) >> 1;
                        copy_write_words_left <= ({1'b0,width[9:0]} + {10'd0,dst[1]} + 11'd1) >> 1;
                        copy_read_word_index <= 0; copy_write_word_index <= 0;
                        cache_side<=width[5:0];cache_row_words<={1'b0,width[5:1]};
                        cache_row_base<=0;cache_source_base<=0;cache_row<=0;
                        state <= cache_eligible ? CACHE_CHECK:C_RPREP;
                    end
                end
            end
            CACHE_CHECK:begin
                if(cache_valid && cache_tag_source==src && cache_tag_side==cache_side)state<=CACHE_SPAN;
                else begin
                    cache_valid<=0;cache_loading<=1;
                    copy_read_words_left<=cache_tile_words;copy_read_word_index<=0;
                    cache_load_row<=0;cache_load_word<=0;cache_first<=63;cache_last<=0;
                    state<=C_RPREP;
                end
            end
            CACHE_SPAN:begin
                cache_left<=cache_span_left_bits[cache_row*6+:6];cache_right<=cache_span_right_bits[cache_row*6+:6];
                state<=CACHE_ROW;
            end
            CACHE_ROW:begin
                if(pf_failed)begin cache_abort<=1;state<=CACHE_ABORT;end
                else if(pf_row==cache_row && pf_state!=PF_IDLE)begin end
                else if(trim_row && cache_left==63)begin
                    // Empty key rows leave the destination entirely untouched.
                    if(rows_left==1)begin done<=1;state<=IDLE;end
                    else begin
                        row_addr<=row_addr+row_step;rows_left<=rows_left-1'b1;
                        cache_row<=cache_row+1'b1;cache_row_base<=cache_row_base+cache_row_words;
                        state<=CACHE_SPAN;
                    end
                end else begin
                    cache_source_base<=cache_row_base+{4'd0,row_left[5:1]};
                    copy_src_half<=row_left[0];copy_dst_half<=cached_row_destination[1];
                    first_high<=cached_row_destination[1];last_low<=cached_row_destination[1]^row_width[0];
                    awaddr<={cached_row_destination[31:2],2'b00};
                    copy_write_row_words<=cached_write_words;copy_write_words_left<=cached_write_words;
                    copy_write_word_index<=0;bg_read_row_words<=cached_write_words;
                    if(blend_ctrl[0] && blend_alpha!=8'hff)begin
                        if(pf_ready && pf_row==cache_row)state<=C_WPREP;
                        else begin
                            main_araddr<={cached_row_destination[31:2],2'b00};bg_read_words_left<=cached_write_words;
                            bg_read_word_index<=cache_row[0] ? 10'd32:10'd0;state<=B_RPREP;
                        end
                    end else state<=C_WPREP;
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
                if(cache_loading)begin
                    if({1'b0,cache_load_word}==cache_row_words-1'b1)begin
                        cache_load_row<=cache_load_row+1'b1;cache_load_word<=0;cache_first<=63;cache_last<=0;
                    end else begin
                        cache_load_word<=cache_load_word+1'b1;cache_first<=load_first;cache_last<=load_last;
                    end
                end
                if (copy_read_beat == copy_read_burst_words-1) begin
                    if (error || copy_read_beat_error) begin
                        done <= 1; state <= IDLE;
                    end else if (copy_read_words_left == {5'd0,copy_read_burst_words}) begin
                        copy_write_word_index <= 0;
                        if(cache_loading)begin
                            cache_loading<=0;cache_valid<=1;cache_tag_source<=src;cache_tag_side<=cache_side;
                            cache_span_key<=color_key;state<=CACHE_SPAN;
                        end else if (blend_mode && blend_ctrl[0] && blend_alpha != 8'hff) begin
                            main_araddr <= {row_addr[31:2],2'b00};
                            bg_read_words_left <= bg_read_row_words;
                            bg_read_word_index <= 0;
                            state <= B_RPREP;
                        end else state <= C_WPREP;
                    end else begin
                        main_araddr <= main_araddr + ({27'd0,copy_read_burst_words} << 2);
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
                        main_araddr <= main_araddr + ({27'd0,bg_read_burst_words} << 2);
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
                state <= C_WALIGN;
            end
            C_WALIGN:begin
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
                if (cache_use && (bresp!=0 || pf_failed))begin cache_abort<=1;state<=CACHE_ABORT;end
                else if (bresp != 0) begin error <= 1; done <= 1; state <= IDLE; end
                else if (copy_write_words_left == {5'd0,copy_write_burst_words}) begin
                    if (rows_left == 1) begin done <= 1; state <= IDLE; end
                    else if(cache_use)begin
                        row_addr<=row_addr+row_step;rows_left<=rows_left-1'b1;
                        cache_row<=cache_row+1'b1;cache_row_base<=cache_row_base+cache_row_words;
                        state<=CACHE_SPAN;
                    end else begin
                        row_addr <= row_addr + row_step;
                        source_row_addr <= next_source_row;
                        awaddr <= {row_addr[31:2],2'b00} + row_step;
                        main_araddr <= {next_source_row[31:2],2'b00};
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
            CACHE_ABORT:if(pf_state==PF_IDLE)begin error<=1;done<=1;state<=IDLE;end
            default: state <= IDLE;
            endcase
        end
    end
endmodule
`default_nettype wire
