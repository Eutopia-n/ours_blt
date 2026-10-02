/* Host-side bounds/visibility checks for the production layout generator. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../software/basic_layout.h"
#include "../software/basic_metrics.h"

_Static_assert(sizeof(basic_block_t)==12,"Simulation descriptor ABI");

static void check_block(const basic_block_t *p,const basic_motion_t *m) {
    assert(p->x>=BASIC_X_MIN && p->x<=BASIC_X_MAX);
    assert(p->y>=BASIC_Y_MIN && p->y<=BASIC_Y_MAX);
    assert(p->x+BASIC_SIDE<=628u && p->y+BASIC_SIDE<=424u);
    assert(m->speed_x>=BASIC_SPEED_MIN && m->speed_x<=BASIC_SPEED_MAX);
    assert(m->speed_y>=BASIC_SPEED_MIN && m->speed_y<=BASIC_SPEED_MAX);
}

static void test_motion(void) {
    for(uint32_t level=0;level<BASIC_LEVELS;++level) {
        basic_layout_t a={0},b={0},c={0};
        a.level=level; a.random_state=100u+level;
        basic_new_layout(&a); b=c=a;
        basic_advance(&a,BASIC_TICK_HZ);
        // 60 FPS and 4 FPS cover exactly the same second with different
        // frame lengths, including leftover CLINT ticks and Q8 fractions.
        for(uint32_t i=0;i<60u;++i)
            basic_advance(&b,(uint32_t)((uint64_t)(i+1u)*BASIC_TICK_HZ/60u-
                                       (uint64_t)i*BASIC_TICK_HZ/60u));
        for(uint32_t i=0;i<4u;++i) basic_advance(&c,BASIC_TICK_HZ/4u);
        assert(memcmp(&a,&b,sizeof(a))==0 && memcmp(&a,&c,sizeof(a))==0);
        basic_layout_t before=a;
        basic_advance(&a,0);
        assert(memcmp(&a,&before,sizeof(a))==0);
        basic_advance(&a,UINT32_MAX); // Long pause, multiple bounces.
        for(uint32_t kind=0;kind<2u;++kind) for(uint32_t n=0;n<a.count;++n) {
            check_block(kind ? &a.copy[n] : &a.fill[n],
                        kind ? &a.copy_motion[n] : &a.fill_motion[n]);
        }
    }
    basic_layout_t a={0}; a.count=1;
    const uint32_t ex=(BASIC_X_MAX-BASIC_X_MIN)*256u;
    const uint32_t ey=(BASIC_Y_MAX-BASIC_Y_MIN)*256u;
    a.fill_motion[0]=(basic_motion_t){ex,ey,32,64};
    a.copy_motion[0]=(basic_motion_t){2u*ex-16u,2u*ey-16u,32,64};
    basic_advance(&a,BASIC_TICK_HZ/256u);
    assert(a.fill[0].x==BASIC_X_MAX-1u && a.fill[0].y==BASIC_Y_MAX-1u);
    assert(a.copy[0].x==BASIC_X_MIN && a.copy[0].y==BASIC_Y_MIN);
    assert(a.fill_motion[0].phase_x>ex && a.fill_motion[0].phase_y>ey);
    assert(a.copy_motion[0].phase_x==16u && a.copy_motion[0].phase_y==48u);
    // Independent repeated reflection of a large displacement, both axes.
    uint32_t dt=UINT32_MAX;
    uint32_t steps=(uint32_t)((uint64_t)dt*256u/BASIC_TICK_HZ);
    int64_t x=16+(int64_t)32*steps,y=48+(int64_t)64*steps;
    while(x<0 || x>ex) x=x<0 ? -x : 2*(int64_t)ex-x;
    while(y<0 || y>ey) y=y<0 ? -y : 2*(int64_t)ey-y;
    basic_advance(&a,dt);
    assert(a.copy[0].x==BASIC_X_MIN+(uint32_t)x/256u);
    assert(a.copy[0].y==BASIC_Y_MIN+(uint32_t)y/256u);
    assert(a.tick_remainder<BASIC_TICK_HZ);
}

int main(void) {
    unsigned odd_x=0,even_x=0,min_x=0,max_x=0,min_y=0,max_y=0;
    unsigned mixed[2][2]={{0}},directions[2]={0},speeds[2]={0};
    for(uint32_t level=0;level<BASIC_LEVELS;++level) for(uint32_t seed=0;seed<2000u;++seed) {
        basic_layout_t a={0}, b={0};
        a.level=b.level=level;
        a.random_state=b.random_state=seed;
        basic_new_layout(&a); basic_new_layout(&b);
        assert(memcmp(&a,&b,sizeof(a))==0);
        assert(a.count==basic_total(level)/2u && a.count<=BASIC_BLOCKS);
        for(uint32_t side=0;side<2u;++side) {
            const basic_block_t *blocks=side ? a.copy : a.fill;
            const basic_motion_t *motion=side ? a.copy_motion : a.fill_motion;
            for(uint32_t n=0;n<a.count;++n) {
                const basic_block_t *p=&blocks[n];
                const basic_motion_t *m=&motion[n];
                check_block(p,m);
                if(!side) assert(p->color!=BASIC_BACKGROUND);
                odd_x|=p->x&1u; even_x|=!(p->x&1u);
                min_x|=p->x==BASIC_X_MIN; max_x|=p->x==BASIC_X_MAX;
                min_y|=p->y==BASIC_Y_MIN; max_y|=p->y==BASIC_Y_MAX;
                mixed[side][p->x>=320u]=1;
                directions[side]|=1u<<((m->phase_x>(BASIC_X_MAX-BASIC_X_MIN)*256u)*2u+
                                      (m->phase_y>(BASIC_Y_MAX-BASIC_Y_MIN)*256u));
                speeds[side]|=(m->speed_x==BASIC_SPEED_MIN ? 1u : 0u)|
                              (m->speed_x==BASIC_SPEED_MAX ? 2u : 0u);
            }
        }
        basic_new_layout(&b);
        assert(memcmp(a.fill,b.fill,sizeof(a.fill))!=0);
        assert(memcmp(a.copy,b.copy,sizeof(a.copy))!=0);
        basic_advance(&a,2u*BASIC_TICK_HZ);
        for(uint32_t n=0;n<a.count;++n) {
            check_block(&a.fill[n],&a.fill_motion[n]);
            check_block(&a.copy[n],&a.copy_motion[n]);
        }
    }
    assert(odd_x && even_x && min_x && max_x && min_y && max_y);
    for(unsigned side=0;side<2;++side) {
        assert(mixed[side][0] && mixed[side][1]);
        assert(directions[side]==15 && speeds[side]==3);
    }
    test_motion();
    assert(basic_sprite_pixel(0,0)==0xffffu);
    assert(basic_sprite_pixel(1,1)==0xf81fu);
    assert(basic_sprite_pixel(8,1)==0x07ffu);
    assert(basic_sprite_pixel(31,15)==0xffffu);
    uint32_t level=0;
    assert(basic_step_level(level,1u)==0u);
    for(uint32_t i=1;i<BASIC_LEVELS;++i) { level=basic_step_level(level,2u); assert(level==i); }
    assert(basic_step_level(level,2u)==0u);
    assert(basic_step_level(level,3u)==0u);
    for(uint32_t i=0;i<BASIC_LEVELS;++i) {
        assert(basic_step_level(i,0u)==i && basic_step_level(i,1u)==i);
        assert(basic_step_level(i,4u)==i && basic_step_level(i,8u)==i);
        assert(basic_step_level(i,2u)==(i+1u)%BASIC_LEVELS);
        assert(basic_step_level(i,3u)==(i+1u)%BASIC_LEVELS);
    }
    for(uint32_t mode=0;mode<2u;++mode) {
        assert(basic_step_renderer(mode,0u)==mode);
        assert(basic_step_renderer(mode,2u)==mode);
        assert(basic_step_renderer(mode,1u)==(mode^1u));
        assert(basic_step_renderer(mode,3u)==(mode^1u));
        assert(basic_step_renderer(basic_step_renderer(mode,1u),1u)==mode);
    }
    assert(basic_total(0)==32 && basic_total(1)==128 && basic_total(2)==256 &&
           basic_total(3)==256 && basic_total(4)==256 && basic_total(UINT32_MAX)==256);
    basic_metrics_t cpu={0},hw={0};
    assert(!basic_metrics_record(&cpu,0,0,1024,100000000));
    assert(!cpu.valid);
    for(unsigned n=0;n<4;++n)
        assert(basic_metrics_record(&cpu,1666667,1000000,1024,100000000)==(n==3));
    assert(cpu.fps10==599 && cpu.render_us==10000 && cpu.ops_per_second==61439);
    assert(cpu.valid && !cpu.frames && !cpu.elapsed);
    assert(basic_metrics_record(&hw,200000000,150000000,1024,100000000));
    assert(hw.fps10==5 && hw.render_us==1500000 && hw.ops_per_second==512);
    assert(basic_metrics_record(&hw,4000000000u,3000000000u,1024,100000000));
    assert(hw.render_us==30000000 && hw.ops_per_second==25);
    cpu.render_us=2000000; hw.render_us=200000;
    assert(basic_speed10(&cpu,&hw)==100);
    basic_metrics_reset(&hw);
    assert(!hw.valid && !hw.ops_per_second && !basic_speed10(&cpu,&hw));
    basic_metrics_reset(&cpu);
    assert(basic_metrics_record(&cpu,100000000,10000000,32,100000000));
    assert(cpu.ops_per_second==32 && cpu.fps10==10); // No old load in new statistics.
    puts("BASIC MOTION TEST PASSED: 6000 mixed layouts, three levels (32/128/256), four directions and speed bounds; frame-rate independent trajectories, wall/corner/multiple bounces, zero delta; throughput, KEY1 wrap and KEY0 renderer toggle");
    return 0;
}
