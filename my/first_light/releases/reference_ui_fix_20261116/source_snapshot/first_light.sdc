# Board clock and DDR clocks follow the supplied SoC demo.
# Peripheral Designer generates the device-specific I/O timing constraints.
create_clock -name clk_25m -period 40.000 [get_ports {clk_25m}]
create_clock -name cpu_clk -period 6.666667 [get_ports {cpu_clk}]
create_clock -name core_clk -period 10.000 [get_ports {core_clk}]
create_clock -name sdram_clk -period 2.500 [get_ports {sdram_clk}]
create_clock -name rx_cal_clk -period 2.500 [get_ports {rx_cal_clk}]
create_clock -name tx_cal_clk -period 2.500 [get_ports {tx_cal_clk}]
create_clock -name tx_cal_clk_90edge -period 2.500 [get_ports {tx_cal_clk_90edge}]
create_clock -name hdmi_tx_slow_clk -period 39.669421 [get_ports {hdmi_tx_slow_clk}]
create_clock -name jtag_inst1_TCK -period 100.000 [get_ports {jtag_inst1_TCK}]
set_clock_groups -asynchronous -group {core_clk} -group {cpu_clk} -group {sdram_clk} -group {rx_cal_clk} -group {tx_cal_clk tx_cal_clk_90edge} -group {hdmi_tx_slow_clk} -group {jtag_inst1_TCK}
