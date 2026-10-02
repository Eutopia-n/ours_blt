#ifndef ALPHA_CONTROL_H
#define ALPHA_CONTROL_H
#include <stdint.h>
#define ALPHA_HOLD_TICKS 50000000u  /* 500 ms at 100 MHz */
#define ALPHA_REPEAT_TICKS 10000000u /* 100 ms */
typedef struct {
    uint32_t percent, armed, holding, repeating, stamp;
} alpha_control_t;
static inline void alpha_control_enter(alpha_control_t *s, uint32_t down) {
    s->percent=0; s->armed=!down; s->holding=0; s->repeating=0; s->stamp=0;
}
static inline uint32_t alpha_control_poll(alpha_control_t *s, uint32_t press,
                                         uint32_t down, uint32_t now) {
    uint32_t old=s->percent;
    if(!s->armed) { if(!down) s->armed=1; return 0; }
    if(press) {
        s->percent=(s->percent+2u)%102u;
        s->holding=down; s->repeating=0; s->stamp=now;
    } else if(!down) {
        s->holding=0; s->repeating=0;
    } else if(s->holding) {
        uint32_t elapsed=now-s->stamp;
        if(!s->repeating && elapsed>=ALPHA_HOLD_TICKS) {
            s->percent=(s->percent+2u)%102u;
            s->stamp+=ALPHA_HOLD_TICKS; s->repeating=1;
        }
        if(s->repeating) {
            uint32_t steps=(now-s->stamp)/ALPHA_REPEAT_TICKS;
            s->percent=(s->percent+2u*(steps%51u))%102u;
            s->stamp+=steps*ALPHA_REPEAT_TICKS;
        }
    }
    return old!=s->percent;
}
/* UI is transparency, whereas the hardware coefficient is foreground opacity. */
static inline uint32_t alpha_opacity(uint32_t percent) {
    return ((100u-percent)*256u+50u)/100u;
}
static inline uint16_t alpha_rgb565(uint16_t f,uint16_t b,uint32_t a) {
    uint32_t k=256u-a;
    uint32_t r=(((f>>11)*a+(b>>11)*k+128u)>>8);
    uint32_t g=((((f>>5)&63u)*a+((b>>5)&63u)*k+128u)>>8);
    uint32_t blue=(((f&31u)*a+(b&31u)*k+128u)>>8);
    return (uint16_t)((r<<11)|(g<<5)|blue);
}
#endif
