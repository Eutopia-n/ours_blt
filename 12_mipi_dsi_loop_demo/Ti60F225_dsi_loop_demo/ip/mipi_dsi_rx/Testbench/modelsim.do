onerror {quit -f}
vlib work
vlog -sv ./modelsim/mipi_dsi_rx.sv
vlog -f filelist.f

vsim -t ps work.TI60F225_MIPI_dsi_tb -voptargs="-debug +designfile" -qwavedb=+signal
run -all

