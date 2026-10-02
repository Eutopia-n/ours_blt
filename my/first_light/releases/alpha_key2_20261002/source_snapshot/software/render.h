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
#define GFX_SRC_STRIDE   0x4cu
#define GFX_ALPHA        0x50u
#define GFX_ALPHA_KEY    0x54u
#define GFX_KEY2_DOWN    0x58u
#define GFX_OP_FILL       0u
#define GFX_OP_COPY       1u
#define GFX_OP_KEYED_COPY 2u
#define GFX_OP_ALPHA_COPY 3u
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
/* Dedicated DDR resource pool; disjoint from both framebuffer pages.
 * The configured 28-bit DDR controller covers 256 MiB; avoid high aliases. */
#define ASSET_BASE  0x01200000u
#define ASSET_BYTES 0x00100000u
#define SPRITE_STRIDE 64u
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
 * drains stores via invalidation/readback. */
int copy_rect(uint32_t src_x, uint32_t src_y, uint32_t dst_x, uint32_t dst_y,
              uint32_t width, uint32_t height);
/* Copy RGB565 from the DDR resource pool with an independent source pitch.
 * Source pitch: even bytes, width*2 .. 65534. Same-page sources are also
 * accepted at FRAME_STRIDE, preserving copy_rect overlap behaviour.
 * Destination coordinates always refer to the selected back/draw page. */
int copy_image(uint32_t source, uint32_t source_stride, uint32_t dst_x,
               uint32_t dst_y, uint32_t width, uint32_t height);
/* Copy RGB565 while preserving each destination pixel whose source pixel
 * equals key. Source and destination limits are the same as copy_image(). */
int copy_image_keyed(uint32_t source, uint32_t source_stride, uint32_t dst_x,
                     uint32_t dst_y, uint32_t width, uint32_t height,
                     uint16_t key);
int copy_image_alpha(uint32_t source, uint32_t source_stride, uint32_t dst_x,
                     uint32_t dst_y, uint32_t width, uint32_t height,
                     uint32_t opacity, uint32_t keyed, uint16_t key);
/* Wait for frame-boundary acknowledgement, including same-page requests.
 * On success the retired front page becomes the new draw target.
 * A timeout does not cancel the request: stop rendering and diagnose/reset. */
int present_frame(void);
#endif
