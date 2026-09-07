`timescale 1ns/1ps

// Solid Fill command generator.
//
// A command produces one write request per pixel.  Addresses are byte
// addresses.  Rows may contain padding, described by line_stride_bytes.
// The ready/valid output is deliberately independent of AXI so that a later
// adapter can packetize requests into bursts without changing this module.
module blt_solid_fill #(
    parameter ADDR_WIDTH  = 32,
    parameter PIXEL_WIDTH = 32,
    parameter SIZE_WIDTH  = 16,
    parameter PIXEL_BYTES = 4
) (
    input  wire                     clk,
    input  wire                     rst,

    input  wire                     start,
    output wire                     cmd_ready,
    input  wire [ADDR_WIDTH-1:0]    base_addr,
    input  wire [ADDR_WIDTH-1:0]    line_stride_bytes,
    input  wire [SIZE_WIDTH-1:0]    width_px,
    input  wire [SIZE_WIDTH-1:0]    height_px,
    input  wire [PIXEL_WIDTH-1:0]   color,

    output reg                      busy,
    output reg                      done,
    output reg                      invalid_cmd,

    output reg                      wr_valid,
    input  wire                     wr_ready,
    output reg  [ADDR_WIDTH-1:0]    wr_addr,
    output wire [PIXEL_WIDTH-1:0]   wr_data,
    output wire                     wr_last
);

    reg [ADDR_WIDTH-1:0]  stride_reg;
    reg [ADDR_WIDTH-1:0]  row_base_reg;
    reg [SIZE_WIDTH-1:0]  width_reg;
    reg [SIZE_WIDTH-1:0]  height_reg;
    reg [SIZE_WIDTH-1:0]  x_reg;
    reg [SIZE_WIDTH-1:0]  y_reg;
    reg [PIXEL_WIDTH-1:0] color_reg;

    wire last_column;
    wire last_row;
    wire write_accept;

    assign cmd_ready    = ~busy;
    assign wr_data      = color_reg;
    assign last_column  = (x_reg == (width_reg - 1'b1));
    assign last_row     = (y_reg == (height_reg - 1'b1));
    assign wr_last      = wr_valid && last_column && last_row;
    assign write_accept = wr_valid && wr_ready;

    always @(posedge clk) begin
        if (rst) begin
            busy          <= 1'b0;
            done          <= 1'b0;
            invalid_cmd   <= 1'b0;
            wr_valid      <= 1'b0;
            wr_addr       <= {ADDR_WIDTH{1'b0}};
            stride_reg    <= {ADDR_WIDTH{1'b0}};
            row_base_reg  <= {ADDR_WIDTH{1'b0}};
            width_reg     <= {SIZE_WIDTH{1'b0}};
            height_reg    <= {SIZE_WIDTH{1'b0}};
            x_reg         <= {SIZE_WIDTH{1'b0}};
            y_reg         <= {SIZE_WIDTH{1'b0}};
            color_reg     <= {PIXEL_WIDTH{1'b0}};
        end else begin
            done        <= 1'b0;
            invalid_cmd <= 1'b0;

            if (!busy) begin
                wr_valid <= 1'b0;

                if (start) begin
                    if ((width_px == {SIZE_WIDTH{1'b0}}) ||
                        (height_px == {SIZE_WIDTH{1'b0}})) begin
                        done        <= 1'b1;
                        invalid_cmd <= 1'b1;
                    end else begin
                        busy         <= 1'b1;
                        wr_valid     <= 1'b1;
                        wr_addr      <= base_addr;
                        stride_reg   <= line_stride_bytes;
                        row_base_reg <= base_addr;
                        width_reg    <= width_px;
                        height_reg   <= height_px;
                        x_reg        <= {SIZE_WIDTH{1'b0}};
                        y_reg        <= {SIZE_WIDTH{1'b0}};
                        color_reg    <= color;
                    end
                end
            end else if (write_accept) begin
                if (last_column && last_row) begin
                    busy     <= 1'b0;
                    done     <= 1'b1;
                    wr_valid <= 1'b0;
                end else if (last_column) begin
                    x_reg         <= {SIZE_WIDTH{1'b0}};
                    y_reg         <= y_reg + 1'b1;
                    row_base_reg  <= row_base_reg + stride_reg;
                    wr_addr       <= row_base_reg + stride_reg;
                end else begin
                    x_reg   <= x_reg + 1'b1;
                    wr_addr <= wr_addr + PIXEL_BYTES;
                end
            end
        end
    end

endmodule
