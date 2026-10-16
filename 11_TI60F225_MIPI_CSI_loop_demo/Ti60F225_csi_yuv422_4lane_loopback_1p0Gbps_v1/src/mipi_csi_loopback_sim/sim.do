#onerror {quit -f}
vlib work
vlog -sv TI60_MIPI_csi_tb.sv
vlog reset.v
vlog -sv ./modelsim/efx_csi2_tx.sv
vlog -sv top.sv -f tx_filelist.f
vlog ./*.v
vsim -t ps  -voptargs=+acc work.TI60_MIPI_csi_tb
do wave.do
run 10000us
