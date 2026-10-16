#cd


#Define vlib
vlib work
vmap work work 
vlog  -sv hdmi_tx_tb.v
vlog  ./../dvi_encoder.v
vlog  ./../encode.v
vlog ./../../color_bar_rgb.v
vlog ./../simple_dual_port_ram.v
vlog ./../ecc_calc.v
vlog ./../ecc_calc_v1.v
vlog ./../tx_aux.v
vlog ./../DC_FIFO.v
vlog ./../packet_assembler.sv
vlog ./../audio_packet.sv
vlog ./../auxiliary_video_information_info_frame.sv
vlog ./../audio_clock_regeneration_packet.sv
vlog ./../efx_fifo.v


vsim -t ps -voptargs=+acc work.hdmi_tx_tb
 

#Run simulation
do wave.do
run 0.7us