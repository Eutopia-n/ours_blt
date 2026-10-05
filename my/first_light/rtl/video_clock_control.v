`ifndef VIDEO_CLOCK_CONTROL_V
`define VIDEO_CLOCK_CONTROL_V
// Reconfigure only HDMI's reference selector. The AXI/CPU clock stays running.
// mode_active changes in pixel blanking after all old line reads have drained.
`default_nettype none
module video_clock_control #(
    parameter integer RESET_CYCLES = 10000,
    parameter integer LOCK_CYCLES = 10000,
    parameter integer DEFAULT_MODE = 0,
    parameter integer FIXED_MODE = 0,
    parameter integer LOCK_TIMEOUT_CYCLES = 1000000
) (
    input wire clk, reset, mode_active, pll_locked,
    output reg [1:0] clock_select,
    output wire pll_reset_n,
    output wire clock_hold,
    output wire clock_ready,
    output wire [7:0] debug_status
);
    localparam RESET_PLL=0, WAIT_LOCK=1, RUN=2;
    reg [1:0] state;
    reg [31:0] count;
    reg target_mode;
    reg [31:0] lock_wait;
    reg [3:0] retries;
    (* async_reg = "true" *) reg [1:0] mode_sync, locked_sync;
    assign pll_reset_n = state != RESET_PLL;
    assign clock_hold = state != RUN;
    assign clock_ready = state == RUN && locked_sync[1] && mode_sync[1] == clock_select[0];
    // [7:4] saturating retry count, [3] PLL lock, [2] ready, [1] hold, [0] reset_n.
    assign debug_status = {retries,locked_sync[1],clock_ready,clock_hold,pll_reset_n};
    always @(posedge clk) begin
        if (reset) begin
            state <= RESET_PLL; count <= 0; clock_select <= DEFAULT_MODE;
            target_mode <= DEFAULT_MODE;
            lock_wait <= 0; retries <= 0;
            mode_sync <= DEFAULT_MODE ? 2'b11 : 2'b00; locked_sync <= 0;
        end else begin
            // A fixed-clock startup must not depend on an unclocked pixel domain.
            mode_sync <= FIXED_MODE ? (DEFAULT_MODE ? 2'b11 : 2'b00) :
                         {mode_sync[0],mode_active};
            locked_sync <= {locked_sync[0],pll_locked};
            case (state)
            RESET_PLL: begin
            clock_select <= {1'b0,target_mode};
            if (count == RESET_CYCLES-1) begin
                count <= 0; lock_wait <= 0; state <= WAIT_LOCK;
            end else count <= count + 1'b1;
            end
            WAIT_LOCK: begin
                lock_wait <= lock_wait + 1'b1;
                if (locked_sync[1] && count == LOCK_CYCLES-1) begin
                    count <= 0; state <= RUN;
                end else if (lock_wait == LOCK_TIMEOUT_CYCLES-1) begin
                    count <= 0; state <= RESET_PLL;
                    if (retries != 4'hf) retries <= retries + 1'b1;
                end else if (!locked_sync[1]) count <= 0;
                else count <= count + 1'b1;
            end
            RUN: if (mode_sync[1] != clock_select[0] || !locked_sync[1]) begin
                target_mode <= mode_sync[1];
                count <= 0; state <= RESET_PLL;
            end
            default: begin state <= RESET_PLL; count <= 0; end
            endcase
        end
    end
endmodule
`default_nettype wire
`endif
