// One-command streaming frontend for the existing RGB565 fill/copy/blend
// engine. No descriptor FIFO/BRAM: the immutable list stays in DDR assets.
// All ports use the renderer clock. A descriptor AR owns the read channel
// through all eight accepted beats, including an error response.
`default_nettype none
module render_batch #(
    parameter [31:0] ASSET_BASE=32'h01200000,
    parameter [31:0] ASSET_BYTES=32'h00100000
)(
    input wire clk,reset,start,memory_ready,
    input wire [31:0] list_address,
    input wire [15:0] command_count,
    input wire packed_positions,
    input wire [31:0] common_source,common_stride,
    input wire [15:0] common_side,common_key,
    input wire [1:0] common_blend,input wire [7:0] common_alpha,
    output wire busy,output reg done,error,
    output reg [31:0] cycles,burst_reads,read_wait,
    output reg [15:0] completed,
    output reg engine_start,
    input wire engine_busy,engine_done,engine_error,
    output reg [31:0] source,destination,extent,source_stride,colors,control,
    output wire read_active,
    output reg [31:0] araddr,
    output wire [7:0] arlen,
    output wire arvalid,input wire arready,
    input wire [31:0] rdata,input wire [1:0] rresp,
    input wire rlast,rvalid,output wire rready
);
    localparam IDLE=0,ADDRESS=1,DATA=2,CHECK=3,ISSUE=4,ACCEPT=5,WAIT_DONE=6;
    reg [2:0] state,beat;
    reg [15:0] remaining;
    reg bad;
    wire [32:0] list_end={1'b0,list_address}+(packed_positions ? {15'd0,command_count,2'd0}:{12'd0,command_count,5'd0});
    assign busy=state!=IDLE;
    assign read_active=state==ADDRESS || state==DATA;
    assign arlen=packed_positions ? 8'd0:8'd7;
    assign arvalid=state==ADDRESS;
    assign rready=state==DATA;
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE;beat<=0;remaining<=0;bad<=0;
            done<=0;error<=0;cycles<=0;burst_reads<=0;read_wait<=0;completed<=0;
            engine_start<=0;araddr<=0;
            source<=0;destination<=0;extent<=0;source_stride<=0;colors<=0;control<=0;
        end else begin
            engine_start<=0;
            if(busy)cycles<=cycles+1'b1;
            if(arvalid && arready)burst_reads<=burst_reads+1'b1;
            if((state==ADDRESS && !arready)||(state==DATA && !rvalid))read_wait<=read_wait+1'b1;
            case(state)
            IDLE: if(start)begin
                done<=0;error<=0;cycles<=0;completed<=0;bad<=0;beat<=0;
                araddr<=list_address;remaining<=command_count;
                if(packed_positions)begin
                    source<=common_source;extent<={common_side,common_side};source_stride<=common_stride;
                    colors<={common_key,16'd0};control<={16'd0,common_alpha,4'd0,common_blend,2'd2};
                end
                if(command_count==0)done<=1;
                else if(!memory_ready || (packed_positions ? list_address[1:0]!=0:list_address[4:0]!=0) ||
                        list_address<ASSET_BASE ||
                        list_end>{1'b0,ASSET_BASE}+{1'b0,ASSET_BYTES})begin
                    done<=1;error<=1;
                end else state<=ADDRESS;
            end
            ADDRESS: if(arready)begin beat<=0;bad<=0;state<=DATA;end
            DATA: if(rvalid)begin
                if(packed_positions)begin
                    destination<=rdata;
                    if(rresp!=0 || !rlast)begin done<=1;error<=1;state<=IDLE;end
                    else state<=CHECK;
                end else begin
                if(rresp!=0 || rlast!=(beat==7))bad<=1;
                case(beat)
                0:source<=rdata;
                1:destination<=rdata;
                2:extent<=rdata;
                3:source_stride<=rdata;
                4:colors<=rdata;
                5:control<=rdata;
                // Both reserved words must be zero; never launch a partial
                // or failed record, but drain the accepted burst first.
                6,7:if(rdata!=0)bad<=1;
                endcase
                if(beat==7)begin
                    if(bad || rresp!=0 || !rlast || rdata!=0)begin
                        done<=1;error<=1;state<=IDLE;
                    end else state<=CHECK;
                end else beat<=beat+1'b1;
                end
            end
            CHECK:begin
                // op[1:0], blend flags[3:2], alpha[15:8]; all other bits zero.
                // UI projection (op3) remains outside the light batch ABI.
                if(control[1:0]==3 || (control & 32'hffff00f0)!=0)begin
                    done<=1;error<=1;state<=IDLE;
                end else state<=ISSUE;
            end
            ISSUE:begin engine_start<=1;state<=ACCEPT;end
            // Ignore the preceding command's sticky DONE on the start edge.
            // This also covers a fill-engine validation failure with no BUSY.
            ACCEPT:state<=WAIT_DONE;
            WAIT_DONE:if(engine_done && !engine_busy)begin
                if(engine_error)begin done<=1;error<=1;state<=IDLE;end
                else begin
                    completed<=completed+1'b1;
                    if(remaining==1)begin done<=1;state<=IDLE;end
                    else begin
                        remaining<=remaining-1'b1;araddr<=araddr+(packed_positions ? 32'd4:32'd32);state<=ADDRESS;
                    end
                end
            end
            default:begin done<=1;error<=1;state<=IDLE;end
            endcase
        end
    end
endmodule
`default_nettype wire
