debug_profile_edb_top debug_profile_edb_top_inst (
    .bscan_CAPTURE      ( jtag_inst1_CAPTURE ),
    .bscan_DRCK         ( jtag_inst1_DRCK ),
    .bscan_RESET        ( jtag_inst1_RESET ),
    .bscan_RUNTEST      ( jtag_inst1_RUNTEST ),
    .bscan_SEL          ( jtag_inst1_SEL ),
    .bscan_SHIFT        ( jtag_inst1_SHIFT ),
    .bscan_TCK          ( jtag_inst1_TCK ),
    .bscan_TDI          ( jtag_inst1_TDI ),
    .bscan_TMS          ( jtag_inst1_TMS ),
    .bscan_UPDATE       ( jtag_inst1_UPDATE ),
    .bscan_TDO          ( jtag_inst1_TDO ),
    .LVDS_TX_clk            ( $INSERT_YOUR_CLOCK_NAME ),
    .LVDS_TX_lvds_tx_data0      ( lvds_tx_data0 ),
    .LVDS_TX_lvds_tx_data1      ( lvds_tx_data1 ),
    .LVDS_TX_lvds_tx_data2      ( lvds_tx_data2 ),
    .LVDS_TX_lvds_tx_data3      ( lvds_tx_data3 ),
    .LVDS_RX_clk            ( $INSERT_YOUR_CLOCK_NAME ),
    .LVDS_RX_lvds_rx_data_slip0     ( lvds_rx_data_slip0 ),
    .LVDS_RX_lvds_rx_data_slip1     ( lvds_rx_data_slip1 ),
    .LVDS_RX_lvds_rx_data_slip2     ( lvds_rx_data_slip2 ),
    .LVDS_RX_lvds_rx_data_slip3     ( lvds_rx_data_slip3 ),
    .LVDS_RX_stat0      ( stat0 ),
    .LVDS_RX_stat1      ( stat1 ),
    .LVDS_RX_stat2      ( stat2 ),
    .LVDS_RX_stat3      ( stat3 ),
    .vio_ctrl_status_clk( $INSERT_YOUR_CLOCK_NAME ),
    .vio_ctrl_status_pll_locked( pll_locked ),
    .vio_ctrl_status_rx_heartbeat( rx_heartbeat ),
    .vio_ctrl_status_tx_heartbeat( tx_heartbeat ),
    .vio_ctrl_status_det_pass( det_pass ),
    .vio_ctrl_status_stat0( stat0 ),
    .vio_ctrl_status_stat1( stat1 ),
    .vio_ctrl_status_stat2( stat2 ),
    .vio_ctrl_status_stat3( stat3 ),
    .vio_ctrl_status_data_source( data_source ),
    .vio_ctrl_status_lvds_tx_data( lvds_tx_data ),
    .vio_ctrl_status_bitslip_binding( bitslip_binding ),
    .vio_ctrl_status_bitslip_all( bitslip_all ),
    .vio_ctrl_status_bitslip0( bitslip0 ),
    .vio_ctrl_status_bitslip1( bitslip1 ),
    .vio_ctrl_status_bitslip2( bitslip2 ),
    .vio_ctrl_status_bitslip3( bitslip3 ),
    .vio_tx_data_clk( $INSERT_YOUR_CLOCK_NAME ),
    .vio_tx_data_lvds_tx_data0( lvds_tx_data0 ),
    .vio_tx_data_lvds_tx_data1( lvds_tx_data1 ),
    .vio_tx_data_lvds_tx_data2( lvds_tx_data2 ),
    .vio_tx_data_lvds_tx_data3( lvds_tx_data3 ),
    .vio_rx_data_clk( $INSERT_YOUR_CLOCK_NAME ),
    .vio_rx_data_lvds_rx_data0( lvds_rx_data0 ),
    .vio_rx_data_lvds_rx_data1( lvds_rx_data1 ),
    .vio_rx_data_lvds_rx_data2( lvds_rx_data2 ),
    .vio_rx_data_lvds_rx_data3( lvds_rx_data3 ),
    .vio_rx_data_lvds_rx_data_slip0( lvds_rx_data_slip0 ),
    .vio_rx_data_lvds_rx_data_slip1( lvds_rx_data_slip1 ),
    .vio_rx_data_lvds_rx_data_slip2( lvds_rx_data_slip2 ),
    .vio_rx_data_lvds_rx_data_slip3( lvds_rx_data_slip3 )
);

////////////////////////////////////////////////////////////////////////////////
// Copyright (C) 2013-2025 Efinix Inc. All rights reserved.              
//
// This   document  contains  proprietary information  which   is        
// protected by  copyright. All rights  are reserved.  This notice       
// refers to original work by Efinix, Inc. which may be derivitive       
// of other work distributed under license of the authors.  In the       
// case of derivative work, nothing in this notice overrides the         
// original author's license agreement.  Where applicable, the           
// original license agreement is included in it's original               
// unmodified form immediately below this header.                        
//                                                                       
// WARRANTY DISCLAIMER.                                                  
//     THE  DESIGN, CODE, OR INFORMATION ARE PROVIDED “AS IS” AND        
//     EFINIX MAKES NO WARRANTIES, EXPRESS OR IMPLIED WITH               
//     RESPECT THERETO, AND EXPRESSLY DISCLAIMS ANY IMPLIED WARRANTIES,  
//     INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTIES OF          
//     MERCHANTABILITY, NON-INFRINGEMENT AND FITNESS FOR A PARTICULAR    
//     PURPOSE.  SOME STATES DO NOT ALLOW EXCLUSIONS OF AN IMPLIED       
//     WARRANTY, SO THIS DISCLAIMER MAY NOT APPLY TO LICENSEE.           
//                                                                       
// LIMITATION OF LIABILITY.                                              
//     NOTWITHSTANDING ANYTHING TO THE CONTRARY, EXCEPT FOR BODILY       
//     INJURY, EFINIX SHALL NOT BE LIABLE WITH RESPECT TO ANY SUBJECT    
//     MATTER OF THIS AGREEMENT UNDER TORT, CONTRACT, STRICT LIABILITY   
//     OR ANY OTHER LEGAL OR EQUITABLE THEORY (I) FOR ANY INDIRECT,      
//     SPECIAL, INCIDENTAL, EXEMPLARY OR CONSEQUENTIAL DAMAGES OF ANY    
//     CHARACTER INCLUDING, WITHOUT LIMITATION, DAMAGES FOR LOSS OF      
//     GOODWILL, DATA OR PROFIT, WORK STOPPAGE, OR COMPUTER FAILURE OR   
//     MALFUNCTION, OR IN ANY EVENT (II) FOR ANY AMOUNT IN EXCESS, IN    
//     THE AGGREGATE, OF THE FEE PAID BY LICENSEE TO EFINIX HEREUNDER    
//     (OR, IF THE FEE HAS BEEN WAIVED, $100), EVEN IF EFINIX SHALL HAVE 
//     BEEN INFORMED OF THE POSSIBILITY OF SUCH DAMAGES.  SOME STATES DO 
//     NOT ALLOW THE EXCLUSION OR LIMITATION OF INCIDENTAL OR            
//     CONSEQUENTIAL DAMAGES, SO THIS LIMITATION AND EXCLUSION MAY NOT   
//     APPLY TO LICENSEE.                                                
//
////////////////////////////////////////////////////////////////////////////////
