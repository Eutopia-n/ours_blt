#ifndef FRAME_METRICS_H
#define FRAME_METRICS_H
#include <stdint.h>
#include "soc.h"

#define FRAME_60_CYCLES ((SYSTEM_CLINT_HZ+30u)/60u)
#define FRAME_60_SAMPLES 30u
// 30 * 150 MHz exceeds uint32_t. Convert the elapsed interval to microseconds
// first, avoiding 64-bit runtime division in this freestanding RV32 firmware.
static inline uint32_t frame_measured_fps(uint32_t samples,uint32_t cycles) {
    uint32_t us=cycles/(SYSTEM_CLINT_HZ/1000000u);
    return us ? (samples*1000000u+us/2u)/us : 0;
}
typedef struct {
    uint32_t frames,peak,failed,maximum;
} FrameMax60;

// Keep the record, but discard samples across pauses, upgrades and restarts.
static inline void frame_max60_clear_window(FrameMax60 *m) {
    m->frames=m->peak=m->failed=0;
}
// Only a complete 30-frame window with no late render or missed refresh can
// certify its highest actually drawn Sprite count. A failed window adds nothing.
static inline void frame_max60_sample(FrameMax60 *m,uint32_t cycles,
                                      uint32_t refreshes,uint32_t sprites) {
    if(cycles>FRAME_60_CYCLES || refreshes!=1u) m->failed=1;
    if(sprites>m->peak) m->peak=sprites;
    if(++m->frames==FRAME_60_SAMPLES) {
        if(!m->failed && m->peak>m->maximum) m->maximum=m->peak;
        frame_max60_clear_window(m);
    }
}
#endif
