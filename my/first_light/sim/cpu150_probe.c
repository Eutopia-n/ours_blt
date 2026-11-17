/* Simulation-only firmware: real CPU, OCR stack, CDC DDR and renderer. */
#include "render.h"
#include "frame_metrics.h"
_Static_assert(SYSTEM_CLINT_HZ==150000000u,"120 MHz test firmware required");
_Static_assert(FRAME_60_CYCLES==2500000u,"60 Hz logic budget changed");
static void putc_uart(char c) {
    while(((mmio_read(SYSTEM_UART_0_IO_CTRL+4)>>16)&255u)==0) {}
    mmio_write(SYSTEM_UART_0_IO_CTRL,(uint32_t)c);
}
static void say(const char *s) { while(*s) putc_uart(*s++); }
static void fail(void) { say("CPU150 PROBE FAIL\r\n"); for(;;) {} }
void fatal_trap(uint32_t cause,uint32_t pc) { (void)cause;(void)pc;fail(); }
static uint32_t now(void) { return mmio_read(SYSTEM_CLINT_CTRL+0xbff8u); }
static void drain(void) {
    __asm__ volatile("fence iorw, iorw\n.word 0x500f" ::: "memory");
    (void)mmio_read(ASSET_BASE);
}
static void reg_write(uint32_t a,uint32_t v) { mmio_write(GFX_BASE+a,v); }
static void wait_draw(uint32_t expected) {
    uint32_t start=now(),s;
    do { s=mmio_read(GFX_BASE+GFX_STATUS); if(now()-start>SYSTEM_CLINT_HZ/5u) fail(); }
    while(!(s&GFX_DONE));
    if(!!(s&GFX_ERROR)!=!!expected) fail();
}
int main(void) {
    mmio_write(SYSTEM_UART_0_IO_CTRL+8,SYSTEM_CLINT_HZ/(115200u*8u)-1u);
    mmio_write(SYSTEM_UART_0_IO_CTRL+12,7u);
    if(mmio_read(GFX_BASE)!=0x32444631u) fail();
    volatile uint32_t *p=(volatile uint32_t *)(uintptr_t)(ASSET_BASE+0xe0000u);
    volatile uint32_t stack[32];
    for(uint32_t i=0;i<32u;i++) stack[i]=0x89abcdefu^i;
    for(uint32_t pass=0;pass<3;pass++) {
        for(uint32_t i=0;i<256;i++) p[i]=0x9e3779b9u*i^(0x13579bdfu+pass);
        drain();
        for(uint32_t i=0;i<256;i++) if(p[i]!=(0x9e3779b9u*i^(0x13579bdfu+pass))) fail();
    }
    p[0]=0x12345678u;
    ((volatile uint8_t *)p)[1]=0xabu;
    ((volatile uint16_t *)p)[1]=0xcdefu;
    drain(); if(p[0]!=0xcdefab78u) fail();
    for(uint32_t i=0;i<32;i++) if(stack[i]!=(0x89abcdefu^i)) fail();
    // Measured by TB in wall time; the counter must take 1 ms at 120 MHz.
    p[256]=0x11111111u; drain();
    uint32_t start=now(); while(now()-start<SYSTEM_CLINT_HZ/1000u) {}
    p[256]=0x22222222u; drain();
    reg_write(GFX_DRAW_PAGE,0); reg_write(GFX_OPERATION,0);
    reg_write(GFX_DST,FRAMEBUFFER); reg_write(GFX_WIDTH,640);
    reg_write(GFX_HEIGHT,480); reg_write(GFX_STRIDE,1280); reg_write(GFX_COLOR,0x001f);
    reg_write(GFX_COMMAND,1); wait_draw(0);
    // An empty draw must finish with an error, without writing DDR.
    reg_write(GFX_WIDTH,0); reg_write(GFX_COMMAND,1); wait_draw(1);
    volatile uint16_t *sprite=(volatile uint16_t *)(uintptr_t)ASSET_BASE;
    for(uint32_t i=0;i<16;i++) sprite[i]=(i&1u)?0xf800u:0;
    drain();
    reg_write(GFX_OPERATION,2); reg_write(GFX_SRC,ASSET_BASE); reg_write(GFX_SRC_STRIDE,8);
    reg_write(GFX_DST,FRAMEBUFFER+10u*1280u+20u); reg_write(GFX_WIDTH,4); reg_write(GFX_HEIGHT,4);
    reg_write(GFX_BLEND_CTRL,3); reg_write(GFX_ALPHA,128); reg_write(GFX_COLOR_KEY,0);
    reg_write(GFX_COMMAND,1);
    // CPU and graphics contend through the two separate vendor CDC paths.
    for(uint32_t i=0;i<256;i++) { p[i]=i^0x76543210u; if(p[i]!=(i^0x76543210u)) fail(); }
    wait_draw(0);
    reg_write(GFX_DISPLAY,1);
    start=now();
    while(mmio_read(GFX_BASE+GFX_FRAME_COUNT)<3u) if(now()-start>SYSTEM_CLINT_HZ/4u) fail();
    if(mmio_read(GFX_BASE+GFX_VIDEO_SIZE)!=((480u<<16)|640u)) fail();
    if(mmio_read(GFX_BASE+GFX_STATUS)&(GFX_UNDERFLOW|GFX_READ_ERR)) fail();
    say("CPU150 CROSS-CLOCK PASS\r\n");
    for(;;) {}
}
