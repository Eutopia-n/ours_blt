// Active-low board keys. GPIO reads one pending mask; GPIO output bit 0
// toggles to acknowledge it. A short press survives a slow CPU-rendered frame.
`default_nettype none
module button_input #(
    parameter DEBOUNCE_CYCLES = 2000000,
    parameter REPEAT_CYCLES = 12000000,
    parameter ENABLE_REPEAT = 1
) (
    input wire clk,
    input wire reset,
    input wire [3:0] key_n,
    input wire ack_toggle,
    output reg [3:0] pending,
    output wire [3:0] held
);
    reg [3:0] key_meta, key_sync, candidate, stable;
    reg [$clog2(DEBOUNCE_CYCLES+1)-1:0] debounce_count;
    reg [$clog2(REPEAT_CYCLES+1)-1:0] repeat_count;
    reg ack_seen, chord_hold;
    // Live debounced state is separate from retained menu press events.
    assign held = stable;
    wire commit = ~key_sync == candidate && candidate != stable &&
                  debounce_count == DEBOUNCE_CYCLES-1;
    wire single_key = stable == 1 || stable == 2 || stable == 4 || stable == 8;

    always @(posedge clk) begin
        if (reset) begin
            key_meta <= 4'hf; key_sync <= 4'hf;
            candidate <= 0; stable <= 0; pending <= 0;
            debounce_count <= 0; repeat_count <= 0;
            ack_seen <= 0; chord_hold <= 0;
        end else begin
            key_meta <= key_n;
            key_sync <= key_meta;
            ack_seen <= ack_toggle;
            if (ack_toggle != ack_seen) pending <= 0;

            if (~key_sync != candidate) begin
                candidate <= ~key_sync;
                debounce_count <= 0;
            end else if (candidate == stable || commit) debounce_count <= 0;
            else debounce_count <= debounce_count + 1'b1;

            if (commit) begin
                stable <= candidate;
                repeat_count <= 0;
                if (candidate == 0) chord_hold <= 0;
                else if (candidate == 3 || candidate == 12) chord_hold <= 1;
                // Release edges do not create another command from half a chord.
                if ((candidate & ~stable) != 0 &&
                    (pending == 0 || ack_toggle != ack_seen)) pending <= candidate;
            end else if (!ENABLE_REPEAT || !single_key || chord_hold) repeat_count <= 0;
            else if (repeat_count == REPEAT_CYCLES-1) begin
                repeat_count <= 0;
                if (pending == 0 || ack_toggle != ack_seen) pending <= stable;
            end else repeat_count <= repeat_count + 1'b1;
        end
    end
endmodule
`default_nettype wire
