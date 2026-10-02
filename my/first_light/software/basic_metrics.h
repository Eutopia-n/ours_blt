#ifndef BASIC_METRICS_H
#define BASIC_METRICS_H
#include <stdint.h>

typedef struct {
    uint64_t elapsed, render;
    uint32_t frames, fps10, render_us, ops_per_second, valid;
} basic_metrics_t;

static inline void basic_metrics_reset(basic_metrics_t *s) {
    s->elapsed=0; s->render=0; s->frames=0;
    s->fps10=0; s->render_us=0; s->ops_per_second=0; s->valid=0;
}

// Call only after presentation completed. Operations exclude the full-screen
// clear and HUD. Elapsed time includes rendering, HUD and waiting for vblank.
// 64-bit intermediates prevent N * frames * 100 MHz overflowing at high load.
static inline uint32_t basic_metrics_record(basic_metrics_t *s,uint32_t ticks,
                                           uint32_t render_ticks,uint32_t operations,
                                           uint32_t clock_hz) {
    if(!ticks || !clock_hz) return 0;
    s->elapsed+=ticks; s->render+=render_ticks; ++s->frames;
    s->fps10=(uint32_t)((uint64_t)s->frames*clock_hz*10u/s->elapsed);
    s->render_us=(uint32_t)(s->render*1000000u/((uint64_t)s->frames*clock_hz));
    s->ops_per_second=(uint32_t)((uint64_t)operations*s->frames*clock_hz/s->elapsed);
    s->valid=1;
    if(s->frames>=4u || s->elapsed>=clock_hz) {
        s->elapsed=0; s->render=0; s->frames=0;
        return 1;
    }
    return 0;
}

static inline uint32_t basic_speed10(const basic_metrics_t *cpu,const basic_metrics_t *hw) {
    if(!cpu->valid || !hw->valid || !hw->render_us) return 0;
    return (uint32_t)((uint64_t)cpu->render_us*10u/hw->render_us);
}
#endif
