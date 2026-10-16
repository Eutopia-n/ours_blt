# Efinity Interface Designer SDC
# Version: 2024.M.263
# Date: 2024-10-02 14:20

# Copyright (C) 2013 - 2024 Efinix Inc. All rights reserved.

# Device: Ti60F225
# Project: ti60f225_demo
# Timing Model: C4 (final)

# PLL Constraints
#################
create_clock -period 10.000 i_mipi_clk
create_clock -waveform {1.000 2.000} -period 2.000 i_mipi_txc_sclk
create_clock -waveform {0.500 1.500} -period 2.000 i_mipi_txd_sclk
create_clock -period 8.000 i_mipi_tx_pclk
create_clock -period 40.000 i_fb_clk
create_clock -period 12.500 i_sysclk
create_clock -period 8.0000 mipi_rx_clk_CLKOUT

# GPIO Constraints
####################
# set_input_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {i_arstn}]
# set_input_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {i_arstn}]
# set_input_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {i_inject_err}]
# set_input_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {i_inject_err}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {o_lcd_rstn}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {o_lcd_rstn}]

# HSIO GPIO Constraints
#########################
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {o_LED16_B}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {o_LED16_B}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {o_LED16_G}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {o_LED16_G}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {o_LED16_R}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {o_LED16_R}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {o_LED17_B}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {o_LED17_B}]

# MIPI RX Lane Constraints
############################
# create_clock -period <USER_PERIOD> [get_ports {mipi_rx_clk_CLKOUT}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~149~1}] -max 0.525 [get_ports {mipi_rx_data0_FIFO_RD}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~149~1}] -min 0.070 [get_ports {mipi_rx_data0_FIFO_RD}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~149~1}] -max 0.315 [get_ports {mipi_rx_data0_RST}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~149~1}] -min -0.140 [get_ports {mipi_rx_data0_RST}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~149~1}] -max 0.630 [get_ports {mipi_rx_data0_FIFO_EMPTY}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~149~1}] -min 0.420 [get_ports {mipi_rx_data0_FIFO_EMPTY}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~149~1}] -max 0.487 [get_ports {mipi_rx_data0_HS_IN[*]}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~149~1}] -min 0.325 [get_ports {mipi_rx_data0_HS_IN[*]}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~157~1}] -max 0.525 [get_ports {mipi_rx_data1_FIFO_RD}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~157~1}] -min 0.070 [get_ports {mipi_rx_data1_FIFO_RD}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~157~1}] -max 0.315 [get_ports {mipi_rx_data1_RST}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~157~1}] -min -0.140 [get_ports {mipi_rx_data1_RST}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~157~1}] -max 0.630 [get_ports {mipi_rx_data1_FIFO_EMPTY}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~157~1}] -min 0.420 [get_ports {mipi_rx_data1_FIFO_EMPTY}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~157~1}] -max 0.487 [get_ports {mipi_rx_data1_HS_IN[*]}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~157~1}] -min 0.325 [get_ports {mipi_rx_data1_HS_IN[*]}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~173~1}] -max 0.525 [get_ports {mipi_rx_data2_FIFO_RD}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~173~1}] -min 0.070 [get_ports {mipi_rx_data2_FIFO_RD}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~173~1}] -max 0.315 [get_ports {mipi_rx_data2_RST}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~173~1}] -min -0.140 [get_ports {mipi_rx_data2_RST}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~173~1}] -max 0.630 [get_ports {mipi_rx_data2_FIFO_EMPTY}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~173~1}] -min 0.420 [get_ports {mipi_rx_data2_FIFO_EMPTY}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~173~1}] -max 0.487 [get_ports {mipi_rx_data2_HS_IN[*]}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~173~1}] -min 0.325 [get_ports {mipi_rx_data2_HS_IN[*]}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~189~1}] -max 0.525 [get_ports {mipi_rx_data3_FIFO_RD}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~189~1}] -min 0.070 [get_ports {mipi_rx_data3_FIFO_RD}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~189~1}] -max 0.315 [get_ports {mipi_rx_data3_RST}]
set_output_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~189~1}] -min -0.140 [get_ports {mipi_rx_data3_RST}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~189~1}] -max 0.630 [get_ports {mipi_rx_data3_FIFO_EMPTY}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~189~1}] -min 0.420 [get_ports {mipi_rx_data3_FIFO_EMPTY}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~189~1}] -max 0.487 [get_ports {mipi_rx_data3_HS_IN[*]}]
set_input_delay -clock mipi_rx_clk_CLKOUT -reference_pin [get_ports {mipi_rx_clk_CLKOUT~CLKOUT~189~1}] -min 0.325 [get_ports {mipi_rx_data3_HS_IN[*]}]

