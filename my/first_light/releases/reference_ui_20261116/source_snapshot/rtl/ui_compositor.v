// Menu-only scanline compositor. Operation 3 consumes a bounded DDR list of
// eight-word texture/solid spans. Legacy fill/copy/blend operations are separate.
// Nearest-neighbour Q16 sampling, RGB565 shading and alpha execute in hardware.
`default_nettype none
module ui_compositor #(
    parameter [31:0] ASSET_BASE=32'h01200000, ASSET_BYTES=32'h00100000
)(
    input wire clk,reset,start,memory_ready,
    input wire [31:0] frame_base,dst,src,background,stride,
    input wire [15:0] width,height,command_count,background_color,
    output wire busy,output reg done,error,output reg [31:0] cycles,
    output reg [31:0] burst_reads,burst_writes,read_wait,write_wait,
    output reg [31:0] awaddr,output wire [7:0] awlen,
    output wire awvalid,input wire awready,
    output wire [31:0] wdata,output wire [3:0] wstrb,
    output wire wlast,wvalid,input wire wready,
    input wire [1:0] bresp,input wire bvalid,output wire bready,
    output reg [31:0] araddr,output reg [7:0] arlen,
    output wire arvalid,input wire arready,
    input wire [31:0] rdata,input wire [1:0] rresp,
    input wire rlast,rvalid,output wire rready
);
    localparam IDLE=0,R_ADDR=1,R_DATA=2,ROW=3,CLEAR=4,
        CMD_PRIME=5,CMD_TEST=6,V_ROW=7,PIXEL_ADDR=8,LOOK=9,SAMPLE=10,
        NEXT_CMD=11,W_PREP=12,W_ADDR=13,W_PRIME=14,W_LOAD=15,W_DATA=16,W_RESP=17,CACHE_PRIME=18,SHADE=19,BLEND=20;
    reg [4:0] state,read_return;
    reg [1:0] read_kind; // 0 command list, 1 background row, 2 texture cache
    reg [3:0] read_beat;
    reg read_bad;
    reg [12:0] loaded_words,total_words;
    reg [9:0] count,command_index;
    reg [8:0] y;
    reg [8:0] row_word;
    reg [3:0] write_beat;
    reg [31:0] frame,background_base,write_data;
    reg [15:0] clear_color,lit_pixel,sampled_pixel;
    reg sampled_skip;
    reg [13:0] mix_fr,mix_fg,mix_fb,mix_br,mix_bg,mix_bb;
    reg [1023:0] packed_bg;
    wire packed_desk=background_base[0];
    wire [1:0] desk_index=(packed_bg[row_word[8:4]*32+:32] >> (row_word[3:0]*2));
    wire [15:0] desk_color=desk_index==0 ? 16'd4260:desk_index==1 ? 16'd8455:16'd15150;
    reg [19:0] cm0_q,cm2_q,cm3_q;
    wire [31:0] c0=cm0_q==20'hfffff ? 0:ASSET_BASE+cm0_q;
    wire [31:0] c2={6'd0,cm2_q[19:10],(cm2_q[9:0]-16'd256)};
    wire [31:0] c3={6'd0,cm3_q[19:10],{6{cm3_q[9]}},cm3_q[9:0]};
    reg [31:0] c1,c4,c5,c6,c7;
    reg [19:0] cm0[0:511];reg [15:0] cm1[0:511];reg [19:0] cm2[0:511],cm3[0:511];
    reg [19:0] cm4[0:511],cm5[0:511];reg [31:0] cm6[0:511],cm7[0:511];
    reg [15:0] line_lo[0:511],line_hi[0:511];
    reg [15:0] bg_lo,bg_hi;
    reg [31:0] cache[0:127],cache_q;
    reg [183:0] cache_tags;
    reg [7:0] cache_valid;
    reg [6:0] cache_index;
    reg [2:0] cache_bank;
    reg [22:0] cache_tag;
    reg [31:0] pixel_address,source_row,u,v_product;
    reg [31:0] texture,ustep;
    reg [9:0] source_w,source_h;
    reg [15:0] source_pitch,key_color;
    reg [1:0] pixel_subindex;
    reg [7:0] alpha,shade,flags;
    reg [9:0] x,last_x;
    reg signed [31:0] left_edge,right_edge;
    wire [8:0] line_index=state==W_DATA ? row_word+1'b1:(state==BLEND || (state==LOOK && alpha==255)) ? ((x+10'd1)>>1):(state==PIXEL_ADDR || state==LOOK || state==SAMPLE || state==CACHE_PRIME || state==SHADE) ? x[9:1]:row_word;
    reg [15:0] front_color;
    wire [7:0] front_index=cache_q>>(pixel_address[1:0]*8);
    always @* begin
        front_color=0;
        case(front_index[5:0])
        `include "rtl/ui_front_palette.vh"
        default:front_color=0;
        endcase
    end
    wire [31:0] sample_u=flags[1] ? source_w-1'b1-(u[31:16]>=source_w ? source_w-1'b1:u[31:16]):(u[31:16]>=source_w ? source_w-1'b1:u[31:16]);
    wire [1:0] texture_desk_index=(cache_q>>(pixel_address[1:0]*8+pixel_subindex*2));
    wire [15:0] texture_desk_color=texture_desk_index==0 ? 16'd4260:texture_desk_index==1 ? 16'd8455:16'd15150;
    wire [15:0] cached_pixel=flags[5] ? texture_desk_color:flags[4] ? front_color:pixel_address[1] ? cache_q[31:16]:cache_q[15:0];
    wire [15:0] background_pixel=x[0] ? bg_hi:bg_lo;
    wire [9:0] dy={1'b0,y}-$signed(c3[15:0]);
    wire [31:0] input_end=src+({22'd0,command_count[9:0]}<<5);
    wire valid_background=background==0 || (background>=ASSET_BASE &&
        {1'b0,background}+(background[0] ? 33'd30720:33'd614400)<={1'b0,ASSET_BASE}+{1'b0,ASSET_BYTES});
    function [5:0] mix_channel;
        input [5:0] a,b;input [7:0] weight;
        reg [13:0] t;reg [14:0] n;
        begin t=a*weight+b*(8'd255-weight)+14'd127;
            n={1'b0,t}+15'd1+{9'd0,t[13:8]};mix_channel=n[13:8];end
    endfunction
    function [15:0] shade_pixel;
        input [15:0] pixel;input [7:0] light;
        reg [5:0] r,g,b;
        begin r=mix_channel({1'b0,pixel[15:11]},0,light);
            g=mix_channel(pixel[10:5],0,light);b=mix_channel({1'b0,pixel[4:0]},0,light);
            shade_pixel={r[4:0],g[5:0],b[4:0]};end
    endfunction
    function [15:0] mix_pixel;
        input [15:0] a,b;input [7:0] weight;
        reg [5:0] r,g,bl;
        begin r=mix_channel({1'b0,a[15:11]},{1'b0,b[15:11]},weight);
            g=mix_channel(a[10:5],b[10:5],weight);
            bl=mix_channel({1'b0,a[4:0]},{1'b0,b[4:0]},weight);
            mix_pixel={r[4:0],g[5:0],bl[4:0]};end
    endfunction
    wire [31:0] sample_address=source_row+(flags[5] ? sample_u>>2:(sample_u<<(flags[4] ? 0:1)));
    wire [31:0] next_u=u+ustep;
    wire [31:0] next_sample_u=flags[1] ? source_w-1'b1-(next_u[31:16]>=source_w ? source_w-1'b1:next_u[31:16]):(next_u[31:16]>=source_w ? source_w-1'b1:next_u[31:16]);
    wire [31:0] next_sample_address=source_row+(flags[5] ? next_sample_u>>2:(next_sample_u<<(flags[4] ? 0:1)));
    wire texture_hit=texture==0 || (cache_valid[pixel_address[8:6]] && cache_tags[pixel_address[8:6]*23+:23]==pixel_address[31:9]);
    // Keep palette selection and RGB565 multiplication in separate clock cycles.
    wire fast_pixel=state==SAMPLE && alpha==255 && texture==0;
    wire opaque_texture=state==LOOK && alpha==255;
    wire [31:0] cache_read_address=(state==BLEND || fast_pixel || opaque_texture) ? next_sample_address:sample_address;
    wire [15:0] foreground=texture==0 ? key_color:shade_pixel(sampled_pixel,shade);
    // Register channel products before summing and normalizing. This keeps
    // the synchronous row-RAM -> alpha -> row-RAM path inside 150 MHz.
    function [5:0] normalize_mix;
        input [13:0] foreground_product,background_product;
        reg [13:0] t;reg [14:0] n;
        begin t=foreground_product+background_product+14'd127;
            n={1'b0,t}+15'd1+{9'd0,t[13:8]};normalize_mix=n[13:8];end
    endfunction
    wire [5:0] mixed_r=normalize_mix(mix_fr,mix_br);
    wire [5:0] mixed_g=normalize_mix(mix_fg,mix_bg);
    wire [5:0] mixed_b=normalize_mix(mix_fb,mix_bb);
    wire [15:0] composed={mixed_r[4:0],mixed_g,mixed_b[4:0]};
    assign busy=state!=IDLE;
    assign awlen=8'd15;assign awvalid=state==W_ADDR;
    assign wdata=write_data;assign wstrb=4'hf;
    assign wlast=write_beat==15;assign wvalid=state==W_DATA;
    assign bready=state==W_RESP;
    assign arvalid=state==R_ADDR;assign rready=state==R_DATA;

    wire background_write=rvalid && rready && read_kind==1 && !packed_desk;
    wire clearing=state==CLEAR;
    wire pixel_write=(state==BLEND || opaque_texture || fast_pixel) && (texture==0 || !sampled_skip);
    wire [8:0] line_write_index=pixel_write ? x[9:1]:row_word;
    wire [15:0] clear_pixel=packed_desk ? desk_color:clear_color;
    wire [15:0] line_write_lo=background_write ? rdata[15:0]:clearing ? clear_pixel:(fast_pixel || opaque_texture) ? foreground:composed;
    wire [15:0] line_write_hi=background_write ? rdata[31:16]:clearing ? clear_pixel:(fast_pixel || opaque_texture) ? foreground:composed;
    always @(posedge clk) begin
        if(background_write || clearing || (pixel_write && !x[0]))line_lo[line_write_index]<=line_write_lo;
        if(background_write || clearing || (pixel_write && x[0]))line_hi[line_write_index]<=line_write_hi;
    end
    wire [8:0] command_read_index=state==NEXT_CMD ? command_index[8:0]+1'b1:command_index[8:0];
    always @(posedge clk) begin
        cm0_q<=cm0[command_read_index];c1<=cm1[command_read_index];
        cm2_q<=cm2[command_read_index];cm3_q<=cm3[command_read_index];
        c4<={8'd0,cm4[command_read_index],4'd0};c5<={8'd0,cm5[command_read_index],4'd0};
        c6<=cm6[command_read_index];c7<=cm7[command_read_index];
        bg_lo<=line_lo[line_index];bg_hi<=line_hi[line_index];
        cache_q<=cache[cache_read_address[8:2]];
        if(rvalid && rready) begin
            if(read_kind==0) case(loaded_words[2:0])
                0:cm0[loaded_words[11:3]]<=rdata==0 ? 20'hfffff:rdata-ASSET_BASE;1:cm1[loaded_words[11:3]]<=rdata;
                2:cm2[loaded_words[11:3]]<={rdata[25:16],(rdata[9:0]+10'd256)};3:cm3[loaded_words[11:3]]<={rdata[25:16],rdata[9:0]};
                4:cm4[loaded_words[11:3]]<=rdata[23:4];5:cm5[loaded_words[11:3]]<=rdata[23:4];
                6:cm6[loaded_words[11:3]]<=rdata;7:cm7[loaded_words[11:3]]<=rdata;
            endcase
            else if(read_kind==1) begin
                if(packed_desk)packed_bg[row_word[4:0]*32+:32]<=rdata;
                
            end else cache[{cache_bank,read_beat}]<=rdata;
        end
        if(reset) begin
            state<=IDLE;done<=0;error<=0;cycles<=0;burst_reads<=0;burst_writes<=0;
            read_wait<=0;write_wait<=0;cache_valid<=0;command_index<=0;
            araddr<=0;arlen<=0;awaddr<=0;row_word<=0;x<=0;cache_index<=0;
            write_data<=0;read_bad<=0;read_kind<=0;read_return<=ROW;read_beat<=0;
            loaded_words<=0;total_words<=0;count<=0;y<=0;frame<=0;background_base<=0;
            mix_fr<=0;mix_fg<=0;mix_fb<=0;mix_br<=0;mix_bg<=0;mix_bb<=0;
            clear_color<=0;sampled_pixel<=0;sampled_skip<=0;write_beat<=0;texture<=0;ustep<=0;source_w<=0;source_h<=0;
            source_pitch<=0;key_color<=0;alpha<=0;shade<=0;flags<=0;last_x<=0;
            pixel_address<=0;pixel_subindex<=0;source_row<=0;u<=0;v_product<=0;left_edge<=0;right_edge<=0;
            cache_bank<=0;cache_tag<=0;
        end else begin
            done<=0;if(busy)cycles<=cycles+1'b1;
            if((state==R_ADDR && !arready)||(state==R_DATA && !rvalid))read_wait<=read_wait+1'b1;
            if((state==W_ADDR && !awready)||(state==W_DATA && !wready)||(state==W_RESP && !bvalid))write_wait<=write_wait+1'b1;
            case(state)
            IDLE:if(start) begin
                error<=0;cycles<=0;cache_valid<=0;loaded_words<=0;
                if(!memory_ready || command_count[15:10]!=6'b101000 || command_count[9:0]==0 ||
                    command_count[9:0]>512 || src[5:0]!=0 || src<ASSET_BASE ||
                    {1'b0,src}+({23'd0,command_count[9:0]}<<5)>{1'b0,ASSET_BASE}+ASSET_BYTES ||
                    dst!=frame_base || width!=640 || height!=480 || stride!=1280 || !valid_background) begin
                    error<=1;done<=1;
                end else begin
                    count<=command_count[9:0];total_words<={command_count[9:0],3'd0};
                    frame<=frame_base;background_base<=background;clear_color<=background_color;
                    araddr<=src;arlen<=command_count[9:0]==1 ? 7:15;
                    read_beat<=0;read_bad<=0;read_kind<=0;state<=R_ADDR;y<=0;
                end
            end
            R_ADDR:if(arready)begin burst_reads<=burst_reads+1'b1;state<=R_DATA;end
            R_DATA:if(rvalid)begin
                if(rresp!=0 || rlast!=(read_beat==arlen))read_bad<=1;
                if(read_kind==0)loaded_words<=loaded_words+1'b1;
                if(read_kind==1)row_word<=row_word+1'b1;
                if(read_beat==arlen)begin
                    read_beat<=0;
                    if(read_bad || rresp!=0 || !rlast)begin error<=1;done<=1;state<=IDLE;end
                    else if(read_kind==0 && loaded_words+1'b1<total_words)begin
                        araddr<=araddr+64;arlen<=total_words-loaded_words-1'b1>=16 ? 15:7;state<=R_ADDR;
                    end else if(read_kind==1 && row_word!=(packed_desk ? 31:319))begin
                        araddr<=araddr+64;state<=R_ADDR;
                    end else begin
                        if(read_kind==2)begin cache_tags[cache_bank*23+:23]<=cache_tag;cache_valid[cache_bank]<=1;end
                        if(read_kind==1 && packed_desk)row_word<=0;
                        state<=read_kind==0 ? ROW:read_return;
                    end
                end else read_beat<=read_beat+1'b1;
            end
            ROW:begin
                row_word<=0;command_index<=0;
                if(background_base==0)state<=CLEAR;
                else begin araddr<=packed_desk ? (background_base&32'hfffffffe)+{y[8:1],7'd0}:background_base+y*1280;arlen<=15;read_beat<=0;
                    read_kind<=1;read_return<=packed_desk ? CLEAR:CMD_PRIME;read_bad<=0;state<=R_ADDR;end
            end
            CLEAR:begin
                if(row_word==319)begin row_word<=0;state<=CMD_PRIME;end
                else row_word<=row_word+1'b1;
            end
            CMD_PRIME:state<=CMD_TEST;
            CMD_TEST:begin
                if($signed({1'b0,y})<$signed(c3[15:0]) ||
                   $signed({1'b0,y})>=$signed(c3[15:0])+$signed({1'b0,c3[31:16]}))state<=NEXT_CMD;
                else if(c3[31:16]==0 || c2[31:16]==0 ||
                    (c0!=0 && ((!c6[28] && !c6[29] && (c0[0] || c1[0])) || c7[17:8]==0 || c7[27:18]==0 ||
                     c1[15:0]<(c6[29] ? ({6'd0,c7[17:8]}>>2):c6[28] ? {6'd0,c7[17:8]}:({6'd0,c7[17:8]}<<1)) || c0<ASSET_BASE)))begin
                    error<=1;done<=1;state<=IDLE;
                end else begin
                    texture<=c0;source_pitch<=c1[15:0];source_w<=c7[17:8];source_h<=c7[27:18];
                    key_color<=c6[15:0];alpha<=c6[23:16];flags<=c6[31:24];shade<=c7[7:0];ustep<=c4;
                    v_product<=dy*c5+(c5>>1);
                    left_edge<=($signed({{16{c2[15]}},c2[15:0]})<<<16);
                    right_edge<=($signed(c2[15:0])+$signed({1'b0,c2[31:16]}))*(32'sd65536);
                    state<=V_ROW;
                end
            end
            V_ROW:begin
                source_row<=texture+(v_product[31:16]>=source_h ? source_h-1'b1:v_product[31:16])*source_pitch;
                x<=left_edge<0 ? 0:left_edge>>>16;
                last_x<=right_edge>640*65536 ? 640:right_edge>>>16;
                u<=left_edge<0 ? (ustep>>1)+((-left_edge>>>16)*ustep):(ustep>>1);
                if(right_edge<=0 || left_edge>=640*65536 || right_edge<=left_edge)state<=NEXT_CMD;
                else state<=PIXEL_ADDR;
            end
            PIXEL_ADDR:begin
                pixel_address<=sample_address;pixel_subindex<=sample_u[1:0];
                state<=SAMPLE;
            end
            SAMPLE:begin
                if(texture!=0 && (pixel_address<ASSET_BASE || pixel_address>=ASSET_BASE+ASSET_BYTES))begin
                    error<=1;done<=1;state<=IDLE;
                end else if(texture!=0 && (!cache_valid[pixel_address[8:6]] || cache_tags[pixel_address[8:6]*23+:23]!=pixel_address[31:9]))begin
                    cache_bank<=pixel_address[8:6];cache_tag<=pixel_address[31:9];
                    araddr<={pixel_address[31:6],6'd0};arlen<=15;read_beat<=0;read_bad<=0;
                    read_kind<=2;read_return<=PIXEL_ADDR;state<=R_ADDR;
                end else begin
                    if(texture!=0)begin
                        sampled_pixel<=cached_pixel;
                        sampled_skip<=(flags[0] && cached_pixel==key_color) ||
                            (flags[3] && (cached_pixel==4260 || cached_pixel==8455 || cached_pixel==15150));
                        state<=LOOK;
                    end else if(alpha==255)begin
                        if(x+1'b1>=last_x)state<=NEXT_CMD;
                        else begin x<=x+1'b1;u<=next_u;pixel_address<=next_sample_address;pixel_subindex<=next_sample_u[1:0];state<=SAMPLE;end
                    end else begin lit_pixel<=key_color;state<=SHADE;end
                end
            end
            LOOK:begin
                if(alpha==255)begin
                    if(x+1'b1>=last_x)state<=NEXT_CMD;
                    else begin x<=x+1'b1;u<=next_u;pixel_address<=next_sample_address;pixel_subindex<=next_sample_u[1:0];state<=SAMPLE;end
                end else begin lit_pixel<=foreground;state<=SHADE;end
            end
            SHADE:begin
                mix_fr<=lit_pixel[15:11]*alpha;mix_fg<=lit_pixel[10:5]*alpha;mix_fb<=lit_pixel[4:0]*alpha;
                mix_br<=background_pixel[15:11]*(8'd255-alpha);
                mix_bg<=background_pixel[10:5]*(8'd255-alpha);mix_bb<=background_pixel[4:0]*(8'd255-alpha);
                state<=BLEND;
            end
            BLEND:begin
                    if(x+1'b1>=last_x)state<=NEXT_CMD;
                    else begin x<=x+1'b1;u<=next_u;pixel_address<=next_sample_address;pixel_subindex<=next_sample_u[1:0];state<=SAMPLE;end
            end
            NEXT_CMD:if(command_index+1'b1>=count)begin row_word<=0;state<=W_PREP;end
                else begin command_index<=command_index+1'b1;state<=CMD_TEST;end
            W_PREP:begin awaddr<=frame+y*1280+{21'd0,row_word,2'd0};write_beat<=0;state<=W_ADDR;end
            W_ADDR:if(awready)begin burst_writes<=burst_writes+1'b1;state<=W_PRIME;end
            W_PRIME:state<=W_LOAD;
            W_LOAD:begin write_data<={bg_hi,bg_lo};state<=W_DATA;end
            W_DATA:if(wready)begin
                if(write_beat==15)state<=W_RESP;
                else begin write_beat<=write_beat+1'b1;row_word<=row_word+1'b1;state<=W_LOAD;end
            end
            W_RESP:if(bvalid)begin
                if(bresp!=0)begin error<=1;done<=1;state<=IDLE;end
                else if(row_word==319)begin
                    if(y==479)begin done<=1;state<=IDLE;end
                    else begin y<=y+1'b1;state<=ROW;end
                end else begin row_word<=row_word+1'b1;state<=W_PREP;end
            end
            default:state<=IDLE;
            endcase
        end
    end
endmodule
`default_nettype wire
