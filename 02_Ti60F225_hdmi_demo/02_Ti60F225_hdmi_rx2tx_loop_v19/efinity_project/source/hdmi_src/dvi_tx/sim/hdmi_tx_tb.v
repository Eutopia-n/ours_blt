`timescale 1ps/1ps
module hdmi_tx_tb;

wire                            video_hs;
wire                            video_vs;
wire                            video_de;
wire[7:0]                       video_r;
wire[7:0]                       video_g;
wire[7:0]                       video_b;
reg                             clk = 'd0;
reg                             rst_p = 'd0;


always #10 clk = ~clk;
initial begin
    #0 
        rst_p = 1;
    #143
        rst_p = 0;
end



color_bar_rgb # (
    .HS_POLORY(1'b1),
    .VS_POLORY(1'b1),
    .NUM_OF_PIXERS_PER_CLOCK(1),
    .H_FRONT_PORCH(50),
    .H_SYNC(30),
    .H_VALID(1920),
    .H_BACK_PORCH(50),
    .V_FRONT_PORCH(5),
    .V_SYNC(5),
    .V_VALID(1080),
    .V_BACK_PORCH(5),
    .TEST_MODE(0)
  )
  color_bar_rgb_inst (
    .clk(clk),
    .rst_n(rst_n),
    .i_rdata(i_rdata),
    .i_gdata(i_gdata),
    .i_bdata(i_bdata),
    .h_cnt(h_cnt),
    .v_cnt(v_cnt),
	.hs(video_hs),
	.vs(video_vs),
	.de(video_de),
	.rgb_r(video_r),
	.rgb_g(video_g),
	.rgb_b(video_b)
  );

reg [11:0] cnt = 'd0;
wire audio_valid;
reg [23:0] audio_L = 'd0;
reg [23:0] audio_R = 'd0;
always @( posedge clk )
begin
  cnt <= cnt + 1'b1;
end

assign audio_valid = &cnt;
always @( posedge clk )
begin
  if( audio_valid) begin
    audio_L <= audio_L + 1'b1;
    audio_R <= audio_R + 2'd2;
  end
end

dvi_encoder dvi_encoder_m0
(
	.pixelclk      (clk          ),// system clock
	.rst_p         (rst_p             ),// reset
	.i_bdata      (video_b            ),//
	.i_gdata      (video_g            ),//   
	.i_rdata       (video_r            ),//   
	.i_hs         (video_hs           ),//   
	.i_vs         (video_vs           ),//  
	.i_de         (video_de           ),//
  .audio_L                (audio_L),
  .audio_R                (audio_R),
  .audio_valid            (audio_valid),
  .audio_N                (),          
  .audio_CTS              (),            
  .audio_sample_frequency (),     
  .audio_word_length      (),


	.tmds_data0    (tmds_data0),
    .tmds_data1    (tmds_data1),
    .tmds_data2    (tmds_data2),
    .tmds_clk      (tmds_clk  )
);


endmodule
