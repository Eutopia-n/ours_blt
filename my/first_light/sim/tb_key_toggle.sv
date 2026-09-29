`timescale 1ns/1ps
module tb_key_toggle;
    reg clk=0, reset=1, key_n=1;
    wire state;
    always #5 clk=~clk;
    key_toggle #(.STABLE_CYCLES(4)) dut(.clk(clk),.reset(reset),.key_n(key_n),.state(state));

    task cycles(input integer n);
        repeat(n) @(negedge clk);
    endtask
    task expect_state(input bit wanted);
        if(state!==wanted) $fatal(1,"KEY1 state=%b expected=%b",state,wanted);
    endtask
    initial begin
        cycles(2); expect_state(0); reset=0;
        // A short low pulse and contact bounce must not count as a press.
        key_n=0; cycles(2); key_n=1; cycles(5); expect_state(0);
        key_n=0; cycles(1); key_n=1; cycles(1); key_n=0;
        cycles(7); expect_state(1);
        // Holding the button cannot generate more events.
        cycles(20); expect_state(1);
        key_n=1; cycles(7); expect_state(1);
        key_n=0; cycles(7); expect_state(0);
        // An incomplete release cannot arm a second press.
        key_n=1; cycles(2); key_n=0; cycles(7); expect_state(0);
        reset=1; cycles(1); expect_state(0);
        key_n=1; reset=0; cycles(7); expect_state(0);
        $display("KEY TOGGLE TEST PASSED"); $finish;
    end
endmodule
