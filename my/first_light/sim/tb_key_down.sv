`timescale 1ns/1ps
module tb_key_down;
    reg clk=0,reset=1,key_n=1;
    wire state,down;
    always #5 clk=~clk;
    key_toggle #(.STABLE_CYCLES(4)) dut(.*);
    task cycles(input integer n); repeat(n) @(negedge clk); endtask
    initial begin
        cycles(4); reset=0; cycles(4);
        if(down || state) $fatal(1,"Bad idle/reset state");
        key_n=0; cycles(2); key_n=1; cycles(8);
        if(down || state) $fatal(1,"Glitch accepted");
        key_n=0; cycles(8);
        if(!down || !state) $fatal(1,"Missing press/held level");
        cycles(50); if(!down || !state) $fatal(1,"Long hold changed toggle");
        key_n=1; cycles(2); key_n=0; cycles(8);
        if(!down || !state) $fatal(1,"Release bounce accepted");
        key_n=1; cycles(8);
        if(down || !state) $fatal(1,"Release level/toggle incorrect");
        key_n=0; cycles(8);
        if(!down || state) $fatal(1,"Second press missing");
        reset=1; cycles(2); if(down || state) $fatal(1,"Reset failed");
        $display("KEY DOWN TEST PASSED"); $finish;
    end
endmodule
