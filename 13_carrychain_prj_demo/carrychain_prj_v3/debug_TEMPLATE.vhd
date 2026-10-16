------------- Begin Cut here for COMPONENT Declaration ------
component edb_top
  port (
         bscan_CAPTURE : in  std_logic;
         bscan_DRCK    : in  std_logic;
         bscan_RESET   : in  std_logic;
         bscan_RUNTEST : in  std_logic;
         bscan_SEL     : in  std_logic;
         bscan_SHIFT   : in  std_logic;
         bscan_TCK     : in  std_logic;
         bscan_TDI     : in  std_logic;
         bscan_TMS     : in  std_logic;
         bscan_UPDATE  : in  std_logic;
         bscan_TDO     : out std_logic;
         la0_clk       : in  std_logic;
         la0_lvds_rx_data : in  std_logic_vector(3 downto 0);
         la0_DLY_RST   : in  std_logic;
         la0_DLY_INC   : in  std_logic;
         la0_DLY_ENA   : in  std_logic;
         la0_mode      : in  std_logic;
         la0_dly_cnt   : in  std_logic_vector(5 downto 0);
         vio0_clk      : in  std_logic;
         vio0_carry_tap03 : in  std_logic_vector(127 downto 0);
         vio0_carry_tap10 : in  std_logic_vector(127 downto 0);
         vio0_carry_tap11 : in  std_logic_vector(127 downto 0);
         vio0_carry_tap12 : in  std_logic_vector(127 downto 0);
         vio0_carry_tap13 : in  std_logic_vector(127 downto 0);
         vio0_left_0_cnt : in  std_logic_vector(7 downto 0);
         vio0_right_0_cnt : in  std_logic_vector(7 downto 0);
         vio1_clk      : in  std_logic;
         vio1_dly_cnt  : in  std_logic_vector(5 downto 0);
         vio1_send_en  : out std_logic;
         vio1_dly_en   : out std_logic;
         vio1_dly_d    : out std_logic_vector(5 downto 0);
         vio1_dly_inc  : out std_logic;
         vio1_mode     : out std_logic
       );
end component ;
---------------------- End COMPONENT Declaration ------------

-- The following code must appear in the VHDL architecture
-- body. Substitute your own instance name and net names.

------------- Begin Cut here for INSTANTIATION Template -----
edb_top_inst : edb_top
port map (
           bscan_CAPTURE => jtag_inst1_CAPTURE,
           bscan_DRCK    => jtag_inst1_DRCK,
           bscan_RESET   => jtag_inst1_RESET,
           bscan_RUNTEST => jtag_inst1_RUNTEST,
           bscan_SEL     => jtag_inst1_SEL,
           bscan_SHIFT   => jtag_inst1_SHIFT,
           bscan_TCK     => jtag_inst1_TCK,
           bscan_TDI     => jtag_inst1_TDI,
           bscan_TMS     => jtag_inst1_TMS,
           bscan_UPDATE  => jtag_inst1_UPDATE,
           bscan_TDO     => jtag_inst1_TDO,
           la0_clk      => #INSERT_YOUR_CLOCK_NAME,
           la0_lvds_rx_data => la0_lvds_rx_data,
           la0_DLY_RST  => la0_DLY_RST,
           la0_DLY_INC  => la0_DLY_INC,
           la0_DLY_ENA  => la0_DLY_ENA,
           la0_mode => la0_mode,
           la0_dly_cnt  => la0_dly_cnt,
           vio0_clk      => #INSERT_YOUR_CLOCK_NAME,
           vio0_carry_tap03 => vio0_carry_tap03,
           vio0_carry_tap10 => vio0_carry_tap10,
           vio0_carry_tap11 => vio0_carry_tap11,
           vio0_carry_tap12 => vio0_carry_tap12,
           vio0_carry_tap13 => vio0_carry_tap13,
           vio0_left_0_cnt => vio0_left_0_cnt,
           vio0_right_0_cnt => vio0_right_0_cnt,
           vio1_clk      => #INSERT_YOUR_CLOCK_NAME,
           vio1_dly_cnt  => vio1_dly_cnt,
           vio1_send_en  => vio1_send_en,
           vio1_dly_en   => vio1_dly_en,
           vio1_dly_d    => vio1_dly_d,
           vio1_dly_inc  => vio1_dly_inc,
           vio1_mode     => vio1_mode
         );
------------------------ End INSTANTIATION Template ---------

--------------------------------------------------------------------------------
-- Copyright (C) 2013-2024 Efinix Inc. All rights reserved.              
--
-- This   document  contains  proprietary information  which   is        
-- protected by  copyright. All rights  are reserved.  This notice       
-- refers to original work by Efinix, Inc. which may be derivitive       
-- of other work distributed under license of the authors.  In the       
-- case of derivative work, nothing in this notice overrides the         
-- original author's license agreement.  Where applicable, the           
-- original license agreement is included in it's original               
-- unmodified form immediately below this header.                        
--                                                                       
-- WARRANTY DISCLAIMER.                                                  
--     THE  DESIGN, CODE, OR INFORMATION ARE PROVIDED “AS IS” AND        
--     EFINIX MAKES NO WARRANTIES, EXPRESS OR IMPLIED WITH               
--     RESPECT THERETO, AND EXPRESSLY DISCLAIMS ANY IMPLIED WARRANTIES,  
--     INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTIES OF          
--     MERCHANTABILITY, NON-INFRINGEMENT AND FITNESS FOR A PARTICULAR    
--     PURPOSE.  SOME STATES DO NOT ALLOW EXCLUSIONS OF AN IMPLIED       
--     WARRANTY, SO THIS DISCLAIMER MAY NOT APPLY TO LICENSEE.           
--                                                                       
-- LIMITATION OF LIABILITY.                                              
--     NOTWITHSTANDING ANYTHING TO THE CONTRARY, EXCEPT FOR BODILY       
--     INJURY, EFINIX SHALL NOT BE LIABLE WITH RESPECT TO ANY SUBJECT    
--     MATTER OF THIS AGREEMENT UNDER TORT, CONTRACT, STRICT LIABILITY   
--     OR ANY OTHER LEGAL OR EQUITABLE THEORY (I) FOR ANY INDIRECT,      
--     SPECIAL, INCIDENTAL, EXEMPLARY OR CONSEQUENTIAL DAMAGES OF ANY    
--     CHARACTER INCLUDING, WITHOUT LIMITATION, DAMAGES FOR LOSS OF      
--     GOODWILL, DATA OR PROFIT, WORK STOPPAGE, OR COMPUTER FAILURE OR   
--     MALFUNCTION, OR IN ANY EVENT (II) FOR ANY AMOUNT IN EXCESS, IN    
--     THE AGGREGATE, OF THE FEE PAID BY LICENSEE TO EFINIX HEREUNDER    
--     (OR, IF THE FEE HAS BEEN WAIVED, $100), EVEN IF EFINIX SHALL HAVE 
--     BEEN INFORMED OF THE POSSIBILITY OF SUCH DAMAGES.  SOME STATES DO 
--     NOT ALLOW THE EXCLUSION OR LIMITATION OF INCIDENTAL OR            
--     CONSEQUENTIAL DAMAGES, SO THIS LIMITATION AND EXCLUSION MAY NOT   
--     APPLY TO LICENSEE.                                                
--
--------------------------------------------------------------------------------
