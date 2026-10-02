`timescale 1ns/1ps
module tb_alpha_blend;
    reg clk=0,reset=1,in_valid=0;
    reg [31:0] foreground=0,background=0;
    reg [8:0] opacity=0;
    wire out_valid;
    wire [31:0] result;
    alpha_blend dut(.*);
    always #5 clk=~clk;
    function automatic [15:0] reference(input [15:0] f,b,input integer a);
        integer r,g,v;
        r=(((f>>11)*a+(b>>11)*(256-a)+128)/256);
        g=((((f>>5)&63)*a+((b>>5)&63)*(256-a)+128)/256);
        v=(((f&31)*a+(b&31)*(256-a)+128)/256);
        reference=(r<<11)|(g<<5)|v;
    endfunction
    reg [31:0] expected[0:16383];
    integer sent=0,received=0;
    always @(posedge clk) begin
        if(!reset && in_valid) begin
            expected[sent]={reference(foreground[31:16],background[31:16],opacity),
                            reference(foreground[15:0],background[15:0],opacity)};
            sent=sent+1;
        end
        #1;
        if(!reset && out_valid) begin
            if(result!==expected[received]) $fatal(1,"Blend %0d: %h != %h",received,result,expected[received]);
            received=received+1;
        end
    end
    initial begin
        repeat(4) @(negedge clk); reset=0;
        repeat(5) begin @(negedge clk); if(out_valid) $fatal(1,"Empty input produced output"); end
        for(integer a=0;a<=256;a++) for(integer n=0;n<16;n++) begin
            @(negedge clk); in_valid=1; opacity=a;
            foreground=$random; background=$random;
            if(n==0) begin foreground=32'hffffffff; background=0; end
            if(n==1) begin foreground=0; background=32'hffffffff; end
        end
        @(negedge clk); in_valid=0;
        repeat(4) @(negedge clk);
        if(received!=sent || sent!=4112) $fatal(1,"Lost blend output");
        in_valid=1; @(negedge clk); reset=1; in_valid=0;
        repeat(3) @(negedge clk); reset=0;
        repeat(4) begin @(negedge clk); if(out_valid) $fatal(1,"Reset retained valid output"); end
        $display("ALPHA BLEND TEST PASSED: 4112 pairs, all 257 coefficients, endpoints, bubbles and reset"); $finish;
    end
endmodule
