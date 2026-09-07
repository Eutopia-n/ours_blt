`timescale 1ns/1ps

// Block Copy command generator.
//
// This correctness-first implementation keeps at most one read outstanding.
// It uses independent ready/valid channels for the read request, read response,
// and write request.  A later AXI adapter may combine sequential requests into
// bursts without changing the command-level behavior of this module.
module blt_block_copy #(
    parameter ADDR_WIDTH  = 32,
    parameter PIXEL_WIDTH = 32,
    parameter SIZE_WIDTH  = 16,
    parameter PIXEL_BYTES = 4
) (
    input  wire                    clk,
    input  wire                    rst,

    input  wire                    start,
    output wire                    cmd_ready,
    input  wire [ADDR_WIDTH-1:0]   src_base_addr,
    input  wire [ADDR_WIDTH-1:0]   dst_base_addr,
    input  wire [ADDR_WIDTH-1:0]   src_stride_bytes,
    input  wire [ADDR_WIDTH-1:0]   dst_stride_bytes,
    input  wire [SIZE_WIDTH-1:0]   width_px,
    input  wire [SIZE_WIDTH-1:0]   height_px,

    output reg                     busy,
    output reg                     done,
    output reg                     invalid_cmd,

    output reg                     rd_valid,
    input  wire                    rd_ready,
    output reg  [ADDR_WIDTH-1:0]   rd_addr,

    input  wire                    rd_data_valid,
    output wire                    rd_data_ready,
    input  wire [PIXEL_WIDTH-1:0]  rd_data,

    output reg                     wr_valid,
    input  wire                    wr_ready,
    output reg  [ADDR_WIDTH-1:0]   wr_addr,
    output wire [PIXEL_WIDTH-1:0]  wr_data,
    output wire                    wr_last
);

    localparam STATE_IDLE      = 2'd0;
    localparam STATE_READ_REQ  = 2'd1;
    localparam STATE_READ_DATA = 2'd2;
    localparam STATE_WRITE     = 2'd3;

    reg [1:0] state;

    reg [ADDR_WIDTH-1:0] src_stride_reg;
    reg [ADDR_WIDTH-1:0] dst_stride_reg;
    reg [ADDR_WIDTH-1:0] src_row_base_reg;
    reg [ADDR_WIDTH-1:0] dst_row_base_reg;
    reg [SIZE_WIDTH-1:0] width_reg;
    reg [SIZE_WIDTH-1:0] height_reg;
    reg [SIZE_WIDTH-1:0] x_reg;
    reg [SIZE_WIDTH-1:0] y_reg;
    reg [PIXEL_WIDTH-1:0] pixel_reg;

    wire last_column;
    wire last_row;
    wire read_request_accept;
    wire read_data_accept;
    wire write_accept;

    assign cmd_ready           = (state == STATE_IDLE);
    assign rd_data_ready       = (state == STATE_READ_DATA);
    assign wr_data             = pixel_reg;
    assign last_column         = (x_reg == (width_reg - 1'b1));
    assign last_row            = (y_reg == (height_reg - 1'b1));
    assign wr_last             = wr_valid && last_column && last_row;
    assign read_request_accept = rd_valid && rd_ready;
    assign read_data_accept    = rd_data_valid && rd_data_ready;
    assign write_accept        = wr_valid && wr_ready;

    always @(posedge clk) begin
        if (rst) begin
            state             <= STATE_IDLE;
            busy              <= 1'b0;
            done              <= 1'b0;
            invalid_cmd       <= 1'b0;
            rd_valid          <= 1'b0;
            rd_addr           <= {ADDR_WIDTH{1'b0}};
            wr_valid          <= 1'b0;
            wr_addr           <= {ADDR_WIDTH{1'b0}};
            src_stride_reg    <= {ADDR_WIDTH{1'b0}};
            dst_stride_reg    <= {ADDR_WIDTH{1'b0}};
            src_row_base_reg  <= {ADDR_WIDTH{1'b0}};
            dst_row_base_reg  <= {ADDR_WIDTH{1'b0}};
            width_reg         <= {SIZE_WIDTH{1'b0}};
            height_reg        <= {SIZE_WIDTH{1'b0}};
            x_reg             <= {SIZE_WIDTH{1'b0}};
            y_reg             <= {SIZE_WIDTH{1'b0}};
            pixel_reg         <= {PIXEL_WIDTH{1'b0}};
        end else begin
            done        <= 1'b0;
            invalid_cmd <= 1'b0;

            case (state)
                STATE_IDLE: begin
                    busy     <= 1'b0;
                    rd_valid <= 1'b0;
                    wr_valid <= 1'b0;

                    if (start) begin
                        if ((width_px == {SIZE_WIDTH{1'b0}}) ||
                            (height_px == {SIZE_WIDTH{1'b0}})) begin
                            done        <= 1'b1;
                            invalid_cmd <= 1'b1;
                        end else begin
                            state             <= STATE_READ_REQ;
                            busy              <= 1'b1;
                            rd_valid          <= 1'b1;
                            rd_addr           <= src_base_addr;
                            wr_addr           <= dst_base_addr;
                            src_stride_reg    <= src_stride_bytes;
                            dst_stride_reg    <= dst_stride_bytes;
                            src_row_base_reg  <= src_base_addr;
                            dst_row_base_reg  <= dst_base_addr;
                            width_reg         <= width_px;
                            height_reg        <= height_px;
                            x_reg             <= {SIZE_WIDTH{1'b0}};
                            y_reg             <= {SIZE_WIDTH{1'b0}};
                        end
                    end
                end

                STATE_READ_REQ: begin
                    if (read_request_accept) begin
                        rd_valid <= 1'b0;
                        state    <= STATE_READ_DATA;
                    end
                end

                STATE_READ_DATA: begin
                    if (read_data_accept) begin
                        pixel_reg <= rd_data;
                        wr_valid  <= 1'b1;
                        state     <= STATE_WRITE;
                    end
                end

                STATE_WRITE: begin
                    if (write_accept) begin
                        wr_valid <= 1'b0;

                        if (last_column && last_row) begin
                            state <= STATE_IDLE;
                            busy  <= 1'b0;
                            done  <= 1'b1;
                        end else begin
                            state    <= STATE_READ_REQ;
                            rd_valid <= 1'b1;

                            if (last_column) begin
                                x_reg             <= {SIZE_WIDTH{1'b0}};
                                y_reg             <= y_reg + 1'b1;
                                src_row_base_reg  <= src_row_base_reg + src_stride_reg;
                                dst_row_base_reg  <= dst_row_base_reg + dst_stride_reg;
                                rd_addr           <= src_row_base_reg + src_stride_reg;
                                wr_addr           <= dst_row_base_reg + dst_stride_reg;
                            end else begin
                                x_reg   <= x_reg + 1'b1;
                                rd_addr <= rd_addr + PIXEL_BYTES;
                                wr_addr <= wr_addr + PIXEL_BYTES;
                            end
                        end
                    end
                end

                default: begin
                    state    <= STATE_IDLE;
                    busy     <= 1'b0;
                    rd_valid <= 1'b0;
                    wr_valid <= 1'b0;
                end
            endcase
        end
    end

endmodule