# MIPI TX Lane Constraints
############################
set_output_delay -clock i_mipi_txd_sclk -reference_pin [get_ports {i_mipi_txd_sclk~CLKOUT~45~1}] -max 0.378 [get_ports {mipi_dp_clk_HS_OUT[*]}]
set_output_delay -clock i_mipi_txd_sclk -reference_pin [get_ports {i_mipi_txd_sclk~CLKOUT~45~1}] -min -0.140 [get_ports {mipi_dp_clk_HS_OUT[*]}]
set_output_delay -clock i_mipi_txd_sclk -reference_pin [get_ports {i_mipi_txd_sclk~CLKOUT~45~1}] -max 0.315 [get_ports {mipi_dp_clk_RST}]
set_output_delay -clock i_mipi_txd_sclk -reference_pin [get_ports {i_mipi_txd_sclk~CLKOUT~45~1}] -min -0.140 [get_ports {mipi_dp_clk_RST}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~21~1}] -max 0.378 [get_ports {mipi_dp_data0_HS_OUT[*]}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~21~1}] -min -0.140 [get_ports {mipi_dp_data0_HS_OUT[*]}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~21~1}] -max 0.315 [get_ports {mipi_dp_data0_RST}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~21~1}] -min -0.140 [get_ports {mipi_dp_data0_RST}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~29~1}] -max 0.378 [get_ports {mipi_dp_data1_HS_OUT[*]}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~29~1}] -min -0.140 [get_ports {mipi_dp_data1_HS_OUT[*]}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~29~1}] -max 0.315 [get_ports {mipi_dp_data1_RST}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~29~1}] -min -0.140 [get_ports {mipi_dp_data1_RST}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~37~1}] -max 0.378 [get_ports {mipi_dp_data2_HS_OUT[*]}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~37~1}] -min -0.140 [get_ports {mipi_dp_data2_HS_OUT[*]}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~37~1}] -max 0.315 [get_ports {mipi_dp_data2_RST}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~37~1}] -min -0.140 [get_ports {mipi_dp_data2_RST}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~54~1}] -max 0.378 [get_ports {mipi_dp_data3_HS_OUT[*]}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~54~1}] -min -0.140 [get_ports {mipi_dp_data3_HS_OUT[*]}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~54~1}] -max 0.315 [get_ports {mipi_dp_data3_RST}]
set_output_delay -clock i_mipi_tx_pclk -reference_pin [get_ports {i_mipi_tx_pclk~CLKOUT~54~1}] -min -0.140 [get_ports {mipi_dp_data3_RST}]

# Clock Latency Constraints
############################
# set_clock_latency -source -setup <pll_clk_latency_i_fb_clk_max -0.007> [get_ports {i_mipi_clk}]
# set_clock_latency -source -hold <pll_clk_latency_i_fb_clk_min -0.005> [get_ports {i_mipi_clk}]
# set_clock_latency -source -setup <pll_clk_latency_i_fb_clk_max -0.007> [get_ports {i_mipi_txc_sclk}]
# set_clock_latency -source -hold <pll_clk_latency_i_fb_clk_min -0.005> [get_ports {i_mipi_txc_sclk}]
# set_clock_latency -source -setup <pll_clk_latency_i_fb_clk_max -0.007> [get_ports {i_mipi_txd_sclk}]
# set_clock_latency -source -hold <pll_clk_latency_i_fb_clk_min -0.005> [get_ports {i_mipi_txd_sclk}]
# set_clock_latency -source -setup <pll_clk_latency_i_fb_clk_max -0.007> [get_ports {i_mipi_tx_pclk}]
# set_clock_latency -source -hold <pll_clk_latency_i_fb_clk_min -0.005> [get_ports {i_mipi_tx_pclk}]
# set_clock_latency -source -setup <board_max -1.053> [get_ports {i_fb_clk}]
# set_clock_latency -source -hold <board_min -0.665> [get_ports {i_fb_clk}]
# set_clock_latency -source -setup <board_max -1.053> [get_ports {i_sysclk}]
# set_clock_latency -source -hold <board_min -0.665> [get_ports {i_sysclk}]

set_clock_groups -exclusive -group {i_fb_clk} -group {i_sysclk} -group {i_mipi_clk} -group {i_mipi_txc_sclk} -group {i_mipi_txd_sclk} -group {i_mipi_tx_pclk} -group {mipi_rx_clk_CLKOUT}
set_multicycle_path 3 -setup -to [get_ports mipi_dp_clk_HS_OUT[*]] -end
set_multicycle_path 2 -hold -to [get_ports mipi_dp_clk_HS_OUT[*]] -end
