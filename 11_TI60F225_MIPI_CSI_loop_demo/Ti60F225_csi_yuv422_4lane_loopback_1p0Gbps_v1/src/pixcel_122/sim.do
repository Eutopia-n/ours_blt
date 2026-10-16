vlib work

vmap work work

vlog ./*.v

#vsim -novopt work.pixcel_122_tb 

vsim -t ps  -voptargs=+acc work.pixcel_122_tb

do wave.do
run 2000us
