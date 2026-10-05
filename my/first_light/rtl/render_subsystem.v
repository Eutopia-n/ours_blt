`default_nettype none
module render_subsystem #(
    parameter [31:0] FB_BYTES = 32'd960000,
    parameter integer FB_WIDTH = 800,
    parameter integer FB_HEIGHT = 600,
    parameter integer FB_PITCH = 1600,
    parameter integer FIXED_SVGA = 1
) (
    input wire clk, reset, pixel_clk, memory_ready, key2_down,
    input wire clock_hold, clock_ready,
    input wire [7:0] clock_debug,
    output wire mode_active,
    input wire [15:0] paddr, input wire psel, penable, pwrite,
    input wire [31:0] pwdata,
    output wire [31:0] prdata, output wire pready, pslverror,
    output wire [31:0] awaddr, output wire [7:0] awlen,
    output wire awvalid, input wire awready,
    output wire [31:0] wdata, output wire [3:0] wstrb,
    output wire wlast, wvalid, input wire wready,
    input wire [1:0] bresp, input wire bvalid, output wire bready,
    output wire [31:0] araddr, output wire [7:0] arlen,
    output wire arvalid, input wire arready,
    input wire [31:0] rdata, input wire [1:0] rresp,
    input wire rlast, rvalid, output wire rready,
    output wire [15:0] pixel, output wire hs, vs, de
);
    wire start, display_enable, busy, done, error, underflow, read_error;
    wire video_fetch_active, underflow_event_pixel;
    wire [9:0] underflow_line_pixel;
    wire [31:0] underflow_count;
    wire [15:0] underflow_last_line;
    wire display_page_active, draw_page, swap_page, swap_toggle, swap_ack_pixel;
    wire [15:0] video_width_pixel, video_height_pixel;
    wire video_mode_valid_pixel, video_mode_toggle_pixel;
    wire [1:0] operation;
    wire [31:0] src, dst, stride, src_stride, cycles;
    wire [15:0] width, height, color;
    wire [8:0] alpha_opacity;
    wire alpha_key_enable;
    wire mode_request;
    (* async_reg = "true" *) reg [1:0] mode_active_sync;
    wire [31:0] fill_araddr, video_araddr, fill_rdata, video_rdata;
    wire [7:0] fill_arlen, video_arlen;
    wire fill_arvalid, fill_arready, fill_rvalid, fill_rready;
    wire video_arvalid, video_arready, video_rvalid, video_rready;
    wire [1:0] fill_rresp, video_rresp;
    wire fill_rlast, video_rlast;
    wire [31:0] fill_awaddr, fill_wdata;
    wire [7:0] fill_awlen;
    wire [3:0] fill_wstrb;
    wire fill_awvalid, fill_awready, fill_wlast, fill_wvalid;
    reg fill_aw_presented;
    wire [31:0] draw_frame_base = draw_page ? 32'h01000000 + FB_BYTES : 32'h01000000;
    (* async_reg = "true" *) reg [1:0] display_page_sync;
    (* async_reg = "true" *) reg [2:0] swap_ack_sync;
    (* async_reg = "true" *) reg [2:0] video_mode_toggle_sync;
    (* async_reg = "true" *) reg [15:0] video_width_meta, video_width_sync;
    (* async_reg = "true" *) reg [15:0] video_height_meta, video_height_sync;
    (* async_reg = "true" *) reg [1:0] video_valid_sync;
    reg [15:0] video_width, video_height;
    reg video_mode_valid, video_mode_seen;
    (* async_reg = "true" *) reg [2:0] underflow_event_sync;
    (* async_reg = "true" *) reg [9:0] underflow_line_meta, underflow_line_sync;
    reg underflow_event_seen;
    reg [31:0] underflow_count_reg;
    reg [15:0] underflow_last_line_reg;
    // Observe actual pixel-clock progress even while display output is disabled.
    reg [9:0] pixel_heartbeat;
    (* async_reg = "true" *) reg [2:0] heartbeat_sync;
    reg [15:0] heartbeat_count;
    always @(posedge pixel_clk or posedge reset)
        if (reset) pixel_heartbeat <= 0;
        else pixel_heartbeat <= pixel_heartbeat + 1'b1;
    always @(posedge clk) begin
        if (reset) begin heartbeat_sync <= 0; heartbeat_count <= 0; end
        else begin
            heartbeat_sync <= {heartbeat_sync[1:0],pixel_heartbeat[9]};
            if (heartbeat_sync[2] != heartbeat_sync[1])
                heartbeat_count <= heartbeat_count + 1'b1;
        end
    end
    assign underflow_count = underflow_count_reg;
    assign underflow_last_line = underflow_last_line_reg;
    always @(posedge clk) begin
        if (reset) begin
            display_page_sync <= 0; swap_ack_sync <= 0;
            mode_active_sync <= FIXED_SVGA ? 2'b11 : 2'b00;
            video_mode_toggle_sync <= 0;
            video_width_meta <= 0; video_width_sync <= 0;
            video_height_meta <= 0; video_height_sync <= 0;
            video_valid_sync <= 0;
            video_width <= 0; video_height <= 0;
            video_mode_valid <= 0; video_mode_seen <= 0;
            underflow_event_sync <= 0; underflow_event_seen <= 0;
            underflow_line_meta <= 0; underflow_line_sync <= 0;
            underflow_count_reg <= 0; underflow_last_line_reg <= 0;
        end
        else begin
            display_page_sync <= {display_page_sync[0],display_page_active};
            mode_active_sync <= {mode_active_sync[0],mode_active};
            swap_ack_sync <= {swap_ack_sync[1:0],swap_ack_pixel};
            // The data bus is stable for a complete video frame. Give it two
            // destination clocks to settle before the third-stage toggle is seen.
            video_width_meta <= video_width_pixel;
            video_width_sync <= video_width_meta;
            video_height_meta <= video_height_pixel;
            video_height_sync <= video_height_meta;
            video_valid_sync <= {video_valid_sync[0],video_mode_valid_pixel};
            video_mode_toggle_sync <= {video_mode_toggle_sync[1:0],video_mode_toggle_pixel};
            underflow_event_sync <= {underflow_event_sync[1:0],underflow_event_pixel};
            underflow_line_meta <= underflow_line_pixel;
            underflow_line_sync <= underflow_line_meta;
            if (video_mode_toggle_sync[2] != video_mode_seen) begin
                video_mode_seen <= video_mode_toggle_sync[2];
                video_width <= video_width_sync;
                video_height <= video_height_sync;
                video_mode_valid <= video_valid_sync[1];
            end
            if (underflow_event_sync[2] != underflow_event_seen) begin
                underflow_event_seen <= underflow_event_sync[2];
                if (underflow_count_reg != 32'hffffffff)
                    underflow_count_reg <= underflow_count_reg + 1'b1;
                underflow_last_line_reg <= {6'd0,underflow_line_sync};
            end
        end
    end
    // Lock the selected master BEFORE asserting ARVALID; keep its ownership
    // through every R beat, including stalls and error responses. Scanout has
    // priority at burst boundaries, so a copy cannot steal a pending video read.
    localparam READ_IDLE=0, READ_ADDRESS=1, READ_DATA=2;
    reg [1:0] read_state;
    reg read_owner_copy;
    reg [7:0] read_beats_left;
    always @(posedge clk) begin
        if (reset) begin
            read_state <= READ_IDLE; read_owner_copy <= 0; read_beats_left <= 0;
        end else case (read_state)
        READ_IDLE: if (video_arvalid || (!video_fetch_active && fill_arvalid)) begin
            read_owner_copy <= !video_arvalid;
            read_state <= READ_ADDRESS;
        end
        READ_ADDRESS: if (arvalid && arready) begin
            read_beats_left <= arlen; read_state <= READ_DATA;
        end
        READ_DATA: if (rvalid && rready) begin
            if (read_beats_left == 0) read_state <= READ_IDLE;
            else read_beats_left <= read_beats_left - 1'b1;
        end
        default: read_state <= READ_IDLE;
        endcase
    end
    assign araddr = read_owner_copy ? fill_araddr : video_araddr;
    assign arlen = read_owner_copy ? fill_arlen : video_arlen;
    assign arvalid = read_state == READ_ADDRESS && (read_owner_copy ? fill_arvalid : video_arvalid);
    assign fill_arready = read_state == READ_ADDRESS && read_owner_copy && arready;
    assign video_arready = read_state == READ_ADDRESS && !read_owner_copy && arready;
    assign fill_rdata = rdata;
    assign video_rdata = rdata;
    assign fill_rresp = rresp;
    assign video_rresp = rresp;
    assign fill_rlast = rlast;
    assign video_rlast = rlast;
    assign fill_rvalid = read_state == READ_DATA && read_owner_copy && rvalid;
    assign video_rvalid = read_state == READ_DATA && !read_owner_copy && rvalid;
    assign rready = read_state == READ_DATA && (read_owner_copy ? fill_rready : video_rready);
    // Once AWVALID is visible it must remain asserted until AWREADY. Remember
    // that commitment across a later scanline request; only unpresented write
    // addresses are throttled while the complete line is fetched.
    always @(posedge clk) begin
        if (reset) fill_aw_presented <= 0;
        else if (awvalid && awready) fill_aw_presented <= 0;
        else if (fill_awvalid && !video_fetch_active) fill_aw_presented <= 1;
    end
    assign awaddr = fill_awaddr;
    assign awlen = fill_awlen;
    assign awvalid = fill_awvalid && (!video_fetch_active || fill_aw_presented);
    assign fill_awready = awready && (!video_fetch_active || fill_aw_presented);
    assign wdata = fill_wdata;
    assign wstrb = fill_wstrb;
    assign wlast = fill_wlast;
    assign wvalid = fill_wvalid;
    render_regs #(.FB_PITCH(FB_PITCH),.FIXED_SVGA(FIXED_SVGA)) regs (
        .clk(clk),.reset(reset),.paddr(paddr),.psel(psel),.penable(penable),
        .pwrite(pwrite),.pwdata(pwdata),.prdata(prdata),.pready(pready),.pslverror(pslverror),
        .memory_ready(memory_ready),.busy(busy),.done(done),.error(error),.cycles(cycles),
        .video_underflow(underflow),.video_error(read_error),
        .video_underflow_count(underflow_count),.video_underflow_line(underflow_last_line),
        .display_page_active(display_page_sync[1]),
        .swap_ack(swap_ack_sync[2]),
        .video_width(video_width),.video_height(video_height),.video_mode_valid(video_mode_valid),
        .key2_down(key2_down),.alpha_opacity(alpha_opacity),.alpha_key_enable(alpha_key_enable),
        .mode_active(mode_active_sync[1]),.clock_ready(clock_ready),.mode_request(mode_request),
        .clock_diagnostic({heartbeat_count,8'd0,clock_debug}),
        .start(start),.display_enable(display_enable),
        .dst(dst),.stride(stride),.src_stride(src_stride),.width(width),.height(height),.color(color),
        .operation(operation),.src(src),.draw_page(draw_page),.swap_page(swap_page),.swap_toggle(swap_toggle)
    );
    fill_engine #(.FB_BYTES(FB_BYTES),.FB_WIDTH(FB_WIDTH),.FB_HEIGHT(FB_HEIGHT),.FB_PITCH(FB_PITCH)) fill (
        .clk(clk),.reset(reset),.start(start),.memory_ready(memory_ready),
        .operation(operation),.src(src),.frame_base(draw_frame_base),
        .alpha_opacity(alpha_opacity),.alpha_key_enable(alpha_key_enable),
        .dst(dst),.stride(stride),.src_stride(src_stride),.width(width),.height(height),.color(color),
        .busy(busy),.done(done),.error(error),.cycles(cycles),
        .awaddr(fill_awaddr),.awlen(fill_awlen),.awvalid(fill_awvalid),.awready(fill_awready),
        .wdata(fill_wdata),.wstrb(fill_wstrb),.wlast(fill_wlast),.wvalid(fill_wvalid),.wready(wready),
        .bresp(bresp),.bvalid(bvalid),.bready(bready),
        .araddr(fill_araddr),.arlen(fill_arlen),.arvalid(fill_arvalid),.arready(fill_arready),
        .rdata(fill_rdata),.rresp(fill_rresp),.rlast(fill_rlast),.rvalid(fill_rvalid),.rready(fill_rready)
    );
    framebuffer_video #(.FB_BYTES(FB_BYTES),.FB_PITCH(FB_PITCH),.FIXED_SVGA(FIXED_SVGA)) video (
        .clk(clk),.reset(reset),.pixel_clk(pixel_clk),.display_enable(display_enable && memory_ready),
        .swap_page(swap_page),.swap_toggle(swap_toggle),
        .mode_request(mode_request),.clock_hold(clock_hold),.mode_active(mode_active),
        .araddr(video_araddr),.arlen(video_arlen),.arvalid(video_arvalid),.arready(video_arready),
        .rdata(video_rdata),.rresp(video_rresp),.rlast(video_rlast),.rvalid(video_rvalid),.rready(video_rready),
        .pixel(pixel),.hs(hs),.vs(vs),.de(de),.active_page(display_page_active),
        .swap_ack(swap_ack_pixel),.fetch_active(video_fetch_active),
        .underflow(underflow),.read_error(read_error),
        .underflow_event_toggle(underflow_event_pixel),.underflow_line(underflow_line_pixel)
    );
    video_mode_measure mode_measure (
        .pixel_clk(pixel_clk),.reset(reset),.hs(hs),.vs(vs),.de(de),
        .width(video_width_pixel),.height(video_height_pixel),
        .valid(video_mode_valid_pixel),.update_toggle(video_mode_toggle_pixel)
    );
endmodule
`default_nettype wire
