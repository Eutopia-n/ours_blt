#include "render.h"
#include "player_asset.h"
#include "demo_controls.h"
static void init_game_assets(void);

static uint32_t cycle_now(void) {
    // This Sapphire configuration traps on mcycle CSR reads. The vendor CLINT
    // exposes mtime at +0xBFF8 and ticks at SYSTEM_CLINT_HZ (100 MHz).
    // Unsigned subtraction remains valid across a low-word rollover.
    return mmio_read(SYSTEM_CLINT_CTRL + 0xbff8u);
}
static void uart_putc(char c) {
    while (((mmio_read(SYSTEM_UART_0_IO_CTRL + 4) >> 16) & 255u) == 0) {}
    mmio_write(SYSTEM_UART_0_IO_CTRL, (uint32_t)c);
}
static void puts_uart(const char *s) { while (*s) uart_putc(*s++); }
static void hex_uart(uint32_t value) {
    const char *digits = "0123456789ABCDEF";
    for (int n = 28; n >= 0; n -= 4) uart_putc(digits[(value >> n) & 15u]);
}
void fatal_trap(uint32_t cause, uint32_t pc) {
    puts_uart("TRAP cause=0x"); hex_uart(cause);
    puts_uart(" pc=0x"); hex_uart(pc); puts_uart("\r\n");
    for (;;) {}
}
static void fail(const char *message) {
    puts_uart(message); puts_uart("\r\n"); for (;;) {}
}
static uint32_t draw_buffer = FRAMEBUFFER;
static uint32_t sprite_count = 64;
static uint32_t collision_hits, collision_active;
enum { DEMO_FILL, DEMO_COPY, DEMO_BUFFER, DEMO_VIDEO,
       DEMO_KEY, DEMO_ALPHA, DEMO_COLLISION, DEMO_BENCH };
