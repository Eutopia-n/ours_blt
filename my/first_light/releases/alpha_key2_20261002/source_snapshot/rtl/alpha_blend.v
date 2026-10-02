// Two RGB565 pixels. Opacity 0..256; round each colour channel independently.
// Two registered arithmetic stages; the caller retains inputs until accepted
// and consumes out_valid before starting another word (no output backpressure).
`ifndef ALPHA_BLEND_V
`define ALPHA_BLEND_V
`default_nettype none
module alpha_blend (
    input wire clk, reset, in_valid,
    input wire [31:0] foreground, background,
    input wire [8:0] opacity,
    output reg out_valid,
    output wire [31:0] result
);
    wire [8:0] inverse = 9'd256 - opacity;
    reg valid_product;
    always @(posedge clk) begin
        if (reset) begin valid_product <= 0; out_valid <= 0; end
        else begin valid_product <= in_valid; out_valid <= valid_product; end
    end
    genvar p;
    generate for (p=0;p<2;p=p+1) begin: pixel
        reg [13:0] fr, fb, br, bb;
        reg [14:0] fg, bg;
        reg [14:0] red, blue;
        reg [15:0] green;
        always @(posedge clk) begin
            if (in_valid) begin
                fr <= foreground[p*16+11+:5] * opacity;
                fg <= foreground[p*16+5+:6] * opacity;
                fb <= foreground[p*16+:5] * opacity;
                br <= background[p*16+11+:5] * inverse;
                bg <= background[p*16+5+:6] * inverse;
                bb <= background[p*16+:5] * inverse;
            end
            if (valid_product) begin
                red <= {1'b0,fr} + {1'b0,br} + 15'd128;
                green <= {1'b0,fg} + {1'b0,bg} + 16'd128;
                blue <= {1'b0,fb} + {1'b0,bb} + 15'd128;
            end
        end
        assign result[p*16+:16] = {red[12:8],green[13:8],blue[12:8]};
    end endgenerate
endmodule
`default_nettype wire
`endif
