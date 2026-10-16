
# Efinity Interface Designer SDC
# Version: 2023.1.150.3.11
# Date: 2023-09-10 18:08

# Copyright (C) 2017 - 2023 Efinix Inc. All rights reserved.

# Device: Ti60F225
# Project: lvds_loopback
# Timing Model: C4 (final)

# PLL Constraints
#################
#create_clock -waveform {0.3125 1.5625} -period 2.5000 tx_fast_clk
#create_clock -period 10.0000 tx_slow_clk
#create_clock -period 10.0000 lvds_tx_pll_CLKOUT3
#create_clock -period 2.5000 fb
#create_clock -waveform {0.9375 2.1875} -period 2.5000 rx_fast_clk
#create_clock -period 10.0000 rx_slow_clk

create_clock -waveform {0.333 1.000} -period 1.333 -name tx_fast_clk [get_ports {tx_fast_clk}]
create_clock -period 5.333 -name tx_slow_clk [get_ports {tx_slow_clk}]
create_clock -period 10.000 -name lvds_tx_pll_CLKOUT3 [get_ports {lvds_tx_pll_CLKOUT3}]
create_clock -period 5.333 -name fb [get_ports {fb}]
create_clock -waveform {0.333 1.000} -period 1.333 -name rx_fast_clk [get_ports {rx_fast_clk}]
create_clock -period 5.333 -name rx_slow_clk [get_ports {rx_slow_clk}]

# GPIO Constraints
####################
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {led[0]}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {led[0]}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {led[1]}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {led[1]}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {led[2]}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {led[2]}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -max <MAX CALCULATION> [get_ports {led[3]}]
# set_output_delay -clock <CLOCK> [-reference_pin <clkout_pad>] -min <MIN CALCULATION> [get_ports {led[3]}]

# JTAG Constraints
####################
# create_clock -period 10 [get_ports {jtag_inst1_TCK}]
set_output_delay -clock jtag_inst1_TCK -max 0.117 [get_ports {jtag_inst1_TDO}]
set_output_delay -clock jtag_inst1_TCK -min -0.075 [get_ports {jtag_inst1_TDO}]
set_input_delay -clock_fall -clock jtag_inst1_TCK -max 0.280 [get_ports {jtag_inst1_CAPTURE}]
set_input_delay -clock_fall -clock jtag_inst1_TCK -min 0.187 [get_ports {jtag_inst1_CAPTURE}]
set_input_delay -clock_fall -clock jtag_inst1_TCK -max 0.280 [get_ports {jtag_inst1_RESET}]
set_input_delay -clock_fall -clock jtag_inst1_TCK -min 0.187 [get_ports {jtag_inst1_RESET}]
set_input_delay -clock_fall -clock jtag_inst1_TCK -max 0.243 [get_ports {jtag_inst1_SEL}]
set_input_delay -clock_fall -clock jtag_inst1_TCK -min 0.162 [get_ports {jtag_inst1_SEL}]
set_input_delay -clock_fall -clock jtag_inst1_TCK -max 0.280 [get_ports {jtag_inst1_UPDATE}]
set_input_delay -clock_fall -clock jtag_inst1_TCK -min 0.187 [get_ports {jtag_inst1_UPDATE}]
set_input_delay -clock_fall -clock jtag_inst1_TCK -max 0.337 [get_ports {jtag_inst1_SHIFT}]
set_input_delay -clock_fall -clock jtag_inst1_TCK -min 0.225 [get_ports {jtag_inst1_SHIFT}]
# JTAG Constraints (extra... not used by current Efinity debug tools)
# create_clock -period <USER_PERIOD> [get_ports {jtag_inst1_DRCK}]
# set_input_delay -clock_fall -clock jtag_inst1_TCK -max 0.280 [get_ports {jtag_inst1_RUNTEST}]
# set_input_delay -clock_fall -clock jtag_inst1_TCK -min 0.187 [get_ports {jtag_inst1_RUNTEST}]
# Create separate clock groups for JTAG clocks. Remove DRCK clock from the list below if it is not defined.
# set_clock_groups -asynchronous -group {jtag_inst1_TCK jtag_inst1_DRCK}

# HSIO GPIO Constraints
#########################

