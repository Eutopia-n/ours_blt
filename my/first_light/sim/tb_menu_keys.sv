`timescale 1ns/1ps
module tb_menu_keys;
    reg clk=0,reset=1;
    reg [3:0] key_n=4'b1111;
    wire [3:0] state;
    always #5 clk=~clk;
    genvar i;
    generate for(i=0;i<4;i=i+1) begin: filters
        key_toggle #(.STABLE_CYCLES(4)) dut(
            .clk(clk),.reset(reset),.key_n(key_n[i]),.state(state[i]));
    end endgenerate
    task cycles(input integer count);
        repeat(count) @(negedge clk);
    endtask
    initial begin
        cycles(3); reset=0;
        // Short noise cannot register as a press.
        key_n[0]=0; cycles(2); key_n[0]=1; cycles(8);
        if(state!==4'b0000) $fatal(1,"KEY0 noise registered");
        key_n[0]=0; cycles(8);
        if(state!==4'b0001) $fatal(1,"KEY0 press missing");
        cycles(12);
        if(state!==4'b0001) $fatal(1,"KEY0 long press repeated");
        key_n[0]=1; cycles(8);
        key_n[0]=0; cycles(8);
        if(state!==4'b0000) $fatal(1,"KEY0 second press missing");
        key_n[0]=1; cycles(8);
        key_n[3:1]=0; cycles(8);
        if(state!==4'b1110) $fatal(1,"KEY1/2/3 independent presses missing");
        reset=1; cycles(2);
        if(state!==4'b0000) $fatal(1,"Reset did not clear key events");
        $display("MENU KEY TEST PASSED");
        $finish;
    end
endmodule
