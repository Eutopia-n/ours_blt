// Benchmark-only stable 32x32 composition, fused with the original viewport
// clear. No private pixel RAM: source/background ports borrow fill_engine's
// existing banks. One outstanding AXI read, max 16 beats, complete error drain.
`default_nettype none
module tile_renderer #(
    parameter [31:0] ASSET_BASE=32'h01200000,ASSET_BYTES=32'h00100000
)(
    input wire clk,reset,start,memory_ready,
    input wire [31:0] source,list_address,frame_base,
    input wire [15:0] side,fragment_count,clear_color,color_key,
    input wire [1:0] blend_ctrl,input wire [7:0] alpha,
    output wire busy,output reg done,error,
    output reg [15:0] completed,
    output reg [31:0] cycles,burst_reads,burst_writes,read_wait,write_wait,
    output reg [31:0] araddr,output wire [7:0] arlen,
    output wire arvalid,input wire arready,
    input wire [31:0] rdata,input wire [1:0] rresp,
    input wire rlast,rvalid,output wire rready,
    output reg [31:0] awaddr,output wire [7:0] awlen,
    output wire awvalid,input wire awready,
    output wire [31:0] wdata,output wire [3:0] wstrb,
    output wire wlast,wvalid,input wire wready,
    input wire [1:0] bresp,input wire bvalid,output wire bready,
    output wire source_write,background_write,span_write,
    output wire [8:0] source_address,source_lo_address,source_hi_address,
    output wire [8:0] background_address,background_read_address,
    output wire [31:0] source_data,background_data,
    output wire [4:0] span_row,
    output wire [5:0] span_left,span_right,
    input wire [31:0] source_q,background_q,
    input wire [191:0] left_bits,right_bits
);
    localparam IDLE=0,RPLAN=1,RADDR=2,RDATA=3,OFFCHECK=4,CLEAR=5,
        POSPLAN=6,POSCHECK=7,ROWSPAN=8,ROWSET=9,PIXELS=10,NEXTROW=11,
        SPRITEEND=12,DRAIN=13,WSET=14,WPRIME=15,WLOAD=16,WADDR=17,WDATA=18,WRESP=19;
    localparam TEXTURE=0,OFFSETS=1,POSITIONS=2;
    reg [4:0] state;
    reg [1:0] read_kind;
    reg [15:0] read_left;
    reg [4:0] read_count,read_beat;
    reg read_bad;
    reg [9:0] texture_index;
    reg [4:0] texture_row,texture_column;
    reg [5:0] first_pixel,last_pixel;
    reg [7:0] tile_number;
    reg [9:0] tile_x,tile_y;
    reg [15:0] bin_start,bin_end,position_next;
    reg [511:0] position_buffer;
    reg [4:0] positions_left;
    reg [3:0] position_word;
    reg [9:0] sprite_x,sprite_y,pixel_y,row_end,pixel_x,word_end;
    reg [5:0] row_left,row_right;
    reg [8:0] source_word,background_word,clear_word,write_read_word;
    reg [9:0] write_y,write_end;
    reg [4:0] load_count;
    reg [3:0] write_beat;
    reg pipe0,pipe1;
    reg [8:0] pipe_address0,pipe_address1;
    reg [1:0] pipe_mask0;
    reg [31:0] pipe_data1;
    wire [9:0] texture_words=side==32 ? 512:side==24 ? 288:side==16 ? 128:8;
    wire [32:0] list_end={1'b0,list_address}+33'd768+{15'd0,fragment_count,2'd0};
    wire [32:0] texture_end={1'b0,source}+{21'd0,texture_words,2'd0};
    wire [10:0] to_boundary=11'd1024-{1'b0,araddr[11:2]};
    wire [4:0] proposed=read_left>16 ? 5'd16:read_left[4:0];
    wire read_failure=rresp!=0 || rlast!=(read_beat==read_count-1'b1);
    wire [5:0] texture_x={texture_column,1'b0};
    wire [5:0] load_first=first_pixel!=63 ? first_pixel:rdata[15:0]!=color_key ? texture_x:
        rdata[31:16]!=color_key ? texture_x+6'd1:6'd63;
    wire [5:0] load_last=rdata[31:16]!=color_key ? texture_x+6'd1:
        rdata[15:0]!=color_key ? texture_x:last_pixel;
    wire [31:0] position_value=position_buffer[position_word*32+:32];
    wire [15:0] position_x=position_value[15:0],position_y=position_value[31:16];
    wire [9:0] sprite_bottom=sprite_y+side[9:0];
    wire [4:0] source_row=pixel_y[4:0]-sprite_y[4:0];
    wire [9:0] span_x0=sprite_x+(blend_ctrl[1] ? {4'd0,row_left}:10'd0);
    wire [9:0] span_x1=sprite_x+(blend_ctrl[1] ? {4'd0,row_right}+10'd1:side[9:0]);
    wire [9:0] clipped_left=span_x0>tile_x ? span_x0:tile_x;
    wire [9:0] clipped_end=span_x1<tile_x+10'd32 ? span_x1:tile_x+10'd32;
    wire [9:0] aligned_left={clipped_left[9:1],1'b0};
    wire [9:0] source_delta=aligned_left-sprite_x;
    wire [8:0] source_row_word=side==32 ? {source_row,4'd0}:side==16 ? {1'd0,source_row,3'd0}:
        side==24 ? ({1'd0,source_row,3'd0}+{2'd0,source_row,2'd0}):{3'd0,source_row,1'd0};
    wire pixel_issue=state==PIXELS;
    wire [31:0] foreground=sprite_x[0] ? {source_q[15:0],source_q[31:16]}:source_q;
    function [5:0] channel;
        input [5:0] f,b;input [7:0] a;
        reg [13:0] t;reg [14:0] normalized;
        begin t=f*a+b*(8'd255-a)+14'd127;
            normalized={1'b0,t}+15'd1+{9'd0,t[13:8]};channel=normalized[13:8];end
    endfunction
    function [15:0] pixel_blend;
        input [15:0] f,b;input lane;
        reg [5:0] r,g,blue;
        begin
            if(!lane || (blend_ctrl[1] && f==color_key))pixel_blend=b;
            else if(!blend_ctrl[0] || alpha==255)pixel_blend=f;
            else begin
                r=channel({1'b0,f[15:11]},{1'b0,b[15:11]},alpha);
                g=channel(f[10:5],b[10:5],alpha);
                blue=channel({1'b0,f[4:0]},{1'b0,b[4:0]},alpha);
                pixel_blend={r[4:0],g[5:0],blue[4:0]};
            end
        end
    endfunction
    assign busy=state!=IDLE;
    assign arvalid=state==RADDR;
    assign arlen={3'd0,read_count}-8'd1;
    assign rready=state==RDATA;
    assign awvalid=state==WADDR;
    assign awlen=8'd15;
    assign wstrb=4'hf;
    assign wlast=write_beat==15;
    assign bready=state==WRESP;
    assign source_write=state==RDATA && read_kind==TEXTURE && rvalid;
    assign source_address=texture_index[8:0];
    assign source_data=rdata;
    assign source_lo_address=source_word+{8'd0,sprite_x[0]};
    assign source_hi_address=source_word;
    assign span_write=source_write && texture_column==side[5:1]-1'b1;
    assign span_row=texture_row;assign span_left=load_first;assign span_right=load_last;
    assign background_write=state==CLEAR || pipe1;
    assign background_address=state==CLEAR ? clear_word:pipe_address1;
    assign background_data=state==CLEAR ? {clear_color,clear_color}:pipe_data1;
    assign background_read_address=state>=WSET ? write_read_word:background_word;
    // A full 16-word row is staged before AW. Packed flops avoid spending two
    // scarce BRAMs on a tiny asynchronous-read FIFO.
    reg [511:0] write_row;
    wire fifo_pop=state==WDATA && wready;
    always @(posedge clk)if(state==WLOAD)write_row[load_count*32+:32]<=background_q;
    assign wdata=write_row[write_beat*32+:32];
    assign wvalid=state==WDATA;
    always @(posedge clk)begin
        if(reset)begin pipe0<=0;pipe1<=0;pipe_address0<=0;pipe_address1<=0;pipe_mask0<=0;pipe_data1<=0;end
        else begin
            pipe0<=pixel_issue;pipe1<=pipe0;
            if(pixel_issue)begin
                pipe_address0<=background_word;
                pipe_mask0<={pixel_x+10'd1<sprite_x+side[9:0],pixel_x>=sprite_x};
            end
            if(pipe0)begin
                pipe_address1<=pipe_address0;
                pipe_data1<={pixel_blend(foreground[31:16],background_q[31:16],pipe_mask0[1]),
                             pixel_blend(foreground[15:0],background_q[15:0],pipe_mask0[0])};
            end
        end
    end
    always @(posedge clk)begin
        if(reset)begin
            state<=IDLE;done<=0;error<=0;completed<=0;cycles<=0;
            burst_reads<=0;burst_writes<=0;read_wait<=0;write_wait<=0;
            araddr<=0;awaddr<=0;read_kind<=0;read_left<=0;read_count<=0;read_beat<=0;read_bad<=0;
            texture_index<=0;texture_row<=0;texture_column<=0;first_pixel<=63;last_pixel<=0;
            tile_number<=0;tile_x<=0;tile_y<=128;bin_start<=0;bin_end<=0;position_next<=0;
            positions_left<=0;position_word<=0;sprite_x<=0;sprite_y<=0;pixel_y<=0;row_end<=0;
            pixel_x<=0;word_end<=0;row_left<=0;row_right<=0;source_word<=0;background_word<=0;
            clear_word<=0;write_read_word<=0;write_y<=0;write_end<=0;load_count<=0;write_beat<=0;
        end else begin
            if(busy)cycles<=cycles+1'b1;
            if(arvalid && arready)burst_reads<=burst_reads+1'b1;
            if(awvalid && awready)burst_writes<=burst_writes+1'b1;
            if((arvalid && !arready)||(rready && !rvalid))read_wait<=read_wait+1'b1;
            if((awvalid && !awready)||(wvalid && !wready)||(bready && !bvalid))write_wait<=write_wait+1'b1;
            case(state)
            IDLE:if(start)begin
                done<=0;error<=0;completed<=0;cycles<=0;
                tile_number<=0;tile_x<=0;tile_y<=128;bin_start<=0;bin_end<=0;
                texture_index<=0;texture_row<=0;texture_column<=0;first_pixel<=63;last_pixel<=0;
                if(!memory_ready || !(side==4 || side==16 || side==24 || side==32) ||
                    source[1:0]!=0 || source<ASSET_BASE || texture_end>{1'b0,ASSET_BASE}+{1'b0,ASSET_BYTES} ||
                    list_address[4:0]!=0 || list_address<ASSET_BASE || list_end>{1'b0,ASSET_BASE}+{1'b0,ASSET_BYTES})begin
                    error<=1;done<=1;
                end else if(fragment_count==0)begin
                    araddr<=list_address;read_left<=2;read_kind<=OFFSETS;state<=RPLAN;
                end else begin araddr<=source;read_left<=texture_words;read_kind<=TEXTURE;state<=RPLAN;end
            end
            RPLAN:begin
                read_count<=to_boundary<proposed ? to_boundary[4:0]:proposed;
                read_beat<=0;read_bad<=0;state<=RADDR;
            end
            RADDR:if(arready)state<=RDATA;
            RDATA:if(rvalid)begin
                if(read_failure)read_bad<=1;
                if(read_kind==TEXTURE)begin
                    texture_index<=texture_index+1'b1;
                    if(texture_column==side[5:1]-1'b1)begin
                        texture_column<=0;texture_row<=texture_row+1'b1;first_pixel<=63;last_pixel<=0;
                    end else begin texture_column<=texture_column+1'b1;first_pixel<=load_first;last_pixel<=load_last;end
                end else if(read_kind==OFFSETS)begin
                    if(tile_number==0 && read_beat==0)begin if(rdata!=0)read_bad<=1;end
                    else begin
                        bin_end<=rdata[15:0];
                        if(rdata[31:16]!=0 || rdata<bin_start || rdata>fragment_count)read_bad<=1;
                    end
                end else position_buffer[read_beat*32+:32]<=rdata;
                if(read_beat==read_count-1'b1)begin
                    if(read_bad || read_failure || (read_kind==OFFSETS &&
                        (rdata[31:16]!=0 || rdata<bin_start || rdata>fragment_count)))begin
                        error<=1;done<=1;state<=IDLE;
                    end else if(read_kind==TEXTURE && read_left!={11'd0,read_count})begin
                        read_left<=read_left-{11'd0,read_count};araddr<=araddr+{25'd0,read_count,2'd0};state<=RPLAN;
                    end else if(read_kind==TEXTURE)begin
                        araddr<=list_address;read_kind<=OFFSETS;read_left<=2;state<=RPLAN;
                    end else if(read_kind==OFFSETS)state<=OFFCHECK;
                    else begin
                        positions_left<=read_count;position_word<=0;
                        position_next<=position_next+{11'd0,read_count};state<=POSCHECK;
                    end
                end else read_beat<=read_beat+1'b1;
            end
            OFFCHECK:begin
                if(tile_number==179 && bin_end!=fragment_count)begin error<=1;done<=1;state<=IDLE;end
                else begin clear_word<=0;position_next<=bin_start;state<=CLEAR;end
            end
            CLEAR:if(clear_word==511)begin
                if(bin_start==bin_end)state<=DRAIN;else state<=POSPLAN;
            end else clear_word<=clear_word+1'b1;
            POSPLAN:begin
                araddr<=list_address+32'd768+{14'd0,position_next,2'd0};
                read_left<=bin_end-position_next;read_kind<=POSITIONS;state<=RPLAN;
            end
            POSCHECK:begin
                if(position_x>16'd640-side || position_y<152 || position_y>16'd408-side ||
                    position_x>={6'd0,tile_x}+16'd32 || position_x+side<={6'd0,tile_x} ||
                    position_y>={6'd0,tile_y}+16'd32 || position_y+side<={6'd0,tile_y})begin
                    error<=1;done<=1;state<=IDLE;
                end else begin
                    sprite_x<=position_x[9:0];sprite_y<=position_y[9:0];
                    pixel_y<=position_y>tile_y ? position_y[9:0]:(tile_y<152 ? 10'd152:tile_y);
                    row_end<=position_y+side<tile_y+32 ? position_y[9:0]+side[9:0]:(tile_y+32>408 ? 10'd408:tile_y+10'd32);
                    state<=ROWSPAN;
                end
            end
            ROWSPAN:begin
                row_left<=left_bits[source_row*6+:6];row_right<=right_bits[source_row*6+:6];state<=ROWSET;
            end
            ROWSET:if((blend_ctrl[1] && row_left==63) || clipped_left>=clipped_end)state<=NEXTROW;
                else begin
                    pixel_x<=aligned_left;word_end<=clipped_end;
                    source_word<=source_row_word+source_delta[9:1];
                    background_word<={pixel_y[4:0],clipped_left[4:1]};state<=PIXELS;
                end
            PIXELS:begin
                source_word<=source_word+1'b1;background_word<=background_word+1'b1;pixel_x<=pixel_x+10'd2;
                if(pixel_x+10'd2>=word_end)state<=NEXTROW;
            end
            NEXTROW:if(pixel_y+10'd1>=row_end)state<=SPRITEEND;
                else begin pixel_y<=pixel_y+1'b1;state<=ROWSPAN;end
            SPRITEEND:begin
                positions_left<=positions_left-1'b1;
                if(positions_left==1)state<=position_next==bin_end ? DRAIN:POSPLAN;
                else begin position_word<=position_word+1'b1;state<=POSCHECK;end
            end
            DRAIN:if(!pipe0 && !pipe1)begin
                write_y<=tile_y<152 ? 10'd152:tile_y;
                write_end<=tile_y+10'd32>408 ? 10'd408:tile_y+10'd32;state<=WSET;
            end
            WSET:begin
                awaddr<=frame_base+({22'd0,write_y}<<10)+({22'd0,write_y}<<8)+{21'd0,tile_x,1'b0};
                write_read_word<={write_y[4:0],4'd0};load_count<=0;write_beat<=0;state<=WPRIME;
            end
            WPRIME:begin write_read_word<=write_read_word+1'b1;state<=WLOAD;end
            WLOAD:begin
                load_count<=load_count+1'b1;
                if(load_count<14)write_read_word<=write_read_word+1'b1;
                if(load_count==15)state<=WADDR;
            end
            WADDR:if(awready)state<=WDATA;
            WDATA:if(fifo_pop)begin write_beat<=write_beat+1'b1;if(wlast)state<=WRESP;end
            WRESP:if(bvalid)begin
                if(bresp!=0)begin error<=1;done<=1;state<=IDLE;end
                else if(write_y+10'd1<write_end)begin write_y<=write_y+1'b1;state<=WSET;end
                else begin
                    completed<=bin_end;
                    if(tile_number==179)begin done<=1;state<=IDLE;end
                    else begin
                        tile_number<=tile_number+1'b1;bin_start<=bin_end;
                        if(tile_x==608)begin tile_x<=0;tile_y<=tile_y+10'd32;end
                        else tile_x<=tile_x+10'd32;
                        araddr<=list_address+{22'd0,tile_number,2'd0}+32'd8;
                        read_kind<=OFFSETS;read_left<=1;state<=RPLAN;
                    end
                end
            end
            default:begin error<=1;done<=1;state<=IDLE;end
            endcase
        end
    end
endmodule
`default_nettype wire