# LVDS Rx Constraints
#######################
set_input_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~152~322}] -max 0.512 [get_ports {lvds_rx_d0_RX_DATA[*]}]
set_input_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~152~322}] -min 0.342 [get_ports {lvds_rx_d0_RX_DATA[*]}]
set_input_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~160~322}] -max 0.512 [get_ports {lvds_rx_d1_RX_DATA[*]}]
set_input_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~160~322}] -min 0.342 [get_ports {lvds_rx_d1_RX_DATA[*]}]
set_input_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~168~322}] -max 0.512 [get_ports {lvds_rx_d2_RX_DATA[*]}]
set_input_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~168~322}] -min 0.342 [get_ports {lvds_rx_d2_RX_DATA[*]}]
set_input_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~184~322}] -max 0.512 [get_ports {lvds_rx_d3_RX_DATA[*]}]
set_input_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~184~322}] -min 0.342 [get_ports {lvds_rx_d3_RX_DATA[*]}]
set_output_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~152~322}] -max 0.315 [get_ports {lvds_rx_d0_RX_RST}]
set_output_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~152~322}] -min -0.140 [get_ports {lvds_rx_d0_RX_RST}]
set_output_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~160~322}] -max 0.315 [get_ports {lvds_rx_d1_RX_RST}]
set_output_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~160~322}] -min -0.140 [get_ports {lvds_rx_d1_RX_RST}]
set_output_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~168~322}] -max 0.315 [get_ports {lvds_rx_d2_RX_RST}]
set_output_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~168~322}] -min -0.140 [get_ports {lvds_rx_d2_RX_RST}]
set_output_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~184~322}] -max 0.315 [get_ports {lvds_rx_d3_RX_RST}]
set_output_delay -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~184~322}] -min -0.140 [get_ports {lvds_rx_d3_RX_RST}]

# LVDS Tx Constraints
#######################
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~147~322}] -max 0.378 [get_ports {lvds_tx_clk_TX_DATA[*]}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~147~322}] -min -0.140 [get_ports {lvds_tx_clk_TX_DATA[*]}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~147~322}] -max 0.378 [get_ports {lvds_tx_clk_TX_OE}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~147~322}] -min -0.140 [get_ports {lvds_tx_clk_TX_OE}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~79~322}] -max 0.378 [get_ports {lvds_tx_d0_TX_DATA[*]}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~79~322}] -min -0.140 [get_ports {lvds_tx_d0_TX_DATA[*]}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~79~322}] -max 0.378 [get_ports {lvds_tx_d0_TX_OE}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~79~322}] -min -0.140 [get_ports {lvds_tx_d0_TX_OE}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~88~322}] -max 0.378 [get_ports {lvds_tx_d1_TX_DATA[*]}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~88~322}] -min -0.140 [get_ports {lvds_tx_d1_TX_DATA[*]}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~88~322}] -max 0.378 [get_ports {lvds_tx_d1_TX_OE}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~88~322}] -min -0.140 [get_ports {lvds_tx_d1_TX_OE}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~127~322}] -max 0.378 [get_ports {lvds_tx_d2_TX_DATA[*]}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~127~322}] -min -0.140 [get_ports {lvds_tx_d2_TX_DATA[*]}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~127~322}] -max 0.378 [get_ports {lvds_tx_d2_TX_OE}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~127~322}] -min -0.140 [get_ports {lvds_tx_d2_TX_OE}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~136~322}] -max 0.378 [get_ports {lvds_tx_d3_TX_DATA[*]}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~136~322}] -min -0.140 [get_ports {lvds_tx_d3_TX_DATA[*]}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~136~322}] -max 0.378 [get_ports {lvds_tx_d3_TX_OE}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~136~322}] -min -0.140 [get_ports {lvds_tx_d3_TX_OE}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~147~322}] -max 0.420 [get_ports {lvds_tx_clk_TX_RST}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~147~322}] -min -0.175 [get_ports {lvds_tx_clk_TX_RST}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~79~322}] -max 0.420 [get_ports {lvds_tx_d0_TX_RST}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~79~322}] -min -0.175 [get_ports {lvds_tx_d0_TX_RST}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~88~322}] -max 0.420 [get_ports {lvds_tx_d1_TX_RST}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~88~322}] -min -0.175 [get_ports {lvds_tx_d1_TX_RST}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~127~322}] -max 0.420 [get_ports {lvds_tx_d2_TX_RST}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~127~322}] -min -0.175 [get_ports {lvds_tx_d2_TX_RST}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~136~322}] -max 0.420 [get_ports {lvds_tx_d3_TX_RST}]
set_output_delay -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~136~322}] -min -0.175 [get_ports {lvds_tx_d3_TX_RST}]

# Clockout Interface
######################
# lvds_rx_d0 -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~152~322}]
# lvds_rx_d1 -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~160~322}]
# lvds_rx_d2 -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~168~322}]
# lvds_rx_d3 -clock rx_slow_clk -reference_pin [get_ports {rx_slow_clk~CLKOUT~184~322}]
# lvds_tx_clk -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~147~322}]
# lvds_tx_d0 -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~79~322}]
# lvds_tx_d1 -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~88~322}]
# lvds_tx_d2 -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~127~322}]
# lvds_tx_d3 -clock tx_slow_clk -reference_pin [get_ports {tx_slow_clk~CLKOUT~136~322}]
