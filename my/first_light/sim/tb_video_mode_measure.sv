`timescale 1ns/1ps
module tb_video_mode_measure;
    reg pixel_clk=0, reset=1, hs=1, vs=1, de=0;
    wire [15:0] width, height;
    wire valid, update_toggle;
    always #5 pixel_clk=~pixel_clk;

    video_mode_measure dut(.*);

    task clocks(input integer count);
        repeat(count) @(posedge pixel_clk);
    endtask
    task emit_line(input integer active_pixels);
        @(negedge pixel_clk); de=active_pixels!=0;
        clocks(active_pixels);
        @(negedge pixel_clk); de=0;
        clocks(2);
        @(negedge pixel_clk); hs=0;
        clocks(2);
        @(negedge pixel_clk); hs=1;
        clocks(2);
    endtask
    task emit_frame(input integer active_width,input integer active_height);
        integer row;
        begin
            for(row=0;row<active_height;row=row+1) emit_line(active_width);
            repeat(3) emit_line(0);
            @(negedge pixel_clk); vs=0;
            clocks(2);
            @(negedge pixel_clk); vs=1;
            clocks(4);
        end
    endtask
    task expect_mode(input [15:0] expected_width,input [15:0] expected_height,
                     input expected_valid,input previous_toggle);
        begin
            if(update_toggle===previous_toggle) $fatal(1,"Missing frame update toggle");
            if(width!==expected_width || height!==expected_height || valid!==expected_valid)
                $fatal(1,"Mode got %0dx%0d valid=%0d expected %0dx%0d valid=%0d",
                       width,height,valid,expected_width,expected_height,expected_valid);
        end
    endtask

    reg old_toggle;
    initial begin
        clocks(4); @(negedge pixel_clk); reset=0;

        old_toggle=update_toggle;
        emit_frame(640,480);
        expect_mode(640,480,1,old_toggle);
        $display("PASS: normal 640x480 raster");

        old_toggle=update_toggle;
        emit_frame(1,1);
        expect_mode(1,1,1,old_toggle);
        $display("PASS: boundary 1x1 raster");

        old_toggle=update_toggle;
        emit_frame(0,0);
        expect_mode(0,0,0,old_toggle);
        $display("PASS: empty raster is invalid");

        $display("ALL VIDEO MODE TESTS PASSED");
        $finish;
    end
    initial begin #10000000; $fatal(1,"Global timeout"); end
endmodule