static const char *const demo_names[8]={
    "矩形填充","图像复制","双缓冲","视频模式",
    "颜色键","透明混合","碰撞检测","精灵压力"
};
static const char *const demo_details[8]={
    "RGB565 硬件填充","DDR 图像复制到显存",
    "垂直消隐交换页面","颜色条与实际尺寸",
    "黑色像素变为透明","按键1加一 按键3减一",
    "RISC-V 包围盒碰撞","64/128/256 精灵测试"
};
static const char *const action_labels[8]={
    "按键1改变颜色","按键1改变位置","按键1改变速度","按键1改变图案",
    "按键1开关颜色键","按键1加一 按键3减一","按键1重新开始","按键1改变数量"
};
static uint32_t menu_level, menu_group, menu_item[2];
static uint32_t fps[2], render_us[2], samples[2], burst_ar[2], burst_aw[2];
static uint32_t draw_page(void) { return draw_buffer == FRAMEBUFFER_B ? 1u : 0u; }
static int wait_display_page(uint32_t page) {
    uint32_t start = cycle_now();
    for (;;) {
        uint32_t status = mmio_read(GFX_BASE+GFX_STATUS);
        if (status & (GFX_ERROR|GFX_UNDERFLOW|GFX_READ_ERR)) return -3;
        if (!(status & GFX_SWAP_PENDING) && ((status >> 6) & 1u) == page) return 0;
        if ((uint32_t)(cycle_now()-start) > 200000000u) return -4;
    }
}
static void select_draw_page(void) {
    mmio_write(GFX_BASE+GFX_DRAW_PAGE, draw_page());
}
// All operations complete through the same status register and timeout.
static int wait_render(void) {
    uint32_t start = cycle_now();
    for (;;) {
        uint32_t status = mmio_read(GFX_BASE+GFX_STATUS);
        if (status & GFX_ERROR) return -3;
        if ((status & (GFX_BUSY|GFX_DONE)) == GFX_DONE) return 0;
        if ((uint32_t)(cycle_now()-start) > 100000000u) return -4;
    }
}
int fill_rect(uint32_t x, uint32_t y, uint32_t width, uint32_t height, uint16_t color) {
    if (!width || !height || x >= 640 || y >= 480 || width > 640-x || height > 480-y)
        return -1;
    if (mmio_read(GFX_BASE+GFX_STATUS) & (GFX_BUSY|GFX_SWAP_PENDING)) return -2;
    select_draw_page();
    mmio_write(GFX_BASE+GFX_OPERATION, 0);
    mmio_write(GFX_BASE+GFX_DST, draw_buffer+y*FRAME_STRIDE+x*2);
    mmio_write(GFX_BASE+GFX_WIDTH, width);
    mmio_write(GFX_BASE+GFX_HEIGHT, height);
    mmio_write(GFX_BASE+GFX_STRIDE, FRAME_STRIDE);
    mmio_write(GFX_BASE+GFX_COLOR, color);
    mmio_write(GFX_BASE+GFX_COMMAND, 1);
    return wait_render();
}
int copy_rect(uint32_t src_x, uint32_t src_y, uint32_t dst_x, uint32_t dst_y,
              uint32_t width, uint32_t height) {
    if (!width || !height || src_x >= 640 || src_y >= 480 || dst_x >= 640 || dst_y >= 480 ||
        width > 640-src_x || width > 640-dst_x || height > 480-src_y || height > 480-dst_y)
        return -1;
    return copy_image(draw_buffer+src_y*FRAME_STRIDE+src_x*2, FRAME_STRIDE,
                      dst_x,dst_y,width,height);
}
int copy_image(uint32_t source, uint32_t source_stride, uint32_t dst_x,
               uint32_t dst_y, uint32_t width, uint32_t height) {
    if (!width || !height || dst_x >= 640 || dst_y >= 480 ||
        width > 640-dst_x || height > 480-dst_y || (source&1u) ||
        (source_stride&1u) || source_stride > 65534 || source_stride < width*2)
        return -1;
    uint32_t bytes=(height-1)*source_stride+width*2;
    uint32_t base=ASSET_BASE, size=ASSET_BYTES;
    if (source>=draw_buffer && source<draw_buffer+FRAMEBUFFER_BYTES &&
        source_stride==FRAME_STRIDE) { base=draw_buffer; size=FRAMEBUFFER_BYTES; }
    // Subtraction after the range check avoids wrapping a 32-bit end address.
    if (source<base || source>=base+size || bytes>base+size-source) return -1;
    if (mmio_read(GFX_BASE+GFX_STATUS) & (GFX_BUSY|GFX_SWAP_PENDING)) return -2;
    select_draw_page();
    mmio_write(GFX_BASE+GFX_OPERATION, 1);
    mmio_write(GFX_BASE+GFX_SRC, source);
    mmio_write(GFX_BASE+GFX_SRC_STRIDE, source_stride);
    mmio_write(GFX_BASE+GFX_DST, draw_buffer+dst_y*FRAME_STRIDE+dst_x*2);
    mmio_write(GFX_BASE+GFX_WIDTH, width);
    mmio_write(GFX_BASE+GFX_HEIGHT, height);
    mmio_write(GFX_BASE+GFX_STRIDE, FRAME_STRIDE);
    mmio_write(GFX_BASE+GFX_COMMAND, 1);
    return wait_render();
}
// Submit an asset Sprite: hardware reads foreground and background, computes
// RGB565 components, and suppresses writes for Color Key pixels.
int blend_image(uint32_t source, uint32_t source_stride, uint32_t dst_x,
                uint32_t dst_y, uint32_t width, uint32_t height,
                uint8_t alpha, uint16_t key, uint32_t flags) {
    if (!width || !height || dst_x >= 640 || dst_y >= 480 ||
        width > 640-dst_x || height > 480-dst_y || (source&1u) ||
        (source_stride&1u) || source_stride > 65534 || source_stride < width*2 ||
        (flags & ~(GFX_BLEND_ALPHA|GFX_BLEND_KEY))) return -1;
    uint32_t bytes=(height-1)*source_stride+width*2;
    if (source<ASSET_BASE || source>=ASSET_BASE+ASSET_BYTES ||
        bytes>ASSET_BASE+ASSET_BYTES-source) return -1;
    if (mmio_read(GFX_BASE+GFX_STATUS) & (GFX_BUSY|GFX_SWAP_PENDING)) return -2;
    select_draw_page();
    mmio_write(GFX_BASE+GFX_OPERATION, 2);
    mmio_write(GFX_BASE+GFX_SRC, source);
    mmio_write(GFX_BASE+GFX_SRC_STRIDE, source_stride);
    mmio_write(GFX_BASE+GFX_DST, draw_buffer+dst_y*FRAME_STRIDE+dst_x*2);
    mmio_write(GFX_BASE+GFX_WIDTH, width);
    mmio_write(GFX_BASE+GFX_HEIGHT, height);
    mmio_write(GFX_BASE+GFX_STRIDE, FRAME_STRIDE);
    mmio_write(GFX_BASE+GFX_BLEND_CTRL, flags);
    mmio_write(GFX_BASE+GFX_ALPHA, alpha);
    mmio_write(GFX_BASE+GFX_COLOR_KEY, key);
    mmio_write(GFX_BASE+GFX_COMMAND, 1);
    return wait_render();
}
int present_frame(void) {
    uint32_t page = draw_page();
    if (mmio_read(GFX_BASE+GFX_STATUS) & (GFX_BUSY|GFX_SWAP_PENDING)) return -2;
    mmio_write(GFX_BASE+GFX_SWAP_PAGE, page);
    mmio_write(GFX_BASE+GFX_SWAP, 1);
    int result = wait_display_page(page);
    if (result) return result;
    draw_buffer = page ? FRAMEBUFFER : FRAMEBUFFER_B;
    select_draw_page();
    return 0;
}
static void publish_pixels(void) {
    // This generated core has a write-through cache, but no CSR 0x810.
    // Invalidate then force a DDR read. Its BmbToAxi4SharedBridge stalls
    // read-after-write until all writes from the same master have responded.
    __asm__ volatile ("fence iorw, iorw\n.word 0x500f" ::: "memory");
    (void)*(volatile uint32_t *)(uintptr_t)draw_buffer;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}
