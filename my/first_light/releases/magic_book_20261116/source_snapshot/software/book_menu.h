#ifndef BOOK_MENU_H
#define BOOK_MENU_H
#include "book_menu_assets.h"

/* Menu-only DDR layers reuse the former scenery gap. No demo image, game
 * texture, framebuffer, measurement interval or production RTL is changed. */
typedef char BookDDRBounds[(ASSET_BASE+0x4000u+73728u<=BOOK_ASSET_BASE &&
    BOOK_SNAPSHOT_BASE+BOOK_SNAPSHOT_BYTES<=ASSET_BASE+0xB0000u)?1:-1];
static uint32_t book_assets_ready,book_closed=1u;

/* Two-stage lossless upload: LZ4 -> compact RLE in DDR, then expand backwards
 * in that same range. It needs no large CPU RAM work buffer. */
static void book_init_assets(void) {
    if(book_assets_ready)return;
    volatile uint8_t *dst=(volatile uint8_t *)(uintptr_t)BOOK_ASSET_BASE;
    uint32_t at=0,out=0;
    while(at<BOOK_COMPRESSED_BYTES) {
        uint32_t token=book_lz4[at++],length=token>>4;
        if(length==15u) {uint32_t n;do {n=book_lz4[at++];length+=n;}while(n==255u);}
        if(at+length>BOOK_COMPRESSED_BYTES || out+length>BOOK_RLE_BYTES)fail("FAIL book literals");
        while(length--)dst[out++]=book_lz4[at++];
        if(at==BOOK_COMPRESSED_BYTES)break;
        uint32_t offset=book_lz4[at]|((uint32_t)book_lz4[at+1u]<<8);at+=2u;
        length=(token&15u)+4u;
        if((token&15u)==15u) {uint32_t n;do {n=book_lz4[at++];length+=n;}while(n==255u);}
        if(!offset || offset>out || out+length>BOOK_RLE_BYTES)fail("FAIL book match");
        while(length--) {dst[out]=dst[out-offset];++out;}
    }
    if(out!=BOOK_RLE_BYTES)fail("FAIL book size");
    volatile uint16_t *pixels=(volatile uint16_t *)(uintptr_t)BOOK_ASSET_BASE;
    uint32_t end=BOOK_ASSET_BYTES/2u;
    for(uint32_t n=BOOK_RLE_BYTES/2u;n;) {
        uint32_t token=pixels[--n],count=token>>6;
        if(!count || count>end || (token&63u)>=sizeof(book_palette)/sizeof(book_palette[0]))fail("FAIL book RLE");
        uint16_t color=book_palette[token&63u];
        while(count--)pixels[--end]=color;
    }
    if(end)fail("FAIL book pixels");
    publish_pixels();book_assets_ready=1u;
}
static const volatile uint16_t *book_pixels(uint32_t id) {
    return (const volatile uint16_t *)(uintptr_t)(BOOK_ASSET_BASE+book_layers[id].offset);
}
/* Nearest-neighbour stamps preserve the original hard pixel edges. */
static void book_stamp(uint32_t id,uint32_t x,uint32_t y,uint32_t scale,uint16_t skip) {
    const BookLayer *r=&book_layers[id];
    const volatile uint16_t *source=book_pixels(id);
    for(uint32_t row=0;row<r->h;++row)for(uint32_t col=0;col<r->w;++col) {
        uint16_t color=source[row*r->w+col];
        if(color && color!=skip)cpu_fill(x+col*scale,y+row*scale,scale,scale,color);
    }
}
static uint16_t book_color(uint32_t r,uint32_t g,uint32_t b) {
    return (uint16_t)(((r>>3)<<11)|((g>>2)<<5)|(b>>3));
}
#define BOOK_BROWN 0x5207u
#define BOOK_MUTED 0x8b8au
#define BOOK_GOLD 0xac2au
#define BOOK_EDGE 0xc52fu
#define BOOK_LIGHT 0xe631u
#define BOOK_PAPER 0xef17u
#define BOOK_SELECT 0xf757u

