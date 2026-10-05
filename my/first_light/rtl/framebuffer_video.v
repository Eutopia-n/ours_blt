// RGB565 scanout: 640x480 (800x525, -/-) or 800x600 (1056x628, +/+).
// Ping-pong line buffers cross from the AXI clock to the pixel clock.
// Request/completion toggles use two-flop synchronizers; line tags remain
// stable until the opposite side acknowledges the transaction.
`default_nettype none
module framebuffer_video #(
    parameter [31:0] FB_BASE = 32'h01000000,
    parameter [31:0] FB_BYTES = 32'd614400,
    parameter integer FB_PITCH = 1280,
    parameter integer FIXED_SVGA = 0
) (
    input wire clk, reset, pixel_clk, display_enable,
    input wire mode_request, clock_hold,
    output reg mode_active,
    input wire swap_page, swap_toggle,
    output reg [31:0] araddr, output wire [7:0] arlen,
    output wire arvalid, input wire arready,
    input wire [31:0] rdata, input wire [1:0] rresp,
    input wire rlast, rvalid, output wire rready,
    output reg [15:0] pixel, output reg hs, vs, de,
    output wire active_page, swap_ack,
    output wire fetch_active,
    output wire underflow, output reg read_error,
    output reg underflow_event_toggle, output reg [9:0] underflow_line
);
    reg [15:0] ram_lo [0:1023];
    reg [15:0] ram_hi [0:1023];
    reg [15:0] qlo, qhi;
    reg [10:0] h;
    reg [9:0] v;
    reg running, line_valid;
    reg req_toggle;
    reg [9:0] req_y;
    reg [8:0] req_words;
    reg done_toggle;
    reg [9:0] done_y;
    reg done_ok;
    (* async_reg = "true" *) reg [2:0] req_sync;
    (* async_reg = "true" *) reg [1:0] done_sync, enable_sync;
    (* async_reg = "true" *) reg [1:0] underflow_sync;
    (* async_reg = "true" *) reg [1:0] pixel_reset_pipe;
    reg seen_done, underflow_pixel;
    reg active_page_reg, req_page, seen_swap;
    (* async_reg = "true" *) reg [1:0] swap_page_sync;
    (* async_reg = "true" *) reg [2:0] swap_sync;
    (* async_reg = "true" *) reg [1:0] req_page_sync;
    (* async_reg = "true" *) reg [1:0] mode_sync;
    reg [1:0] bank_ready;
    reg [9:0] tag0, tag1;
    reg hs_d, vs_d, de_d, odd_d, valid_d;
    wire pixel_reset = pixel_reset_pipe[1];
    (* async_reg = "true" *) reg [1:0] hold_pipe;
    // Clock control is in the AXI domain. Release its hold synchronously,
    // including when pixel_clk was stopped for PLL reset.
    always @(posedge pixel_clk or posedge reset or posedge clock_hold)
        if (reset || clock_hold) hold_pipe <= 2'b11;
        else hold_pipe <= {hold_pipe[0],1'b0};
    assign active_page = active_page_reg;
    assign swap_ack = seen_swap;
    wire [10:0] h_active = mode_active ? 11'd800 : 11'd640;
    wire [10:0] h_total = mode_active ? 11'd1056 : 11'd800;
    wire [9:0] v_active = mode_active ? 10'd600 : 10'd480;
    wire [9:0] v_total = mode_active ? 10'd628 : 10'd525;
    wire [10:0] h_sync_start = mode_active ? 11'd840 : 11'd656;
    wire [10:0] h_sync_end = mode_active ? 11'd968 : 11'd752;
    wire [9:0] v_sync_start = mode_active ? 10'd601 : 10'd490;
    wire [9:0] v_sync_end = mode_active ? 10'd605 : 10'd492;
    wire mode_change = !FIXED_SVGA && mode_sync[1] != mode_active;
    wire frame_boundary = h == 0 && v == v_total-1;
    wire fetch_idle = req_toggle == done_sync[1];
    wire current_ready = bank_ready[v[0]] &&
                         ((v[0] ? tag1 : tag0) == v);
    wire active = running && h < h_active && v < v_active;
    wire [9:0] read_index = {v[0],h[9:1]};
    always @(posedge pixel_clk or posedge reset) begin
        if (reset) pixel_reset_pipe <= 2'b11;
        else pixel_reset_pipe <= {pixel_reset_pipe[0],1'b0};
    end
    // No reset on memory read registers, allowing block RAM inference.
    always @(posedge pixel_clk) begin
        qlo <= ram_lo[read_index];
        qhi <= ram_hi[read_index];
    end
    always @(posedge pixel_clk) begin
        if (pixel_reset) begin
            h <= 0; v <= FIXED_SVGA ? 600 : 480; running <= 0; line_valid <= 0;
            req_toggle <= 0; req_y <= 0; done_sync <= 0; enable_sync <= 0;
            req_words <= FIXED_SVGA ? 400 : 320;
            mode_sync <= FIXED_SVGA ? 2'b11 : 2'b00;
            mode_active <= FIXED_SVGA ? 1'b1 : 1'b0;
            seen_done <= 0; underflow_pixel <= 0; bank_ready <= 0;
            underflow_event_toggle <= 0; underflow_line <= 0;
            active_page_reg <= 0; req_page <= 0; seen_swap <= 0;
            swap_page_sync <= 0; swap_sync <= 0;
            tag0 <= 0; tag1 <= 0;
            hs_d <= 1; vs_d <= 1; de_d <= 0; odd_d <= 0; valid_d <= 0;
            pixel <= 0; hs <= 1; vs <= 1; de <= 0;
        end else begin
            done_sync <= {done_sync[0],done_toggle};
            enable_sync <= {enable_sync[0],display_enable};
            swap_page_sync <= {swap_page_sync[0],swap_page};
            // The page settles before the extra request synchronizer stage.
            // Registers hold page/toggle until this domain acknowledges it.
            swap_sync <= {swap_sync[1:0],swap_toggle};
            mode_sync <= {mode_sync[0],mode_request};
            if (h == h_total-1) begin h <= 0; v <= v == v_total-1 ? 10'd0 : v+10'd1; end
            else h <= h + 1'b1;
            if (done_sync[1] != seen_done) begin
                seen_done <= done_sync[1];
                bank_ready[done_y[0]] <= done_ok;
                if (done_y[0]) tag1 <= done_y; else tag0 <= done_y;
            end
            if (h == 0) begin
                if (frame_boundary && swap_sync[2] != seen_swap && fetch_idle) begin
                    // No old-page AXI line fetch may survive page retirement.
                    seen_swap <= swap_sync[2];
                    active_page_reg <= swap_page_sync[1];
                    req_page <= swap_page_sync[1];
                end else if (frame_boundary) begin
                    req_page <= active_page_reg;
                end
                if (frame_boundary) running <= enable_sync[1];
                if (running && v < v_active) begin
                    line_valid <= current_ready;
                    if (!current_ready) begin
                        underflow_pixel <= 1;
                        underflow_event_toggle <= ~underflow_event_toggle;
                        underflow_line <= v;
                    end
                end
                // Start next-line prefetch at the beginning of the current line.
                if (!(frame_boundary && mode_change) &&
                    ((frame_boundary && enable_sync[1]) || (v < v_active-1 && running))) begin
                    if (fetch_idle) begin
                        req_y <= frame_boundary ? 10'd0 : v+1'b1;
                        req_words <= mode_active ? 9'd400 : 9'd320;
                        req_toggle <= ~req_toggle;
                        if (frame_boundary) bank_ready[0] <= 0;
                        else bank_ready[~v[0]] <= 0;
                    end else underflow_pixel <= 1;
                end
            end
            hs_d <= mode_active ? (h >= h_sync_start && h < h_sync_end) :
                                 !(h >= h_sync_start && h < h_sync_end);
            vs_d <= mode_active ? (v >= v_sync_start && v < v_sync_end) :
                                 !(v >= v_sync_start && v < v_sync_end);
            de_d <= active; odd_d <= h[0];
            valid_d <= h == 0 ? current_ready : line_valid;
            hs <= hs_d; vs <= vs_d; de <= de_d;
            pixel <= de_d && valid_d ? (odd_d ? qhi : qlo) : 16'h0000;
            if (frame_boundary && mode_change && fetch_idle) begin
                // No AXI transaction or live cache tag survives a timing change.
                mode_active <= mode_sync[1];
                h <= 0; v <= mode_sync[1] ? 10'd600 : 10'd480;
                running <= 0; line_valid <= 0; bank_ready <= 0;
            end
            if (hold_pipe[1]) begin
                // PLL relock must not reset the AXI request/completion toggles,
                // page ownership, or the software mode register.
                h <= 0; v <= v_active; running <= 0;
                bank_ready <= 0; line_valid <= 0;
                hs_d <= !mode_active; vs_d <= !mode_active; de_d <= 0;
                hs <= !mode_active; vs <= !mode_active; de <= 0; pixel <= 0;
            end
        end
    end

    localparam WAIT_REQ=0, PREP=1, ADDRESS=2, RECEIVE=3;
    reg [1:0] state;
    reg req_seen, active_toggle, bad_line;
    reg [9:0] fetch_y;
    reg [8:0] word_count, fetch_words;
    // A longer scanout burst reduces AXI address/scheduler overhead. The 4 KiB
    // boundary limiter below still splits a line wherever AXI requires it.
    localparam [9:0] MAX_BURST_WORDS = 10'd64;
    reg [6:0] burst_words, beat;
    wire [10:0] boundary_words = 11'd1024 - {1'b0,araddr[11:2]};
    wire [9:0] remaining = {1'b0,fetch_words} - {1'b0,word_count};
    wire [9:0] proposed = remaining > MAX_BURST_WORDS ? MAX_BURST_WORDS : remaining;
    wire [9:0] write_index = {fetch_y[0],word_count};
    wire beat_error = rresp != 0 || (rlast != (beat == burst_words-1));
    assign arlen = {1'b0,burst_words} - 8'd1;
    assign arvalid = state == ADDRESS;
    assign rready = state == RECEIVE;
    // While asserted, the complete requested scanline owns DDR. Accelerator
    // traffic may finish an accepted burst but must not start another one.
    assign fetch_active = state != WAIT_REQ;
    assign underflow = underflow_sync[1];
    always @(posedge clk) begin
        if (rvalid && rready) begin
            ram_lo[write_index] <= rdata[15:0];
            ram_hi[write_index] <= rdata[31:16];
        end
        if (reset) begin
            req_sync <= 0; underflow_sync <= 0;
            state <= WAIT_REQ; req_seen <= 0; active_toggle <= 0;
            done_toggle <= 0; done_y <= 0; done_ok <= 0;
            fetch_y <= 0; word_count <= 0; araddr <= FB_BASE;
            fetch_words <= 320;
            burst_words <= 0; beat <= 0; bad_line <= 0; read_error <= 0;
            req_page_sync <= 0;
        end else begin
            req_sync <= {req_sync[1:0],req_toggle};
            req_page_sync <= {req_page_sync[0],req_page};
            underflow_sync <= {underflow_sync[0],underflow_pixel};
            case (state)
            WAIT_REQ: if (req_sync[2] != req_seen) begin
                req_seen <= req_sync[2]; active_toggle <= req_sync[2];
                fetch_y <= req_y; word_count <= 0; bad_line <= 0;
                fetch_words <= req_words;
                araddr <= (req_page_sync[1] ? FB_BASE + FB_BYTES : FB_BASE) +
                          req_y * FB_PITCH;
                state <= PREP;
            end
            PREP: begin
                burst_words <= boundary_words < proposed ? boundary_words[6:0] : proposed[6:0];
                beat <= 0; state <= ADDRESS;
            end
            ADDRESS: if (arready) state <= RECEIVE;
            RECEIVE: if (rvalid) begin
                if (beat_error) begin bad_line <= 1; read_error <= 1; end
                word_count <= word_count + 1'b1; beat <= beat + 1'b1;
                if (beat == burst_words-1) begin
                    if (word_count == fetch_words-1) begin
                        done_y <= fetch_y; done_ok <= !bad_line && !beat_error;
                        done_toggle <= active_toggle; state <= WAIT_REQ;
                    end else begin
                        araddr <= araddr + ({25'd0,burst_words} << 2); state <= PREP;
                    end
                end
            end
            default: state <= WAIT_REQ;
            endcase
        end
    end
endmodule
`default_nettype wire
