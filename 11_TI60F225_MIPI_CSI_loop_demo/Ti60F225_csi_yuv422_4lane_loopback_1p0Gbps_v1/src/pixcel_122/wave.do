onerror {resume}
quietly WaveActivateNextPane {} 0
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/clk
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/rst_n
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/i_vs
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/i_de
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/vin
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/fifo_wr_en
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/fifo_wr_data
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/frame_start
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/fifo_rst
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/frame_cnt
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/din_r0
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/shift_cnt
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/vs_r0
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/de_r0
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/de_r1
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/neg_vs
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/pos_vs
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/wr_data
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/wr_en
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/r_frame_start
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/fifo_reset_en
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/frame_stable
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/last_data_shift
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/last_shift_en
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/last_cnt
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/last_wr_state
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/last_wr_en
add wave -noupdate /frame_buffer_tb/u_frame_buffer_ch0/u_ddr_rx_buffer/u_vid_rx_align/negtive_sync
TreeUpdate [SetDefaultTree]
WaveRestoreCursors {{Cursor 1} {0 ps} 0}
quietly wave cursor active 0
configure wave -namecolwidth 150
configure wave -valuecolwidth 85
configure wave -justifyvalue left
configure wave -signalnamewidth 1
configure wave -snapdistance 10
configure wave -datasetprefix 0
configure wave -rowmargin 4
configure wave -childrowmargin 2
configure wave -gridoffset 0
configure wave -gridperiod 1
configure wave -griddelta 40
configure wave -timeline 0
configure wave -timelineunits us
update
WaveRestoreZoom {0 ps} {36795 ps}
