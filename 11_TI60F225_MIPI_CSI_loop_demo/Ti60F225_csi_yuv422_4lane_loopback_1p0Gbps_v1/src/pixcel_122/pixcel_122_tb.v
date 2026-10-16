`timescale  1ns/1ns


module pixcel_122_tb;


parameter	MAX_HRES		= 12'd200;
parameter	MAX_VRES		= 12'd100;
parameter	HSP				= 8'd2;
parameter	HBP				= 8'd88;
parameter	HFP				= 8'd120;
parameter	VSP				= 8'd2;
parameter	VBP				= 8'd20;
parameter	VFP				= 8'd20;
  // Parameters
  localparam  DIN = 24;
  localparam  PAR_WIDTH = 2;

  //Ports
  reg  wrclk = 0;
  reg  rdclk = 0;
  reg  rst_n = 0;
  wire [DIN*PAR_WIDTH-1:0] dout;
  wire  o_hs;
  wire  o_vs;
  wire  o_de;

  wire [7:0] rgb_r;
  wire [7:0] rgb_g;
  wire [7:0] rgb_b;
  wire hs;
  wire vs;
  wire de;

  always #10 wrclk = ~wrclk;
  always #20 rdclk = ~rdclk;
  initial begin
    #0
        rst_n = 1'b0;
    #100
        rst_n = 1'b1;
  end

  color_bar_rgb # (
    .HS_POLORY(1'b1),
    .VS_POLORY(1'b1),
    .NUM_OF_PIXERS_PER_CLOCK(1),
    .H_FRONT_PORCH(HFP),
    .H_SYNC(HSP),
    .H_VALID(MAX_HRES),
    .H_BACK_PORCH(HBP),
    .V_FRONT_PORCH(VFP),
    .V_SYNC(VSP),
    .V_VALID(MAX_VRES),
    .V_BACK_PORCH(VBP),
    .TEST_MODE(0)
  )
  color_bar_rgb_inst (
    .clk(wrclk),
    .rst_n(rst_n),
    .i_rdata(i_rdata),
    .i_gdata(i_gdata),
    .i_bdata(i_bdata),
    .h_cnt(h_cnt),
    .v_cnt(v_cnt),
    .hs(hs),
    .vs(vs),
    .de(de),
    .rgb_r(rgb_r),
    .rgb_g(rgb_g),
    .rgb_b(rgb_b)
  );


  pixcel_122 # (
    .DIN(24),
    .PAR_WIDTH(2)
  )
  pixcel_122_inst (
    .wrclk(wrclk),
    .rdclk(rdclk),
    .rst_n(rst_n),
    .din({rgb_r,rgb_b,rgb_g}),
    .i_hs(hs),
    .i_vs(vs),
    .i_de(de),
    .dout(dout),
    .o_hs(o_hs),
    .o_vs(o_vs),
    .o_de(o_de)
  );

//always #5  clk = ! clk ;

endmodule