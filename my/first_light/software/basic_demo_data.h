#ifndef BASIC_DEMO_DATA_H
#define BASIC_DEMO_DATA_H
#include <stdint.h>
#include "render.h"

#define BASIC_IMAGE_W 256u
#define BASIC_IMAGE_H 192u
#define BASIC_IMAGE_STRIDE (BASIC_IMAGE_W*2u)
#define BASIC_IMAGE_BYTES (BASIC_IMAGE_STRIDE*BASIC_IMAGE_H)
// Keep the existing dedicated DDR address; the game wall cache is now unused.
#define BASIC_IMAGE_BASE (ASSET_BASE+0xC0000u)
#define BASIC_IMAGE_X 32u
#define BASIC_COPY_X 352u
#define BASIC_IMAGE_Y 176u
#define BASIC_VIEW_Y 176u
#define BASIC_VIEW_H 224u
#define BASIC_SAMPLE_FRAMES 30u
// Both comparison modes draw at the same point in the active raster. The
// existing acknowledgement is at v=524; 8 ms later is around visible row 251.
// Only the deliberately unsafe single-buffer mode writes the displayed page.
#define BASIC_BUFFER_PHASE_CYCLES (8u*(SYSTEM_CLINT_HZ/1000u))
#if BASIC_IMAGE_BASE+2u*BASIC_IMAGE_BYTES > ASSET_BASE+ASSET_BYTES
#error Basic images exceed the existing DDR resource pool
#endif
typedef struct {
    uint32_t load,image,color,view,mode,speed,paused,grid;
} BasicConfig;
typedef struct { uint32_t x,y,w,h; uint16_t color; } BasicRect;
typedef struct {
    uint32_t fps,op_cycles,frame_us,reads,writes,rwait,wwait,valid;
} BasicSample;
static const uint16_t basic_fill_counts[4]={8u,32u,64u,128u};
static const uint8_t basic_copy_counts[4]={1u,2u,4u,8u};
static inline uint32_t basic_source(uint32_t image) {
    return BASIC_IMAGE_BASE+image*BASIC_IMAGE_BYTES;
}
static inline uint32_t basic_bounce(uint32_t phase,uint32_t limit) {
    phase%=limit*2u;return phase>limit ? limit*2u-phase : phase;
}
static inline BasicRect basic_rectangle(uint32_t frame,uint32_t n,uint32_t color) {
    uint32_t seed=(n+1u)*0x9e3779b9u;
    seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;
    static const uint16_t colors[6]={0x07ff,0xffe0,0xf81f,0x07e0,0xf800,0x001f};
    BasicRect r={16u+2u*basic_bounce((seed&65535u)+frame*(1u+((seed>>16)&3u)),288u),
        BASIC_VIEW_Y+basic_bounce((seed>>16)+frame*(1u+((seed>>24)&3u)),200u),
        32u,24u,colors[(n+color)%6u]};
    return r;
}
// Reserved/multiple keys do not accidentally change a configuration.
// S manually toggles CPU/FPGA; Enter toggles the visual/bus detail view.
static inline uint32_t basic_control(BasicConfig *c,uint32_t demo,uint32_t keys) {
    if(demo==2u) {
        if(keys==1u)c->speed=(c->speed+1u)%3u;
        else if(keys==2u)c->mode^=1u;
        else if(keys==8u)c->grid^=1u;
        else if(keys==16u)c->paused^=1u;
        else return 0;
    } else {
        if(keys==1u)c->load=(c->load+1u)%4u;
        else if(keys==8u) { if(demo==1u)c->image^=1u;else c->color=(c->color+1u)%6u; }
        else if(keys==2u)c->mode^=1u;
        else if(keys==16u)c->view^=1u;
        else return 0;
    }
    return 1;
}
// floor(100*a/b), bounded for the display, without RV32 64-bit division.
static inline uint32_t basic_ratio100(uint32_t a,uint32_t b) {
    if(!b)return 0;
    uint32_t whole=a/b,r=a%b,rem=0,fraction=0;
    if(whole>=10000u)return 999999u;
    for(uint32_t n=0;n<100u;++n) {
        if(rem>=b-r) {rem-=b-r;++fraction;} else rem+=r;
    }
    return whole*100u+fraction;
}
#endif
