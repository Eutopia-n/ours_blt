#include <assert.h>
#include <stdio.h>
#include "../software/alpha_control.h"
int main(void) {
    alpha_control_t s;
    alpha_control_enter(&s,1);
    alpha_control_poll(&s,1,1,0);
    alpha_control_poll(&s,0,1,200000000u);
    assert(s.percent==0); /* Holding menu ENTER cannot change transparency. */
    alpha_control_poll(&s,0,0,200000001u);
    for(uint32_t i=1;i<=102;i++) {
        alpha_control_poll(&s,1,0,i);
        assert(s.percent==(i%51u)*2u);
    }
    alpha_control_enter(&s,0);
    alpha_control_poll(&s,1,1,100);
    assert(s.percent==2);
    alpha_control_poll(&s,0,1,ALPHA_HOLD_TICKS+99);
    assert(s.percent==2);
    alpha_control_poll(&s,0,1,ALPHA_HOLD_TICKS+100);
    assert(s.percent==4);
    alpha_control_poll(&s,0,1,ALPHA_HOLD_TICKS+ALPHA_REPEAT_TICKS+100);
    assert(s.percent==6);
    alpha_control_poll(&s,0,1,ALPHA_HOLD_TICKS+5u*ALPHA_REPEAT_TICKS+100);
    assert(s.percent==14); /* Slow frame catches up by elapsed time. */
    alpha_control_poll(&s,0,0,ALPHA_HOLD_TICKS+6u*ALPHA_REPEAT_TICKS+100);
    alpha_control_poll(&s,0,1,ALPHA_HOLD_TICKS+7u*ALPHA_REPEAT_TICKS+100);
    assert(s.percent==14); /* No phantom repeats without another press. */
    alpha_control_enter(&s,0);
    uint32_t start=0xfffffff0u;
    alpha_control_poll(&s,1,1,start);
    alpha_control_poll(&s,0,1,start+ALPHA_HOLD_TICKS+49u*ALPHA_REPEAT_TICKS);
    assert(s.percent==0); /* 51 steps including the initial press, wraps. */
    alpha_control_poll(&s,0,1,start+ALPHA_HOLD_TICKS+50u*ALPHA_REPEAT_TICKS);
    assert(s.percent==2);
    assert(alpha_opacity(0)==256 && alpha_opacity(50)==128 && alpha_opacity(100)==0);
    for(uint32_t f=0;f<65536;f+=17) {
        uint16_t b=(uint16_t)(65535u-f);
        assert(alpha_rgb565((uint16_t)f,b,256)==f);
        assert(alpha_rgb565((uint16_t)f,b,0)==b);
    }
    puts("ALPHA CONTROL TEST PASSED: clicks, repeat timing, release, menu entry, modulo and clock rollover");
}
