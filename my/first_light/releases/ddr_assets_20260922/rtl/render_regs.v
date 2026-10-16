// APB3 control interface at the existing Sapphire IO_APB_SLAVE_0_INPUT.
`default_nettype none
module render_regs (
    input wire clk, reset,
    input wire [15:0] paddr, input wire psel, penable, pwrite,
    input wire [31:0] pwdata,
    output reg [31:0] prdata, output wire pready, output wire pslverror,
    input wire memory_ready, busy, done, error,
    input wire [31:0] cycles,
    input wire video_underflow, video_error, display_page_active, swap_ack,
    input wire [15:0] video_width, video_height,
    input wire video_mode_valid,
    output reg start, output reg display_enable,
    output reg [1:0] operation, output reg [31:0] src, dst, stride, src_stride,
    output reg draw_page, output reg swap_page, output reg swap_toggle,
    output reg [15:0] width, height, color
);
    wire transfer = psel && penable;
    wire wr = transfer && pwrite;
    wire swap_pending = swap_toggle != swap_ack;
    wire known = paddr == 0 || paddr == 4 || paddr == 8 || paddr == 12 ||
        paddr == 16 || paddr == 20 || paddr == 24 || paddr == 28 ||
        paddr == 32 || paddr == 36 || paddr == 40 || paddr == 44 ||
        paddr == 48 || paddr == 52 || paddr == 56 || paddr == 60 ||
        paddr == 64 || paddr == 68 || paddr == 72 || paddr == 76;
    wire writable = paddr == 8 || paddr == 12 || paddr == 16 || paddr == 20 ||
        paddr == 24 || paddr == 28 || paddr == 32 || paddr == 48 || paddr == 52 ||
        paddr == 56 || paddr == 60 || paddr == 64 || paddr == 76;
    assign pready = 1'b1;
    assign pslverror = transfer && (!known || paddr[1:0] != 0 ||
        (pwrite && (!writable || busy || start ||
         (swap_pending && (paddr == 60 || paddr == 64 || paddr == 8)) ||
         (paddr == 8 && pwdata != 1) || (paddr == 32 && pwdata > 1) ||
         (paddr == 48 && pwdata > 1) || (paddr == 56 && pwdata > 1) ||
         (paddr == 60 && pwdata > 1) || (paddr == 64 && pwdata != 1))));
    always @* begin
        case (paddr)
        0: prdata = 32'h32444631; // "2DF1"
        4: prdata = {24'd0,swap_pending,display_page_active,video_error,video_underflow,
                     memory_ready,error,done,busy};
        8: prdata = 0;
        12: prdata = dst;
        16: prdata = {16'd0,width};
        20: prdata = {16'd0,height};
        24: prdata = stride;
        28: prdata = {16'd0,color};
        32: prdata = {31'd0,display_enable};
        36: prdata = cycles;
        40: prdata = 32'h01000000;
        44: prdata = 32'd1280;
        48: prdata = {30'd0,operation};
        52: prdata = src;
        56: prdata = {31'd0,draw_page};
        60: prdata = {31'd0,swap_page};
        64: prdata = {31'd0,swap_toggle};
        68: prdata = {video_height,video_width};
        72: prdata = {31'd0,video_mode_valid};
        76: prdata = src_stride;
        default: prdata = 0;
        endcase
    end
    always @(posedge clk) begin
        if (reset) begin
            start <= 0; display_enable <= 0;
            operation <= 0; src <= 32'h01000000; dst <= 32'h01000000; stride <= 1280;
            src_stride <= 1280; // Preserve old framebuffer-only firmware.
            draw_page <= 0; swap_page <= 0; swap_toggle <= 0;
            width <= 0; height <= 0; color <= 0;
        end else begin
            start <= 0;
            if (wr && !pslverror) case (paddr)
            8: start <= 1;
            12: dst <= pwdata;
            16: width <= pwdata[15:0];
            20: height <= pwdata[15:0];
            24: stride <= pwdata;
            28: color <= pwdata[15:0];
            32: display_enable <= pwdata[0];
            48: operation <= pwdata[1:0];
            52: src <= pwdata;
            56: draw_page <= pwdata[0];
            60: swap_page <= pwdata[0];
            64: swap_toggle <= ~swap_toggle;
            76: src_stride <= pwdata;
            default: ;
            endcase
        end
    end
endmodule
`default_nettype wire
