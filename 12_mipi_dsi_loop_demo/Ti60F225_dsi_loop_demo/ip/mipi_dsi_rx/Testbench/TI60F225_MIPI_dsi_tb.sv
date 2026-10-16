// note: this simulation is bypassing HSIO connection and purely for showcasing the pixel data transfer.
`timescale 1ns/1ps

module TI60F225_MIPI_dsi_tb();

logic        i_arstn;
logic        i_fb_clk;
logic        i_sysclk;
logic        i_pll_locked;
logic        i_mipi_clk;
logic        i_mipi_tx_pclk;
logic        i_mipi_tx_pll_locked;
logic        o_lcd_rstn;
logic        o_pll_rstn;
logic        o_mipi_pll_rstn;
logic        i_inject_err;
logic        o_LED16_R;
logic        o_LED16_G;
logic        o_LED16_B;
logic        o_LED17_B;
logic        mipi_dp_clk_LP_P_OUT;
logic        mipi_dp_clk_LP_N_OUT;
logic [7:0]  mipi_dp_clk_HS_OUT;
logic        mipi_dp_clk_HS_OE;
logic        mipi_dp_data3_LP_P_OUT;
logic        mipi_dp_data2_LP_P_OUT;
logic        mipi_dp_data1_LP_P_OUT;
logic        mipi_dp_data0_LP_P_OUT;
logic        mipi_dp_data3_LP_N_OUT;
logic        mipi_dp_data2_LP_N_OUT;
logic        mipi_dp_data1_LP_N_OUT;
logic        mipi_dp_data0_LP_N_OUT;
logic [7:0]  mipi_dp_data0_HS_OUT;
logic [7:0]  mipi_dp_data1_HS_OUT;
logic [7:0]  mipi_dp_data2_HS_OUT;
logic [7:0]  mipi_dp_data3_HS_OUT;
logic        mipi_dp_data3_HS_OE;
logic        mipi_dp_data2_HS_OE;
logic        mipi_dp_data1_HS_OE;
logic        mipi_dp_data0_HS_OE;
logic        mipi_dp_clk_RST;
logic        mipi_dp_data0_RST;
logic        mipi_dp_data1_RST;
logic        mipi_dp_data2_RST;
logic        mipi_dp_data3_RST;
logic        mipi_dp_clk_LP_P_OE;
logic        mipi_dp_clk_LP_N_OE;
logic        mipi_dp_data3_LP_P_OE;
logic        mipi_dp_data3_LP_N_OE;
logic        mipi_dp_data2_LP_P_OE;
logic        mipi_dp_data2_LP_N_OE;
logic        mipi_dp_data1_LP_P_OE;
logic        mipi_dp_data1_LP_N_OE;
logic        mipi_dp_data0_LP_P_OE;
logic        mipi_dp_data0_LP_N_OE;
logic        mipi_dp_data0_LP_P_IN;
logic        mipi_dp_data0_LP_N_IN;
logic        mipi_rx_clk_CLKOUT; 
logic        mipi_rx_clk_LP_P_IN; 
logic        mipi_rx_clk_LP_N_IN;
logic        mipi_rx_clk_HS_ENA; 
logic        mipi_rx_clk_HS_TERM;
logic        mipi_rx_data0_LP_P_IN;
logic        mipi_rx_data0_LP_N_IN;
logic        mipi_rx_data1_LP_P_IN;
logic        mipi_rx_data1_LP_N_IN;
logic        mipi_rx_data2_LP_P_IN;
logic        mipi_rx_data2_LP_N_IN;
logic        mipi_rx_data3_LP_P_IN;
logic        mipi_rx_data3_LP_N_IN;
logic [7:0]  mipi_rx_data0_HS_IN;
logic [7:0]  mipi_rx_data1_HS_IN;
logic [7:0]  mipi_rx_data2_HS_IN;
logic [7:0]  mipi_rx_data3_HS_IN;
logic        mipi_rx_data0_HS_ENA;   
logic        mipi_rx_data1_HS_ENA;
logic        mipi_rx_data2_HS_ENA;
logic        mipi_rx_data3_HS_ENA;           
logic        mipi_rx_data0_HS_TERM;
logic        mipi_rx_data1_HS_TERM;
logic        mipi_rx_data2_HS_TERM;
logic        mipi_rx_data3_HS_TERM;
logic        mipi_rx_data0_FIFO_RD;
logic        mipi_rx_data1_FIFO_RD;
logic        mipi_rx_data2_FIFO_RD;
logic        mipi_rx_data3_FIFO_RD;                         
logic        mipi_rx_data0_FIFO_EMPTY;
logic        mipi_rx_data1_FIFO_EMPTY;
logic        mipi_rx_data2_FIFO_EMPTY;
logic        mipi_rx_data3_FIFO_EMPTY;
logic        mipi_rx_data0_LP_P_OUT;
logic        mipi_rx_data0_LP_P_OE;
logic        mipi_rx_data0_LP_N_OUT;
logic        mipi_rx_data0_LP_N_OE;
logic        mipi_rx_data0_RST;
logic        mipi_rx_data1_RST;
logic        mipi_rx_data2_RST;
logic        mipi_rx_data3_RST;

logic clk100, clk125, clk80, clk25;

// clk generation
    initial begin 
        clk100  = 0;
        clk125  = 0;
        clk80   = 0;
        clk25   = 0;
    end

    always #(10.000ns/2)    clk100  =   ~clk100 ;
    always #(8ns/2)         clk125  =   ~clk125 ;
    always #(12.50ns/2)     clk80   =   ~clk80  ;
    always #(40ns/2)        clk25   =   ~clk25  ;
    
    assign i_mipi_clk       = clk100;
    assign i_fb_clk         = clk25;
    assign i_sysclk         = clk80;
    assign i_mipi_tx_pclk   = clk125;

// reset generation
    initial begin
    $display (" Mipi test: begin @ %0t",$time);
    i_arstn = 0;
    i_pll_locked = 0;
    i_mipi_tx_pll_locked = 0;
    i_inject_err = 1;
    #1ns;
    $display (" Mipi test: reset released @ %0t",$time);
    i_arstn = 1;
    $display (" Mipi test: pll locked @ %0t",$time);
    #1us;
    i_pll_locked = 1;
    i_mipi_tx_pll_locked = 1;

    #2ms;

    $display (" Mipi test: simulation done @ %0t",$time);

    $display (" Mipi test: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
    if (dut.dsichk_inst.o_hsync_match && dut.dsichk_inst.o_vsync_match && dut.dsichk_inst.o_pdata_match) begin
        $display(" Mipi test: RESULT ...... TEST PASSED ^_^ ");
    end
    else begin
        $display(" Mipi test: RESULT ...... TEST FAILED !!!!! ");
    end
    $display (" Mipi test: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");

    $finish;
    end

// // waveform dump
//   initial begin
//     //if ($test$plusargs("dump")) begin
//     $shm_open("test.shm");
//     $shm_probe(TI60F225_MIPI_dsi_tb,"ACMTF");
// //  $dumpfile("verilog.vcd");
// //  $dumpvars();
//     //end
//   end

// top module instantiation
TI60F225_MIPI_dsi dut (
.i_arstn                  (i_arstn                  ),
.i_fb_clk                 (i_fb_clk                 ),
.i_sysclk                 (i_sysclk                 ),
.i_pll_locked             (i_pll_locked             ),
.i_mipi_clk               (i_mipi_clk               ),
.i_mipi_tx_pclk           (i_mipi_tx_pclk           ),
.i_mipi_tx_pll_locked     (i_mipi_tx_pll_locked     ),
.o_lcd_rstn               (o_lcd_rstn               ),
.o_pll_rstn               (o_pll_rstn               ),
.o_mipi_pll_rstn          (o_mipi_pll_rstn          ),
.i_inject_err             (i_inject_err             ),
.o_LED16_R                (o_LED16_R                ),
.o_LED16_G                (o_LED16_G                ),
.o_LED16_B                (o_LED16_B                ),
.o_LED17_B                (o_LED17_B                ),
.mipi_dp_clk_LP_P_OUT     (mipi_dp_clk_LP_P_OUT     ),
.mipi_dp_clk_LP_N_OUT     (mipi_dp_clk_LP_N_OUT     ),
.mipi_dp_clk_HS_OUT       (                         ),
.mipi_dp_clk_HS_OE        (                         ),
.mipi_dp_data3_LP_P_OUT   (mipi_dp_data3_LP_P_OUT   ),
.mipi_dp_data2_LP_P_OUT   (mipi_dp_data2_LP_P_OUT   ),
.mipi_dp_data1_LP_P_OUT   (mipi_dp_data1_LP_P_OUT   ),
.mipi_dp_data0_LP_P_OUT   (mipi_dp_data0_LP_P_OUT   ),
.mipi_dp_data3_LP_N_OUT   (mipi_dp_data3_LP_N_OUT   ),
.mipi_dp_data2_LP_N_OUT   (mipi_dp_data2_LP_N_OUT   ),
.mipi_dp_data1_LP_N_OUT   (mipi_dp_data1_LP_N_OUT   ),
.mipi_dp_data0_LP_N_OUT   (mipi_dp_data0_LP_N_OUT   ),
.mipi_dp_data0_HS_OUT     (mipi_dp_data0_HS_OUT     ),
.mipi_dp_data1_HS_OUT     (mipi_dp_data1_HS_OUT     ),
.mipi_dp_data2_HS_OUT     (mipi_dp_data2_HS_OUT     ),
.mipi_dp_data3_HS_OUT     (mipi_dp_data3_HS_OUT     ),
.mipi_dp_data3_HS_OE      (                         ),
.mipi_dp_data2_HS_OE      (                         ),
.mipi_dp_data1_HS_OE      (                         ),
.mipi_dp_data0_HS_OE      (                         ),
.mipi_dp_clk_RST          (                         ),
.mipi_dp_data0_RST        (                         ),
.mipi_dp_data1_RST        (                         ),
.mipi_dp_data2_RST        (                         ),
.mipi_dp_data3_RST        (                         ),
.mipi_dp_clk_LP_P_OE      (                         ),
.mipi_dp_clk_LP_N_OE      (                         ),
.mipi_dp_data3_LP_P_OE    (                         ),
.mipi_dp_data3_LP_N_OE    (                         ),
.mipi_dp_data2_LP_P_OE    (                         ),
.mipi_dp_data2_LP_N_OE    (                         ),
.mipi_dp_data1_LP_P_OE    (                         ),
.mipi_dp_data1_LP_N_OE    (                         ),
.mipi_dp_data0_LP_P_OE    (                         ),
.mipi_dp_data0_LP_N_OE    (                         ),
.mipi_dp_data0_LP_P_IN    (                         ),
.mipi_dp_data0_LP_N_IN    (                         ),
.mipi_rx_clk_CLKOUT       (i_mipi_tx_pclk           ),
.mipi_rx_clk_LP_P_IN      (mipi_dp_clk_LP_P_OUT     ),
.mipi_rx_clk_LP_N_IN      (mipi_dp_clk_LP_N_OUT     ),
.mipi_rx_clk_HS_ENA       (                         ),
.mipi_rx_clk_HS_TERM      (                         ),
.mipi_rx_data0_LP_P_IN    (mipi_dp_data0_LP_P_OUT   ),
.mipi_rx_data0_LP_N_IN    (mipi_dp_data0_LP_N_OUT   ),
.mipi_rx_data1_LP_P_IN    (mipi_dp_data1_LP_P_OUT   ),
.mipi_rx_data1_LP_N_IN    (mipi_dp_data1_LP_N_OUT   ),
.mipi_rx_data2_LP_P_IN    (mipi_dp_data2_LP_P_OUT   ),
.mipi_rx_data2_LP_N_IN    (mipi_dp_data2_LP_N_OUT   ),
.mipi_rx_data3_LP_P_IN    (mipi_dp_data3_LP_P_OUT   ),
.mipi_rx_data3_LP_N_IN    (mipi_dp_data3_LP_N_OUT   ),
.mipi_rx_data0_HS_IN      (mipi_dp_data0_HS_OUT     ),
.mipi_rx_data1_HS_IN      (mipi_dp_data1_HS_OUT     ),
.mipi_rx_data2_HS_IN      (mipi_dp_data2_HS_OUT     ),
.mipi_rx_data3_HS_IN      (mipi_dp_data3_HS_OUT     ),
.mipi_rx_data0_HS_ENA     (                         ),
.mipi_rx_data1_HS_ENA     (                         ),
.mipi_rx_data2_HS_ENA     (                         ),
.mipi_rx_data3_HS_ENA     (                         ),
.mipi_rx_data0_HS_TERM    (                         ),
.mipi_rx_data1_HS_TERM    (                         ),
.mipi_rx_data2_HS_TERM    (                         ),
.mipi_rx_data3_HS_TERM    (                         ),
.mipi_rx_data0_FIFO_RD    (                         ),
.mipi_rx_data1_FIFO_RD    (                         ),
.mipi_rx_data2_FIFO_RD    (                         ),
.mipi_rx_data3_FIFO_RD    (                         ),     
.mipi_rx_data0_FIFO_EMPTY (                         ),
.mipi_rx_data1_FIFO_EMPTY (                         ),
.mipi_rx_data2_FIFO_EMPTY (                         ),
.mipi_rx_data3_FIFO_EMPTY (                         ),
.mipi_rx_data0_LP_P_OUT   (                         ),
.mipi_rx_data0_LP_P_OE    (                         ),
.mipi_rx_data0_LP_N_OUT   (                         ),
.mipi_rx_data0_LP_N_OE    (                         ),
.mipi_rx_data0_RST        (                         ),
.mipi_rx_data1_RST        (                         ),
.mipi_rx_data2_RST        (                         ),
.mipi_rx_data3_RST        (                         )
);

endmodule

