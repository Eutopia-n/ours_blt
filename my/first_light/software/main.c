#include "render.h"

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
    if (mmio_read(GFX_BASE+GFX_STATUS) & (GFX_BUSY|GFX_SWAP_PENDING)) return -2;
    select_draw_page();
    mmio_write(GFX_BASE+GFX_OPERATION, 1);
    mmio_write(GFX_BASE+GFX_SRC, draw_buffer+src_y*FRAME_STRIDE+src_x*2);
    mmio_write(GFX_BASE+GFX_DST, draw_buffer+dst_y*FRAME_STRIDE+dst_x*2);
    mmio_write(GFX_BASE+GFX_WIDTH, width);
    mmio_write(GFX_BASE+GFX_HEIGHT, height);
    mmio_write(GFX_BASE+GFX_STRIDE, FRAME_STRIDE);
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
        for (uint32_t col=0; col<w; ++col) p[col]=c;
    }
}
static void cpu_copy(uint32_t x, uint32_t y) {
    for (uint32_t row=0; row<32; ++row) {
        const volatile uint16_t *s=(const volatile uint16_t *)(uintptr_t)(draw_buffer+(64+row)*1280);
        volatile uint16_t *d=(volatile uint16_t *)(uintptr_t)(draw_buffer+(y+row)*1280+x*2);
        for (uint32_t col=0; col<32; ++col) d[col]=s[col];
    }
}
static uint32_t bounce(uint32_t phase, uint32_t limit) {
    phase %= limit*2;
    return phase>limit ? limit*2-phase : phase;
}
static void scene(uint32_t frame, uint32_t hw) {
    if (!hw) {
        // Sapphire BSP 0x500F invalidates stale reads left by hardware writes.
        __asm__ volatile (".word 0x500f" ::: "memory");
    }
    if (hw) { if (fill_rect(0,0,640,480,0x1082)) fail("FAIL fill"); }
    else cpu_fill(0,0,640,480,0x1082);
    static const uint16_t colors[3]={0x07ff,0xf81f,0xffe0};
    for (uint32_t n=0;n<3;++n) {
        uint32_t height=n==2 ? 12 : 10;
        if (hw) { if (fill_rect(0,64+n*10,32,height,colors[n])) fail("FAIL fill"); }
        else cpu_fill(0,64+n*10,32,height,colors[n]);
    }
    for (uint32_t n=0;n<32;++n) {
        uint32_t x=48+bounce(n*74+frame*4,552), y=112+bounce(n*46+frame*2,320);
        if (hw) { if (copy_rect(0,64,x,y,32,32)) fail("FAIL copy"); }
        else cpu_copy(x,y);
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
static void text_at(uint32_t x,uint32_t y,const char *s,uint16_t color) {
    while (*s) {
        char c=*s++;
        uint16_t bits=c=='-' ? 0x01c0 : c>='0'&&c<='9' ? font[c-'0'] :
                      c>='A'&&c<='Z' ? font[c-'A'+10] : 0;
        for (uint32_t row=0;row<5;++row) for (uint32_t col=0;col<3;++col)
            if (bits & (1u<<(14-row*3-col))) cpu_fill(x+col*3,y+row*3,3,3,color);
        x+=12;
    }
}
static char *decimal(char *out,uint32_t value) {
    char digits[10]; uint32_t n=0;
    do { digits[n++]=(char)('0'+value%10); value/=10; } while (value);
    while(n) *out++=digits[--n];
    *out=0; return out;
}
static void resolution_hud(void) {
    uint32_t status=mmio_read(GFX_BASE+GFX_VIDEO_STATUS);
    if (!(status&GFX_VIDEO_VALID)) {
        text_at(532,56,"RES WAIT",0xffff);
        return;
    }
    uint32_t size=mmio_read(GFX_BASE+GFX_VIDEO_SIZE);
    uint32_t width=size&0xffffu, height=size>>16;
    char label[16]="RES ";
    char *end=decimal(label+4,width);
    *end++='X';
    end=decimal(end,height);
    uint32_t glyphs=(uint32_t)(end-label);
    text_at(640-12-glyphs*12,56,label,0xffff);
}
static uint32_t fps[2],render_us[2],samples[2];
static void hud(uint32_t hw) {
    for (uint32_t n=0;n<2;++n) {
        uint32_t x=12+n*320;
        uint16_t color=n==hw ? 0xffff : 0x8410;
        char number[11];
        text_at(x,8,n ? "HW FPS" : "CPU FPS",color);
        decimal(number,fps[n]); text_at(x+100,8,samples[n] ? number : "-",color);
        text_at(x,32,"US",color);
        decimal(number,render_us[n]); text_at(x+36,32,samples[n] ? number : "-",color);
    }
    resolution_hud();
    publish_pixels();
}
int main(void) {
    mmio_write(SYSTEM_UART_0_IO_CTRL+8, SYSTEM_CLINT_HZ/(115200u*8u)-1u);
    mmio_write(SYSTEM_UART_0_IO_CTRL+12, 7u); // 8 data bits, no parity, one stop bit
    puts_uart("Ti60 MOTION 32 CPU/HW\r\n");
    if (mmio_read(GFX_BASE+GFX_ID)!=0x32444631u) fail("FAIL ID");
    publish_pixels();
    uint32_t hw=0,frame=0,phase_start=cycle_now(),previous=phase_start;
    uint32_t elapsed=0,render=0,count=0;
    for (;;) {
        uint32_t next=hw;
        uint32_t rx=mmio_read(SYSTEM_UART_0_IO_CTRL);
        if(rx&0x10000u) {
            if((rx&255u)=='h') next=1;
            if((rx&255u)=='c') next=0;
        } else if ((uint32_t)(cycle_now()-phase_start)>=400000000u) next=hw^1u;
        if(next!=hw) {
            hw=next; frame=0; count=0; elapsed=0; render=0;
            phase_start=cycle_now(); previous=phase_start;
        }
        uint32_t start=cycle_now();
        scene(frame++,hw);
        render+=cycle_now()-start;
        hud(hw);
        if(present_frame()) fail("FAIL present");
        uint32_t now=cycle_now();
        elapsed+=now-previous; previous=now;
        mmio_write(GFX_BASE+GFX_DISPLAY,1);
        if(++count==4) {
            fps[hw]=400000000u/elapsed; render_us[hw]=render/400u; samples[hw]=1;
            char number[11];
            puts_uart(hw ? "HW FPS " : "CPU FPS "); decimal(number,fps[hw]); puts_uart(number);
            puts_uart(" US "); decimal(number,render_us[hw]); puts_uart(number); puts_uart("\r\n");
            count=0; elapsed=0; render=0;
        }
    }
}
