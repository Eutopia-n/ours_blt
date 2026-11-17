`timescale 1ns/1ps
// Boot the real Sapphire CPU and current game firmware. DDR is held idle;
// success requires the startup UART banner, APB ID access and high-half stack.
module tb_soc_ram_boot;
    reg clk=0,reset=1,uart_rx=1;
    always #3.333333 clk=~clk;
    reg mem_clk=0;
    always #5 mem_clk=~mem_clk;
    `define SOC_MEMORY_CLK mem_clk
    wire soc_reset,master_reset,uart_tx;
    wire [4:0] button_pending=0;
    wire [3:0] button_ack;
    wire [15:0] paddr;
    wire psel,penable,pwrite;
    wire pready=1;
    wire pslverror=0;
    wire [31:0] pwdata;
    wire [31:0] prdata=32'h32444631;
    wire [31:0] awaddr,wdata,araddr;
    wire [31:0] rdata=0;
    wire [7:0] awlen,arlen;
    wire [3:0] wstrb;
    wire [1:0] bresp=0,rresp=0;
    wire awvalid,wvalid,wlast,bready,arvalid,rready;
    wire awready=0;
    wire wready=0;
    wire bvalid=0;
    wire arready=0;
    wire rvalid=0;
    wire rlast=0;
    `include "soc_wiring.vh"
    integer upper_writes=0,upper_reads=0,lower_reads=0,id_reads=0;
    integer uart_count=0;
    reg [7:0] uart_byte;
    string banner="Ti60 INDIVIDUAL DEMOS\015\012";
    `define CORE cpu.u_EfxSapphireSoc
    always @(posedge clk) if(!soc_reset) begin
        if(`CORE.system_ramA_ctrl_slaveModel_arbiterGen_oneToOne_arbiter_cmd_combStage_valid &&
           `CORE.system_ramA_logic_io_bus_cmd_ready) begin
            if(`CORE.system_ramA_ctrl_slaveModel_arbiterGen_oneToOne_arbiter_cmd_combStage_payload_fragment_address[16]) begin
                if(`CORE.system_ramA_ctrl_slaveModel_arbiterGen_oneToOne_arbiter_cmd_combStage_payload_fragment_opcode)
                    upper_writes++;
                else upper_reads++;
            end else if(!`CORE.system_ramA_ctrl_slaveModel_arbiterGen_oneToOne_arbiter_cmd_combStage_payload_fragment_opcode)
                lower_reads++;
        end
        if(psel && penable && !pwrite && paddr==0) id_reads++;
    end
    `undef CORE
    initial begin repeat(50) @(negedge clk); reset=0; end
    initial forever begin
        @(negedge uart_tx);
        if(!soc_reset) begin
            #(12960); // 1.5 bit periods: 150 MHz / (162 * 8) UART baud.
            for(integer bit_index=0;bit_index<8;bit_index++) begin
                uart_byte[bit_index]=uart_tx; #8640;
            end
            if(uart_byte!==banner[uart_count]) $fatal(1,"Unexpected boot UART byte %0d: %h expected %h",uart_count,uart_byte,banner[uart_count]);
            uart_count++;
            if(uart_count==banner.len()) begin
                if(!upper_writes || !upper_reads || !lower_reads || !id_reads)
                    $fatal(1,"Missing expanded-RAM boot coverage: %0d/%0d/%0d ID=%0d",upper_writes,upper_reads,lower_reads,id_reads);
                $display("OCR128 CPU BOOT PASSED: real firmware UART banner; APB ID; upper-half stack writes=%0d reads=%0d; lower reads=%0d",upper_writes,upper_reads,lower_reads);
                $finish;
            end
        end
    end
    initial begin #5000000; $fatal(1,"Expanded-RAM CPU boot timeout"); end
endmodule
