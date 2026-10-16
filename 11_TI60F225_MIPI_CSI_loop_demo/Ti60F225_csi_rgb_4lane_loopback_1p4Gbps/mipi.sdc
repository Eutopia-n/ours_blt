# PLL Constraints
#################
create_clock -period 5.714 -name mipi_dphy_tx_SLOWCLK [get_ports {mipi_dphy_tx_SLOWCLK}]
create_clock -period 5.714 -name mipi_dphy_rx_clk_CLKOUT [get_ports {mipi_dphy_rx_clk_CLKOUT}]
set_clock_groups -exclusive -group {mipi_clk} -group {mipi_dphy_rx_clk_CLKOUT} -group {pixel_clk} -group {jtag_inst1_TCK}
set_clock_groups -exclusive -group {mipi_clk} -group {mipi_dphy_tx_SLOWCLK} -group {pixel_clk} -group {jtag_inst1_TCK}



create_clock -waveform {0.714 1.429} -period 1.429 -name mipi_dphy_tx_FASTCLK_C [get_ports {mipi_dphy_tx_FASTCLK_C}]
create_clock -waveform {0.357 1.072} -period 1.429 -name mipi_dphy_tx_FASTCLK_D [get_ports {mipi_dphy_tx_FASTCLK_D}]
create_clock -period 10.000 -name mipi_clk [get_ports {mipi_clk}]
create_clock -period 10.000 -name CLKOUT0 [get_ports {CLKOUT0}]
create_clock -period 20.000 -name pixel_clk [get_ports {pixel_clk}]

# GPIO Constraints
####################
# set_input_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {reset_n}]
# set_input_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {reset_n}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {O_LED[0]}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {O_LED[0]}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {O_LED[1]}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {O_LED[1]}]

# HSIO GPIO Constraints
#########################
create_clock -period 40.000 -name gpio_clk_25m [get_ports {gpio_clk_25m}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {O_LED[2]}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {O_LED[2]}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {O_LED[3]}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {O_LED[3]}]

# MIPI RX Lane Constraints
############################

set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~73~322}] -max 0.525 [get_ports {mipi_dphy_rx_data0_FIFO_RD}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~73~322}] -min 0.070 [get_ports {mipi_dphy_rx_data0_FIFO_RD}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~73~322}] -max 0.315 [get_ports {mipi_dphy_rx_data0_RST}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~73~322}] -min -0.140 [get_ports {mipi_dphy_rx_data0_RST}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~73~322}] -max 0.630 [get_ports {mipi_dphy_rx_data0_FIFO_EMPTY}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~73~322}] -min 0.420 [get_ports {mipi_dphy_rx_data0_FIFO_EMPTY}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~73~322}] -max 0.487 [get_ports {mipi_dphy_rx_data0_HS_IN[*]}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~73~322}] -min 0.325 [get_ports {mipi_dphy_rx_data0_HS_IN[*]}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~82~322}] -max 0.525 [get_ports {mipi_dphy_rx_data1_FIFO_RD}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~82~322}] -min 0.070 [get_ports {mipi_dphy_rx_data1_FIFO_RD}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~82~322}] -max 0.315 [get_ports {mipi_dphy_rx_data1_RST}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~82~322}] -min -0.140 [get_ports {mipi_dphy_rx_data1_RST}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~82~322}] -max 0.630 [get_ports {mipi_dphy_rx_data1_FIFO_EMPTY}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~82~322}] -min 0.420 [get_ports {mipi_dphy_rx_data1_FIFO_EMPTY}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~82~322}] -max 0.487 [get_ports {mipi_dphy_rx_data1_HS_IN[*]}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~82~322}] -min 0.325 [get_ports {mipi_dphy_rx_data1_HS_IN[*]}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~130~322}] -max 0.525 [get_ports {mipi_dphy_rx_data2_FIFO_RD}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~130~322}] -min 0.070 [get_ports {mipi_dphy_rx_data2_FIFO_RD}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~130~322}] -max 0.315 [get_ports {mipi_dphy_rx_data2_RST}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~130~322}] -min -0.140 [get_ports {mipi_dphy_rx_data2_RST}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~130~322}] -max 0.630 [get_ports {mipi_dphy_rx_data2_FIFO_EMPTY}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~130~322}] -min 0.420 [get_ports {mipi_dphy_rx_data2_FIFO_EMPTY}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~130~322}] -max 0.487 [get_ports {mipi_dphy_rx_data2_HS_IN[*]}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~130~322}] -min 0.325 [get_ports {mipi_dphy_rx_data2_HS_IN[*]}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~141~322}] -max 0.525 [get_ports {mipi_dphy_rx_data3_FIFO_RD}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~141~322}] -min 0.070 [get_ports {mipi_dphy_rx_data3_FIFO_RD}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~141~322}] -max 0.315 [get_ports {mipi_dphy_rx_data3_RST}]
set_output_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~141~322}] -min -0.140 [get_ports {mipi_dphy_rx_data3_RST}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~141~322}] -max 0.630 [get_ports {mipi_dphy_rx_data3_FIFO_EMPTY}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~141~322}] -min 0.420 [get_ports {mipi_dphy_rx_data3_FIFO_EMPTY}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~141~322}] -max 0.487 [get_ports {mipi_dphy_rx_data3_HS_IN[*]}]
set_input_delay -clock mipi_dphy_rx_clk_CLKOUT -reference_pin [get_ports {mipi_dphy_rx_clk_CLKOUT~CLKOUT~141~322}] -min 0.325 [get_ports {mipi_dphy_rx_data3_HS_IN[*]}]

