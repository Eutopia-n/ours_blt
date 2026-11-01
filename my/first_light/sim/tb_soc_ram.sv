`timescale 1ns/1ps
// The runner extracts the actual public RAM module and decoder expression
// from each checked-in SoC model; no replacement memory implementation.
module tb_soc_ram;
    reg clk=0,reset=1,valid=0,write=0,ready=1;
    reg [31:0] address=32'hf9000000,data=0;
    reg [3:0] mask=15,tag=0;
    wire selected,cmd_ready,rsp_valid;
    wire [31:0] rsp_data;
    wire [3:0] rsp_context;
    always #5 clk=~clk;
    ocr_test_wrapper dut(clk,reset,address,valid,write,data,mask,tag,
                         ready,selected,cmd_ready,rsp_valid,rsp_data,rsp_context);

    task automatic access(input [16:0] offset,input bit wr,input [31:0] value,
                          input [3:0] strobes,input [31:0] expected,input integer stall);
        reg [31:0] held;
        begin
            @(negedge clk);
            address=32'hf9000000+offset; valid=1; write=wr; data=value;
            mask=strobes; tag=offset[5:2]; ready=(stall==0);
            @(posedge clk);
            if(!selected || !cmd_ready) $fatal(1,"Request not accepted at %h",address);
            #1;
            if(!rsp_valid || rsp_context!==tag) $fatal(1,"Invalid response at %h",address);
            if(!wr && rsp_data!==expected) $fatal(1,"Read %h: got %h expected %h",address,rsp_data,expected);
            held=rsp_data;
            @(negedge clk); valid=0;
            repeat(stall) begin
                @(posedge clk); #1;
                if(!rsp_valid || cmd_ready || rsp_data!==held || rsp_context!==tag)
                    $fatal(1,"Response changed under backpressure");
            end
            @(negedge clk); ready=1;
            @(posedge clk); #1;
            if(rsp_valid) $fatal(1,"Response did not retire");
        end
    endtask

    initial begin
        repeat(3) @(negedge clk); reset=0;
        access(17'h00000,0,0,15,`OCR_INITIAL_WORD,0);
        access(17'h10000,0,0,15,0,0);
        access(17'h1fffc,0,0,15,0,3);
        access(17'h00000,1,32'h01234567,15,0,0);
        access(17'h10000,1,32'h89abcdef,15,0,0);
        access(17'h0fffc,1,32'h13579bdf,15,0,0);
        access(17'h1fffc,1,32'h2468ace0,15,0,0);
        access(17'h00000,0,0,15,32'h01234567,0);
        access(17'h10000,0,0,15,32'h89abcdef,5);
        access(17'h0fffc,0,0,15,32'h13579bdf,0);
        access(17'h1fffc,0,0,15,32'h2468ace0,0);
        access(17'h10000,1,32'h11223344,4'b0101,0,0);
        access(17'h10000,0,0,15,32'h8922cd44,0);
        access(17'h10000,1,32'hffffffff,0,0,0);
        access(17'h10000,0,0,15,32'h8922cd44,0);
        // Exercise every word, including all high address bits, before reading.
        for(integer n=0;n<32768;n++)
            access(n*4,1,32'hb10c0000^n,15,0,0);
        for(integer n=0;n<32768;n++)
            access(n*4,0,0,15,32'hb10c0000^n,(n%4096)==0 ? 3 : 0);
        @(negedge clk); address=32'hf8ffffff; #1;
        if(selected) $fatal(1,"Decoder accepted below OCR");
        address=32'hf9020000; #1;
        if(selected) $fatal(1,"Decoder accepted past OCR");
        address=32'hf901ffff; #1;
        if(!selected) $fatal(1,"Decoder rejected last OCR byte");
        @(negedge clk); reset=1;
        repeat(2) @(negedge clk); reset=0;
        access(17'h10000,0,0,15,32'hb10c4000,0);
        $display("OCR128 TEST PASSED: all 32768 words; no 64KiB alias; byte masks; zero mask; backpressure; decoder bounds; reset");
        $finish;
    end
    initial begin #10000000; $fatal(1,"OCR128 test timeout"); end
endmodule
