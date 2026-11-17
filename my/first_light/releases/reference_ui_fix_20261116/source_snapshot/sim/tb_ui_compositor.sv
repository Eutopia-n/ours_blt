`timescale 1ns/1ps
module tb_ui_compositor;
`include "sim/ui_command_count.vh"
string case_name;
reg [31:0] metadata[0:2];
reg clk=0,reset=1,start=0;always #3.333 clk=~clk;
wire busy,done,error;wire [31:0] cycles,br,bw,rwait,wwait;
wire [31:0] awaddr,wdata,araddr;wire [7:0] awlen,arlen;
wire [3:0] wstrb;wire awvalid,wlast,wvalid,bready,arvalid,rready;
reg awready=0,wready=0,bvalid=0,arready=0,rvalid=0,rlast=0;
reg [31:0] rdata=0;reg [31:0] mem[0:262143],expected[0:153599],frame[0:153599];
reg [31:0] rng=32'h512ba9f3;integer tick=0,read_at,read_left,write_at,write_left,errors;
reg reading=0,writing=0;
ui_compositor #(.ASSET_BASE(32'h10000000)) dut(
 .clk(clk),.reset(reset),.start(start),.memory_ready(1'b1),.frame_base(32'h11096000),
 .dst(32'h11096000),.src(32'h10004000),.background(metadata[1]),.stride(32'd1280),
 .width(16'd640),.height(16'd480),.command_count(metadata[0][15:0]),.background_color(metadata[2][15:0]),
 .busy(busy),.done(done),.error(error),.cycles(cycles),.burst_reads(br),.burst_writes(bw),.read_wait(rwait),.write_wait(wwait),
 .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
 .wdata(wdata),.wstrb(wstrb),.wlast(wlast),.wvalid(wvalid),.wready(wready),
 .bresp(2'd0),.bvalid(bvalid),.bready(bready),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
 .rdata(rdata),.rresp(2'd0),.rlast(rlast),.rvalid(rvalid),.rready(rready));
always @(negedge clk)begin
 rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);
 awready=!writing && !bvalid && rng[0];wready=writing && rng[2:1]!=0;arready=!reading && rng[4:3]!=0;
 if(reading && !rvalid && rng[6:5]!=0)begin rdata=mem[(read_at-32'h10000000)/4];rvalid=1;rlast=read_left==1;end
end
always @(posedge clk)if(!reset)begin
 tick=tick+1;
 if(arvalid && arready)begin
  if(araddr<32'h10000000 || araddr+4*(arlen+1)>32'h10100000 || araddr[11:0]+4*(arlen+1)>4096)$fatal(1,"invalid AR %h",araddr);
  read_at=araddr;read_left=arlen+1;reading=1;
 end
 if(rvalid && rready)begin rvalid<=0;read_at=read_at+4;read_left=read_left-1;if(!read_left)reading=0;end
 if(awvalid && awready)begin
  if(awaddr<32'h11096000 || awaddr+64>32'h1112c000 || awlen!=15)$fatal(1,"front/invalid AW %h",awaddr);
  write_at=(awaddr-32'h11096000)/4;write_left=16;writing=1;
 end
 if(wvalid && wready)begin
  if(wstrb!=15 || wlast!=(write_left==1))$fatal(1,"bad W beat");
  frame[write_at]=wdata;write_at=write_at+1;write_left=write_left-1;
  if(!write_left)begin writing=0;bvalid<=1;end
 end
 if(bvalid && bready)bvalid<=0;
 if(tick>12000000)$fatal(1,"UI timeout state %d row %d",dut.state,dut.y);
end
initial begin
 if(!$value$plusargs("CASE=%s",case_name))case_name="curved";
 $readmemh({"software/build/reference_ui_check/",case_name,"_assets.hex"},mem);
 $readmemh({"software/build/reference_ui_check/",case_name,"_expected.hex"},expected);
 $readmemh({"software/build/reference_ui_check/",case_name,"_metadata.hex"},metadata);
 repeat(5)@(negedge clk);reset=0;start=1;@(negedge clk);start=0;
 wait(done);@(negedge clk);
 repeat(257)@(negedge clk);
 if(!done || busy)$fatal(1,"UI completion did not persist for CPU polling");
 if(error)$fatal(1,"UI error state %d row %d command %d",dut.state,dut.y,dut.command_index);
 errors=0;
 for(integer i=0;i<153600;i=i+1)if(frame[i]!==expected[i])begin
  if(errors<12)$display("mismatch pixel %d,%d got %h expected %h",(i*2)%640,(i*2)/640,frame[i],expected[i]);errors=errors+1;
 end
 if(errors)$fatal(1,"UI pixel mismatches %d",errors);
 $display("PASS UI actual curved book frame, randomized AXI stalls, exact scalar pixels, back-page writes only. case=%s cycles=%d bursts AR=%d AW=%d",case_name,cycles,br,bw);
 $finish;
end
endmodule
