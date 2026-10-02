#ifndef BASIC_LAYOUT_H
#define BASIC_LAYOUT_H
#include <stdint.h>

#define BASIC_BLOCKS 128u
#define BASIC_LEVELS 3u
#define BASIC_SIDE 32u
#define BASIC_BACKGROUND 0x1082u
#define BASIC_X_MIN 12u
#define BASIC_X_MAX 596u
#define BASIC_Y_MIN 160u
#define BASIC_Y_MAX 392u
#define BASIC_TICK_HZ 100000000u
#define BASIC_SPEED_MIN 24u
#define BASIC_SPEED_MAX 96u

typedef struct {
    uint32_t x, y;
    uint16_t color;
} basic_block_t;

typedef struct {
    // Unfolded Q8 coordinates: the second half of each period moves backward.
    uint32_t phase_x, phase_y;
    uint16_t speed_x, speed_y; // Absolute component speeds, pixels/second.
} basic_motion_t;

typedef struct {
    uint32_t random_state, level, count, tick_remainder;
    basic_block_t fill[BASIC_BLOCKS], copy[BASIC_BLOCKS];
    basic_motion_t fill_motion[BASIC_BLOCKS], copy_motion[BASIC_BLOCKS];
} basic_layout_t;

static inline uint32_t basic_total(uint32_t level) {
    static const uint32_t totals[BASIC_LEVELS]={32u,128u,256u};
    return totals[level<BASIC_LEVELS ? level : BASIC_LEVELS-1u];
}

static inline uint32_t basic_step_level(uint32_t level,uint32_t pressed) {
    if(pressed&2u) return level+1u<BASIC_LEVELS ? level+1u : 0u;
    return level; // KEY1 cycles the workload; KEY0 belongs to renderer selection.
}

static inline uint32_t basic_step_renderer(uint32_t hw,uint32_t pressed) {
    return hw^((pressed&1u) ? 1u : 0u);
}

static inline uint32_t basic_random(basic_layout_t *layout) {
    uint32_t x=layout->random_state;
    if(!x) x=0x6d2b79f5u;
    x^=x<<13; x^=x>>17; x^=x<<5;
    layout->random_state=x;
    return x;
}

static inline uint32_t basic_position(uint32_t phase,uint32_t minimum,uint32_t maximum) {
    uint32_t extent=(maximum-minimum)*256u;
    return minimum+(phase<=extent ? phase : 2u*extent-phase)/256u;
}

static inline void basic_init_block(basic_layout_t *layout,basic_block_t *block,
                                    basic_motion_t *motion) {
    block->x=BASIC_X_MIN+basic_random(layout)%(BASIC_X_MAX-BASIC_X_MIN+1u);
    block->y=BASIC_Y_MIN+basic_random(layout)%(BASIC_Y_MAX-BASIC_Y_MIN+1u);
    motion->phase_x=(block->x-BASIC_X_MIN)*256u;
    motion->phase_y=(block->y-BASIC_Y_MIN)*256u;
    if(basic_random(layout)&1u)
        motion->phase_x=(2u*(BASIC_X_MAX-BASIC_X_MIN)*256u-motion->phase_x)%
                        (2u*(BASIC_X_MAX-BASIC_X_MIN)*256u);
    if(basic_random(layout)&1u)
        motion->phase_y=(2u*(BASIC_Y_MAX-BASIC_Y_MIN)*256u-motion->phase_y)%
                        (2u*(BASIC_Y_MAX-BASIC_Y_MIN)*256u);
    motion->speed_x=(uint16_t)(BASIC_SPEED_MIN+basic_random(layout)%
                             (BASIC_SPEED_MAX-BASIC_SPEED_MIN+1u));
    motion->speed_y=(uint16_t)(BASIC_SPEED_MIN+basic_random(layout)%
                             (BASIC_SPEED_MAX-BASIC_SPEED_MIN+1u));
}

static inline void basic_new_layout(basic_layout_t *layout) {
    static const uint16_t colors[]={
        0xf800u,0x07e0u,0x001fu,0xffe0u,
        0x07ffu,0xf81fu,0xfd20u,0xffffu
    };
    layout->count=basic_total(layout->level)/2u;
    layout->tick_remainder=0;
    // Both operations share the full play area. Overlap is allowed at every
    // load and every operation is executed, including overwritten blocks.
    for(uint32_t n=0;n<layout->count;++n) {
        basic_init_block(layout,&layout->fill[n],&layout->fill_motion[n]);
        layout->fill[n].color=colors[basic_random(layout)%8u];
        basic_init_block(layout,&layout->copy[n],&layout->copy_motion[n]);
        layout->copy[n].color=0;
    }
}

static inline void basic_advance(basic_layout_t *layout,uint32_t ticks) {
    // Quantize elapsed time once to 1/256 second, retaining the remainder.
    // Splitting the same elapsed time into CPU/HW frame intervals produces
    // identical positions. Each update handles any number of wall bounces.
    uint64_t scaled=(uint64_t)ticks*256u+layout->tick_remainder;
    uint32_t steps=(uint32_t)(scaled/BASIC_TICK_HZ);
    layout->tick_remainder=(uint32_t)(scaled%BASIC_TICK_HZ);
    if(!steps) return;
    for(uint32_t n=0;n<layout->count;++n) for(uint32_t kind=0;kind<2u;++kind) {
        basic_block_t *p=kind ? &layout->copy[n] : &layout->fill[n];
        basic_motion_t *m=kind ? &layout->copy_motion[n] : &layout->fill_motion[n];
        uint32_t next_x=m->phase_x+m->speed_x*steps;
        uint32_t next_y=m->phase_y+m->speed_y*steps;
        const uint32_t period_x=2u*(BASIC_X_MAX-BASIC_X_MIN)*256u;
        const uint32_t period_y=2u*(BASIC_Y_MAX-BASIC_Y_MIN)*256u;
        // Normal video-frame intervals rarely wrap a full unfolded period.
        // Keep exact long-pause behaviour while avoiding two DIVU per block.
        m->phase_x=next_x<period_x ? next_x : next_x%period_x;
        m->phase_y=next_y<period_y ? next_y : next_y%period_y;
        p->x=basic_position(m->phase_x,BASIC_X_MIN,BASIC_X_MAX);
        p->y=basic_position(m->phase_y,BASIC_Y_MIN,BASIC_Y_MAX);
    }
}

static inline uint16_t basic_sprite_pixel(uint32_t x,uint32_t y) {
    if(x==0u || y==0u || x==BASIC_SIDE-1u || y==BASIC_SIDE-1u)
        return 0xffffu;
    return ((x/8u)^(y/8u))&1u ? 0x07ffu : 0xf81fu;
}
#endif
