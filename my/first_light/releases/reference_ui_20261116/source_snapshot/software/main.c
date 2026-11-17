#include "render.h"
#include "player_asset.h"
#include "demo_controls.h"
#include "frame_metrics.h"
/* Freestanding GCC may emit memcpy for the small strip descriptors. */
__attribute__((used,externally_visible)) void *memcpy(void *destination,const void *source,unsigned int size) {
    volatile unsigned char *dst=destination;
    const volatile unsigned char *src=source;
    while(size--)*dst++=*src++;
    return destination;
}
static void init_game_assets(void);

static uint32_t cycle_now(void) {
    // This Sapphire configuration traps on mcycle CSR reads. The vendor CLINT
    // exposes mtime at +0xBFF8 and ticks at SYSTEM_CLINT_HZ (150 MHz).
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
    puts_uart(message);
    puts_uart(" STATUS=0x"); hex_uart(mmio_read(GFX_BASE+GFX_STATUS));
    puts_uart(" OP=0x"); hex_uart(mmio_read(GFX_BASE+GFX_OPERATION));
    puts_uart(" DST=0x"); hex_uart(mmio_read(GFX_BASE+GFX_DST));
    puts_uart("\r\n"); for (;;) {}
}
static uint32_t draw_buffer = FRAMEBUFFER;
static uint32_t sprite_count = 1;
static uint32_t bench60_pass;
#define BENCH_FRAME_BUDGET_CYCLES FRAME_60_CYCLES
#define BENCH_VARIANTS 4u
#define BENCH_ASSET_BASE (ASSET_BASE+0x2800u)
static uint32_t sprite_best_60[BENCH_VARIANTS];
static const uint8_t bench_sizes[BENCH_VARIANTS]={4u,16u,24u,32u};
static const uint32_t bench_sources[BENCH_VARIANTS]={
    BENCH_ASSET_BASE+0x0680u,
    BENCH_ASSET_BASE,
    BENCH_ASSET_BASE+0x0200u,
    BENCH_ASSET_BASE+0x0800u
};
static uint32_t bench_size_index=BENCH_VARIANTS-1u;
static uint32_t bench_next_size(uint32_t index) {
    return index ? index-1u : BENCH_VARIANTS-1u;
}
enum { DEMO_FILL, DEMO_COPY, DEMO_BUFFER,
       DEMO_KEY, DEMO_ALPHA, DEMO_BENCH };