static uint32_t book_text_width(const char *s,uint32_t mode) {
    uint32_t width=0;
    while(*s) {
        uint32_t cp=font_cn_utf8_next(&s);
        width+=font_cn_find(cp) ? (mode==2u ? 28u:14u):mode==2u ? 18u:mode ? 12u:6u;
    }
    return width;
}
static void book_text(uint32_t x,uint32_t y,const char *s,uint16_t color,uint32_t mode) {
    while(*s) {
        uint32_t cp=font_cn_utf8_next(&s);
        const uint16_t *cn=font_cn_find(cp);
        uint32_t k=mode==2u ? (cn ? 2u:3u):cn ? 1u:mode ? 2u:1u;
        uint32_t width=cn ? 14u*k:6u*k;
        if(x+width>640u || y+(cn ? 14u*k:7u*k+4u)>480u)break;
        if(cn) {
            for(uint32_t row=0;row<14u;++row)for(uint32_t col=0;col<14u;++col)
                if(cn[row]&(1u<<col))cpu_fill(x+col*k,y+row*k,k,k,color);
        } else {
            for(uint32_t col=0;col<5u;++col) {
                uint8_t bits=font_column(cp,col);
                if(cp==':')bits=col==1u ? 20u:0u;
                if(cp=='.')bits=col==1u ? 64u:0u;
                for(uint32_t row=0;row<7u;++row)if(bits&(1u<<row))
                    cpu_fill(x+col*k,y+row*k+(mode==2u ? 4u:0u),k,k,color);
            }
        }
        x+=width;
    }
}
static void book_center(uint32_t center,uint32_t y,const char *s,uint16_t color,uint32_t mode) {
    uint32_t width=book_text_width(s,mode);
    book_text(center>width/2u ? center-width/2u:0u,y,s,color,mode);
}
static void book_line(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t color) {
    cpu_fill(x,y,w,h,color);
}
static void book_desk(void) {
    uint16_t base=book_pixels(BOOK_DESK)[0];
    paint(0,0,640,480,base,1);
    book_stamp(BOOK_DESK,0,0,2,base);
}
static void book_cover(void) {
    book_desk();book_stamp(BOOK_COVER,170,32,2,0);
    book_center(320,446,"ENTER 打开",book_color(228,201,139),1);
}
static void book_hero(uint32_t x,uint32_t y,uint32_t scale) {
    if(scale==1u) {draw_player(0,x,y,1);return;}
    const volatile uint16_t *src=(const volatile uint16_t *)(uintptr_t)PLAYER_ASSET_BASE;
    for(uint32_t row=0;row<32u;++row)for(uint32_t col=0;col<32u;++col)
        if(src[row*32u+col])cpu_fill(x+col*scale,y+row*scale,scale,scale,src[row*32u+col]);
}
static void book_hint(uint32_t x,uint32_t y,const char *key,const char *caption) {
    uint32_t w=book_text_width(key,0)+8u;
    book_line(x,y-2u,w,1,0xa44cu);book_line(x,y+15u,w,1,0xa44cu);
    book_line(x,y-2u,1,18,0xa44cu);book_line(x+w-1u,y-2u,1,18,0xa44cu);
    book_text(x+4u,y+3u,key,BOOK_BROWN,0);book_text(x+w+5u,y,caption,BOOK_BROWN,1);
}
static void book_menu_frame(void) {
    static const char *const labels[3][3]={
        {"基础演示","高阶演示","冰霜幸存者"},
        {"矩形填充","图像复制","双缓冲"},
        {"颜色键","透明混合","SPRITE压力"}};
    static const char *const details[3][3]={
        {"绘制 / 复制 / 缓冲","颜色键 / 透明混合","生存360秒"},
        {"RGB565 硬件填充","256 X 192 图像","垂直消隐交换"},
        {"匹配色跳过写入","前景与背景混合","ALPHA + COLOR KEY"}};
    static const uint8_t icons[3][3]={{BOOK_ICON_BASIC,BOOK_ICON_ADVANCED,BOOK_ICON_GAME},
        {BOOK_ICON_FILL,BOOK_ICON_COPY,BOOK_ICON_BUFFER},{BOOK_ICON_KEY,BOOK_ICON_ALPHA,BOOK_ICON_PRESSURE}};
    static const char *const caption1[6]={"32 X 24 RGB565","256 X 192 RGB565","VBLANK / DOUBLE BUFFER",
        "COLOR KEY / RGB565","ALPHA / 0 - 255","SPRITE / 32 X 32"};
    static const char *const caption2[6]={"CPU / FPGA","DDR 图像复制","单缓冲与双缓冲",
        "黑色 / 品红色","透明度越大 越透明","FPGA 硬件绘制"};
    uint32_t group=menu_level ? menu_group+1u:0u;
    uint32_t choice=menu_level ? menu_item[menu_group]:menu_group;
    book_desk();book_stamp(BOOK_SPREAD,0,0,2,0);
    book_center(166,46,group==2u ? "高阶演示":group ? "基础演示":"二维实验室",BOOK_BROWN,2);
    book_center(474,46,group ? "选择功能":"选择演示",BOOK_BROWN,2);
    for(uint32_t n=0;n<3u;++n) {
        uint32_t y=112u+n*52u;char number[3]={'0',(char)('1'+n),0};
        book_line(615,y,24,36,0x6a87u);book_line(617,y+2u,20,32,
            n==menu_group ? 0x296au:BOOK_EDGE);
        book_text(622,y+13u,number,n==menu_group ? 0x9f1cu:BOOK_BROWN,0);
    }
    book_center(166,110,group==2u ? "ARCANA":group ? "BASIC":"INDEX",BOOK_MUTED,0);
    book_stamp(BOOK_ORNAMENT,BOOK_ORNAMENT_X,BOOK_ORNAMENT_Y,2,0);
    if(!group) {
        book_hero(118,192,3);
        book_center(166,336,labels[0][choice],BOOK_BROWN,1);
        book_center(166,365,"RISC-V + FPGA",BOOK_MUTED,0);
    } else {
        book_stamp(icons[group][choice],118,190,3,0);book_hero(214,280,2);
        uint32_t demo=(group-1u)*3u+choice;
        book_center(166,344,caption1[demo],BOOK_MUTED,0);
        book_center(166,370,caption2[demo],BOOK_BROWN,1);
    }
    for(uint32_t n=0;n<3u;++n) {
        uint32_t x=342u,y=126u+n*88u;
        if(n==choice) {
            book_line(x+8u,y,238,74,BOOK_EDGE);book_line(x,y+8u,254,58,BOOK_EDGE);
            book_line(x+4u,y+4u,246,66,BOOK_SELECT);
            for(uint32_t side=0;side<2u;++side) {
                uint32_t xx=side ? x+234u:x+6u;
                book_line(xx,y+6u,14,2,0x6a87u);book_line(side ? xx+12u:xx,y+6u,2,12,0x6a87u);
                book_line(xx,y+66u,14,2,0x6a87u);book_line(side ? xx+12u:xx,y+56u,2,12,0x6a87u);
            }
            book_stamp(BOOK_CURSOR,x-16u,y+26u,1,0);
        } else book_line(x+12u,y+74u,230,1,BOOK_EDGE);
        book_stamp(icons[group][n],x+12u,y+20u,1,0);
        uint32_t mode=book_text_width(labels[group][n],2)<=192u ? 2u:1u;
        book_text(x+56u,y+11u,labels[group][n],BOOK_BROWN,mode);
        book_text(x+56u,y+49u,details[group][n],n==choice ? BOOK_BROWN:BOOK_MUTED,
            book_text_width(details[group][n],1)>192u ? 0u:1u);
    }
    book_hint(46,423,"W","选择");book_hint(107,423,"S","");
    book_hint(346,423,"ENTER","打开");book_hint(427,423,"A","返回");
    char left[2]={(char)('1'+group*2u),0},right[2]={(char)('2'+group*2u),0};
    book_text(280,448,left,BOOK_MUTED,0);book_text(580,448,right,BOOK_MUTED,0);
}

