`default_nettype none
module render_subsystem #(
    parameter KEY_COUNT = 5
)(
    input wire clk, reset, pixel_clk, memory_ready,
    input wire [KEY_COUNT-1:0] button_held,
    input wire button_enter_pending,
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
    wire display_page_active, draw_page, swap_page, swap_toggle, swap_ack_pixel;
    wire [15:0] video_width_pixel, video_height_pixel;
    wire video_mode_valid_pixel, video_mode_toggle_pixel;
    wire [1:0] operation;
    wire [31:0] src, dst, stride, src_stride, cycles;
    wire [31:0] burst_reads, burst_writes;
    wire [31:0] ddr_read_wait_cycles, ddr_write_wait_cycles;
    wire [15:0] width, height, color;
    wire [1:0] blend_ctrl;
    wire [7:0] blend_alpha;
    wire [15:0] color_key;
    wire [31:0] fill_araddr, video_araddr, fill_rdata, video_rdata;
    wire [7:0] fill_arlen, video_arlen;
    wire fill_arvalid, fill_arready, fill_rvalid, fill_rready;
    wire video_arvalid, video_arready, video_rvalid, video_rready;
    wire [1:0] fill_rresp, video_rresp;
    wire fill_rlast, video_rlast;
    wire [31:0] draw_frame_base = draw_page ? 32'h01096000 : 32'h01000000;
    (* async_reg = "true" *) reg [1:0] display_page_sync;
    (* async_reg = "true" *) reg [2:0] swap_ack_sync;
    (* async_reg = "true" *) reg [2:0] video_mode_toggle_sync;
    (* async_reg = "true" *) reg [15:0] video_width_meta, video_width_sync;
    (* async_reg = "true" *) reg [15:0] video_height_meta, video_height_sync;
    (* async_reg = "true" *) reg [1:0] video_valid_sync;
    reg [15:0] video_width, video_height;
    reg video_mode_valid, video_mode_seen;
    reg [31:0] video_frame_count;
    always @(posedge clk) begin
        if (reset) begin
            display_page_sync <= 0; swap_ack_sync <= 0;
            video_mode_toggle_sync <= 0;
            video_width_meta <= 0; video_width_sync <= 0;
            video_height_meta <= 0; video_height_sync <= 0;
            video_valid_sync <= 0;
            video_width <= 0; video_height <= 0;
            video_mode_valid <= 0; video_mode_seen <= 0;
            video_frame_count <= 0;
        end
        else begin
            display_page_sync <= {display_page_sync[0],display_page_active};
            swap_ack_sync <= {swap_ack_sync[1:0],swap_ack_pixel};
            // The data bus is stable for a complete video frame. Give it two
            // destination clocks to settle before the third-stage toggle is seen.
            video_width_meta <= video_width_pixel;
            video_width_sync <= video_width_meta;
            video_height_meta <= video_height_pixel;
            video_height_sync <= video_height_meta;
            video_valid_sync <= {video_valid_sync[0],video_mode_valid_pixel};
            video_mode_toggle_sync <= {video_mode_toggle_sync[1:0],video_mode_toggle_pixel};
            if (video_mode_toggle_sync[2] != video_mode_seen) begin
                // Count in the APB clock domain after the existing VSYNC-toggle
                // synchronizer. No asynchronous multi-bit counter crosses CDC.
                video_frame_count <= video_frame_count + 1'b1;
                video_mode_seen <= video_mode_toggle_sync[2];
                video_width <= video_width_sync;
                video_height <= video_height_sync;
                video_mode_valid <= video_valid_sync[1];
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
        READ_IDLE: if (video_arvalid || fill_arvalid) begin
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
    render_regs #(.KEY_COUNT(KEY_COUNT)) regs (
        .clk(clk),.reset(reset),.paddr(paddr),.psel(psel),.penable(penable),
        .pwrite(pwrite),.pwdata(pwdata),.prdata(prdata),.pready(pready),.pslverror(pslverror),
        .memory_ready(memory_ready),.busy(busy),.done(done),.error(error),.cycles(cycles),
        .burst_reads(burst_reads),.burst_writes(burst_writes),
        .ddr_read_wait_cycles(ddr_read_wait_cycles),.ddr_write_wait_cycles(ddr_write_wait_cycles),
        .video_frame_count(video_frame_count),
        .button_held(button_held),
        .button_enter_pending(button_enter_pending),
        .video_underflow(underflow),.video_error(read_error),.display_page_active(display_page_sync[1]),
        .swap_ack(swap_ack_sync[2]),
        .video_width(video_width),.video_height(video_height),.video_mode_valid(video_mode_valid),
        .start(start),.display_enable(display_enable),
        .dst(dst),.stride(stride),.src_stride(src_stride),.width(width),.height(height),.color(color),
        .operation(operation),.src(src),.draw_page(draw_page),.swap_page(swap_page),.swap_toggle(swap_toggle),
        .blend_ctrl(blend_ctrl),.blend_alpha(blend_alpha),.color_key(color_key)
    );
    wire ui_selected=operation==3;
    wire legacy_busy,ui_busy;
    wire legacy_done,ui_done;
    wire legacy_error,ui_error;
    wire [31:0] legacy_cycles,ui_cycles;
    wire [31:0] legacy_burst_reads,ui_burst_reads;
    wire [31:0] legacy_burst_writes,ui_burst_writes;
    wire [31:0] legacy_ddr_read_wait_cycles,ui_ddr_read_wait_cycles;
    wire [31:0] legacy_ddr_write_wait_cycles,ui_ddr_write_wait_cycles;
    wire [31:0] legacy_awaddr,ui_awaddr;
    wire [7:0] legacy_awlen,ui_awlen;
    wire legacy_awvalid,ui_awvalid;
    wire [31:0] legacy_wdata,ui_wdata;
    wire [3:0] legacy_wstrb,ui_wstrb;
    wire legacy_wlast,ui_wlast;
    wire legacy_wvalid,ui_wvalid;
    wire legacy_bready,ui_bready;
    wire [31:0] legacy_fill_araddr,ui_fill_araddr;
    wire [7:0] legacy_fill_arlen,ui_fill_arlen;
    wire legacy_fill_arvalid,ui_fill_arvalid;
    wire legacy_fill_rready,ui_fill_rready;
    assign busy=ui_selected ? ui_busy:legacy_busy;
    assign done=ui_selected ? ui_done:legacy_done;
    assign error=ui_selected ? ui_error:legacy_error;
    assign cycles=ui_selected ? ui_cycles:legacy_cycles;
    assign burst_reads=legacy_burst_reads+ui_burst_reads;
    assign burst_writes=legacy_burst_writes+ui_burst_writes;
    assign ddr_read_wait_cycles=legacy_ddr_read_wait_cycles+ui_ddr_read_wait_cycles;
    assign ddr_write_wait_cycles=legacy_ddr_write_wait_cycles+ui_ddr_write_wait_cycles;
    assign awaddr=ui_selected ? ui_awaddr:legacy_awaddr;
    assign awlen=ui_selected ? ui_awlen:legacy_awlen;
    assign awvalid=ui_selected ? ui_awvalid:legacy_awvalid;
    assign wdata=ui_selected ? ui_wdata:legacy_wdata;
    assign wstrb=ui_selected ? ui_wstrb:legacy_wstrb;
    assign wlast=ui_selected ? ui_wlast:legacy_wlast;
    assign wvalid=ui_selected ? ui_wvalid:legacy_wvalid;
    assign bready=ui_selected ? ui_bready:legacy_bready;
    assign fill_araddr=ui_selected ? ui_fill_araddr:legacy_fill_araddr;
    assign fill_arlen=ui_selected ? ui_fill_arlen:legacy_fill_arlen;
    assign fill_arvalid=ui_selected ? ui_fill_arvalid:legacy_fill_arvalid;
    assign fill_rready=ui_selected ? ui_fill_rready:legacy_fill_rready;
    fill_engine fill (
        .clk(clk),.reset(reset),.start(start && !ui_selected),.memory_ready(memory_ready),
        .operation(operation),.src(src),.frame_base(draw_frame_base),
        .dst(dst),.stride(stride),.src_stride(src_stride),.width(width),.height(height),.color(color),
        .blend_ctrl(blend_ctrl),.blend_alpha(blend_alpha),.color_key(color_key),
        .busy(legacy_busy),.done(legacy_done),.error(legacy_error),.cycles(legacy_cycles),
        .burst_reads(legacy_burst_reads),.burst_writes(legacy_burst_writes),
        .ddr_read_wait_cycles(legacy_ddr_read_wait_cycles),.ddr_write_wait_cycles(legacy_ddr_write_wait_cycles),
        .awaddr(legacy_awaddr),.awlen(legacy_awlen),.awvalid(legacy_awvalid),.awready(awready && !ui_selected),
        .wdata(legacy_wdata),.wstrb(legacy_wstrb),.wlast(legacy_wlast),.wvalid(legacy_wvalid),.wready(wready && !ui_selected),
        .bresp(bresp),.bvalid(bvalid && !ui_selected),.bready(legacy_bready),
        .araddr(legacy_fill_araddr),.arlen(legacy_fill_arlen),.arvalid(legacy_fill_arvalid),.arready(fill_arready && !ui_selected),
        .rdata(fill_rdata),.rresp(fill_rresp),.rlast(fill_rlast),.rvalid(fill_rvalid && !ui_selected),.rready(legacy_fill_rready)
    );
    ui_compositor ui (
        .clk(clk),.reset(reset),.start(start && ui_selected),.memory_ready(memory_ready),
        .frame_base(draw_frame_base),.dst(dst),.src(src),.background(src_stride),.stride(stride),
        .width(width),.height(height),.command_count(color),.background_color(color_key),
        .busy(ui_busy),.done(ui_done),.error(ui_error),.cycles(ui_cycles),
        .burst_reads(ui_burst_reads),.burst_writes(ui_burst_writes),
        .read_wait(ui_ddr_read_wait_cycles),.write_wait(ui_ddr_write_wait_cycles),
        .awaddr(ui_awaddr),.awlen(ui_awlen),.awvalid(ui_awvalid),.awready(awready && ui_selected),
        .wdata(ui_wdata),.wstrb(ui_wstrb),.wlast(ui_wlast),.wvalid(ui_wvalid),.wready(wready && ui_selected),
        .bresp(bresp),.bvalid(bvalid && ui_selected),.bready(ui_bready),
        .araddr(ui_fill_araddr),.arlen(ui_fill_arlen),.arvalid(ui_fill_arvalid),.arready(fill_arready && ui_selected),
        .rdata(fill_rdata),.rresp(fill_rresp),.rlast(fill_rlast),.rvalid(fill_rvalid && ui_selected),.rready(ui_fill_rready)
    );
    framebuffer_video video (
        .clk(clk),.reset(reset),.pixel_clk(pixel_clk),.display_enable(display_enable && memory_ready),
        .swap_page(swap_page),.swap_toggle(swap_toggle),
        .araddr(video_araddr),.arlen(video_arlen),.arvalid(video_arvalid),.arready(video_arready),
        .rdata(video_rdata),.rresp(video_rresp),.rlast(video_rlast),.rvalid(video_rvalid),.rready(video_rready),
        .pixel(pixel),.hs(hs),.vs(vs),.de(de),.active_page(display_page_active),
        .swap_ack(swap_ack_pixel),
        .underflow(underflow),.read_error(read_error)
    );
    video_mode_measure mode_measure (
        .pixel_clk(pixel_clk),.reset(reset),.hs(hs),.vs(vs),.de(de),
        .width(video_width_pixel),.height(video_height_pixel),
        .valid(video_mode_valid_pixel),.update_toggle(video_mode_toggle_pixel)
    );
endmodule
`default_nettype wire
