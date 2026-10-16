#ifndef RENDER_H
#define RENDER_H
#include <stdint.h>
#include "soc.h"
#define GFX_BASE IO_APB_SLAVE_0_INPUT
#define GFX_ID       0x00u
#define GFX_STATUS   0x04u
#define GFX_COMMAND  0x08u
#define GFX_DST      0x0cu
#define GFX_WIDTH    0x10u
#define GFX_HEIGHT   0x14u
#define GFX_STRIDE   0x18u
#define GFX_COLOR    0x1cu
#define GFX_DISPLAY  0x20u
#define GFX_CYCLES   0x24u
#define GFX_FB_BASE  0x28u
#define GFX_PITCH    0x2cu
#define GFX_OPERATION 0x30u
#define GFX_SRC      0x34u
#define GFX_DRAW_PAGE 0x38u
#define GFX_SWAP_PAGE 0x3cu
#define GFX_SWAP      0x40u
#define GFX_VIDEO_SIZE   0x44u
#define GFX_VIDEO_STATUS 0x48u
#define GFX_VIDEO_VALID  1u
#define GFX_BUSY       1u
#define GFX_DONE       2u
#define GFX_ERROR      4u
#define GFX_DDR_READY  8u
#define GFX_UNDERFLOW 16u
#define GFX_READ_ERR  32u
#define GFX_ACTIVE_PAGE 64u
#define GFX_SWAP_PENDING 128u
#define FRAMEBUFFER 0x01000000u
#define FRAMEBUFFER_BYTES 614400u
#define FRAMEBUFFER_B (FRAMEBUFFER + FRAMEBUFFER_BYTES)
#define FRAME_STRIDE 1280u
static inline uint32_t mmio_read(uint32_t address) {
    uint32_t value = *(volatile uint32_t *)(uintptr_t)address;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    return value;
}
static inline void mmio_write(uint32_t address, uint32_t value) {
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    *(volatile uint32_t *)(uintptr_t)address = value;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}
/* Returns 0 only after the last AXI B response. No CPU pixel writes. */
int fill_rect(uint32_t x, uint32_t y, uint32_t width, uint32_t height, uint16_t color);
/* Copy within the fixed RGB565 framebuffer. Same 1280-byte stride on both
 * sides; overlapping rectangles are supported using a complete row buffer.
 * Returns 0 after the final AXI B response. CPU writes to source pixels must
 * reach DDR before this call. This core uses write-through; publish_pixels()
 * drains stores via invalidation/readback. HW-mode sources use hardware. */
int copy_rect(uint32_t src_x, uint32_t src_y, uint32_t dst_x, uint32_t dst_y,
              uint32_t width, uint32_t height);
/* Wait for frame-boundary acknowledgement, including same-page requests.
 * On success the retired front page becomes the new draw target.
 * A timeout does not cancel the request: stop rendering and diagnose/reset. */
int present_frame(void);
#endif
