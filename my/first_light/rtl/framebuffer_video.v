// Fixed 640x480 RGB565 scanout. 800x525 totals, negative sync polarity.
// Ping-pong line buffers cross from the AXI clock to the pixel clock.
// Request/completion toggles use two-flop synchronizers; line tags remain
// stable until the opposite side acknowledges the transaction.
`default_nettype none
module framebuffer_video #(
    parameter [31:0] FB_BASE = 32'h01000000,
    parameter [31:0] FB_BYTES = 32'd614400
) (
    input wire clk, reset, pixel_clk, display_enable,
    input wire swap_page, swap_toggle,
    output reg [31:0] araddr, output wire [7:0] arlen,
    output wire arvalid, input wire arready,
    input wire [31:0] rdata, input wire [1:0] rresp,
    input wire rlast, rvalid, output wire rready,
    output reg [15:0] pixel, output reg hs, vs, de,
    output wire active_page, swap_ack,
    output wire underflow, output reg read_error
);
    reg [15:0] ram_lo [0:1023];
    reg [15:0] ram_hi [0:1023];
    reg [15:0] qlo, qhi;
    reg [9:0] h, v;
    reg running, line_valid;
    reg req_toggle;
    reg [8:0] req_y;
    reg done_toggle;
    reg [8:0] done_y;
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
    reg [1:0] bank_ready;
    reg [8:0] tag0, tag1;
    reg hs_d, vs_d, de_d, odd_d, valid_d;
    wire pixel_reset = pixel_reset_pipe[1];
    assign active_page = active_page_reg;
    assign swap_ack = seen_swap;
    wire current_ready = bank_ready[v[0]] &&
                         ((v[0] ? tag1 : tag0) == v[8:0]);
    wire active = running && h < 640 && v < 480;
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
            h <= 0; v <= 480; running <= 0; line_valid <= 0;
            req_toggle <= 0; req_y <= 0; done_sync <= 0; enable_sync <= 0;
            seen_done <= 0; underflow_pixel <= 0; bank_ready <= 0;
            active_page_reg <= 0; req_page <= 0; seen_swap <= 0;
            swap_page_sync <= 0; swap_sync <= 0;
            tag0 <= 0; tag1 <= 0;
            hs_d <= 1; vs_d <= 1; de_d <= 0; odd_d <= 0; valid_d <= 0;
            pixel <= 0; hs <= 1; vs <= 1; de <= 0;
        end else begin
            done_sync <= {done_sync[0],done_toggle};
            enable_sync <= {enable_sync[0],display_enable};
            // A deliberate display pause is the recovery boundary for a
            // transient missed line. Clear only after scanout has stopped;
            // active-frame underflow remains sticky for software diagnostics.
            if (!running && !enable_sync[1]) underflow_pixel <= 0;
            swap_page_sync <= {swap_page_sync[0],swap_page};
            // The page settles before the extra request synchronizer stage.
            // Registers hold page/toggle until this domain acknowledges it.
            swap_sync <= {swap_sync[1:0],swap_toggle};
            if (h == 799) begin h <= 0; v <= v == 524 ? 10'd0 : v+10'd1; end
            else h <= h + 1'b1;
            if (done_sync[1] != seen_done) begin
                seen_done <= done_sync[1];
                bank_ready[done_y[0]] <= done_ok;
                if (done_y[0]) tag1 <= done_y; else tag0 <= done_y;
            end
            if (h == 0) begin
                if (v == 524 && swap_sync[2] != seen_swap && req_toggle == done_sync[1]) begin
                    // No old-page AXI line fetch may survive page retirement.
                    seen_swap <= swap_sync[2];
                    active_page_reg <= swap_page_sync[1];
                    req_page <= swap_page_sync[1];
                end else if (v == 524) begin
                    req_page <= active_page_reg;
                end
                if (v == 524) running <= enable_sync[1];
                if (running && v < 480) begin
                    line_valid <= current_ready;
                    if (!current_ready) underflow_pixel <= 1;
                end
                // Start next-line prefetch at the beginning of the current line.
                if ((v == 524 && enable_sync[1]) || (v < 479 && running)) begin
                    if (req_toggle == done_sync[1]) begin
                        req_y <= v == 524 ? 9'd0 : v[8:0]+1'b1;
                        req_toggle <= ~req_toggle;
                        if (v == 524) bank_ready[0] <= 0;
                        else bank_ready[~v[0]] <= 0;
                    end else underflow_pixel <= 1;
                end
            end
            hs_d <= !(h >= 656 && h < 752);
            vs_d <= !(v >= 490 && v < 492);
            de_d <= active; odd_d <= h[0];
            valid_d <= h == 0 ? current_ready : line_valid;
            hs <= hs_d; vs <= vs_d; de <= de_d;
            pixel <= de_d && valid_d ? (odd_d ? qhi : qlo) : 16'h0000;
        end
    end

    localparam WAIT_REQ=0, PREP=1, ADDRESS=2, RECEIVE=3;
    reg [1:0] state;
    reg req_seen, active_toggle, bad_line;
    reg [8:0] fetch_y, word_count;
    reg [4:0] burst_words, beat;
    wire [10:0] boundary_words = 11'd1024 - {1'b0,araddr[11:2]};
    wire [9:0] remaining = 10'd320 - {1'b0,word_count};
    wire [9:0] proposed = remaining > 16 ? 10'd16 : remaining;
    wire [9:0] write_index = {fetch_y[0],word_count};
    wire beat_error = rresp != 0 || (rlast != (beat == burst_words-1));
    assign arlen = {3'd0,burst_words} - 8'd1;
    assign arvalid = state == ADDRESS;
    assign rready = state == RECEIVE;
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
                araddr <= (req_page_sync[1] ? FB_BASE + FB_BYTES : FB_BASE) +
                          ({23'd0,req_y} << 10) + ({23'd0,req_y} << 8);
                state <= PREP;
            end
            PREP: begin
                burst_words <= boundary_words < proposed ? boundary_words[4:0] : proposed[4:0];
                beat <= 0; state <= ADDRESS;
            end
            ADDRESS: if (arready) state <= RECEIVE;
            RECEIVE: if (rvalid) begin
                if (beat_error) begin bad_line <= 1; read_error <= 1; end
                word_count <= word_count + 1'b1; beat <= beat + 1'b1;
                if (beat == burst_words-1) begin
                    if (word_count == 319) begin
                        done_y <= fetch_y; done_ok <= !bad_line && !beat_error;
                        done_toggle <= active_toggle; state <= WAIT_REQ;
                    end else begin
                        araddr <= araddr + ({27'd0,burst_words} << 2); state <= PREP;
                    end
                end
            end
            default: state <= WAIT_REQ;
            endcase
        end
    end
endmodule
`default_nettype wire
