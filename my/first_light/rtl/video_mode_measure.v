// Measure the active raster presented to the HDMI encoder.
// DE counts active pixels, falling HS completes a line, and falling VS
// publishes the completed frame. Results remain stable for a whole frame.
`default_nettype none
module video_mode_measure (
    input wire pixel_clk,
    input wire reset,
    input wire hs,
    input wire vs,
    input wire de,
    output reg [15:0] width,
    output reg [15:0] height,
    output reg valid,
    output reg update_toggle
);
    reg hs_d, vs_d;
    reg [15:0] line_pixels, frame_width, frame_lines;
    wire line_end = hs_d && !hs;
    wire frame_end = vs_d && !vs;
    wire [15:0] counted_pixels = de && line_pixels != 16'hffff ?
        line_pixels + 1'b1 : line_pixels;
    wire line_has_pixels = counted_pixels != 0;
    wire [15:0] completed_width = line_has_pixels && counted_pixels > frame_width ?
        counted_pixels : frame_width;
    wire [15:0] completed_lines = line_has_pixels && frame_lines != 16'hffff ?
        frame_lines + 1'b1 : frame_lines;

    always @(posedge pixel_clk or posedge reset) begin
        if (reset) begin
            hs_d <= 1'b1;
            vs_d <= 1'b1;
            line_pixels <= 0;
            frame_width <= 0;
            frame_lines <= 0;
            width <= 0;
            height <= 0;
            valid <= 0;
            update_toggle <= 0;
        end else begin
            hs_d <= hs;
            vs_d <= vs;
            line_pixels <= counted_pixels;
            if (line_end) begin
                line_pixels <= 0;
                frame_width <= completed_width;
                frame_lines <= completed_lines;
            end
            if (frame_end) begin
                // In a legal raster VS follows the last HS. The conditional
                // also handles a simultaneous final HS/VS in a test source.
                width <= line_end ? completed_width : frame_width;
                height <= line_end ? completed_lines : frame_lines;
                valid <= (line_end ? completed_width : frame_width) != 0 &&
                         (line_end ? completed_lines : frame_lines) != 0;
                update_toggle <= ~update_toggle;
                line_pixels <= 0;
                frame_width <= 0;
                frame_lines <= 0;
            end
        end
    end
endmodule
`default_nettype wire