static void cpu_fill(uint32_t x, uint32_t y, uint32_t w, uint32_t h, uint16_t c) {
    for (uint32_t row=0; row<h; ++row) {
        volatile uint16_t *p=(volatile uint16_t *)(uintptr_t)(draw_buffer+(y+row)*1280+x*2);
        uint32_t col=0;
        if(x&1u) { p[col++]=c; }
        for (;col+1<w;col+=2)
            *(volatile uint32_t *)(p+col)=(uint32_t)c|((uint32_t)c<<16);
        if(col<w) p[col]=c;
    }
}
static uint16_t sprite_pixel(uint32_t row, uint32_t col) {
    uint32_t dx=col>15 ? col-15 : 15-col;
    uint32_t dy=row>15 ? row-15 : 15-row;
    if (dx+dy>13) return 0x0000;
    return row<10 ? 0x07ff : row<20 ? 0xf800 : 0xffe0;
}
static uint16_t blend_rgb565(uint16_t foreground, uint16_t background,
                             uint32_t alpha, uint16_t key, uint32_t flags) {
    if ((flags&GFX_BLEND_KEY) && foreground==key) return background;
    if (!(flags&GFX_BLEND_ALPHA)) return foreground;
    uint32_t r=(((foreground>>11)&31u)*alpha+((background>>11)&31u)*(255u-alpha)+127u)/255u;
    uint32_t g=(((foreground>>5)&63u)*alpha+((background>>5)&63u)*(255u-alpha)+127u)/255u;
    uint32_t b=((foreground&31u)*alpha+(background&31u)*(255u-alpha)+127u)/255u;
    return (uint16_t)((r<<11)|(g<<5)|b);
}
static void cpu_blend_copy_source(uint32_t source, uint32_t x, uint32_t y,
                                  uint32_t alpha, uint32_t flags) {
    for (uint32_t row=0; row<32; ++row) {
        const volatile uint16_t *s=(const volatile uint16_t *)(uintptr_t)(source+row*SPRITE_STRIDE);
        volatile uint16_t *d=(volatile uint16_t *)(uintptr_t)(draw_buffer+(y+row)*1280+x*2);
        for (uint32_t col=0; col<32; ++col)
            d[col]=blend_rgb565(s[col],d[col],alpha,0,flags);
    }
}
static void cpu_blend_copy(uint32_t x, uint32_t y, uint32_t alpha, uint32_t flags) {
    cpu_blend_copy_source(ASSET_BASE,x,y,alpha,flags);
}
#include "font5x7.h"
#include "font_cn.h"
static void text_at(uint32_t x,uint32_t y,const char *s,uint16_t color) {
    while (*s) {
        uint32_t codepoint=font_cn_utf8_next(&s);
        const uint16_t *cn=font_cn_find(codepoint);
        if(cn) {
            for(uint32_t row=0;row<14;++row)
                for(uint32_t col=0;col<12;++col)
                    if(cn[row]&(1u<<col)) cpu_fill(x+col,y+row,1,1,color);
            x+=14;
            continue;
        }
        char c=(char)codepoint;
        int glyph=c>='0'&&c<='9' ? c-'0' : c>='A'&&c<='Z' ? c-'A'+10 : -1;
        for (uint32_t col=0;col<5;++col) {
            uint8_t bits=glyph>=0 ? font5x7[glyph][col] : c=='-' ? 8 :
                         c=='/' ? (1u<<(5-col)) : c=='+' ? (col==2 ? 0x3e : 8) : 0;
            for (uint32_t row=0;row<7;++row)
                if (bits&(1u<<row)) cpu_fill(x+col*2,y+row*2,2,2,color);
        }
        x+=12;
    }
}
static char *decimal(char *out,uint32_t value) {
    char digits[10]; uint32_t n=0;
    do { digits[n++]=(char)('0'+value%10); value/=10; } while (value);
    while(n) *out++=digits[--n];
    *out=0; return out;
}
static void number_at(uint32_t x,uint32_t y,uint32_t value,uint16_t color) {
    char number[11]; decimal(number,value); text_at(x,y,number,color);
}
static void uart_number(const char *label,uint32_t value) {
    char number[11]; decimal(number,value); puts_uart(label); puts_uart(number);
}
static uint32_t button_event(void) {
    static uint32_t action_held;
    uint32_t held=mmio_read(GFX_BASE+GFX_BUTTON_HELD)&31u;
    uint32_t keys=mmio_read(SYSTEM_GPIO_0_IO_CTRL)&15u;
    // The Sapphire GPIO peripheral is four bits wide in the generated SoC.
    // The fifth J28 key is therefore edge-detected from the renderer's live
    // debounced register; it still shares the normal GPIO acknowledgement.
    if((held&16u) && !(action_held&16u)) keys|=16u;
    action_held=held&16u;
    // The FPGA retains one debounced event until this GPIO toggle acknowledges it.
    if (keys) mmio_write(SYSTEM_GPIO_0_IO_CTRL+4,mmio_read(SYSTEM_GPIO_0_IO_CTRL+4)^1u);
    return keys;
}
// Upload the RGB565 image once. Both CPU and hardware subsequently read
// this same immutable DDR resource; clearing either framebuffer cannot erase it.
static void init_assets(void) {
    volatile uint16_t *p=(volatile uint16_t *)(uintptr_t)ASSET_BASE;
    for (uint32_t row=0;row<32;++row)
        for (uint32_t col=0;col<32;++col)
            p[row*32+col]=sprite_pixel(row,col);
    for (uint32_t frame=0;frame<PLAYER_FRAME_COUNT;++frame) {
        volatile uint16_t *player=(volatile uint16_t *)(uintptr_t)
            (PLAYER_ASSET_BASE+frame*PLAYER_FRAME_BYTES);
        uint32_t out=0;
        for (uint32_t at=player_rle_offsets[frame];at<player_rle_offsets[frame+1];++at) {
            uint32_t count=player_rle[at]>>9;
            uint16_t color=player_palette[player_rle[at]&511u];
            while (count--) player[out++]=color;
        }
    }
    publish_pixels(); // Drain CPU stores before any hardware source reads.
    init_game_assets();
}
static uint32_t bounce(uint32_t phase, uint32_t limit) {
    phase %= limit*2;
    return phase>limit ? limit*2-phase : phase;
}
// Reproducible pseudo-random phase, speed and initial direction per Sprite.
// Bouncing preserves continuous motion; CPU and FPGA get identical positions.
static uint32_t sprite_seed(uint32_t n) {
    uint32_t v=(n+1)*0x9e3779b9u;
    v^=v<<13; v^=v>>17; v^=v<<5;
    return v;
}
static void draw_image(uint32_t x,uint32_t y,uint32_t flags,uint32_t alpha,uint32_t hw) {
    if (hw) {
        int result=flags ? blend_image(ASSET_BASE,SPRITE_STRIDE,x,y,32,32,alpha,0,flags) :
                           copy_image(ASSET_BASE,SPRITE_STRIDE,x,y,32,32);
        if (result) fail("FAIL image");
    } else cpu_blend_copy(x,y,alpha,flags);
}
static void draw_player(uint32_t frame,uint32_t x,uint32_t y,uint32_t hw) {
    uint32_t source=PLAYER_ASSET_BASE+(frame%PLAYER_FRAME_COUNT)*PLAYER_FRAME_BYTES;
    if (hw) {
        if (blend_image(source,SPRITE_STRIDE,x,y,32,32,255,0,GFX_BLEND_KEY))
            fail("FAIL player");
    } else cpu_blend_copy_source(source,x,y,255,GFX_BLEND_KEY);
}
static void paint(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t c,uint32_t hw) {
    if (hw) { if (fill_rect(x,y,w,h,c)) fail("FAIL fill"); }
    else cpu_fill(x,y,w,h,c);
}
// Same-page, non-overlapping reference copy used by the dedicated Copy page.
static void cpu_copy_sample(uint32_t dst_y) {
    for(uint32_t row=0;row<96;++row) {
        const volatile uint16_t *src=(const volatile uint16_t *)(uintptr_t)(draw_buffer+(192+row)*1280+64*2);
        volatile uint16_t *dst=(volatile uint16_t *)(uintptr_t)(draw_buffer+(dst_y+row)*1280+384*2);
        for(uint32_t col=0;col<128;++col) dst[col]=src[col];
    }
}
static uint32_t alpha_value(uint32_t variant) { return variant; }
static uint32_t scene_sprites(uint32_t demo) {
    return demo==DEMO_BENCH ? sprite_count : (demo==DEMO_KEY || demo==DEMO_ALPHA) ? 8 : 0;
}
static void scene(uint32_t frame,uint32_t hw,uint32_t demo,uint32_t variant) {
    static const uint16_t colors[8]={0xffff,0xffe0,0x07ff,0x07e0,0xf81f,0xf800,0x001f,0};
    // Sapphire BSP 0x500F invalidates stale reads left by hardware writes.
    __asm__ volatile (".word 0x500f" ::: "memory");
    paint(0,0,640,480,0x0862,hw);
    switch(demo) {
    case DEMO_FILL:
        for(uint32_t n=0;n<3;++n)
            paint(48+n*184,176+bounce(frame*(variant+1),80),128+n*16,72+n*16,
                  colors[1+(n+variant)%3],hw);
        break;
    case DEMO_COPY:
        for(uint32_t n=0;n<4;++n)
            paint(64+(n&1u)*64,192+(n>>1)*48,64,48,colors[1+n],hw);
        if(hw) {
            if(copy_rect(64,192,384,192+variant*80,128,96)) fail("FAIL copy");
        } else cpu_copy_sample(192+variant*80);
        break;
    case DEMO_BUFFER:
        paint(32,160,576,240,draw_page() ? 0x2104 : 0x084b,hw);
        paint(40+bounce(frame*(variant ? 24 : 8),520),184,24,160,0xffff,hw);
        paint(48,272,544,4,0x07ff,hw);
        break;
    case DEMO_VIDEO:
        for(uint32_t n=0;n<8;++n)
            paint(32+n*72,160,72,240,colors[n],hw);
        if(variant) {
            for(uint32_t n=0;n<9;++n) paint(32+n*71,160,2,240,0xffff,hw);
            for(uint32_t n=0;n<5;++n) paint(32,160+n*59,576,2,0xffff,hw);
        }
        break;
    case DEMO_KEY:
    case DEMO_ALPHA:
        // Isolate Key and Alpha. Alpha uses flags=1: Color Key stays disabled.
        for(uint32_t panel=0;panel<2;++panel) {
            uint32_t x=40+panel*304;
            paint(x,176,128,216,0x0514,hw); paint(x+128,176,128,216,0xfca0,hw);
            uint32_t flags=panel ? (demo==DEMO_KEY ? (variant ? 2 : 0) : 1) : 0;
            for(uint32_t n=0;n<4;++n)
                draw_image(x+112+(n&1u)*16,208+(n>>1)*96,flags,alpha_value(variant),hw);
        }
        break;
    case DEMO_COLLISION: {
        uint32_t x=200+bounce(frame*16,200);
        collision_active=x<360 && x+80>280; // Two 80x80 AABBs, edge contact excluded.
        if(collision_active) collision_hits++;
        paint(280,224,80,80,0x07ff,hw);
        paint(x,240,80,80,collision_active ? 0xf800 : 0x07e0,hw);
        break;
    }
    default: // Performance scene contains only the selected moving Sprite load.
        paint(0,152,640,256,0x2945,hw);
        for(uint32_t n=0;n<sprite_count;++n) {
            uint32_t seed=sprite_seed(n);
            uint32_t x=8+bounce((seed&65535u)+frame*(1+((seed>>16)&7u)),600);
            uint32_t y=160+bounce((seed>>16)+frame*(1+((seed>>24)&3u)),208);
            draw_image(x,y,3,128,hw);
        }
        break;
    }
    publish_pixels();
}
static void clear_samples(void) {
    for (uint32_t n=0;n<2;++n) fps[n]=render_us[n]=samples[n]=burst_ar[n]=burst_aw[n]=0;
}
static void hud(uint32_t hw,uint32_t demo,uint32_t automatic,uint32_t frame,uint32_t variant) {
    text_at(16,8,demo_names[demo],0x07ff);
    if(demo==DEMO_BENCH) { text_at(200,8,"精灵",0xffff); number_at(260,8,sprite_count,0xffe0); }
    text_at(400,8,automatic ? "自动 CPU/FPGA" : "手动",0x07ff);
    for (uint32_t n=0;n<2;++n) {
        uint32_t x=16+n*320;
        uint16_t color=n==hw ? 0xffe0 : 0xffff;
        text_at(x,32,n ? "FPGA 帧率" : "RISC-V 帧率",color);
        if(samples[n]) number_at(x+108,32,fps[n],color);
        else text_at(x+108,32,"-",color);
        text_at(x,54,"渲染微秒",color);
        if(samples[n]) number_at(x+120,54,render_us[n],color);
        else text_at(x+120,54,"-",color);
        text_at(x,76,"DDR 读",color); text_at(x+160,76,"写",color);
        if(samples[n]) {
            number_at(x+72,76,burst_ar[n],color);
            number_at(x+184,76,burst_aw[n],color);
        }
    }
    text_at(16,102,"每帧突发",0x9cf3);
    if(demo==DEMO_COLLISION) {
        text_at(240,102,"命中",0x9cf3); number_at(288,102,collision_hits,0x9cf3);
    }
    if(mmio_read(GFX_BASE+GFX_VIDEO_STATUS)&GFX_VIDEO_VALID) {
        uint32_t size=mmio_read(GFX_BASE+GFX_VIDEO_SIZE);
        number_at(448,102,size&65535,0x9cf3); text_at(484,102,"×",0x9cf3);
        number_at(496,102,size>>16,0x9cf3);
    }
    switch(demo) {
    case DEMO_FILL: text_at(32,128,"RGB565 矩形填充",0xffff); break;
    case DEMO_COPY:
        text_at(64,152,"源图像",0xffff); text_at(384,152,"复制 128×96",0xffff); break;
    case DEMO_BUFFER:
        text_at(32,128,draw_page() ? "页面B" : "页面A",0xffff);
        text_at(200,128,"帧",0xffff); number_at(272,128,frame,0xffff);
        text_at(48,372,"只在垂直消隐时交换",0xffff); break;
    case DEMO_VIDEO: text_at(32,128,"HDMI 颜色与对齐测试",0xffff); break;
    case DEMO_KEY:
        text_at(40,144,"颜色键关",0xffff);
        text_at(344,144,variant ? "颜色键开" : "颜色键关",0xffff); break;
    case DEMO_ALPHA:
        text_at(40,144,"参考不透明",0xffff); text_at(344,144,"FPGA 透明度",0xffff);
        number_at(480,144,alpha_value(variant),0xffe0); text_at(516,144,"/255",0xffff);
        text_at(40,400,"步进1 长按连发 颜色键关",0x07ff); break;
    case DEMO_COLLISION:
        text_at(32,128,collision_active ? "重叠 - 红色" : "空闲 - 绿色",0xffff);
        text_at(32,368,"RISC-V 计算两个 80×80 包围盒",0xffff); break;
    default: text_at(32,128,"随机运动 / 透明与颜色键",0xffff); break;
    }
    text_at(16,426,action_labels[demo],0xffff);
    text_at(16,450,"按键2切换 CPU/FPGA  按键4返回",0x07ff);
    publish_pixels();
}
static uint32_t menu_screen(void) {
    for (;;) {
        puts_uart("MENU\r\n");
        // Menu pixels are UI work, outside the CPU/HW benchmark interval.
        __asm__ volatile (".word 0x500f" ::: "memory");
        if(fill_rect(0,0,640,480,0x0843)) fail("FAIL menu fill");
        if(fill_rect(24,18,592,64,0x10a6)) fail("FAIL menu header");
        text_at(40,30,menu_level ? (menu_group ? "高阶演示" : "基础演示") :
                    "TI60 二维实验室",0xffff);
        text_at(40,54,menu_level ? "选择功能" : "选择测试",0x07ff);
        draw_player(0,566,34,1);
        uint32_t count=menu_level ? 4 : 3;
        uint32_t choice=menu_level ? menu_item[menu_group] : menu_group;
        if (!menu_level) {
            for(uint32_t n=0;n<3;++n) {
                uint32_t y=96+n*80;
                if(fill_rect(32,y,576,68,n==choice ? 0x22ae : 0x10c7)) fail("FAIL menu card");
                if(n==choice && fill_rect(32,y,4,68,0x07ff)) fail("FAIL menu selection");
                text_at(52,y+12,n==2 ? "冰霜幸存者" : n ? "高阶演示" : "基础演示",0xffff);
                text_at(52,y+40,n==2 ? "自动施法 生存180秒" : "4项功能",0x07ff);
            }
            text_at(40,356,"按键1上一项    按键2下一项",0xffff);
            text_at(40,384,"按键5打开      按键4返回",0xffe0);
            text_at(40,432,"8项演示 + 幸存者游戏",0x9cf3);
        } else {
            for(uint32_t n=0;n<4;++n) {
                uint32_t y=90+n*72, demo=menu_group*4+n;
                if(fill_rect(32,y,576,58,n==choice ? 0x22ae : 0x10c7)) fail("FAIL menu card");
                if(n==choice && fill_rect(32,y,4,58,0x07ff)) fail("FAIL menu selection");
                text_at(52,y+8,demo_names[demo],0xffff);
                text_at(52,y+32,demo_details[demo],0x07ff);
            }
            text_at(40,404,"按键1上一项    按键2下一项",0xffff);
            text_at(40,432,"按键5开始      按键4返回",0xffe0);
        }
        publish_pixels();
        if(present_frame()) fail("FAIL menu present");
        mmio_write(GFX_BASE+GFX_DISPLAY,1);
        uint32_t keys;
        do { keys=button_event(); } while (!keys);
        if(keys==8) { menu_level=0; continue; }
        if(keys==16) {
            if(!menu_level && menu_group==2) return 8;
            if(menu_level) return menu_group*4+menu_item[menu_group];
            menu_level=1;
        }
        if(keys==1 || keys==2) {
            choice=(choice+(keys==1 ? count-1 : 1))%count;
            if(menu_level) menu_item[menu_group]=choice; else menu_group=choice;
        }
    }
}
#include "game_view.h"
int main(void) {
    mmio_write(SYSTEM_UART_0_IO_CTRL+8,SYSTEM_CLINT_HZ/(115200u*8u)-1u);
    mmio_write(SYSTEM_UART_0_IO_CTRL+12,7u); // 8 data bits, no parity, one stop bit
    mmio_write(SYSTEM_GPIO_0_IO_CTRL+8,0); // Board keys are input-only.
    mmio_write(SYSTEM_GPIO_0_IO_CTRL+4,0);
    puts_uart("Ti60 INDIVIDUAL DEMOS 64/128/256\r\n");
    if(mmio_read(GFX_BASE+GFX_ID)!=0x32444631u) fail("FAIL ID");
    init_assets();
    for (;;) {
        uint32_t demo=menu_screen();
        if(demo==8) { puts_uart("GAME\r\n"); game_loop(); continue; }
        clear_samples(); collision_hits=collision_active=0;
        uint32_t variant=demo==DEMO_ALPHA ? 128 : demo==DEMO_KEY ? 1 : 0;
        uart_number("DEMO ",demo); puts_uart("\r\n");
        uint32_t automatic=demo==DEMO_BENCH,hw=automatic ? 0 : 1;
        uint32_t frame=0,previous=cycle_now();
        uint32_t elapsed=0,render=0,count=0,read_bursts=0,write_bursts=0,alpha_next_repeat=0;
        int32_t alpha_repeat_direction=0;
        for (;;) {
            uint32_t keys=button_event(), reset_sample=0;
            if(keys==8) break;
            if(demo==DEMO_ALPHA) {
                uint32_t old_variant=variant;
                variant=demo_alpha_update(variant,keys&5u,
                                          mmio_read(GFX_BASE+GFX_BUTTON_HELD),
                                          cycle_now(),&alpha_next_repeat,&alpha_repeat_direction);
                if(variant!=old_variant) { clear_samples(); reset_sample=1; }
            }
            if(keys==1) {
                if(demo==DEMO_BENCH) sprite_count=sprite_count==256 ? 64 : sprite_count*2;
                else if(demo==DEMO_ALPHA) { /* handled by demo_alpha_update() above */ }
                else if(demo==DEMO_FILL) variant=(variant+1)%3;
                else variant^=1u;
                clear_samples(); collision_hits=0; frame=0; reset_sample=1;
            }
            if(keys==2) { hw^=1u; automatic=0; frame=0; reset_sample=1; }
            if(keys==16) break;
            if(automatic && frame>=8) { hw^=1u; frame=0; reset_sample=1; }
            // Keep each four-frame report tied to one Sprite load. A change in
            // object count starts a fresh measurement window.
            // Never mix two rendering modes in one report either.
            if(reset_sample) {
                count=elapsed=render=read_bursts=write_bursts=0; previous=cycle_now();
            }
            uint32_t start=cycle_now();
            uint32_t read_before=mmio_read(GFX_BASE+GFX_BURST_READ);
            uint32_t write_before=mmio_read(GFX_BASE+GFX_BURST_WRITE);
            scene(frame,hw,demo,variant);
            read_bursts+=mmio_read(GFX_BASE+GFX_BURST_READ)-read_before;
            write_bursts+=mmio_read(GFX_BASE+GFX_BURST_WRITE)-write_before;
            render+=cycle_now()-start;
            hud(hw,demo,automatic,frame++,variant);
            if(present_frame()) fail("FAIL present");
            uint32_t now=cycle_now(); elapsed+=now-previous; previous=now;
            if(++count==4) {
                fps[hw]=400000000u/elapsed; render_us[hw]=render/400u; samples[hw]=1;
                burst_ar[hw]=read_bursts/4; burst_aw[hw]=write_bursts/4;
                uart_number(hw ? "HW FPS " : "CPU FPS ",fps[hw]);
                uart_number(" RENDER_US ",render_us[hw]); uart_number(" SPRITES ",scene_sprites(demo));
                uart_number(" DDR_AR ",read_bursts); uart_number(" DDR_AW ",write_bursts);
                uart_number(" HIT ",collision_hits); puts_uart("\r\n");
                count=elapsed=render=read_bursts=write_bursts=0; previous=cycle_now();
            }
        }
    }
}
