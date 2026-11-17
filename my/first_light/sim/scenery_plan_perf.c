#include "render.h"
#include "game_scenery.h"
static SceneryItem items[SCENERY_MAX_ITEMS];
static volatile uint32_t digest;
static void put(char c) {
    while(((mmio_read(SYSTEM_UART_0_IO_CTRL+4)>>16)&255u)==0){}
    mmio_write(SYSTEM_UART_0_IO_CTRL,(uint32_t)c);
}
static void say(const char *s){while(*s)put(*s++);}
static void number(uint32_t n){char b[12];uint32_t size=0;do{b[size++]=(char)('0'+n%10u);n/=10u;}while(n);while(size)put(b[--size]);}
void fatal_trap(uint32_t cause,uint32_t pc){(void)cause;(void)pc;say("SCENE PERF FAIL\r\n");for(;;){}}
int main(void) {
    static const int32_t cameras[4][2]={{712,524},{0,0},{1424,1048},{1053,680}};
    mmio_write(SYSTEM_UART_0_IO_CTRL+8,SYSTEM_CLINT_HZ/(115200u*8u)-1u);
    mmio_write(SYSTEM_UART_0_IO_CTRL+12,7u);
    for(uint32_t scene=0;scene<4;scene++) {
        uint32_t maximum=0,total=0;
        for(uint32_t i=0;i<16;i++) {
            uint32_t start=mmio_read(SYSTEM_CLINT_CTRL+0xbff8u);
            uint32_t count=scenery_select(cameras[scene][0],cameras[scene][1],i*10u,items);
            uint32_t cycles=mmio_read(SYSTEM_CLINT_CTRL+0xbff8u)-start;
            if(cycles>maximum)maximum=cycles;
            total+=cycles;
            if(count>1 || (scene==0 && count!=1) ||
               ((scene==1 || scene==2) && count!=0))fatal_trap(0,0);
            for(uint32_t n=0;n<count;n++)digest+=items[n].x+items[n].y+items[n].frame;
        }
        say("SCENE PERF ");number(scene);say(" MAX_CYCLES ");number(maximum);say(" AVG_CYCLES ");number(total/16u);say("\r\n");
    }
    say("SCENE PERF PASS\r\n");for(;;){}
}