/* 10-bit smoothstep and a small fixed-point sine table avoid soft-float code.
 * The cover and following leaf use separate delays and a curved strip mesh. */
static int32_t book_ease(int32_t t) {
    if(t<=0)return 0;
    if(t>=1024)return 1024;
    int32_t t2=t*t/1024,t3=t2*t/1024;
    return t3*(10240-15*t+6*t2)/1024;
}
static int32_t book_phase(int32_t t,int32_t start,int32_t duration) {
    return book_ease((t-start)*1024/duration);
}
static int32_t book_sin(int32_t angle) {
    while(angle<0)angle+=256;
    return book_sine[(uint32_t)angle&255u];
}
static void book_capture(void) {
    publish_pixels();
    const volatile uint16_t *src=(const volatile uint16_t *)(uintptr_t)draw_buffer;
    volatile uint16_t *dst=(volatile uint16_t *)(uintptr_t)BOOK_SNAPSHOT_BASE;
    for(uint32_t y=0;y<240u;++y)for(uint32_t x=0;x<320u;++x)dst[y*320u+x]=src[y*1280u+x*2u];
    publish_pixels();
}
static void book_capture_half(uint32_t base,uint32_t first,uint32_t last) {
    const volatile uint16_t *src=(const volatile uint16_t *)(uintptr_t)base;
    volatile uint16_t *dst=(volatile uint16_t *)(uintptr_t)BOOK_SNAPSHOT_BASE;
    for(uint32_t y=0;y<240u;++y)for(uint32_t x=first;x<last;++x)dst[y*320u+x]=src[y*1280u+x*2u];
    publish_pixels();
}
/* Draw a projected texture rectangle in half-resolution coordinates. Every
 * destination sample becomes one crisp 2x2 pixel; all edges clip to 640x480. */
