#ifndef BOOK_MENU_H
#define BOOK_MENU_H
#include "reference_ui_assets.h"
/* Static art and projection commands reuse the original DDR pool. The FPGA ROM
 * holds the compressed assets, leaving the 128 KiB RISC-V RAM for game logic. */
static uint32_t book_assets_ready,book_closed=1u,book_cache_valid,book_cache_key;
static uint32_t book_hero_loaded=0xffffffffu;
static uint32_t book_transient=0xffffffffu,book_anim_frames,book_anim_ms;
static uint32_t book_menu_key(void) {
    return menu_level | (menu_group<<2) | (menu_item[0]<<4) | (menu_item[1]<<6);
}
static uint32_t book_stream_word=0xffffffffu,book_stream_value;
static uint8_t book_stream_byte(uint32_t at) {
#ifdef UI_NATIVE_REFERENCE
    extern uint8_t book_native_rom[];
    return book_native_rom[at];
#else
    if(book_stream_word!=at/4u) {
        book_stream_word=at/4u;mmio_write(GFX_BASE+0x80u,book_stream_word);
        book_stream_value=mmio_read(GFX_BASE+0x84u);
    }
    return (uint8_t)(book_stream_value>>((at&3u)*8u));
#endif
}
/* Expand an LZ4 stream into the temporary DDR menu cache. */
static inline __attribute__((always_inline)) void book_unpack(uint32_t at,uint32_t bytes,uint32_t expected) {
    volatile uint8_t *dst=(volatile uint8_t *)(uintptr_t)BOOK_SCRATCH_BASE;
    uint32_t end=at+bytes,out=0;
    while(at<end) {
        uint32_t token=book_stream_byte(at++),length=token>>4;
        if(length==15u){uint32_t n;do{n=book_stream_byte(at++);length+=n;}while(n==255u);}
        if(at+length>end || out+length>expected)fail("FAIL UI literal");
        while(length--)dst[out++]=book_stream_byte(at++);
        if(at==end)break;
        uint32_t offset=book_stream_byte(at++);offset|=(uint32_t)book_stream_byte(at++)<<8;
        length=(token&15u)+4u;
        if((token&15u)==15u){uint32_t n;do{n=book_stream_byte(at++);length+=n;}while(n==255u);}
        if(!offset || offset>out || out+length>expected)fail("FAIL UI match");
        while(length--){dst[out]=dst[out-offset];++out;}
    }
    if(out!=expected)fail("FAIL UI size");
}
static void book_load(uint32_t id) {
    const BookResource *r=&book_resources[id];
    book_unpack(r->offset,r->compressed,r->rle);
    const volatile uint16_t *tokens=(const volatile uint16_t *)(uintptr_t)BOOK_SCRATCH_BASE;
    volatile uint16_t *pixels=(volatile uint16_t *)(uintptr_t)(ASSET_BASE+r->base);
    uint32_t out=0;
    uint32_t mask=(1u<<r->bits)-1u;
    for(uint32_t n=0;n<r->rle/2u;++n) {
        uint32_t token=tokens[n],count=token>>r->bits;
        if(!count || out+count>r->bytes/2u)fail("FAIL UI RLE");
        uint16_t color=book_resource_palette[r->palette+(token&mask)];
        while(count--)pixels[out++]=color;
    }
    if(out!=r->bytes/2u)fail("FAIL UI pixels");
    publish_pixels();book_cache_valid=0;
}
static void book_init_assets(void) {
    if(book_assets_ready)return;
    for(uint32_t id=0;id<BOOK_RESOURCE_COUNT;++id)
        if(id!=BOOK_GAME_ORNAMENT && id!=BOOK_HERO_HOME && id!=BOOK_HERO_CHAPTER && id!=BOOK_HERO_GAME)book_load(id);
    book_assets_ready=1;book_transient=BOOK_BLANK;book_hero_loaded=0xffffffffu;
}
static const volatile uint16_t *book_pixels(uint32_t id) {
    return (const volatile uint16_t *)(uintptr_t)(ASSET_BASE+book_resources[id].base);
}
static void book_stamp(uint32_t id,uint32_t x,uint32_t y,uint32_t scale,uint16_t skip) {
    const BookResource *r=&book_resources[id];const volatile uint16_t *src=book_pixels(id);
    for(uint32_t row=0;row<r->h;++row)for(uint32_t col=0;col<r->w;++col) {
        uint16_t color=(id==BOOK_FRONT || id==BOOK_BLANK || id==BOOK_LEAF || id==BOOK_COVER) ? book_front_palette[((const volatile uint8_t *)src)[row*r->w+col]]:src[row*r->w+col];
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
                if(cp=='+')bits=col==2u ? 62u:8u;
                if(cp=='/')bits=32u>>col;
                if(cp=='_')bits=64u;
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
    const volatile uint8_t *desk=(const volatile uint8_t *)(uintptr_t)(ASSET_BASE+book_resources[BOOK_DESK].base);
    paint(0,0,640,480,book_desk_palette[0],1);
    for(uint32_t y=0;y<240u;++y)for(uint32_t x=0;x<320u;) {
        uint32_t first=x,index=(desk[y*128u+x/4u]>>((x%4u)*2u))&3u;++x;
        while(x<320u && ((desk[y*128u+x/4u]>>((x%4u)*2u))&3u)==index)++x;
        if(index)cpu_fill(first*2u,y*2u,(x-first)*2u,2,book_desk_palette[index]);
    }
}
static void book_cover(void) {
    book_init_assets();book_load(BOOK_COVER);book_load(BOOK_COVER_CLASP);book_transient=BOOK_COVER;
    book_desk();book_stamp(BOOK_COVER,170,32,2,0);book_stamp(BOOK_FRONT,174,32,1,0);book_stamp(BOOK_COVER_CLASP,418,222,1,0);
    book_center(320,446,"ENTER 打开",book_color(228,201,139),1);
}
static void book_hero(uint32_t x,uint32_t y,uint32_t scale) {
    if(scale==1u){draw_player(0,x,y,1);return;}
    uint32_t id=scale==2u ? BOOK_HERO_CHAPTER:book_transient==BOOK_GAME_ORNAMENT ? BOOK_HERO_GAME:BOOK_HERO_HOME;
    if(book_hero_loaded!=id){book_load(id);book_hero_loaded=id;}
    const BookResource *r=&book_resources[id];const volatile uint16_t *p=book_pixels(id);
    for(uint32_t row=0;row<r->h;++row)for(uint32_t col=0;col<r->w;++col)cpu_fill(x+col,y+row,1,1,p[row*r->w+col]);
}
static void book_hint(uint32_t x,uint32_t y,const char *key,const char *caption) {
    uint32_t w=book_text_width(key,0)+8u;if(w<18u)w=18u;
    book_line(x,y-2u,w,1,0xa44cu);book_line(x,y+15u,w,1,0xa44cu);
    book_line(x,y-2u,1,18,0xa44cu);book_line(x+w-1u,y-2u,1,18,0xa44cu);
    book_text(x+4u,y+3u,key,BOOK_BROWN,0);book_text(x+w+5u,y,caption,BOOK_BROWN,1);
}
static void book_menu_frame(void) {
    if(book_cache_valid && book_cache_key==book_menu_key()) {
        if(copy_image(BOOK_CACHE_BASE,FRAME_STRIDE,0,0,640,480))fail("FAIL book cache");
        return;
    }
    book_init_assets();if(book_transient!=BOOK_BLANK){book_load(BOOK_BLANK);book_transient=BOOK_BLANK;}
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
    book_desk();book_stamp(BOOK_BLANK,0,0,2,0);
    book_center(166,46,group==2u ? "高阶演示":group ? "基础演示":"二维实验室",BOOK_BROWN,2);
    book_center(474,46,group ? "选择功能":"选择演示",BOOK_BROWN,2);
    for(uint32_t n=0;n<3u;++n) {
        uint32_t y=112u+n*52u;char number[3]={'0',(char)('1'+n),0};
        for(uint32_t row=0;row<=36u;++row) {
            uint32_t inset=row<4u ? 4u-row:row>32u ? row-32u:0u;
            book_line(615,y+row,25u-inset,1,0x6a87u);
        }
        uint32_t active=n==(group==2u ? 1u:0u);
        book_line(617,y+2u,20,32,active ? 0x296au:BOOK_EDGE);
        book_line(618,y+3u,18,1,0xe651u);
        book_text(622,y+13u,number,active ? 0x9f1cu:BOOK_BROWN,0);
    }
    book_center(166,110,group==2u ? "ARCANA":group ? "BASIC":"INDEX",BOOK_MUTED,0);
    book_stamp(BOOK_ORNAMENT,72,158,2,0);
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
            for(uint32_t row=0;row<74u;++row) {
                uint32_t inset=row<8u ? 8u-row:row>65u ? row-65u:0u;
                book_line(x+inset,y+row,254u-inset*2u,1,BOOK_EDGE);
            }
            book_line(x+4u,y+4u,246,66,BOOK_SELECT);
            for(uint32_t corner=0;corner<4u;++corner) {
                uint32_t xx=x+((corner&1u) ? 234u:5u),yy=y+((corner&2u) ? 55u:5u);
                for(uint32_t row=0;row<15u;++row)for(uint32_t col=0;col<15u;++col)
                    if(book_corner_masks[corner*15u+row]&(1u<<col))book_line(xx+col,yy+row,1,1,0x6a87u);
            }
            book_line(x+20u,y+2u,214,1,BOOK_GOLD);
            book_stamp(BOOK_CURSOR,x-16u,y+26u,1,0);
        } else {
            book_line(x+12u,y+74u,230,1,BOOK_EDGE);
            for(int32_t dy=-2;dy<=2;++dy) {
                uint32_t r=(uint32_t)(2-(dy<0 ? -dy:dy));book_line(x+127u-r,y+74u+dy,r*2u+1u,1,BOOK_GOLD);
            }
        }
        book_stamp(icons[group][n],x+12u,y+20u,1,0);
        uint32_t mode=book_text_width(labels[group][n],2)<=192u ? 2u:1u;
        book_text(x+56u,y+11u,labels[group][n],n==choice ? 0x18e6u:BOOK_BROWN,mode);
        book_text(x+56u,y+49u,details[group][n],n==choice ? BOOK_BROWN:BOOK_MUTED,
            book_text_width(details[group][n],1)>192u ? 0u:1u);
    }
    book_hint(46,423,"W","选择");book_hint(107,423,"S","");
    book_hint(346,423,"ENTER","打开");book_hint(427,423,"A","返回");
    char left[2]={(char)('1'+group*2u),0},right[2]={(char)('2'+group*2u),0};
    book_text(280,448,left,BOOK_MUTED,0);book_text(580,448,right,BOOK_MUTED,0);
}


#include "reference_book_animation.h"
#endif