# MIPI TX Lane Constraints
############################
set_output_delay -clock mipi_dphy_tx_FASTCLK_D -reference_pin [get_ports {mipi_dphy_tx_FASTCLK_D~CLKOUT~171~322}] -max 0.378 [get_ports {mipi_dphy_tx_clk_HS_OUT}]
set_output_delay -clock mipi_dphy_tx_FASTCLK_D -reference_pin [get_ports {mipi_dphy_tx_FASTCLK_D~CLKOUT~171~322}] -min -0.140 [get_ports {mipi_dphy_tx_clk_HS_OUT}]
set_output_delay -clock mipi_dphy_tx_FASTCLK_D -reference_pin [get_ports {mipi_dphy_tx_FASTCLK_D~CLKOUT~171~322}] -max 0.315 [get_ports {mipi_dphy_tx_clk_RST}]
set_output_delay -clock mipi_dphy_tx_FASTCLK_D -reference_pin [get_ports {mipi_dphy_tx_FASTCLK_D~CLKOUT~171~322}] -min -0.140 [get_ports {mipi_dphy_tx_clk_RST}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~155~322}] -max 0.378 [get_ports {mipi_dphy_tx_data0_HS_OUT}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~155~322}] -min -0.140 [get_ports {mipi_dphy_tx_data0_HS_OUT}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~155~322}] -max 0.315 [get_ports {mipi_dphy_tx_data0_RST}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~155~322}] -min -0.140 [get_ports {mipi_dphy_tx_data0_RST}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~163~322}] -max 0.378 [get_ports {mipi_dphy_tx_data1_HS_OUT}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~163~322}] -min -0.140 [get_ports {mipi_dphy_tx_data1_HS_OUT}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~163~322}] -max 0.315 [get_ports {mipi_dphy_tx_data1_RST}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~163~322}] -min -0.140 [get_ports {mipi_dphy_tx_data1_RST}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~187~322}] -max 0.378 [get_ports {mipi_dphy_tx_data2_HS_OUT}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~187~322}] -min -0.140 [get_ports {mipi_dphy_tx_data2_HS_OUT}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~187~322}] -max 0.315 [get_ports {mipi_dphy_tx_data2_RST}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~187~322}] -min -0.140 [get_ports {mipi_dphy_tx_data2_RST}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~195~322}] -max 0.378 [get_ports {mipi_dphy_tx_data3_HS_OUT}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~195~322}] -min -0.140 [get_ports {mipi_dphy_tx_data3_HS_OUT}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~195~322}] -max 0.315 [get_ports {mipi_dphy_tx_data3_RST}]
set_output_delay -clock mipi_dphy_tx_SLOWCLK -reference_pin [get_ports {mipi_dphy_tx_SLOWCLK~CLKOUT~195~322}] -min -0.140 [get_ports {mipi_dphy_tx_data3_RST}]

# Clock Latency Constraints
############################
# set_clock_latency -source -setup <pll_clk_latency_mipi_clk_max + 1.812> [get_ports {CLKOUT0}]
# set_clock_latency -source -hold <pll_clk_latency_mipi_clk_min + 1.172> [get_ports {CLKOUT0}]
# set_clock_latency -source -setup <pll_clk_latency_mipi_clk_max + 1.812> [get_ports {pixel_clk}]
# set_clock_latency -source -hold <pll_clk_latency_mipi_clk_min + 1.172> [get_ports {pixel_clk}]
# set_clock_latency -source -setup <board_max + 0.810> [get_ports {mipi_dphy_tx_SLOWCLK}]
# set_clock_latency -source -hold <board_min + 0.541> [get_ports {mipi_dphy_tx_SLOWCLK}]
# set_clock_latency -source -setup <board_max + 0.810> [get_ports {mipi_dphy_tx_FASTCLK_C}]
# set_clock_latency -source -hold <board_min + 0.541> [get_ports {mipi_dphy_tx_FASTCLK_C}]
# set_clock_latency -source -setup <board_max + 0.810> [get_ports {mipi_dphy_tx_FASTCLK_D}]
# set_clock_latency -source -hold <board_min + 0.541> [get_ports {mipi_dphy_tx_FASTCLK_D}]
# set_clock_latency -source -setup <board_max + 0.810> [get_ports {mipi_clk}]
# set_clock_latency -source -hold <board_min + 0.541> [get_ports {mipi_clk}]
# set_clock_latency -source -setup <board_max + 0.828> [get_ports {gpio_clk_25m}]
# set_clock_latency -source -hold <board_min + 0.552> [get_ports {gpio_clk_25m}]
