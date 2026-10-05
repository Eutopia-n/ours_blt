`timescale 1ns/1ps
module tb_embedded_rom;
    reg clk=0,reset=1;
    always #5 clk=~clk;
    reg [15:0] paddr=0;
    reg psel=0,penable=0,pwrite=0;
    reg [31:0] pwdata=0;
    wire [31:0] prdata;
    wire pready,pslverror;
    reg [31:0] expected[0:4095];
    render_regs dut(.clk(clk),.reset(reset),.paddr(paddr),.psel(psel),.penable(penable),
        .pwrite(pwrite),.pwdata(pwdata),.prdata(prdata),.pready(pready),.pslverror(pslverror),
        .memory_ready(1'b1),.busy(1'b0),.done(1'b0),.error(1'b0),.cycles(32'd0),
        .video_underflow(1'b0),.video_error(1'b0),
        .video_underflow_count(32'd0),.video_underflow_line(16'd0),
        .clock_diagnostic(32'd0),
        .display_page_active(1'b0),.swap_ack(1'b0),
        .video_width(16'd640),.video_height(16'd480),.video_mode_valid(1'b1),.key2_down(1'b0),
        .mode_active(1'b0),.clock_ready(1'b1),.mode_request(),.start(),.display_enable(),
        .operation(),.src(),.dst(),.stride(),.src_stride(),.draw_page(),.swap_page(),
        .swap_toggle(),.width(),.height(),.color(),.alpha_opacity(),.alpha_key_enable());
    task access(input [15:0] addr,input write,input err,input [31:0] value);
        @(negedge clk); paddr=addr; psel=1; pwrite=write;
        @(negedge clk); penable=1; #1;
        if(!pready || pslverror!==err) $fatal(1,"APB response at %h",addr);
        if(!write && !err && prdata!==value) $fatal(1,"ROM data at %h",addr);
        @(negedge clk); psel=0; penable=0; pwrite=0;
    endtask
    initial begin
        $readmemh("software/build/embedded_app.memh",expected);
        repeat(3) @(negedge clk); reset=0;
        for(integer n=0;n<4096;n=n+1) access(16'h8000+n*4,0,0,expected[n]);
        access(16'h8000,1,1,0); // ROM writes are rejected.
        access(16'h8000,0,0,expected[0]);
        access(16'h8002,0,1,0); // Misaligned address.
        access(16'hc000,0,1,0); // Outside the ROM window.
        access(16'h0000,0,0,32'h32444631); // Existing APB registers still decode.
        $display("EMBEDDED ROM TEST PASSED: all words, read-only, alignment and address boundary");
        $finish;
    end
endmodule
