#include "render.h"
#include "basic_layout.h"
#include "basic_metrics.h"
#include "alpha_control.h"
_Static_assert(SYSTEM_CLINT_HZ==BASIC_TICK_HZ,"BASIC movement clock must match CLINT");

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
static uint32_t key_enabled = 1;
static alpha_control_t transparency;
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
// Both operations complete through the same status register and timeout.
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
    mmio_write(GFX_BASE+GFX_OPERATION, GFX_OP_FILL);
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
static int copy_image_mode(uint32_t source, uint32_t source_stride, uint32_t dst_x,
                           uint32_t dst_y, uint32_t width, uint32_t height,
                           uint16_t key, uint32_t operation) {
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
    mmio_write(GFX_BASE+GFX_OPERATION, operation);
    if (operation == GFX_OP_KEYED_COPY || operation == GFX_OP_ALPHA_COPY)
        mmio_write(GFX_BASE+GFX_COLOR, key);
    mmio_write(GFX_BASE+GFX_SRC, source);
    mmio_write(GFX_BASE+GFX_SRC_STRIDE, source_stride);
    mmio_write(GFX_BASE+GFX_DST, draw_buffer+dst_y*FRAME_STRIDE+dst_x*2);
    mmio_write(GFX_BASE+GFX_WIDTH, width);
    mmio_write(GFX_BASE+GFX_HEIGHT, height);
    mmio_write(GFX_BASE+GFX_STRIDE, FRAME_STRIDE);
    mmio_write(GFX_BASE+GFX_COMMAND, 1);
    return wait_render();
}
int copy_image(uint32_t source, uint32_t source_stride, uint32_t dst_x,
               uint32_t dst_y, uint32_t width, uint32_t height) {
    return copy_image_mode(source, source_stride, dst_x, dst_y, width, height,
                           0, GFX_OP_COPY);
}
int copy_image_keyed(uint32_t source, uint32_t source_stride, uint32_t dst_x,
                     uint32_t dst_y, uint32_t width, uint32_t height,
                     uint16_t key) {
    return copy_image_mode(source, source_stride, dst_x, dst_y, width, height,
                           key, GFX_OP_KEYED_COPY);
}
int copy_image_alpha(uint32_t source, uint32_t source_stride, uint32_t dst_x,
                     uint32_t dst_y, uint32_t width, uint32_t height,
                     uint32_t opacity, uint32_t keyed, uint16_t key) {
    if(opacity>256u || keyed>1u) return -1;
    if(mmio_read(GFX_BASE+GFX_STATUS)&(GFX_BUSY|GFX_SWAP_PENDING)) return -2;
    mmio_write(GFX_BASE+GFX_ALPHA,opacity);
    mmio_write(GFX_BASE+GFX_ALPHA_KEY,keyed);
    return copy_image_mode(source,source_stride,dst_x,dst_y,width,height,key,GFX_OP_ALPHA_COPY);
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
#define ASSET_MAGIC 0x37375341u /* "AS77" */
#define ASSET_VERSION 1u
#define ASSET_TABLE_BYTES (77u*8u)
#define ASSET_PIXEL_OFFSET (16u+ASSET_TABLE_BYTES)
#define POSE_TICKS 8333333u
#define BASIC_SPRITE_BASE (ASSET_BASE+0x000f0000u)
#define MENU_MODE 0u
#define BASIC_MODE 1u
#define ADVANCED_MODE 2u
typedef struct {
    uint32_t offset;
    uint8_t width, height;
    int8_t dx, dy;
} sprite_frame_t;
static int asset_valid(void) {
    const volatile uint32_t *h=(const volatile uint32_t *)(uintptr_t)ASSET_BASE;
    __asm__ volatile (".word 0x500f" ::: "memory");
    uint32_t length=h[2];
    if(h[0]!=ASSET_MAGIC || h[1]!=ASSET_VERSION ||
       length<=ASSET_PIXEL_OFFSET || length>ASSET_BYTES || (length&1u)) return 0;
    const volatile sprite_frame_t *f=(const volatile sprite_frame_t *)(uintptr_t)(ASSET_BASE+16);
    for(uint32_t i=0;i<77;++i)
        if(!f[i].width || !f[i].height || f[i].offset<ASSET_PIXEL_OFFSET ||
           f[i].offset>length ||
           (uint32_t)f[i].width*f[i].height*2u>length-f[i].offset) return 0;
    return 1;
}
static void cpu_fill(uint32_t x, uint32_t y, uint32_t w, uint32_t h, uint16_t c) {
    for (uint32_t row=0; row<h; ++row) {
        volatile uint16_t *p=(volatile uint16_t *)(uintptr_t)(draw_buffer+(y+row)*1280+x*2);
        for (uint32_t col=0; col<w; ++col) p[col]=c;
    }
}
static void cpu_copy(uint32_t source,uint32_t x,uint32_t y,uint32_t width,uint32_t height) {
    uint32_t a=alpha_opacity(transparency.percent);
    for (uint32_t row=0; row<height; ++row) {
        const volatile uint16_t *s=(const volatile uint16_t *)(uintptr_t)(source+row*width*2u);
        volatile uint16_t *d=(volatile uint16_t *)(uintptr_t)(draw_buffer+(y+row)*1280+x*2);
        for (uint32_t col=0; col<width; ++col) {
            uint16_t pixel=s[col];
            if (!key_enabled || pixel!=0xf81f)
                d[col]=transparency.percent ? alpha_rgb565(pixel,d[col],a) : pixel;
        }
    }
}
static basic_layout_t basic_layout;
static basic_metrics_t basic_metrics[2];
static void reset_basic_metrics(void) {
    basic_metrics_reset(&basic_metrics[0]);
    basic_metrics_reset(&basic_metrics[1]);
}
// The 32x32 checkerboard resource lives after the uploaded 77-frame asset.
static void init_basic_sprite(void) {
    volatile uint16_t *p=(volatile uint16_t *)(uintptr_t)BASIC_SPRITE_BASE;
    for(uint32_t row=0;row<32;++row)
        for(uint32_t col=0;col<32;++col)
            p[row*32u+col]=basic_sprite_pixel(col,row);
    publish_pixels();
}
static void basic_cpu_copy(uint32_t x,uint32_t y) {
    for(uint32_t row=0;row<32;++row) {
        const volatile uint16_t *s=(const volatile uint16_t *)(uintptr_t)
            (BASIC_SPRITE_BASE+row*SPRITE_STRIDE);
        volatile uint16_t *d=(volatile uint16_t *)(uintptr_t)
            (draw_buffer+(y+row)*FRAME_STRIDE+x*2u);
        for(uint32_t col=0;col<32;++col) d[col]=s[col];
    }
}
static void basic_hw_block(uint32_t operation,const basic_block_t *p) {
    // Width, height, pitches, source and draw page are fixed for this frame.
    // The command's existing MMIO fences drain ordered configuration stores
    // before START, and complete START before polling DONE. Public drivers
    // retain all validation for arbitrary rectangles and advanced sprites.
    *(volatile uint32_t *)(uintptr_t)(GFX_BASE+GFX_OPERATION)=operation;
    *(volatile uint32_t *)(uintptr_t)(GFX_BASE+GFX_DST)=
        draw_buffer+p->y*FRAME_STRIDE+p->x*2u;
    if(operation==GFX_OP_FILL)
        *(volatile uint32_t *)(uintptr_t)(GFX_BASE+GFX_COLOR)=p->color;
    mmio_write(GFX_BASE+GFX_COMMAND,1);
    if(wait_render()) fail("FAIL basic command");
}
static void basic_scene(uint32_t hw,uint32_t motion_ticks) {
    // Diagnostic mailbox shared with the advanced scene; descriptors let
    // simulation independently rasterize all commands, including overlaps.
    mmio_write(0x013fff00u,0xba000000u|(hw<<20)|basic_layout.count);
    mmio_write(0x013fff04u,(uint32_t)(uintptr_t)basic_layout.fill);
    mmio_write(0x013fff08u,(uint32_t)(uintptr_t)basic_layout.copy);
    mmio_write(0x013fff0cu,(uint32_t)(uintptr_t)basic_layout.fill_motion);
    mmio_write(0x013fff10u,(uint32_t)(uintptr_t)basic_layout.copy_motion);
    mmio_write(0x013fff14u,motion_ticks);
    mmio_write(0x013fff18u,basic_layout.tick_remainder);
    if(!hw) __asm__ volatile (".word 0x500f" ::: "memory");
    if(hw) {
        if(fill_rect(0,0,640,480,BASIC_BACKGROUND)) fail("FAIL basic fill");
        mmio_write(GFX_BASE+GFX_WIDTH,BASIC_SIDE);
        mmio_write(GFX_BASE+GFX_HEIGHT,BASIC_SIDE);
        mmio_write(GFX_BASE+GFX_SRC,BASIC_SPRITE_BASE);
        mmio_write(GFX_BASE+GFX_SRC_STRIDE,SPRITE_STRIDE);
    }
    else cpu_fill(0,0,640,480,BASIC_BACKGROUND);
    for(uint32_t n=0;n<basic_layout.count;++n) {
        const basic_block_t *f=&basic_layout.fill[n], *c=&basic_layout.copy[n];
        if(hw) {
            basic_hw_block(GFX_OP_FILL,f);
            basic_hw_block(GFX_OP_COPY,c);
        } else {
            cpu_fill(f->x,f->y,BASIC_SIDE,BASIC_SIDE,f->color);
            basic_cpu_copy(c->x,c->y);
        }
    }
    publish_pixels();
}
static void advanced_scene(uint32_t pose,uint32_t x,uint32_t hw) {
    mmio_write(0x013fff1cu,transparency.percent);
    *(volatile uint32_t *)(uintptr_t)0x013fff00u =
        0x77000000u | (hw<<21) | (key_enabled<<20) | (x<<8) | pose;
    const volatile sprite_frame_t *frames=(const volatile sprite_frame_t *)(uintptr_t)(ASSET_BASE+16);
    sprite_frame_t f=frames[pose];
    uint32_t dst_x=(uint32_t)((int32_t)x+f.dx);
    uint32_t dst_y=(uint32_t)(320+f.dy);
    uint32_t source=ASSET_BASE+f.offset;
    if (!hw) {
        // Sapphire BSP 0x500F invalidates stale reads left by hardware writes.
        __asm__ volatile (".word 0x500f" ::: "memory");
    }
    if (hw) { if (fill_rect(0,0,640,480,0x1082)) fail("FAIL fill"); }
    else cpu_fill(0,0,640,480,0x1082);
    if (hw) {
        if(fill_rect(0,277,640,20,0x07e0)) fail("FAIL fill");
        if(fill_rect(0,321,640,20,0x001f)) fail("FAIL fill");
        int result=transparency.percent ?
            copy_image_alpha(source,(uint32_t)f.width*2u,dst_x,dst_y,f.width,f.height,
                             alpha_opacity(transparency.percent),key_enabled,0xf81f) :
            (key_enabled ? copy_image_keyed(source,(uint32_t)f.width*2u,dst_x,dst_y,f.width,f.height,0xf81f)
                         : copy_image(source,(uint32_t)f.width*2u,dst_x,dst_y,f.width,f.height));
        if(result) fail("FAIL copy");
    } else {
        cpu_fill(0,277,640,20,0x07e0);
        cpu_fill(0,321,640,20,0x001f);
        cpu_copy(source,dst_x,dst_y,f.width,f.height);
    }
    publish_pixels();
}
// Original 3x5 bitmap glyphs, row-major, most significant pixel first.
static const uint16_t font[36]={
    0x7b6f,0x2492,0x73e7,0x73cf,0x5bc9,0x79cf,0x79ef,0x7249,0x7bef,0x7bcf,
    0x2bed,0x6bae,0x7927,0x6b6e,0x79a7,0x79a4,0x796f,0x5bed,0x7497,0x124f,
    0x5bad,0x4927,0x5fed,0x5f7d,0x7b6f,0x7be4,0x7b7b,0x7bac,0x79cf,0x7492,
    0x5b6f,0x5b6a,0x5bfd,0x5aad,0x5a92,0x72a7
};
static uint32_t basic_text_fast;
static void text_at(uint32_t x,uint32_t y,const char *s,uint16_t color) {
    while (*s) {
        char c=*s++;
        uint16_t bits=c=='%' ? 0x52a5 : c=='+' ? 0x05d0 : c=='-' ? 0x01c0 : c=='.' ? 0x0002 : c=='/' ? 0x12a4 : c>='0'&&c<='9' ? font[c-'0'] :
                      c>='A'&&c<='Z' ? font[c-'A'+10] : 0;
        if(basic_text_fast && !(x&1u)) {
            // BASIC has a known cleared background. Pack pairs of pixels
            // into aligned 32-bit stores, avoiding a DDR write per halfword.
            // Menu button faces and advanced overlays retain generic text.
            for(uint32_t row=0;row<5;++row) {
                uint32_t mask=(bits>>(12u-row*3u))&7u;
                uint32_t a=mask&4u ? color : BASIC_BACKGROUND;
                uint32_t b=mask&2u ? color : BASIC_BACKGROUND;
                uint32_t c=mask&1u ? color : BASIC_BACKGROUND;
                for(uint32_t r=0;r<3;++r) {
                    volatile uint32_t *p=(volatile uint32_t *)(uintptr_t)
                        (draw_buffer+(y+row*3u+r)*FRAME_STRIDE+x*2u);
                    if(mask&4u) p[0]=a|(a<<16);
                    if(mask&6u) p[1]=a|(b<<16);
                    if(mask&2u) p[2]=b|(b<<16);
                    if(mask&1u) { p[3]=c|(c<<16); p[4]=c|(BASIC_BACKGROUND<<16); }
                }
            }
        } else {
            for (uint32_t row=0;row<5;++row) for (uint32_t col=0;col<3;++col)
                if (bits & (1u<<(14-row*3-col))) cpu_fill(x+col*3,y+row*3,3,3,color);
        }
        x+=12;
    }
}
static void square_button(uint32_t x,uint32_t selected,const char *label) {
    const uint32_t y=145u, side=180u;
    uint16_t edge=selected ? 0x07ffu : 0x8410u;
    uint16_t face=selected ? 0x2104u : 0x18c3u;
    uint32_t letters=0;
    while(label[letters]) ++letters;
    cpu_fill(x,y,side,side,edge);
    cpu_fill(x+6u,y+6u,side-12u,side-12u,face);
    text_at(x+(side-letters*12u)/2u,
            y+80u,label,selected ? 0xffffu : 0xbdf7u);
}
static void draw_menu(uint32_t selection) {
    cpu_fill(0,0,640,480,0x1082u);
    text_at(242,76,"FUNCTION MENU",0xffffu);
    square_button(112,selection==0u,"BASIC");
    square_button(348,selection==1u,"ADVANCED");
    text_at(194,366,"KEY0 LEFT  KEY1 RIGHT",0xffffu);
    text_at(200,392,"KEY2 ENTER KEY3 BACK",0xffffu);
    publish_pixels();
}
static char *decimal(char *out,uint32_t value) {
    char digits[10]; uint32_t n=0;
    do { digits[n++]=(char)('0'+value%10); value/=10; } while (value);
    while(n) *out++=digits[--n];
    *out=0; return out;
}
static void resolution_hud(uint32_t y) {
    uint32_t status=mmio_read(GFX_BASE+GFX_VIDEO_STATUS);
    if (!(status&GFX_VIDEO_VALID)) {
        text_at(532,y,"RES WAIT",0xffff);
        return;
    }
    uint32_t size=mmio_read(GFX_BASE+GFX_VIDEO_SIZE);
    uint32_t width=size&0xffffu, height=size>>16;
    char label[16]="RES ";
    char *end=decimal(label+4,width);
    *end++='X';
    end=decimal(end,height);
    uint32_t glyphs=(uint32_t)(end-label);
    text_at(640-12-glyphs*12,y,label,0xffff);
}
static char *tenths(char *out,uint32_t value) {
    out=decimal(out,value/10u); *out++='.';
    *out++=(char)('0'+value%10u); *out=0; return out;
}
static char basic_log[96];
static uint32_t basic_log_length,basic_log_index;
static char *append_text(char *out,const char *text) {
    while(*text) *out++=*text++;
    *out=0; return out;
}
static void basic_log_pump(void) {
    uint32_t room=(mmio_read(SYSTEM_UART_0_IO_CTRL+4)>>16)&255u;
    if(room>16u) room=16u;
    while(room-- && basic_log_index<basic_log_length)
        mmio_write(SYSTEM_UART_0_IO_CTRL,(uint32_t)basic_log[basic_log_index++]);
}
static void basic_log_flush(void) {
    while(basic_log_index<basic_log_length) basic_log_pump();
}
static void basic_log_queue(const basic_metrics_t *s,uint32_t hw,uint32_t blocks) {
    // Sending a whole status line synchronously can cost several ms at
    // 115200 baud. Keep frame rendering independent of TX FIFO drain time.
    if(basic_log_index<basic_log_length) return;
    char *p=append_text(basic_log,hw ? "BASIC HW BLOCKS " : "BASIC CPU BLOCKS ");
    p=decimal(p,blocks); p=append_text(p," FPS "); p=tenths(p,s->fps10);
    p=append_text(p," US "); p=decimal(p,s->render_us);
    p=append_text(p," OPS/S "); p=decimal(p,s->ops_per_second);
    p=append_text(p,"\r\n");
    basic_log_length=(uint32_t)(p-basic_log); basic_log_index=0;
}
static void basic_hud(uint32_t hw) {
    basic_text_fast=1;
    char number[16];
    for(uint32_t n=0;n<2;++n) {
        uint32_t x=12u+n*320u;
        uint16_t color=n==hw ? 0xffffu : 0x8410u;
        const basic_metrics_t *s=&basic_metrics[n];
        text_at(x,8,n ? "HW FPS" : "CPU FPS",color);
        tenths(number,s->fps10); text_at(x+100u,8,s->valid ? number : "-",color);
        text_at(x,32,"US",color);
        decimal(number,s->render_us); text_at(x+36u,32,s->valid ? number : "-",color);
        text_at(x,56,"OPS/S",color);
        decimal(number,s->ops_per_second); text_at(x+76u,56,s->valid ? number : "-",color);
    }
    text_at(12,80,"BLOCKS",0xffff); decimal(number,basic_layout.count*2u); text_at(96,80,number,0xffff);
    text_at(208,80,"FILL",0xffff); decimal(number,basic_layout.count); text_at(268,80,number,0xffff);
    text_at(388,80,"COPY",0xffff); text_at(448,80,number,0xffff);
    text_at(12,104,"CPU/HW",0xffff);
    if(basic_metrics[0].valid && basic_metrics[1].valid && basic_metrics[1].render_us) {
        char *end=tenths(number,basic_speed10(&basic_metrics[0],&basic_metrics[1]));
        *end++='X'; *end=0;
        text_at(108,104,number,0xffff);
    } else text_at(108,104,"-",0xffff);
    resolution_hud(104);
    text_at(122,132,"MOVING SOLID FILL AND IMAGE COPY",0xffff);
    text_at(134,448,"KEY0 CPU/HW KEY1 NEXT KEY3 BACK",0xffff);
    basic_text_fast=0;
    publish_pixels();
}
static uint32_t fps[2],render_us[2],samples[2];
static void hud(uint32_t hw,uint32_t pose,uint32_t mode) {
    if(mode==BASIC_MODE) { basic_hud(hw); return; }
    for (uint32_t n=0;n<2;++n) {
        uint32_t x=12+n*320;
        uint16_t color=n==hw ? 0xffff : 0x8410;
        char number[11];
        text_at(x,8,n ? "HW FPS" : "CPU FPS",color);
        decimal(number,fps[n]); text_at(x+100,8,samples[n] ? number : "-",color);
        text_at(x,32,"US",color);
        decimal(number,render_us[n]); text_at(x+36,32,samples[n] ? number : "-",color);
    }
    if(mode==ADVANCED_MODE) {
        text_at(12,56,key_enabled ? "KEY ON" : "KEY OFF",0xffff);
        char number[11];
        decimal(number,pose+1u);
        text_at(164,56,"FRAME",0xffff);
        text_at(236,56,number,0xffff);
        char label[20];
        char *end=append_text(label,"TRANSPARENCY ");
        end=decimal(end,transparency.percent);
        *end++='%'; *end=0;
        text_at(12,80,label,0xffff);
        text_at(98,448,"KEY1 KEY  KEY2 +2 HOLD  KEY3 BACK",0xffff);
    }
    resolution_hud(56);
    publish_pixels();
}
int main(void) {
    mmio_write(SYSTEM_UART_0_IO_CTRL+8, SYSTEM_CLINT_HZ/(115200u*8u)-1u);
    mmio_write(SYSTEM_UART_0_IO_CTRL+12, 7u); // 8 data bits, no parity, one stop bit
    puts_uart("Ti60 ALPHA KEY2 20261002\r\n");
    if (mmio_read(GFX_BASE+GFX_ID)!=0x32444631u) fail("FAIL ID");
    if(!asset_valid()) fail("FAIL ASSET");
    if(mmio_read(ASSET_BASE+8u)>0x000f0000u) fail("FAIL ASSET OVERLAP");
    init_basic_sprite();
    uint32_t hw=0,pose=0,pose_phase=0,phase_start=cycle_now(),previous=phase_start;
    uint32_t pose_previous=phase_start;
    uint32_t motion_previous=phase_start;
    uint32_t key_last=mmio_read(SYSTEM_GPIO_0_IO_CTRL)&15u;
    uint32_t mode=MENU_MODE,selection=0,menu_dirty=1;
    uint32_t elapsed=0,render=0,count=0;
    for (;;) {
        uint32_t key_now=mmio_read(SYSTEM_GPIO_0_IO_CTRL)&15u;
        uint32_t pressed=key_now^key_last;
        key_last=key_now;
        if(mode==MENU_MODE) {
            if(pressed&1u) { selection=0; menu_dirty=1; }
            if(pressed&2u) { selection=1; menu_dirty=1; }
            if(pressed&4u) {
                mode=selection ? ADVANCED_MODE : BASIC_MODE;
                hw=0; pose=0; pose_phase=0;
                count=0; elapsed=0; render=0;
                fps[0]=fps[1]=render_us[0]=render_us[1]=samples[0]=samples[1]=0;
                phase_start=cycle_now(); previous=phase_start;
                pose_previous=phase_start;
                if(mode==ADVANCED_MODE)
                    alpha_control_enter(&transparency,mmio_read(GFX_BASE+GFX_KEY2_DOWN)&1u);
                if(mode==BASIC_MODE) {
                    // User entry timing varies the pseudo-random sequence.
                    basic_layout.random_state=phase_start;
                    basic_layout.level=0;
                    basic_new_layout(&basic_layout);
                    reset_basic_metrics();
                    motion_previous=cycle_now();
                }
                puts_uart(mode==BASIC_MODE ? "BASIC DEMO\r\n" : "ADVANCED DEMO\r\n");
                continue;
            }
            if(menu_dirty) {
                draw_menu(selection);
                if(present_frame()) fail("FAIL menu present");
                mmio_write(GFX_BASE+GFX_DISPLAY,1);
                menu_dirty=0;
            }
            continue;
        }
        if(pressed&8u) {
            if(mode==BASIC_MODE) basic_log_flush();
            selection=mode==ADVANCED_MODE ? 1u : 0u;
            mode=MENU_MODE; menu_dirty=1;
            continue;
        }
        if(mode==ADVANCED_MODE && (pressed&2u)) key_enabled^=1u;
        if(mode==ADVANCED_MODE && alpha_control_poll(&transparency,pressed&4u,
                mmio_read(GFX_BASE+GFX_KEY2_DOWN)&1u,cycle_now())) {
            // Old measurements belong to a different transparency workload.
            fps[0]=fps[1]=render_us[0]=render_us[1]=samples[0]=samples[1]=0;
            count=0; elapsed=0; render=0; previous=cycle_now();
        }
        if(mode==BASIC_MODE) {
            uint32_t level=basic_step_level(basic_layout.level,pressed);
            if(level!=basic_layout.level) {
                basic_layout.level=level;
                basic_new_layout(&basic_layout);
                reset_basic_metrics();
                count=0; elapsed=0; render=0;
                phase_start=cycle_now(); previous=phase_start;
                motion_previous=phase_start;
            }
        }
        uint32_t next=hw;
        uint32_t rx=mmio_read(SYSTEM_UART_0_IO_CTRL);
        if(rx&0x10000u) {
            if((rx&255u)=='h') next=1;
            if((rx&255u)=='c') next=0;
            if((rx&255u)=='m') {pose=38;pose_phase=0;}
            if((rx&255u)=='z') {pose=76;pose_phase=0;}
            if((rx&255u)=='0') {pose=0;pose_phase=0;}
        } else if (mode==ADVANCED_MODE && (uint32_t)(cycle_now()-phase_start)>=400000000u) {
            next=hw^1u;
        }
        if(mode==BASIC_MODE && (pressed&1u)) next=basic_step_renderer(hw,pressed);
        if(next!=hw) {
            // Renderer changes retain every trajectory and the motion clock.
            hw=next; count=0; elapsed=0; render=0;
            phase_start=cycle_now(); previous=phase_start;
        }
        uint32_t motion_now=cycle_now();
        uint32_t motion_ticks=motion_now-motion_previous;
        if(mode==BASIC_MODE) basic_advance(&basic_layout,motion_ticks);
        motion_previous=motion_now;
        uint32_t start=cycle_now(); // Scene time excludes movement bookkeeping.
        uint32_t x=120u;
        if(mode==ADVANCED_MODE) {
            pose_phase+=start-pose_previous;
            pose_previous=start;
            while(pose_phase>=POSE_TICKS) {
                pose_phase-=POSE_TICKS;
                pose=(pose+1u)%77u;
            }
            x+=(pose*400u)/77u+(pose_phase*400u)/(77u*POSE_TICKS);
        }
        if(mode==BASIC_MODE) basic_scene(hw,motion_ticks);
        else advanced_scene(pose,x,hw);
        uint32_t frame_render=cycle_now()-start;
        render+=frame_render;
        hud(hw,pose,mode);
        if(present_frame()) fail("FAIL present");
        uint32_t now=cycle_now();
        uint32_t frame_elapsed=now-previous;
        elapsed+=frame_elapsed; previous=now;
        mmio_write(GFX_BASE+GFX_DISPLAY,1);
        if(mode==BASIC_MODE) {
            if(basic_metrics_record(&basic_metrics[hw],frame_elapsed,frame_render,
                                    basic_layout.count*2u,SYSTEM_CLINT_HZ)) {
                basic_log_queue(&basic_metrics[hw],hw,basic_layout.count*2u);
            }
            basic_log_pump();
            continue;
        }
        if(++count==4) {
            fps[hw]=400000000u/elapsed; render_us[hw]=render/400u; samples[hw]=1;
            char number[11];
            puts_uart(hw ? "HW FPS " : "CPU FPS "); decimal(number,fps[hw]); puts_uart(number);
            puts_uart(" US "); decimal(number,render_us[hw]); puts_uart(number); puts_uart("\r\n");
            count=0; elapsed=0; render=0;
        }
    }
}
