//***************************************************************/
//
// Moudel Name    : ddr3_example_top.v
// Version        : 1.1
// Date Created   : 2023-02-23 10:37:59
// Last Modified  : 2023-02-24 15:27:41
// Abstract       : ---
//
//***************************************************************/
//Modification History
//1.initial
//***************************************************************/
`include "ddr3_controller/ddr3_parameter.vh"

`define Efinity_Debug
`timescale 1ps/1ps
// `define SOFT_JTAG

module competition_top #
(
parameter                       RANK_RATIO         = 1,       // # of unique CS outputs per rank
parameter                       CK_RATIO           = `CK_RATIO, 
parameter                       ASYN_AXI_CLK       = `ASYN_AXI_CLK, 
parameter                       RANKS              = `RANKS,
parameter                       CK_WIDTH           = `CK_WIDTH,       // # of CK/CK# outputs to memory   
parameter                       CKE_WIDTH          = `CKE_WIDTH,       // # of cke outputs
parameter                       CS_WIDTH           = `CS_WIDTH,       // # of unique CS outputs
parameter                       BANK_WIDTH         = `BANK_WIDTH,       // # of bank bits
parameter                       ROW_WIDTH          = `ROW_WIDTH,       // DRAM address bus width
parameter                       COL_WIDTH          = `COL_WIDTH,      // column address width
parameter                       DM_WIDTH           = `DM_WIDTH,       // # of DM (data mask)
parameter                       DQS_WIDTH          = `DQS_WIDTH,       // # of DQS (strobe)
parameter                       DQ_WIDTH           = `DQ_WIDTH,      // # of DQ (data)
parameter                       ODT_WIDTH          = `ODT_WIDTH,
parameter                       DQ_CNT_WIDTH       = `DQ_CNT_WIDTH,       // = ceil(log2(DQ_WIDTH))
parameter                       DQS_CNT_WIDTH      = `DQS_CNT_WIDTH,       // = ceil(log2(DQS_WIDTH))  
parameter                       DRAM_WIDTH         = `DRAM_WIDTH,       // # of DQ per DQS   
parameter                       DATA_WIDTH         = `DATA_WIDTH,
parameter                       ADDR_WIDTH         = `ADDR_WIDTH,    
parameter                       AXI_ID_WIDTH       = `AXI_ID_WIDTH,
parameter                       AXI_ADDR_WIDTH     = `AXI_ADDR_WIDTH,
parameter                       AXI_DATA_WIDTH     = `AXI_DATA_WIDTH
)
(

   // HDMI TX serializer ports imported from the board HDMI demo.
   input hdmi_tx_locked,
   input hdmi_tx_slow_clk,
   output [9:0] tmds_data0_o, tmds_data1_o, tmds_data2_o, tmds_clk_o,
   output tmds_data0_TX_OE, tmds_data1_TX_OE, tmds_data2_TX_OE, tmds_clk_TX_OE,
   output tmds_data0_TX_RST, tmds_data1_TX_RST, tmds_data2_TX_RST, tmds_clk_TX_RST,
   // Clock and reset ports
   input                              axi_clk,      
   input                              core_clk,     // CORE CLK @ 100MHz
   input                              sdram_clk,    // SDRAM CK @ 400MHz
   input                              rx_cal_clk,   // SDRAM CK @ 400MHz
   input                              tx_cal_clk,   // SDRAM CK @ 400MHz
   input                              tx_cal_clk_90edge,   // SDRAM CK @ 400MHz
   input                              pll_locked,
   input                              user_pll_locked,
  //  input                              peripheralClk,
   //&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
   output  wire                       system_uart_0_io_txd,
   input                              system_uart_0_io_rxd,   
   input  [3:0]                       key_i,
    // debug core ports
`ifdef  Efinity_Debug  //&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&& 
`ifdef SOFT_JTAG
  input                               io_jtag_tms,
  input                               io_jtag_tdi,
  output  wire                        io_jtag_tdo,
  input                               io_jtag_tck,
`else
  input                               jtag_inst1_CAPTURE ,
  input                               jtag_inst1_DRCK    ,
  input                               jtag_inst1_RESET   ,
  input                               jtag_inst1_RUNTEST ,
  input                               jtag_inst1_SEL     ,
  input                               jtag_inst1_SHIFT   ,
  input                               jtag_inst1_TCK     ,
  input                               jtag_inst1_TDI     ,
  input                               jtag_inst1_TMS     ,
  input                               jtag_inst1_UPDATE  ,
  output                              jtag_inst1_TDO     ,
`endif 

`endif  //&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
   // PLL status flags  
   output [2:0]                       pll_shift,  
   output [4:0]                       pll_shift_sel,
   output                             pll_shift_ena,  
   // memory interface ports
   output                             ddr_ck_hi,
   output                             ddr_ck_lo,
   output                             ddr_reset_n,
   output [CKE_WIDTH-1:0]             ddr_cke,     
   output [ROW_WIDTH-1:0]             ddr_addr,
   output [BANK_WIDTH-1:0]            ddr_ba,
   output                             ddr_cas_n,

   output [CS_WIDTH*RANK_RATIO-1:0]   ddr_cs_n,
   output                             ddr_ras_n,
   output                             ddr_we_n,
   
   input  [DQS_WIDTH-1:0]             ddr_dqs_in_hi,
   input  [DQS_WIDTH-1:0]             ddr_dqs_in_lo,
   input  [DQ_WIDTH-1:0]              ddr_dq_in_hi,
   input  [DQ_WIDTH-1:0]              ddr_dq_in_lo,
   
   output [DQS_WIDTH-1:0]             ddr_dqs_oe,
   output [DQS_WIDTH-1:0]             ddr_dqs_oe_n,
   output [DQ_WIDTH-1:0]              ddr_dq_oe,  
   output [DQS_WIDTH-1:0]             ddr_dqs_out_hi,
   output [DQS_WIDTH-1:0]             ddr_dqs_out_lo,
   output [DQ_WIDTH-1:0]              ddr_dq_out_hi,
   output [DQ_WIDTH-1:0]              ddr_dq_out_lo,
   output [DM_WIDTH-1:0]              ddr_dm_hi,
   output [DM_WIDTH-1:0]              ddr_dm_lo,
   output [ODT_WIDTH-1:0]             ddr_odt,

   input                              system_spi_0_io_data_0_IN,
   input                              system_spi_0_io_data_1_IN,
   output                             system_spi_0_io_ss,
   output                             system_spi_0_io_sclk_write,
   output                             system_spi_0_io_data_0_OUT,
   output                             system_spi_0_io_data_0_OE,
   output                             system_spi_0_io_data_1_OUT,
   output                             system_spi_0_io_data_1_OE

   );


      
