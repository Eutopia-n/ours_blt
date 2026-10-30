#include "render.h"

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
        if ((uint32_t)(cycle_now()-start) > (2u*SYSTEM_CLINT_HZ)) return -4;
    }
}
static void select_draw_page(void) {
    mmio_write(GFX_BASE+GFX_DRAW_PAGE, draw_page());
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
    uint32_t start = cycle_now();
    for (;;) {
        uint32_t status = mmio_read(GFX_BASE+GFX_STATUS);
        if (status & GFX_ERROR) return -3;
        if ((status & (GFX_BUSY|GFX_DONE)) == GFX_DONE) return 0;
        if ((uint32_t)(cycle_now()-start) > SYSTEM_CLINT_HZ) return -4;
    }
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
    mmio_write(GFX_BASE+GFX_SRC_STRIDE, FRAME_STRIDE);
    mmio_write(GFX_BASE+GFX_DST, draw_buffer+dst_y*FRAME_STRIDE+dst_x*2);
    mmio_write(GFX_BASE+GFX_WIDTH, width);
    mmio_write(GFX_BASE+GFX_HEIGHT, height);
    mmio_write(GFX_BASE+GFX_STRIDE, FRAME_STRIDE);
    mmio_write(GFX_BASE+GFX_COMMAND, 1);
    uint32_t start = cycle_now();
    for (;;) {
        uint32_t status = mmio_read(GFX_BASE+GFX_STATUS);
        if (status & GFX_ERROR) return -3;
        if ((status & (GFX_BUSY|GFX_DONE)) == GFX_DONE) return 0;
        if ((uint32_t)(cycle_now()-start) > SYSTEM_CLINT_HZ) return -4;
    }
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
static uint16_t expected_pixel_page(uint32_t x, uint32_t y, uint16_t background) {
    if ((x >= 31 && x < 160 && y >= 301 && y < 398) ||
        (x >= 211 && x < 340 && y >= 321 && y < 418)) {
        uint32_t local_y = x < 160 ? y-301 : y-321;
        return local_y < 32 ? 0x07ff : local_y < 64 ? 0xf81f : 0xffe0;
    }
    if (x >= 64 && x < 256 && y >= 60 && y < 180) return 0xf800;
    if (x >= 301 && x < 428 && y >= 161 && y < 260) return 0x07e0;
    if (x >= 501 && x < 602 && y >= 351 && y < 424) return 0x001f;
    return background;
}
static int verify_page(uint32_t base, uint16_t background) {
    const volatile uint16_t *fb = (const volatile uint16_t *)(uintptr_t)base;
    for (uint32_t y=0; y<480; ++y) for (uint32_t x=0; x<640; ++x)
        if (fb[y*640+x] != expected_pixel_page(x,y,background)) return -1;
    return 0;
}
int main(void) {
    mmio_write(SYSTEM_UART_0_IO_CTRL+8, SYSTEM_CLINT_HZ/(115200u*8u)-1u);
    mmio_write(SYSTEM_UART_0_IO_CTRL+12, 7u); // 8 data bits, no parity, one stop bit
    puts_uart("Ti60: RISC-V -> AXI FILL/COPY -> DDR -> HDMI\r\n");
    if (mmio_read(GFX_BASE+GFX_ID) != 0x32444631u) fail("FAIL register ID");
    if (!(mmio_read(GFX_BASE+GFX_STATUS) & GFX_DDR_READY)) fail("FAIL DDR not ready");
    if (mmio_read(GFX_BASE+GFX_FB_BASE) != FRAMEBUFFER) fail("FAIL framebuffer base");
    mmio_write(GFX_BASE+GFX_DISPLAY, 0);
    draw_buffer = FRAMEBUFFER;
    select_draw_page();
    if (fill_rect(0,0,640,480,0x1082)) fail("FAIL background fill");
    if (fill_rect(64,60,192,120,0xf800)) fail("FAIL red rectangle");
    if (fill_rect(301,161,127,99,0x07e0)) fail("FAIL green rectangle");
    if (fill_rect(501,351,101,73,0x001f)) fail("FAIL blue rectangle");
    // Create an image in DDR using fills, then copy its mixed pixel data.
    // No CPU pixel writes or cache flush of dirty source data are needed.
    if (fill_rect(31,301,129,32,0x07ff) ||
        fill_rect(31,333,129,32,0xf81f) ||
        fill_rect(31,365,129,33,0xffe0)) fail("FAIL source tile");
    if (copy_rect(31,301,211,321,129,97)) fail("FAIL block copy");
    // Sapphire BSP vexriscv.h defines 0x500F as whole-data-cache invalidate.
    // CPU has not written this framebuffer: there are no dirty pixel lines to lose.
    __asm__ volatile ("fence iorw, iorw\n.word 0x500f\nfence iorw, iorw" ::: "memory");
    if (verify_page(FRAMEBUFFER, 0x1082)) fail("FAIL page A DDR pixels");
    if (present_frame()) fail("FAIL page A present");
    mmio_write(GFX_BASE+GFX_DISPLAY, 1);
    // Render a second frame into the non-displayed page. A different
    // background makes the page switch visible on the monitor.
    if (fill_rect(0,0,640,480,0x18c3)) fail("FAIL page B");
    if (fill_rect(64,60,192,120,0xf800)) fail("FAIL page B");
    if (fill_rect(301,161,127,99,0x07e0)) fail("FAIL page B");
    if (fill_rect(501,351,101,73,0x001f)) fail("FAIL page B");
    if (fill_rect(31,301,129,32,0x07ff) ||
        fill_rect(31,333,129,32,0xf81f) ||
        fill_rect(31,365,129,33,0xffe0)) fail("FAIL page B");
    if (copy_rect(31,301,211,321,129,97)) fail("FAIL page B");
    __asm__ volatile ("fence iorw, iorw\n.word 0x500f\nfence iorw, iorw" ::: "memory");
    if (verify_page(FRAMEBUFFER_B, 0x18c3)) fail("FAIL page B DDR pixels");
    if (present_frame()) fail("FAIL page B present");
    puts_uart("PASS DOUBLE BUFFER: page A -> page B at frame boundary\r\n");
    puts_uart("VIDEO status=0x"); hex_uart(mmio_read(GFX_BASE+GFX_STATUS)); puts_uart("\r\n");
    for (;;) {
        if (mmio_read(GFX_BASE+GFX_STATUS) & (GFX_UNDERFLOW|GFX_READ_ERR))
            fail("FAIL video underflow or AXI read error");
    }
}