static void book_texture(const volatile uint16_t *source,uint32_t stride,
                         int32_t sx,int32_t sy,int32_t sw,int32_t sh,
                         int32_t x,int32_t y,int32_t w,int32_t h,uint32_t flip) {
    if(w<=0 || h<=0)return;
    for(int32_t row=0;row<h;++row) {
        int32_t yy=y+row;if(yy<0 || yy>=240)continue;
        uint32_t iy=(uint32_t)(sy+row*sh/h)*stride;
        for(int32_t col=0;col<w;++col) {
            int32_t xx=x+col;if(xx<0 || xx>=320)continue;
            int32_t ix=col*sw/w;if(flip)ix=sw-1-ix;
            uint16_t color=source[iy+(uint32_t)(sx+ix)];if(!color)continue;
            volatile uint32_t *dst=(volatile uint32_t *)(uintptr_t)(draw_buffer+(uint32_t)yy*2560u+(uint32_t)xx*4u);
            uint32_t pair=(uint32_t)color|((uint32_t)color<<16);
            dst[0]=pair;dst[320]=pair;
        }
    }
}
static void book_sheet(uint32_t front,uint32_t back,int32_t hinge,int32_t top,
                       int32_t width,int32_t height,int32_t angle,int32_t bend) {
    int32_t x=0,z=0;
    for(int32_t strip=0;strip<32;++strip) {
        int32_t local=angle+bend*book_sin((strip*128+64)/32)/1024;
        int32_t nx=x+width*book_sin(local+64)/32,nz=z+width*book_sin(local)/32;
        int32_t x0=hinge+x*2600/(2662400-z),x1=hinge+nx*2600/(2662400-nz);
        int32_t middle=(z+nz)/2,hh=height*2662400/(2662400-middle);
        int32_t yy=top+height/2-middle/40960-hh/2;
        uint32_t facing=book_sin(local+64)<0;
        const volatile uint16_t *src=front ? book_pixels(BOOK_FRONT):
            (const volatile uint16_t *)(uintptr_t)BOOK_SNAPSHOT_BASE;
        uint32_t stride=front ? book_layers[BOOK_FRONT].w:320u;
        int32_t sw=front ? book_layers[BOOK_FRONT].w:153,sh=front ? book_layers[BOOK_FRONT].h:231;
        int32_t sx=front ? 0:160,sy=front ? 0:9;
        if(facing) {src=(const volatile uint16_t *)(uintptr_t)BOOK_SNAPSHOT_BASE;stride=320;sw=153;sh=231;sx=7;sy=9;}
        int32_t a=strip*sw/32,b=(strip+1)*sw/32;
        if(facing && back)sx+=sw-b;else sx+=a;
        book_texture(src,stride,sx,sy,b-a,sh,x0<x1 ? x0:x1,yy,x0<x1 ? x1-x0:x0-x1,hh,facing);
        x=nx;z=nz;
    }
}
static void book_opening_frame(uint32_t frame) {
    if(!frame) {book_cover();return;}
    if(frame>=120u) {book_menu_frame();return;}
    int32_t t=(int32_t)frame*1024/120,pose=book_phase(t,133,758);
    int32_t ca=book_phase(t,123,655)*128/1024,la=book_phase(t,287,635)*128/1024;
    int32_t hinge=87+73*book_phase(t,195,686)/1024,top=16-7*pose/1024;
    int32_t width=139+14*pose/1024,height=198+33*pose/1024;
    book_desk();
    const volatile uint16_t *snap=(const volatile uint16_t *)(uintptr_t)BOOK_SNAPSHOT_BASE;
    book_texture(snap,320,160,9,158,231,hinge,top,149+9*pose/1024,208+23*pose/1024,0);
    int32_t bend=15*book_sin(la)/1024;
    if(book_sin(ca)>book_sin(la)) {
        book_sheet(0,1,hinge,top,width,height,la,bend);book_sheet(1,1,hinge,top,width,height,ca,0);
    } else {
        book_sheet(1,1,hinge,top,width,height,ca,0);book_sheet(0,1,hinge,top,width,height,la,bend);
    }
    if(t<260) {
        int32_t unlock=book_phase(t,0,164),cw=27*book_sin(unlock*81/1024+64)/1024;
        if(cw<0)cw=-cw;
        book_texture(book_pixels(BOOK_CLASP),27,0,0,27,20,236-cw,111,cw,20,unlock>810);
    }
}
static void book_animate(uint32_t closing) {
    book_menu_frame();book_capture();
    uint32_t start=cycle_now(),frame=0;
    for(;;) {
        book_opening_frame(closing ? 120u-frame:frame);
        publish_pixels();if(present_frame())fail("FAIL book animation");
        mmio_write(GFX_BASE+GFX_DISPLAY,1);
        if(frame==120u)break;
        uint32_t elapsed=cycle_now()-start;
        uint32_t next=(elapsed/(SYSTEM_CLINT_HZ/1000u))*120u/2400u;
        frame=next>frame ? next:frame+1u;if(frame>120u)frame=120u;
        uint32_t deadline=frame*(SYSTEM_CLINT_HZ/50u);
        while((uint32_t)(cycle_now()-start)<deadline) {}
    }
    (void)button_event();
}
/* A chapter change turns one curved leaf over the already composed target.
 * Its front comes from the visible page; its back contains the new left leaf. */
static void book_turn(void) {
    book_capture_half(draw_buffer==FRAMEBUFFER ? FRAMEBUFFER_B:FRAMEBUFFER,160,320);
    book_menu_frame();publish_pixels();book_capture_half(draw_buffer,0,160);
    uint32_t start=cycle_now(),frame=0;
    for(;;) {
        book_menu_frame();
        if(frame<32u) {
            int32_t angle=book_ease((int32_t)frame*1024/32)*128/1024;
            book_sheet(0,1,160,18,146,205,angle,12*book_sin(angle)/1024);
        }
        publish_pixels();if(present_frame())fail("FAIL book turn");
        if(frame==32u)break;
        uint32_t elapsed=cycle_now()-start,next=(elapsed/(SYSTEM_CLINT_HZ/1000u))*32u/640u;
        frame=next>frame ? next:frame+1u;if(frame>32u)frame=32u;
        while((uint32_t)(cycle_now()-start)<frame*(SYSTEM_CLINT_HZ/50u)) {}
    }
}
#endif
