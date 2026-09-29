// Small single-clock FIFO used to stage one complete AXI write burst.
// DEPTH must be a power of two and match 1 << ADDR_WIDTH.
`default_nettype none
module sync_fifo #(
    parameter WIDTH = 37,
    parameter DEPTH = 16,
    parameter ADDR_WIDTH = 4
) (
    input wire clk,
    input wire reset,
    input wire clear,
    input wire push,
    input wire [WIDTH-1:0] push_data,
    input wire pop,
    output wire [WIDTH-1:0] pop_data,
    output wire full,
    output wire empty,
    output wire [ADDR_WIDTH:0] level,
    output reg overflow,
    output reg underflow
);
    reg [WIDTH-1:0] mem [0:DEPTH-1];
    reg [ADDR_WIDTH-1:0] write_pointer;
    reg [ADDR_WIDTH-1:0] read_pointer;
    reg [ADDR_WIDTH:0] count;

    wire push_accept = push && !full;
    wire pop_accept = pop && !empty;

    assign pop_data = mem[read_pointer];
    assign full = count == DEPTH;
    assign empty = count == 0;
    assign level = count;

    always @(posedge clk) begin
        if (reset || clear) begin
            write_pointer <= 0;
            read_pointer <= 0;
            count <= 0;
            overflow <= 0;
            underflow <= 0;
        end else begin
            overflow <= push && full;
            underflow <= pop && empty;

            if (push_accept) begin
                mem[write_pointer] <= push_data;
                write_pointer <= write_pointer + 1'b1;
            end
            if (pop_accept)
                read_pointer <= read_pointer + 1'b1;

            case ({push_accept,pop_accept})
            2'b10: count <= count + 1'b1;
            2'b01: count <= count - 1'b1;
            default: count <= count;
            endcase
        end
    end
endmodule
`default_nettype wire