static const char *const demo_names[6]={
    "矩形填充","图像复制","双缓冲",
    "颜色键","透明混合","SPRITE 压力"
};
static const char *const demo_details[6]={
    "RGB565 硬件填充","DDR 图像复制到显存",
    "垂直消隐交换页面",
    "黑色像素变为透明","W加5 D减5",
    "FPGA ALPHA + COLOR KEY / 60 FPS"
};
static const char *const action_labels[6]={
    "W改变颜色","W改变位置","W改变速度",
    "W开关颜色键","W加5 D减5","W加5 S减5 长按连发"
};
static uint32_t menu_level, menu_group, menu_item[2], menu_repaint_pages;
static uint32_t fps[2], render_us[2], samples[2], burst_ar[2], burst_aw[2];
static uint32_t draw_page(void) { return draw_buffer == FRAMEBUFFER_B ? 1u : 0u; }
static int wait_display_page(uint32_t page) {
    uint32_t start = cycle_now();
    for (;;) {
        uint32_t status = mmio_read(GFX_BASE+GFX_STATUS);
        if (status & (GFX_ERROR|GFX_READ_ERR)) return -3;
        // A disabled scanout retires its final line before clearing its sticky
        // underflow flag. Do not abort that deliberate display shutdown.
        if ((status & GFX_UNDERFLOW) && (mmio_read(GFX_BASE+GFX_DISPLAY)&1u)) return -3;
        if (!(status & GFX_SWAP_PENDING) && ((status >> 6) & 1u) == page) return 0;
        if ((uint32_t)(cycle_now()-start) > (2u*SYSTEM_CLINT_HZ)) return -4;
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
        if ((uint32_t)(cycle_now()-start) > SYSTEM_CLINT_HZ) return -4;
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
static uint16_t sprite_pixel_sized(uint32_t size, uint32_t row, uint32_t col) {
    uint32_t center=size-1u,x=col*2u,y=row*2u;
    uint32_t dx=x>center ? x-center : center-x;
    uint32_t dy=y>center ? y-center : center-y;
    /* Keep the same silhouette at every resolution and keep the full image
     * inside its selected frame instead of cropping the 32x32 source. */
    if (dx+dy > (size*13u+15u)/16u) return 0x0000;
    return row*32u < size*10u ? 0x07ff :
           row*32u < size*20u ? 0xf800 : 0xffe0;
}
static uint16_t sprite_pixel(uint32_t row, uint32_t col) {
    return sprite_pixel_sized(32u,row,col);
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
static uint8_t font_column(uint32_t c,uint32_t col) {
    if(c>='a'&&c<='z') c=c-'a'+'A';
    int glyph=c>='0'&&c<='9' ? (int)(c-'0') : c>='A'&&c<='Z' ? (int)(c-'A'+10) : -1;
    return glyph>=0 ? font5x7[glyph][col] : c=='-' ? 8 :
           c=='/' ? (1u<<(5-col)) : c=='+' ? (col==2 ? 0x3e : 8) :
           c=='_' ? 0x40 : 0;
}
static void text_at_width(uint32_t x,uint32_t y,const char *s,uint16_t color,uint32_t width) {
    if(x>=640u || y>466u) return;
    if(width>640u-x) width=640u-x;
    uint32_t right=x+width;
    while (*s) {
        uint32_t codepoint=font_cn_utf8_next(&s);
        const uint16_t *cn=font_cn_find(codepoint);
        uint32_t cell=cn ? 14u : 12u;
        if(cell>right-x) break; // Keep whole glyphs inside the caller's field.
        if(cn) {
            for(uint32_t row=0;row<14;++row) {
                /* Fusion Pixel glyphs already contain their designed pixel
                 * weight. Draw the centered 12x12 bitmap without widening it. */
                for(uint32_t col=0;col<14;++col)
                    if(cn[row]&(1u<<col)) cpu_fill(x+col,y+row,1,1,color);
            }
            x+=14;
            continue;
        }
        /* The compact 5x7 table stores capitals; normalize lowercase labels
         * so English metrics remain visible instead of leaving blank cells. */
        for (uint32_t col=0;col<5;++col) {
            uint8_t bits=font_column(codepoint,col);
            for (uint32_t row=0;row<7;++row)
                if (bits&(1u<<row)) cpu_fill(x+col*2,y+row*2,2,2,color);
        }
        x+=12;
    }
}
static void text_at(uint32_t x,uint32_t y,const char *s,uint16_t color) {
    text_at_width(x,y,s,color,640u);
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
// A '+' after the largest fitting prefix denotes overflow; the full value is
// still reported over UART. No numeric field may overwrite its next label.
static void decimal_field(char *out,uint32_t value,uint32_t cells) {
    char *end=decimal(out,value);
    if(cells && (uint32_t)(end-out)>cells) {
        for(uint32_t n=0;n+1u<cells;++n) out[n]='9';
        out[cells-1u]='+'; out[cells]=0;
    }
}
static void number_field_at(uint32_t x,uint32_t y,uint32_t width,uint32_t value,uint16_t color) {
    char number[11]; decimal_field(number,value,width/12u);
    text_at_width(x,y,number,color,width);
}
static void uart_number(const char *label,uint32_t value) {
    char number[11]; decimal(number,value); puts_uart(label); puts_uart(number);
}
static uint32_t button_event(void) {
    uint32_t keys=mmio_read(SYSTEM_GPIO_0_IO_CTRL)&15u;
    // GPIO exposes four event bits; the renderer preserves key five separately.
    if(mmio_read(GFX_BASE+GFX_BUTTON_ENTER_EVENT)&1u) keys=16u;
    // The FPGA clears both event sources on the same GPIO acknowledgement toggle.
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
    for (uint32_t variant=0;variant<BENCH_VARIANTS;++variant) {
        uint32_t size=bench_sizes[variant];
        volatile uint16_t *bench=(volatile uint16_t *)(uintptr_t)bench_sources[variant];
        for (uint32_t row=0;row<size;++row)
            for (uint32_t col=0;col<size;++col)
                bench[row*size+col]=sprite_pixel_sized(size,row,col);
    }
    init_game_assets();
    // The game atlas already contains these identical four direction frames.
    // Reuse its decoded DDR pixels instead of embedding a second RLE palette.
    for (uint32_t frame=0;frame<PLAYER_FRAME_COUNT;++frame) {
        volatile uint32_t *player=(volatile uint32_t *)(uintptr_t)
            (PLAYER_ASSET_BASE+frame*PLAYER_FRAME_BYTES);
        const volatile uint32_t *source=(const volatile uint32_t *)(uintptr_t)
            (ASSET_BASE+0x4000u+frame*4u*PLAYER_FRAME_BYTES);
        for(uint32_t word=0;word<PLAYER_FRAME_BYTES/4u;++word) player[word]=source[word];
    }
    publish_pixels(); // Drain CPU stores before any hardware source reads.
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
static void draw_bench_sprite(uint32_t x,uint32_t y) {
    uint32_t size=bench_sizes[bench_size_index];
    uint32_t source=bench_sources[bench_size_index];
    if (blend_image(source,size*2u,x,y,size,size,128,0,
                    GFX_BLEND_ALPHA|GFX_BLEND_KEY))
        fail("FAIL bench sprite");
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
// UI transparency rises toward 255; the blend engine takes foreground opacity.
static uint32_t alpha_value(uint32_t variant) { return 255u-variant; }
static uint32_t scene_sprites(uint32_t demo) {
    return demo==DEMO_BENCH ? sprite_count : (demo==DEMO_KEY || demo==DEMO_ALPHA) ? 8 : 0;
}
static void scene(uint32_t frame,uint32_t hw,uint32_t demo,uint32_t variant) {
    static const uint16_t colors[8]={0xffff,0xffe0,0x07ff,0x07e0,0xf81f,0xf800,0x001f,0};
    // Sapphire BSP 0x500F invalidates stale reads left by hardware writes.
    __asm__ volatile (".word 0x500f" ::: "memory");
    // The pressure HUD persists in both pages; only its moving viewport clears.
    if(demo!=DEMO_BENCH) paint(0,0,640,480,0x0862,hw);
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
    default: // Performance scene contains only the selected moving Sprite load.
        paint(0,152,640,256,0x0843,hw);
        for(uint32_t n=0;n<sprite_count;++n) {
            uint32_t seed=sprite_seed(n);
            uint32_t size=bench_sizes[bench_size_index];
            uint32_t x=8+bounce((seed&65535u)+frame*(1+((seed>>16)&7u)),632u-size);
            uint32_t y=160+bounce((seed>>16)+frame*(1+((seed>>24)&3u)),240u-size);
            draw_bench_sprite(x,y);
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
    {
        text_at(400,8,automatic ? "自动 CPU/FPGA" : "手动",0x07ff);
        for (uint32_t n=0;n<2;++n) {
            uint32_t x=16+n*320;
            uint16_t color=n==hw ? 0xffe0 : 0xffff;
            text_at(x,32,n ? "FPGA FPS" : "RISC-V FPS",color);
            if(samples[n]) number_field_at(x+132,32,60,fps[n],color);
            else text_at(x+132,32,"-",color);
            text_at(x,54,"RENDER_US",color);
            if(samples[n]) number_field_at(x+120,54,144,render_us[n],color);
            else text_at(x+120,54,"-",color);
            text_at(x,76,"DDR_RD",color); text_at(x,96,"DDR_WR",color);
            if(samples[n]) {
                number_field_at(x+120,76,144,burst_ar[n],color);
                number_field_at(x+120,96,144,burst_aw[n],color);
            }
        }
    }
    text_at(16,114,"每帧突发",0x9cf3);
    if(mmio_read(GFX_BASE+GFX_VIDEO_STATUS)&GFX_VIDEO_VALID) {
        uint32_t size=mmio_read(GFX_BASE+GFX_VIDEO_SIZE);
        number_field_at(448,114,60,size&65535,0x9cf3); text_at(520,114,"×",0x9cf3);
        number_field_at(548,114,60,size>>16,0x9cf3);
    }
    switch(demo) {
    case DEMO_FILL: text_at(32,128,"RGB565 矩形填充",0xffff); break;
    case DEMO_COPY:
        text_at(64,152,"源图像",0xffff); text_at(384,152,"复制 128×96",0xffff); break;
    case DEMO_BUFFER:
        text_at(32,128,"双缓冲演示",0xffff);
        text_at(200,128,"帧",0xffff); number_at(272,128,frame,0xffff);
        text_at(48,372,"只在垂直消隐时交换",0xffff); break;
    case DEMO_KEY:
        text_at(40,144,"颜色键关",0xffff);
        text_at(344,144,variant ? "颜色键开" : "颜色键关",0xffff); break;
    case DEMO_ALPHA:
        text_at(40,144,"参考不透明",0xffff); text_at(344,144,"FPGA 透明度",0xffff);
        number_field_at(480,144,36,variant,0xffe0); text_at(528,144,"/255",0xffff);
        text_at(40,400,"步进5 长按连发 颜色键关",0x07ff); break;
    default: text_at(32,128,"随机运动 / 透明与颜色键",0xffff); break;
    }
    text_at(16,426,action_labels[demo],0xffff);
    text_at(16,450,demo==DEMO_ALPHA ? "S切换 CPU/FPGA  A返回" : "D调整参数  S切换 CPU/FPGA  A返回",0x07ff);
    publish_pixels();
}
#include "book_menu.h"
#include "demo_skin.h"
static uint32_t menu_screen(void) {
    book_init_assets();
    for (;;) {
        if(book_closed) {
            puts_uart("BOOK COVER\r\n");
            book_cover();publish_pixels();
            if(present_frame())fail("FAIL book cover");
            mmio_write(GFX_BASE+GFX_DISPLAY,1);
            uint32_t key;
            do {key=button_event();}while(key!=16u);
            book_closed=0;book_animate(0);continue;
        }
        puts_uart("MENU\r\n");
        // Menu pixels are UI work, outside the CPU/HW benchmark interval.
        __asm__ volatile (".word 0x500f" ::: "memory");
        book_menu_frame();publish_pixels();
        if(present_frame())fail("FAIL menu present");
        mmio_write(GFX_BASE+GFX_DISPLAY,1);
        // A basic-demo exit primes both retired pages with this same menu.
        // No old moving-page pixels remain available for a later page switch.
        if(menu_repaint_pages && --menu_repaint_pages)continue;
        uint32_t keys;
        do {keys=button_event();}while(!keys);
        if(keys==4u) {
            if(menu_level) {menu_level=0;book_turn();}
            else {book_animate(1);book_closed=1;}
            continue;
        }
        if(keys==16u) {
            if(!menu_level && menu_group==2u)return 8u;
            if(menu_level)return menu_group*3u+menu_item[menu_group];
            menu_level=1;book_turn();
        }
        if(keys==1u || keys==2u) {
            uint32_t choice=menu_level ? menu_item[menu_group]:menu_group;
            choice=(choice+(keys==1u ? 2u:1u))%3u;
            if(menu_level)menu_item[menu_group]=choice;else menu_group=choice;
        }
    }
}
#include "game_view.h"
#include "basic_demo.h"
#include "effects_demo.h"
// Game and pressure pages never run together, so share their per-page HUD cache.
static void bench_hud(void) {
    uint32_t page=draw_page(),size=bench_sizes[bench_size_index];
    game_hud_number(page,0,112,58,120,sprite_count,0xffe0);
    game_hud_number(page,1,414,58,120,sprite_best_60[bench_size_index],0xffe0);
    game_hud_number(page,2,160,82,24,size,0xffe0);
    game_hud_number(page,3,220,82,24,size,0xffe0);
    game_hud_number(page,4,64,106,36,fps[1],0xffe0);
    game_hud_number(page,5,272,106,120,render_us[1],0xffff);
    game_hud_number(page,6,100,130,120,burst_ar[1],0xffff);
    game_hud_number(page,7,414,130,120,burst_aw[1],0xffff);
    uint32_t state=samples[1] ? (bench60_pass ? 2u : 1u) : 0u;
    if(!(game_hud_number_valid[page]&256u) || game_hud_numbers[page][8]!=state) {
        cpu_fill(424,106,144,14,0x10a6);
        text_at(424,106,state==2u ? "60FPS PASS" : state ? "60FPS FAIL" : "60FPS WAIT",0x9cf3);
        game_hud_numbers[page][8]=state;
        game_hud_number_valid[page]|=256u;
    }
    publish_pixels();
}
static void bench_prime_framebuffers(void) {
    // Keep the complete menu visible while composing the retired back page.
    // Present each finished pressure page at vblank; never blank HDMI here.
    puts_uart("BENCH INIT\r\n");
    // Draw static text before sampling, once in each retired back buffer.
    game_hud_number_valid[0]=game_hud_number_valid[1]=0;
    for(uint32_t page=0;page<2;++page) {
        demo_skin(DEMO_BENCH,"FPGA");demo_metrics();
        text_at(24,58,"SPRITES",UI_CREAM);text_at(338,58,"MAX60",UI_ICE);
        text_at(24,82,"SPRITE SIZE",UI_CREAM);text_at(196,82,"X",UI_CREAM);
        text_at(24,106,"FPS",UI_CREAM);text_at(152,106,"RENDER_US",UI_CREAM);
        text_at(24,130,"DDR_RD",UI_CREAM);text_at(338,130,"DDR_WR",UI_CREAM);
        text_at(16,430,action_labels[DEMO_BENCH],UI_CREAM);
        text_at(16,454,"D换尺寸  A返回",UI_ICE);
        demo_window(0,152,640,256);
        // Seed the moving region too: the first visible pressure page already
        // contains its Sprite rather than waiting for the measurement loop.
        scene(0,1,DEMO_BENCH,0);
        bench_hud();
        if(present_frame()) fail("FAIL bench init");
    }
    puts_uart("BENCH RUN\r\n");
}
int main(void) {
    mmio_write(SYSTEM_UART_0_IO_CTRL+8,SYSTEM_CLINT_HZ/(115200u*8u)-1u);
    mmio_write(SYSTEM_UART_0_IO_CTRL+12,7u); // 8 data bits, no parity, one stop bit
    mmio_write(SYSTEM_GPIO_0_IO_CTRL+8,0); // Board keys are input-only.
    mmio_write(SYSTEM_GPIO_0_IO_CTRL+4,0);
    puts_uart("Ti60 INDIVIDUAL DEMOS\r\n");
    if(mmio_read(GFX_BASE+GFX_ID)!=0x32444631u) fail("FAIL ID");
    init_assets();
    for (;;) {
        uint32_t demo=menu_screen();
        // Animation cache shares DDR with these mutually exclusive images.
        // Reload at entry, before sampling; never upload inside a timed batch.
        book_cache_valid=0;basic_assets_ready=0;effects_assets_ready=0;
        if(demo==8) { puts_uart("GAME\r\n"); game_loop();book_assets_ready=0;book_cache_valid=0;continue; }
        if(demo<=DEMO_BUFFER) { basic_demo_loop(demo); basic_return_to_menu(); continue; }
        if(demo==DEMO_KEY || demo==DEMO_ALPHA) { effects_demo_loop(demo); continue; }
        clear_samples();
        if(demo==DEMO_BENCH) {
            for (uint32_t n=0;n<BENCH_VARIANTS;++n) sprite_best_60[n]=0;
            bench_size_index=BENCH_VARIANTS-1u;
            bench60_pass=0;
        }
        uint32_t variant=demo==DEMO_ALPHA ? 128 : demo==DEMO_KEY ? 1 : 0;
        uart_number("DEMO ",demo); puts_uart("\r\n");
        uint32_t automatic=0,hw=1;
        if(demo==DEMO_BENCH) {
            sprite_count=1;
            bench_prime_framebuffers();
        }
        uint32_t frame=0,previous=cycle_now();
        uint32_t previous_video=mmio_read(GFX_BASE+GFX_FRAME_COUNT);
        uint32_t elapsed=0,render=0,count=0,read_bursts=0,write_bursts=0,alpha_next_repeat=0;
        uint32_t render_peak=0,missed_refreshes=0;
        uint32_t bench60_frame_ok=1;
        int32_t alpha_repeat_direction=0,bench_repeat_direction=0;
        uint32_t bench_next_repeat=0;
        for (;;) {
            uint32_t keys=button_event(), reset_sample=0;
            if(keys==4) break;
            if(demo==DEMO_BENCH) {
                uint32_t old_count=sprite_count;
                sprite_count=demo_bench_update(sprite_count,keys,
                    mmio_read(GFX_BASE+GFX_BUTTON_HELD),cycle_now(),
                    &bench_next_repeat,&bench_repeat_direction);
                if(sprite_count!=old_count) { clear_samples(); reset_sample=1; }
            }
            if(demo==DEMO_ALPHA) {
                uint32_t old_variant=variant;
                uint32_t held=mmio_read(GFX_BASE+GFX_BUTTON_HELD);
                uint32_t alpha_keys=(keys&1u)|((keys&8u)?4u:0u);
                uint32_t alpha_held=(held&1u)|((held&8u)?4u:0u);
                variant=demo_alpha_update(variant,alpha_keys,alpha_held,
                                          cycle_now(),&alpha_next_repeat,&alpha_repeat_direction);
                if(variant!=old_variant) { clear_samples(); reset_sample=1; }
            }
            if(keys==1 && demo!=DEMO_BENCH && demo!=DEMO_ALPHA) {
                // Pressure controls use DEMO_BENCH_STEP in demo_bench_update().
                // There is no coarse load table or artificial benchmark ceiling.
                if(demo==DEMO_FILL) variant=(variant+1)%3;
                else variant^=1u;
                clear_samples(); frame=0; reset_sample=1;
            }
            if(keys==8 && demo==DEMO_BENCH) {
                bench_size_index=bench_next_size(bench_size_index);
                clear_samples(); frame=0; reset_sample=1; bench60_pass=0;
            }
            if(keys==8 && demo!=DEMO_BENCH && demo!=DEMO_ALPHA) {
                if(demo==DEMO_FILL) variant=(variant+1u)%3u;
                else variant^=1u;
                clear_samples(); frame=0; reset_sample=1;
            }
            if(keys==2 && demo!=DEMO_BENCH) { hw^=1u; automatic=0; frame=0; reset_sample=1; }
            if(automatic && frame>=8) { hw^=1u; frame=0; reset_sample=1; }
            // Keep each report tied to one Sprite load. A change in
            // object count starts a fresh measurement window.
            // Never mix two rendering modes in one report either.
            if(reset_sample) {
                count=elapsed=render=read_bursts=write_bursts=0;
                render_peak=missed_refreshes=0;
                bench60_frame_ok=1; bench60_pass=0;
                if(demo!=DEMO_BENCH) previous=cycle_now();
            }
            uint32_t start=cycle_now();
            uint32_t read_before=mmio_read(GFX_BASE+GFX_BURST_READ);
            uint32_t write_before=mmio_read(GFX_BASE+GFX_BURST_WRITE);
            scene(frame,hw,demo,variant);
            if(demo==DEMO_BENCH) bench_hud();
            read_bursts+=mmio_read(GFX_BASE+GFX_BURST_READ)-read_before;
            write_bursts+=mmio_read(GFX_BASE+GFX_BURST_WRITE)-write_before;
            uint32_t frame_render=cycle_now()-start;
            render+=frame_render;
            if(frame_render>render_peak) render_peak=frame_render;
            if(demo!=DEMO_BENCH) hud(hw,demo,automatic,frame,variant);
            ++frame;
            if(present_frame()) fail("FAIL present");
            uint32_t now=cycle_now(),frame_elapsed=now-previous;
            elapsed+=frame_elapsed; previous=now;
            if(demo==DEMO_BENCH) {
                uint32_t video=mmio_read(GFX_BASE+GFX_FRAME_COUNT);
                uint32_t refreshes=video-previous_video;
                // Exactly one display refresh per new frame, with the complete
                // scene + HUD inside 1/60 s. Avoid APB poll jitter at the limit.
                if(frame_render>BENCH_FRAME_BUDGET_CYCLES || refreshes!=1u)
                    bench60_frame_ok=0;
                if(refreshes>1u) missed_refreshes+=refreshes-1u;
                previous_video=video;
            }
            uint32_t sample_target=demo==DEMO_BENCH ? 30u : 4u;
            if(++count==sample_target) {
                fps[hw]=frame_measured_fps(count,elapsed);
                render_us[hw]=render/(count*(SYSTEM_CLINT_HZ/1000000u)); samples[hw]=1;
                burst_ar[hw]=read_bursts/count; burst_aw[hw]=write_bursts/count;
                if(demo==DEMO_BENCH) {
                    // Every sampled frame must meet its render budget and
                    // retire on the next display refresh; never force FPS=60.
                    bench60_pass=bench60_frame_ok;
                    if(bench60_pass && sprite_count>sprite_best_60[bench_size_index])
                        sprite_best_60[bench_size_index]=sprite_count;
                }
                uart_number(hw ? "HW FPS " : "CPU FPS ",fps[hw]);
                uart_number(" RENDER_US ",render_us[hw]); uart_number(" SPRITES ",scene_sprites(demo));
                if(demo==DEMO_BENCH) {
                    uart_number(" SIZE ",bench_sizes[bench_size_index]);
                    uart_number(" MAX60 ",sprite_best_60[bench_size_index]);
                    puts_uart(bench60_pass ? " PASS" : " FAIL");
                    uart_number(" MAX_US ",render_peak/(SYSTEM_CLINT_HZ/1000000u));
                    uart_number(" MISSED ",missed_refreshes);
                }
                uart_number(" DDR_AR ",read_bursts); uart_number(" DDR_AW ",write_bursts);
                puts_uart("\r\n");
                count=elapsed=render=read_bursts=write_bursts=0;
                render_peak=missed_refreshes=0;
                bench60_frame_ok=1; // A later complete window may recover.
                // Retain the last presentation timestamp: the next interval
                // includes UART reporting instead of hiding serial overhead.
            }
        }
    }
}
