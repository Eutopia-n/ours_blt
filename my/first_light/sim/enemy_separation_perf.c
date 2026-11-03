/* Simulation-only real RISC-V timing probe, no DDR / renderer timing claim. */
#include "render.h"
#include "survivor_game.h"
static SurvivorGame game;
static uint32_t maximum[3],total[3];
__attribute__((used,externally_visible))
void *memcpy(void *to,const void *from,unsigned size) {
    volatile unsigned char *dst=to;const unsigned char *src=from;
    for(unsigned i=0;i<size;i++) dst[i]=src[i];
    return to;
}
static void putc_uart(char c) {
    while(((mmio_read(SYSTEM_UART_0_IO_CTRL+4)>>16)&255u)==0) {}
    mmio_write(SYSTEM_UART_0_IO_CTRL,(uint32_t)c);
}
static void say(const char *s) { while(*s) putc_uart(*s++); }
static void number(uint32_t n) {
    char buf[12];uint32_t size=0;
    do { buf[size++]=(char)('0'+n%10u);n/=10u; } while(n);
    while(size) putc_uart(buf[--size]);
}
void fatal_trap(uint32_t cause,uint32_t pc) {
    (void)cause;(void)pc;say("SEP PERF FAIL\r\n");for(;;) {}
}
int main(void) {
    mmio_write(SYSTEM_UART_0_IO_CTRL+8,SYSTEM_CLINT_HZ/(115200u*8u)-1u);
    mmio_write(SYSTEM_UART_0_IO_CTRL+12,7u);
    for(uint32_t kind=0;kind<3;kind++) {
        game_reset(&game,12345);game.state=GAME_PLAY;game.orbit_count=0;
        game.spawn_wait=game.attack_wait=game.invincible=65535;game.ticks=15u*15u*60u;
        for(uint32_t i=0;i<GAME_MAX_ENEMIES;i++) {
            int32_t x=kind ? 1320 : 700+(int32_t)(i%16u)*32;
            int32_t y=kind ? 704 : 400+(int32_t)(i/16u)*32;
            game.enemies[i]=(GameEnemy){x*32,y*32,200,200,(uint8_t)(i%5u),0};
        }
        if(kind==2) for(uint32_t i=0;i<GAME_MAX_BOLTS;i++)
            game.bolts[i]=(GameBolt){32*32,32*32,0,0,60000,1,0};
        for(uint32_t tick=0;tick<4;tick++) {
            uint32_t start=mmio_read(SYSTEM_CLINT_CTRL+0xbff8u);
            game_tick(&game,0);
            uint32_t cycles=mmio_read(SYSTEM_CLINT_CTRL+0xbff8u)-start;
            if(cycles>maximum[kind]) maximum[kind]=cycles;
            total[kind]+=cycles;
        }
        if(game.enemy_count!=GAME_MAX_ENEMIES) fatal_trap(0,0);
        say("SEP PERF ");number(kind);say(" MAX_CYCLES ");number(maximum[kind]);
        say(" AVG_CYCLES ");number(total[kind]/4u);say("\r\n");
    }
    say("SEP PERF PASS\r\n");for(;;) {}
}
