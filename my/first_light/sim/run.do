# Optional waveform view inside an already open ModelSim GUI.
# For verified batch runs use: python tools/build.py sim
onerror {error "Simulation failed; see transcript"}
if {![file exists sim/work]} {vlib sim/work}
vlog -work sim/work -sv rtl/sync_fifo.v rtl/fill_engine.v rtl/render_regs.v rtl/framebuffer_video.v rtl/video_mode_measure.v rtl/render_subsystem.v sim/tb_render.sv
vsim -t 1ps -lib sim/work tb_render
add wave sim:/tb_render/dut/*
run -all
