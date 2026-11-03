#ifndef BASIC_DEMO_DATA_H
#define BASIC_DEMO_DATA_H
#include <stdint.h>
#include "render.h"

#define BASIC_IMAGE_W 256u
#define BASIC_IMAGE_H 192u
#define BASIC_IMAGE_STRIDE (BASIC_IMAGE_W*2u)
#define BASIC_IMAGE_BYTES (BASIC_IMAGE_STRIDE*BASIC_IMAGE_H)
// Dedicated DDR space, beyond the unchanged game's wall cache.
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
// Procedural RGB565 test pictures: landscape/sun and a lit city at night.
// Only uploaded on first entry to the Copy page, outside every measurement.
static inline uint16_t basic_pixel(uint32_t image,uint32_t x,uint32_t y) {
    uint32_t r,g,b;
    if(!image) {
        r=3u+y/20u;g=24u+y/8u;b=31u-y/14u;
        int32_t dx=(int32_t)x-198,dy=(int32_t)y-42;
        if(dx*dx+dy*dy<19*19) {r=31;g=56;b=8;}
        uint32_t ridge=96u+((x<128u ? x : 255u-x)/3u);
        if(y>ridge) {r=4u;g=30u+(x/16u)%12u;b=9u;}
        if(y>151u) {r=7u+(x/16u)%5u;g=38u+(y/8u)%12u;b=12u;}
        if(y>160u && x>112u-(y-160u)/2u && x<144u+(y-160u)/2u)
            {r=22u;g=43u;b=18u;}
    } else {
        r=2u;g=5u+y/12u;b=12u+y/12u;
        uint32_t building=x/32u,height=45u+(building*23u)%90u;
        if(x%32u<27u && y>182u-height) {
            r=5u;g=9u;b=13u;
            if(x%8u>2u && y%12u>4u) {r=31u;g=43u;b=7u;}
        }
        if(y>182u) {r=10u;g=12u;b=18u;}
    }
    if(x<3u || x>=253u || y<3u || y>=189u)return image ? 0xf81fu : 0x07ffu;
    if(x>=10u && x<34u && y>=10u && y<46u) {
        uint32_t px=x-10u,py=y-10u;
        uint32_t mark=!image ? (px>=10u && px<15u) :
            (py<5u || (py>=16u && py<21u) || py>=31u || (py<18u ? px>=19u : px<5u));
        return mark ? 0xffffu : 0x0843u;
    }
    return (uint16_t)((r<<11)|(g<<5)|b);
}
#endif