//Parameter Define
parameter FREQ = 100;			// default is 100 MHz.  Redefine as needed.
`ifndef SIM
    localparam CNT_INIT = 1.5*FREQ*1000;
`else
    localparam CNT_INIT = 10;
`endif    
  localparam   AIW               = AXI_ID_WIDTH      ;
  localparam   ADW               = AXI_DATA_WIDTH    ;
  localparam   ABN               = AXI_DATA_WIDTH/8   ;
  /////////////////////////////////////////////////////////
  // Wire declarations
  reg  [19:0]                       cnt;    
  wire                              clk;
  wire                              rst;
  wire                              mmcm_locked;
  reg                               aresetn;
  wire                              app_sr_active;
  wire                              app_ref_ack;
  wire                              app_zq_ack;

  wire                              cal_done;

  wire [15:0] apb_paddr;
  wire [31:0] apb_pwdata, apb_prdata;
  wire apb_psel, apb_penable, apb_pready, apb_pwrite, apb_pslverror;
  wire soc_reset, master_reset;
  wire [3:0] button_pending, button_ack, button_held;
  button_input #(.ENABLE_REPEAT(0)) buttons (
      .clk(user_clk),.reset(soc_reset),.key_n(key_i),
      .ack_toggle(button_ack[0]),.pending(button_pending),.held(button_held)
  );
  reg [1:0] calibration_sync;
  always @(posedge user_clk or negedge sys_rst)
    if (!sys_rst) calibration_sync <= 0;
    else calibration_sync <= {calibration_sync[0],cal_done};
  wire [31:0] cpu_ddr_awaddr, cpu_ddr_araddr;
  assign s_axi_awaddr = cpu_ddr_awaddr[27:0];
  assign s_axi_araddr = cpu_ddr_araddr[27:0];
  wire [31:0] gfx_awaddr, gfx_wdata, gfx_araddr, gfx_rdata;
  wire [7:0] gfx_awlen, gfx_arlen;
  wire [3:0] gfx_wstrb;
  wire [1:0] gfx_bresp, gfx_rresp;
  wire gfx_awvalid, gfx_awready, gfx_wvalid, gfx_wready, gfx_wlast;
  wire gfx_bvalid, gfx_bready, gfx_arvalid, gfx_arready, gfx_rvalid, gfx_rready, gfx_rlast;
  wire [15:0] video_pixel;
  wire video_hs, video_vs, video_de;
  wire [9:0] tmds_data0, tmds_data1, tmds_data2, tmds_clk;
  wire renderer_reset = soc_reset | master_reset | !hdmi_tx_locked;


  // Slave Interface Write Address Ports
  wire [AXI_ID_WIDTH-1:0]           s_axi_awid;
  wire [AXI_ADDR_WIDTH-1:0]         s_axi_awaddr;
  wire [7:0]                        s_axi_awlen;
  wire [2:0]                        s_axi_awsize;
  wire [1:0]                        s_axi_awburst;
  wire [0:0]                        s_axi_awlock;
  wire [3:0]                        s_axi_awcache;
  wire [2:0]                        s_axi_awprot;
  wire                              s_axi_awvalid;
  wire                              s_axi_awready;
   // Slave Interface Write Data Ports
  wire [AXI_DATA_WIDTH-1:0]         s_axi_wdata;
  wire [(AXI_DATA_WIDTH/8)-1:0]     s_axi_wstrb;
  wire                              s_axi_wlast;
  wire                              s_axi_wvalid;
  wire                              s_axi_wready;
   // Slave Interface Write Response Ports
  wire                              s_axi_bready;
  wire [AXI_ID_WIDTH-1:0]           s_axi_bid;
  wire [1:0]                        s_axi_bresp;
  wire                              s_axi_bvalid;
   // Slave Interface Read Address Ports
  wire [AXI_ID_WIDTH-1:0]           s_axi_arid;
  wire [AXI_ADDR_WIDTH-1:0]         s_axi_araddr;
  wire [7:0]                        s_axi_arlen;
  wire [2:0]                        s_axi_arsize;
  wire [1:0]                        s_axi_arburst;
  wire [0:0]                        s_axi_arlock;
  wire [3:0]                        s_axi_arcache;
  wire [2:0]                        s_axi_arprot;
  wire                              s_axi_arvalid;
  wire                              s_axi_arready;
   // Slave Interface Read Data Ports
  wire                              s_axi_rready;
  wire [AXI_ID_WIDTH-1:0]           s_axi_rid;
  wire [AXI_DATA_WIDTH-1:0]         s_axi_rdata;
  wire [1:0]                        s_axi_rresp;
  wire                              s_axi_rlast;
  wire                              s_axi_rvalid;


//***************************************************************************
  wire [2:0]                        vio_pll_shift;  
  wire [4:0]                        vio_pll_shift_sel;
  wire                              vio_pll_shift_ena; 
  wire                              pos_pll_shift_ena; 
  wire [2:0]                        phy_pll_shift;  
  wire [4:0]                        phy_pll_shift_sel;
  wire                              phy_pll_shift_ena; 
  wire                              ddr_reset; 
  wire                              sys_rst;
  wire  [2:0]                       phy_wr_pll_shift;
  wire                              idelay_ld       ;
  wire                              mpr_rdlvl_dly   ;
  wire  [7:0]                       wrlvl_dq_check  ;
  wire  [7:0]                       rd_level_dqs_check;  
  wire  [2:0]                       rdlvl_shift;  
  wire  [2:0]                       wrlvl_shift;  
  wire  [15:0]                      debug_fifo;  
  wire  [15:0]                      overflow_fifo;  
  wire  [6:0]                       init_cur_state;  
  wire  [35:0]                      ddr_debug_port;  
  wire                              app_rdy;  
  wire                              user_clk;  
  wire                              ddr_rstn;  
  wire                                phy_rddata_valid;
  wire [2*CK_RATIO*DQ_WIDTH-1:0]      phy_rd_data;
  wire [2*CK_RATIO*DATA_WIDTH-1:0]    app_rd_data_to_axi; 
  wire                                app_rd_data_end;
  wire                                app_rd_data_valid;
  wire [2*CK_RATIO*DQ_WIDTH-1:0]      rd_data;          
  wire                                rd_data_en;            
  wire                                rd_data_end;   
   
  
// Start of User Design top instance
//***************************************************************************
// The User design is instantiated below. The memory interface ports are
// connected to the top-level and the application interface ports are
// connected to the traffic generator module. This provides a reference
// for connecting the memory controller to system.
//***************************************************************************
always @(posedge user_clk or negedge sys_rst) begin
	if (!sys_rst)
		cnt <= 0;
    else if (cnt != CNT_INIT) 
        cnt <= cnt + 20'd1;
	else 
        cnt <= cnt;
end
assign ddr_rstn = (cnt == CNT_INIT);


generate
if (ASYN_AXI_CLK) begin
assign user_clk = axi_clk;

end else begin
assign user_clk = core_clk;
end
endgenerate
//***************************************************************************
// The traffic generation module instantiated below drives traffic (patterns)
// on the application interface of the memory controller
//***************************************************************************
//***************************************************************************

assign sys_rst       = pll_locked & user_pll_locked;

//***************************************************************************
ddr3_top                 u_ddr3_top
      (
      
    .axi_clk                (user_clk             ),
    .core_clk               (core_clk            ),
    .sdram_clk              (sdram_clk           ),  
    .rx_cal_clk             (rx_cal_clk          ),
    .tx_cal_clk             (tx_cal_clk          ),
    .tx_cal_clk_90edge      (tx_cal_clk_90edge   ),
    .rstn                   (ddr_rstn            ),      
    .pll_shift              (pll_shift           ),
    .pll_shift_sel          (pll_shift_sel       ),
    .pll_shift_ena          (pll_shift_ena       ), 
///////////////DDR BUS
    .ddr_ck_hi              (ddr_ck_hi           ),
    .ddr_ck_lo              (ddr_ck_lo           ),
    .ddr_cke                (ddr_cke             ),    
    .ddr_reset_n            (ddr_reset_n         ),
    .ddr_cs_n               (ddr_cs_n            ),
    .ddr_ras_n              (ddr_ras_n           ),
    .ddr_cas_n              (ddr_cas_n           ),
    .ddr_we_n               (ddr_we_n            ),     
    .ddr_addr               (ddr_addr            ),
    .ddr_ba                 (ddr_ba              ),

    .ddr_dqs_oe             (ddr_dqs_oe          ),
    .ddr_dqs_oe_n           (ddr_dqs_oe_n        ),
    .ddr_dq_oe              (ddr_dq_oe           ),
    .ddr_dqs_in_hi          (ddr_dqs_in_hi       ),
    .ddr_dqs_in_lo          (ddr_dqs_in_lo       ),
    .ddr_dq_in_hi           (ddr_dq_in_hi        ),
    .ddr_dq_in_lo           (ddr_dq_in_lo        ),

    .ddr_dqs_out_hi         (ddr_dqs_out_hi      ),
    .ddr_dqs_out_lo         (ddr_dqs_out_lo      ),
    .ddr_dq_out_hi          (ddr_dq_out_hi       ),
    .ddr_dq_out_lo          (ddr_dq_out_lo       ),
    
    .ddr_dm_hi              (ddr_dm_hi           ),
    .ddr_dm_lo              (ddr_dm_lo           ),
    .ddr_odt                (ddr_odt             ),

// Application interface ports
       .app_sr_req                     (1'b0),
       .app_ref_req                    (1'b0),
       .app_zq_req                     (1'b0),
       .app_sr_active                  (app_sr_active),
       .app_ref_ack                    (app_ref_ack),
       .app_zq_ack                     (app_zq_ack),

// Slave Interface Write Address Ports
       .s_axi_awid                     (s_axi_awid        ),
       .s_axi_awaddr                   (s_axi_awaddr      ),
       .s_axi_awlen                    (s_axi_awlen       ),
       .s_axi_awsize                   (s_axi_awsize      ),
       .s_axi_awburst                  (s_axi_awburst     ),
       .s_axi_awlock                   (s_axi_awlock      ),
       .s_axi_awcache                  (s_axi_awcache     ),
       .s_axi_awprot                   (s_axi_awprot      ),
       .s_axi_awqos                    (4'h0              ),
       .s_axi_awvalid                  (s_axi_awvalid     ),
       .s_axi_awready                  (s_axi_awready     ),
// Slave Interface Write Data Ports
       .s_axi_wdata                    (s_axi_wdata       ),
       .s_axi_wstrb                    (s_axi_wstrb       ),
       .s_axi_wlast                    (s_axi_wlast       ),
       .s_axi_wvalid                   (s_axi_wvalid      ),
       .s_axi_wready                   (s_axi_wready      ),
// Slave Interface Write Response Ports
       .s_axi_bid                      (s_axi_bid         ),
       .s_axi_bresp                    (s_axi_bresp       ),
       .s_axi_bvalid                   (s_axi_bvalid      ),
       .s_axi_bready                   (s_axi_bready      ),
// Slave Interface Read Address Ports
       .s_axi_arid                     (s_axi_arid        ),
       .s_axi_araddr                   (s_axi_araddr      ),
       .s_axi_arlen                    (s_axi_arlen       ),
       .s_axi_arsize                   (s_axi_arsize      ),
       .s_axi_arburst                  (s_axi_arburst     ),
       .s_axi_arlock                   (s_axi_arlock      ),
       .s_axi_arcache                  (s_axi_arcache     ),
       .s_axi_arprot                   (s_axi_arprot      ),
       .s_axi_arqos                    (4'h0              ),
       .s_axi_arvalid                  (s_axi_arvalid     ),
       .s_axi_arready                  (s_axi_arready     ),
// Slave Interface Read Data Ports
       .s_axi_rid                      (s_axi_rid         ),
       .s_axi_rdata                    (s_axi_rdata       ),
       .s_axi_rresp                    (s_axi_rresp       ),
       .s_axi_rlast                    (s_axi_rlast       ),
       .s_axi_rvalid                   (s_axi_rvalid      ),
       .s_axi_rready                   (s_axi_rready      ),
//DEBUG       
       .wrlvl_dq_check                 (wrlvl_dq_check    ) ,
       .rd_level_dqs_check             (rd_level_dqs_check) ,
       .rdlvl_shift                    (rdlvl_shift) ,
       .wrlvl_shift                    (wrlvl_shift) ,
       .init_cur_state                 (init_cur_state    ) ,
       .idelay_ld                      (idelay_ld         ) ,
       .mpr_rdlvl_dly                  (mpr_rdlvl_dly     ) ,
       .ddr_debug_port                 (ddr_debug_port    ) ,
       .cal_done                       (cal_done          ) 
       );
// End of User Design top instance

//***************************************************************************


//***************************************************************************
soc u_sapphire_soc(
    .io_systemClk (user_clk),
    .io_ddrA_w_payload_strb (s_axi_wstrb),
    .io_ddrA_w_payload_data (s_axi_wdata),
    .axiA_awready (1'b0),
    .axiA_awlen (),
    .axiA_awsize (),
    .axiA_arburst (),
    .axiA_awlock (),
    .axiA_arcache (),
    .axiA_awqos (),
    .axiA_awprot (),
    .axiA_arsize (),
    .axiA_arregion (),
    .axiA_arready (1'b0),
    .axiA_arqos (),
    .axiA_arprot (),
    .axiA_arlock (),
    .axiA_arlen (),
    .axiA_arid (),
    .axiA_awcache (),
    .axiA_awburst (),
    .axiA_awaddr (),
    .axiAInterrupt (1'b0),
    .axiA_rlast (1'b0),
    .jtagCtrl_enable (jtag_inst1_SEL),
    .jtagCtrl_tdi (jtag_inst1_TDI),
    .jtagCtrl_capture (jtag_inst1_CAPTURE),
    .jtagCtrl_shift (jtag_inst1_SHIFT),
    .jtagCtrl_update (jtag_inst1_UPDATE),
    .jtagCtrl_reset (jtag_inst1_RESET),
    .jtagCtrl_tdo (jtag_inst1_TDO),
    .jtagCtrl_tck (jtag_inst1_TCK),
    .axiA_araddr (),
    .axiA_wvalid (),
    .axiA_wready (1'b0),
    .axiA_wdata (),
    .axiA_wstrb (),
    .axiA_wlast (),
    .axiA_bvalid (1'b0),
    .axiA_bready (),
    .axiA_bid ('b0),
    .axiA_bresp ('b0),
    .axiA_rvalid (1'b0),
    .axiA_rready (),
    .axiA_rdata ('b0),
    .axiA_rid ('b0),
    .axiA_rresp ('b0),
    .axiA_arvalid (),
    .axiA_awid (),
    .axiA_awregion (),
    .axiA_awvalid (),
    .io_ddrA_r_payload_last (s_axi_rlast),
    .io_ddrA_r_payload_resp (s_axi_rresp),
    .io_ddrA_r_payload_id (s_axi_rid),
    .io_ddrA_r_payload_data (s_axi_rdata),
    .io_ddrA_r_ready (s_axi_rready),
    .io_ddrA_r_valid (s_axi_rvalid),
    .io_ddrA_b_payload_resp (s_axi_bresp),
    .io_ddrA_b_payload_id (s_axi_bid),
    .io_ddrA_b_ready (s_axi_bready),
    .io_ddrA_b_valid (s_axi_bvalid),
    .io_ddrA_w_payload_last (s_axi_wlast),
    .io_ddrA_w_ready (s_axi_wready),
    .io_ddrA_w_valid (s_axi_wvalid),
    .io_ddrA_aw_payload_prot (s_axi_awprot),
    .io_ddrA_aw_payload_qos (),
    .io_ddrA_aw_payload_cache (s_axi_awcache),
    .io_ddrA_aw_payload_lock (s_axi_awlock),
    .io_ddrA_aw_payload_burst (s_axi_awburst),
    .io_ddrA_aw_payload_size (s_axi_awsize),
    .io_ddrA_aw_payload_len (s_axi_awlen),
    .io_ddrA_aw_payload_region (),
    .io_ddrA_aw_payload_id (s_axi_awid),
    .io_ddrA_aw_payload_addr (cpu_ddr_awaddr),
    .io_ddrA_aw_ready (s_axi_awready),
    .io_ddrA_aw_valid (s_axi_awvalid),
    .io_ddrA_ar_payload_prot (s_axi_arprot),
    .io_ddrA_ar_payload_qos (),
    .io_ddrA_ar_payload_cache (s_axi_arcache),
    .io_ddrA_ar_payload_lock (s_axi_arlock),
    .io_ddrA_ar_payload_burst (s_axi_arburst),
    .io_ddrA_ar_payload_size (s_axi_arsize),
    .io_ddrA_ar_payload_len (s_axi_arlen),
    .io_ddrA_ar_payload_region (),
    .io_ddrA_ar_payload_id (s_axi_arid),
    .io_ddrA_ar_payload_addr (cpu_ddr_araddr),
    .io_ddrA_ar_ready (s_axi_arready),
    .io_ddrA_ar_valid (s_axi_arvalid),
    .system_spi_0_io_data_0_read (system_spi_0_io_data_0_IN),
    .system_spi_0_io_data_0_write (system_spi_0_io_data_0_OUT),
    .system_spi_0_io_data_0_writeEnable (system_spi_0_io_data_0_OE),
    .system_spi_0_io_data_1_read (system_spi_0_io_data_1_IN),
    .system_spi_0_io_data_1_write (system_spi_0_io_data_1_OUT),
    .system_spi_0_io_data_1_writeEnable (system_spi_0_io_data_1_OE),
    .system_spi_0_io_data_2_read (1'b0),
    .system_spi_0_io_data_2_write (),
    .system_spi_0_io_data_2_writeEnable (),
    .system_spi_0_io_data_3_read (1'b0),
    .system_spi_0_io_data_3_write (),
    .system_spi_0_io_data_3_writeEnable (),
    .system_spi_0_io_sclk_write (system_spi_0_io_sclk_write),
    .userInterruptA (1'b0),
    .io_apbSlave_0_PADDR (apb_paddr),
    .io_apbSlave_0_PENABLE (apb_penable),
    .io_apbSlave_0_PRDATA (apb_prdata),
    .io_apbSlave_0_PREADY (apb_pready),
    .io_apbSlave_0_PSEL (apb_psel),
    .io_apbSlave_0_PSLVERROR (apb_pslverror),
    .io_apbSlave_0_PWDATA (apb_pwdata),
    .io_apbSlave_0_PWRITE (apb_pwrite),
    .io_asyncReset (!calibration_sync[1]),
    .io_memoryClk (user_clk),
    .io_systemReset (soc_reset),
    .system_uart_0_io_txd (system_uart_0_io_txd),
    .io_memoryReset (),
    .system_uart_0_io_rxd (system_uart_0_io_rxd),
    .system_i2c_0_io_scl_read (1'b1),
    .system_i2c_0_io_scl_write (),
    .system_i2c_0_io_sda_read (1'b1),
    .system_i2c_0_io_sda_write (),
    .system_gpio_0_io_writeEnable (),
    .io_ddrMasters_0_reset (master_reset),
    .io_ddrMasters_0_clk (user_clk),
    .io_ddrMasters_0_r_payload_last (gfx_rlast),
    .io_ddrMasters_0_r_payload_resp (gfx_rresp),
    .io_ddrMasters_0_r_payload_id (),
    .io_ddrMasters_0_r_payload_data (gfx_rdata),
    .io_ddrMasters_0_r_ready (gfx_rready),
    .io_ddrMasters_0_r_valid (gfx_rvalid),
    .io_ddrMasters_0_ar_payload_prot (3'd0),
    .io_ddrMasters_0_ar_payload_qos (4'd0),
    .io_ddrMasters_0_ar_payload_cache (4'd0),
    .io_ddrMasters_0_ar_payload_lock (1'b0),
    .io_ddrMasters_0_ar_payload_burst (2'b01),
    .io_ddrMasters_0_ar_payload_size (3'd2),
    .io_ddrMasters_0_ar_payload_len (gfx_arlen),
    .io_ddrMasters_0_ar_payload_region (4'd0),
    .io_ddrMasters_0_ar_payload_id (4'd0),
    .io_ddrMasters_0_ar_payload_addr (gfx_araddr),
    .io_ddrMasters_0_ar_ready (gfx_arready),
    .io_ddrMasters_0_ar_valid (gfx_arvalid),
    .io_ddrMasters_0_b_payload_resp (gfx_bresp),
    .io_ddrMasters_0_b_payload_id (),
    .io_ddrMasters_0_b_ready (gfx_bready),
    .io_ddrMasters_0_b_valid (gfx_bvalid),
    .io_ddrMasters_0_w_payload_last (gfx_wlast),
    .io_ddrMasters_0_w_payload_strb (gfx_wstrb),
    .io_ddrMasters_0_w_payload_data (gfx_wdata),
    .io_ddrMasters_0_w_ready (gfx_wready),
    .io_ddrMasters_0_w_valid (gfx_wvalid),
    .io_ddrMasters_0_aw_payload_prot (3'd0),
    .io_ddrMasters_0_aw_payload_qos (4'd0),
    .io_ddrMasters_0_aw_payload_cache (4'd0),
    .io_ddrMasters_0_aw_payload_lock (1'b0),
    .io_ddrMasters_0_aw_payload_burst (2'b01),
    .io_ddrMasters_0_aw_payload_size (3'd2),
    .io_ddrMasters_0_aw_payload_len (gfx_awlen),
    .io_ddrMasters_0_aw_payload_region (4'd0),
    .io_ddrMasters_0_aw_payload_id (4'd0),
    .io_ddrMasters_0_aw_payload_addr (gfx_awaddr),
    .io_ddrMasters_0_aw_ready (gfx_awready),
    .io_ddrMasters_0_aw_valid (gfx_awvalid),
    .system_gpio_0_io_write (button_ack),
    .system_gpio_0_io_read (button_pending),
    .system_spi_0_io_ss (system_spi_0_io_ss)
);


render_subsystem graphics (
    .clk(user_clk),.reset(renderer_reset),.pixel_clk(hdmi_tx_slow_clk),
    .memory_ready(calibration_sync[1]),
    .button_held(button_held),
    .paddr(apb_paddr),.psel(apb_psel),.penable(apb_penable),.pwrite(apb_pwrite),
    .pwdata(apb_pwdata),.prdata(apb_prdata),.pready(apb_pready),.pslverror(apb_pslverror),
    .awaddr(gfx_awaddr),.awlen(gfx_awlen),.awvalid(gfx_awvalid),.awready(gfx_awready),
    .wdata(gfx_wdata),.wstrb(gfx_wstrb),.wvalid(gfx_wvalid),.wready(gfx_wready),.wlast(gfx_wlast),
    .bresp(gfx_bresp),.bvalid(gfx_bvalid),.bready(gfx_bready),
    .araddr(gfx_araddr),.arlen(gfx_arlen),.arvalid(gfx_arvalid),.arready(gfx_arready),
    .rdata(gfx_rdata),.rresp(gfx_rresp),.rlast(gfx_rlast),.rvalid(gfx_rvalid),.rready(gfx_rready),
    .pixel(video_pixel),.hs(video_hs),.vs(video_vs),.de(video_de)
);
reg [1:0] hdmi_reset_pipe;
always @(posedge hdmi_tx_slow_clk or posedge renderer_reset)
    if (renderer_reset) hdmi_reset_pipe <= 2'b11;
    else hdmi_reset_pipe <= {hdmi_reset_pipe[0],1'b0};
dvi_encoder hdmi (
    .pixelclk(hdmi_tx_slow_clk),.rstin(hdmi_reset_pipe[1]),
    .red_din({video_pixel[15:11],video_pixel[15:13]}),
    .green_din({video_pixel[10:5],video_pixel[10:9]}),
    .blue_din({video_pixel[4:0],video_pixel[4:2]}),
    .hsync(video_hs),.vsync(video_vs),.de(video_de),
    .tmds_data0(tmds_data0),.tmds_data1(tmds_data1),.tmds_data2(tmds_data2),.tmds_clk(tmds_clk)
);
// The board swaps P/N on all four TX pairs: preserve the vendor inversion.
assign tmds_data0_o = ~tmds_data0;
assign tmds_data1_o = ~tmds_data1;
assign tmds_data2_o = ~tmds_data2;
assign tmds_clk_o = ~tmds_clk;
assign {tmds_data0_TX_OE,tmds_data1_TX_OE,tmds_data2_TX_OE,tmds_clk_TX_OE} = 4'b1111;
assign {tmds_data0_TX_RST,tmds_data1_TX_RST,tmds_data2_TX_RST,tmds_clk_TX_RST} = 4'b0000;
    

//***************************************************************************


//***************************************************************************

endmodule
