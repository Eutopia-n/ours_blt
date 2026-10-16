
`timescale 1 ns / 1 ns

module	phy_ctrl_tb;

	reg clk_25m =1'b0;
	
	reg	in =0;
	always #10 clk_25m = ~clk_25m;
	
	TOP u_top(

  /*i*/.pll_locked	(1'b1),
  /*i*/.ETH_MDIO_IN	(in),
  /*i*/.clk_25m			(clk_25m),
  /*o*/.ETH_MDC			(),
  /*o*/.ETH_MDIO_OUT(),
  /*o*/.ETH_MDIO_OE ()
  
  );
  
  
  always @( posedge clk_25m )
  begin
  		in <= $random % 2;
  end


endmodule