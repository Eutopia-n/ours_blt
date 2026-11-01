/* Actual CPU timing of game_tick only, excluding rendering and DDR traffic. */
#include "render.h"
#include "survivor_game.h"
static SurvivorGame game;
static uint32_t maximum[5],total[5];
__attribute__((used,externally_visible))
void *memcpy(void *to,const void *from,unsigned size) {
    volatile unsigned char *d=to;const unsigned char *s=from;
    for(unsigned i=0;i<size;i++)d[i]=s[i];
    return to;
}
static void put(char c) {
    while(((mmio_read(SYSTEM_UART_0_IO_CTRL+4)>>16)&255u)==0){}
    mmio_write(SYSTEM_UART_0_IO_CTRL,(uint32_t)c);
}
static void say(const char *s){while(*s)put(*s++);}
static void number(uint32_t n){char b[12];uint32_t size=0;do{b[size++]=(char)('0'+n%10u);n/=10u;}while(n);while(size)put(b[--size]);}
void fatal_trap(uint32_t cause,uint32_t pc){(void)cause;(void)pc;say("GRID PERF FAIL\r\n");for(;;){}}
int main(void) {
    mmio_write(SYSTEM_UART_0_IO_CTRL+8,SYSTEM_CLINT_HZ/(115200u*8u)-1u);
    mmio_write(SYSTEM_UART_0_IO_CTRL+12,7u);
    for(uint32_t kind=0;kind<5;kind++) {
        game_reset(&game,12345);game.state=GAME_PLAY;game.orbit_count=0;
        game.spawn_wait=game.attack_wait=game.invincible=65535;game.ticks=15u*15u*60u;
        for(uint32_t i=0;i<GAME_MAX_ENEMIES;i++) {
            int32_t x=kind>=3?1320:700+(int32_t)(i%16u)*32;
            int32_t y=kind>=3?704:400+(int32_t)(i/16u)*32;
            uint8_t hp=kind==4?1:200;
            game.enemies[i]=(GameEnemy){x*32,y*32,hp,hp,(uint8_t)(i%5u),0};
        }
        uint32_t count=kind==0?0:kind==1?48:GAME_MAX_BOLTS;
        for(uint32_t i=0;i<count;i++)
            game.bolts[i]=(GameBolt){(kind==4?1320:32)*32,(kind==4?704:32)*32,0,0,60000,2,(uint8_t)(kind==4?2:0)};
        for(uint32_t tick=0;tick<4;tick++) {
            uint32_t start=mmio_read(SYSTEM_CLINT_CTRL+0xbff8u);
            game_tick(&game,0);
            uint32_t cycles=mmio_read(SYSTEM_CLINT_CTRL+0xbff8u)-start;
            if(cycles>maximum[kind])maximum[kind]=cycles;
            total[kind]+=cycles;
        }
        if(game.enemy_count!=(kind==4?0u:GAME_MAX_ENEMIES))fatal_trap(0,0);
        const unsigned char *bytes=(const unsigned char *)&game;uint32_t digest=2166136261u;
        for(uint32_t i=0;i<sizeof(game);i++)digest=(digest^bytes[i])*16777619u;
        say("GRID PERF ");number(kind);say(" MAX_CYCLES ");number(maximum[kind]);
        say(" AVG_CYCLES ");number(total[kind]/4u);say(" STATE_HASH ");number(digest);say("\r\n");
    }
    say("GRID PERF PASS\r\n");for(;;){}
}
