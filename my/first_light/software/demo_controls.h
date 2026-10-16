#ifndef DEMO_CONTROLS_H
#define DEMO_CONTROLS_H
#include <stdint.h>

#define DEMO_ALPHA_REPEAT_DELAY 30000000u
#define DEMO_ALPHA_REPEAT_PERIOD 12000000u
#define DEMO_ALPHA_STEP 1u

static uint32_t demo_alpha_update(uint32_t value,uint32_t pressed,uint32_t held,
                                  uint32_t now,uint32_t *next_repeat,
                                  int32_t *repeat_direction) {
    /* 按键1提高透明度，按键3降低透明度；单键长按更容易操作。 */
    int32_t direction=0;
    if(pressed&1u) direction=1;
    else if(pressed&4u) direction=-1;
    if(direction) {
        *repeat_direction=direction;
        *next_repeat=now+DEMO_ALPHA_REPEAT_DELAY;
        if(direction>0) return value<255u ? value+DEMO_ALPHA_STEP : 255u;
        return value>DEMO_ALPHA_STEP ? value-DEMO_ALPHA_STEP : 0u;
    }
    if(!(held&5u)) { *next_repeat=0; *repeat_direction=0; return value; }
    if((held&5u)==1u) *repeat_direction=1;
    else if((held&5u)==4u) *repeat_direction=-1;
    direction=*repeat_direction;
    if(!direction) { *next_repeat=0; return value; }
    if(!*next_repeat) { *next_repeat=now+DEMO_ALPHA_REPEAT_DELAY; return value; }
    if((int32_t)(now-*next_repeat)>=0) {
        *next_repeat=now+DEMO_ALPHA_REPEAT_PERIOD;
        if(direction>0) return value<255u ? value+DEMO_ALPHA_STEP : 255u;
        return value>DEMO_ALPHA_STEP ? value-DEMO_ALPHA_STEP : 0u;
    }
    return value;
}
#endif
