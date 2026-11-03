#include <assert.h>
#include <stdio.h>
#include "frame_metrics.h"
#include "demo_controls.h"
int main(void) {
    assert(SYSTEM_CLINT_HZ==150000000u && FRAME_60_CYCLES==2500000u);
    assert(DEMO_BENCH_REPEAT_DELAY==45000000u && DEMO_BENCH_REPEAT_PERIOD==9000000u);
    assert(DEMO_ALPHA_REPEAT_DELAY==45000000u && DEMO_ALPHA_REPEAT_PERIOD==18000000u);
    uint32_t next=0;int32_t direction=0;
    assert(demo_bench_update(1,1,1,100,&next,&direction)==2 && next==45000100u);
    assert(demo_alpha_update(128,1,1,200,&next,&direction)==129 && next==45000200u);
    assert(frame_measured_fps(30,75000000u)==60);
    assert(frame_measured_fps(30,150000000u)==30);
    assert(frame_measured_fps(30,37500000u)==120);
    assert(frame_measured_fps(4,10000000u)==60);
    assert(frame_measured_fps(30,UINT32_MAX)==1);
    assert(frame_measured_fps(30,0)==0 && frame_measured_fps(30,149)==0);
    FrameMax60 m={0};
    for(unsigned i=0;i<30;i++) frame_max60_sample(&m,2500000u,1,100);
    assert(m.maximum==100);
    for(unsigned i=0;i<30;i++) frame_max60_sample(&m,2500001u,1,200);
    assert(m.maximum==100);
    puts("CPU150 TIME TEST PASSED: FPS overflow/zero/rounding, 60Hz budget, repeat intervals");
    return 0;
}
