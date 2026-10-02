// KEY1 is active low. Synchronize it, accept only stable transitions, and
// retain each valid press as a toggle that software can poll between frames.
module key_toggle #(
    parameter integer STABLE_CYCLES = 1500000
) (
    input wire clk,
    input wire reset,
    input wire key_n,
    output reg state,
    output wire down
);
    localparam integer COUNT_WIDTH = STABLE_CYCLES > 1 ? $clog2(STABLE_CYCLES) : 1;
    reg key_meta, key_sync, stable_n;
    assign down = !stable_n;
    reg [COUNT_WIDTH-1:0] count;

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            key_meta <= 1'b1;
            key_sync <= 1'b1;
            stable_n <= 1'b1;
            count <= 0;
            state <= 1'b0;
        end else begin
            key_meta <= key_n;
            key_sync <= key_meta;
            if (key_sync == stable_n) begin
                count <= 0;
            end else if (count == STABLE_CYCLES-1) begin
                stable_n <= key_sync;
                count <= 0;
                if (!key_sync) state <= ~state;
            end else begin
                count <= count + 1'b1;
            end
        end
    end
endmodule
