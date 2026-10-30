#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "survivor_game.h"
static SurvivorGame g,copy,empty;
static int mag(int v) { return v<0 ? -v : v; }
static void start(SurvivorGame *s) {
    game_reset(s,12345);s->state=GAME_PLAY;s->orbit_count=0;
    s->spawn_wait=65535;s->attack_wait=65535;s->invincible=65535;
}
static void put(unsigned i,int x,int y) {
    g.enemies[i]=(GameEnemy){x*32,y*32,200,200,1,0};
}
static unsigned pairs(unsigned radius) {
    unsigned result=0;
    for(unsigned i=0;i<GAME_MAX_ENEMIES;i++) if(g.enemies[i].hp)
        for(unsigned j=i+1;j<GAME_MAX_ENEMIES;j++) if(g.enemies[j].hp &&
            mag(g.enemies[i].x-g.enemies[j].x)<(int)radius*32 &&
            mag(g.enemies[i].y-g.enemies[j].y)<(int)radius*32) result++;
    return result;
}
static void advance(unsigned ticks) {
    for(unsigned t=0;t<ticks;t++) {
        copy=g;game_tick(&g,0);
        for(unsigned i=0;i<GAME_MAX_ENEMIES;i++) if(g.enemies[i].hp) {
            assert(g.enemies[i].x>=GAME_WORLD_X_MIN*32 && g.enemies[i].x<=GAME_WORLD_X_MAX*32);
            assert(g.enemies[i].y>=GAME_WORLD_Y_MIN*32 && g.enemies[i].y<=GAME_WORLD_Y_MAX*32);
            assert(mag(g.enemies[i].x-copy.enemies[i].x)<=80);
            assert(mag(g.enemies[i].y-copy.enemies[i].y)<=96);
            assert(g.enemies[i].hp==200);
        }
    }
}
int main(void) {
    start(&g);game_tick(&g,0);assert(g.enemy_count==0);
#ifndef SEPARATION_BASELINE
    // A reused slot must not inherit the dead body's cached steering.
    start(&g);g.enemy_steer[0][0]=32;g.enemy_steer[0][1]=-32;
    g.spawn_wait=0;game_tick(&g,0);
    assert(g.enemies[0].hp && g.enemy_steer[0][0]==0 && g.enemy_steer[0][1]==0);
#endif
    start(&g);put(0,1320,704);put(1,1520,704);advance(1);
    assert(g.enemies[0].x==1320*32-20 && g.enemies[1].x==1520*32-20);
    assert(g.enemies[0].y==704*32 && g.enemies[1].y==704*32);
    start(&g);put(0,1320,704);put(1,1320,704);advance(90);
    printf("PAIR hard=%u body=%u\n",pairs(6),pairs(20));
#ifndef SEPARATION_BASELINE
    assert(pairs(6)==0);
#endif
    // Two bodies straddling a 32-pixel cell boundary must still separate.
    start(&g);put(0,1343,704);put(1,1344,704);advance(90);
#ifndef SEPARATION_BASELINE
    assert(pairs(6)==0);
#endif
    start(&g);
    for(unsigned i=0;i<64;i++) put(i,1320,704);
    advance(120);
    printf("CLUSTER64 hard=%u body=%u count=%u\n",pairs(6),pairs(20),g.enemy_count);
    assert(g.enemy_count==64);
#ifndef SEPARATION_BASELINE
    assert(pairs(6)<2016u/4u);
#endif
    start(&g);
    for(unsigned i=0;i<GAME_MAX_ENEMIES;i++) put(i,1320,704);
    advance(180);
    printf("CLUSTER270 hard=%u body=%u count=%u\n",pairs(6),pairs(20),g.enemy_count);
    assert(g.enemy_count==GAME_MAX_ENEMIES);
#ifndef SEPARATION_BASELINE
    assert(pairs(6)<(GAME_MAX_ENEMIES*(GAME_MAX_ENEMIES-1u)/2u)/4u);
#endif
    // Walls/corners and sparse dead slots; every live body remains on-map.
    start(&g);
    for(unsigned i=0;i<GAME_MAX_ENEMIES;i++) put(i,GAME_WORLD_X_MIN,GAME_WORLD_Y_MIN);
    advance(90);assert(g.enemy_count==GAME_MAX_ENEMIES);
    printf("CORNER270 hard=%u body=%u\n",pairs(6),pairs(20));
    start(&g);put(0,GAME_WORLD_X_MAX,GAME_WORLD_Y_MAX);
    put(GAME_MAX_ENEMIES-1u,GAME_WORLD_X_MAX,GAME_WORLD_Y_MAX);advance(60);
#ifndef SEPARATION_BASELINE
    assert(pairs(6)==0);
#endif
    // Scratch must not leak across separate games or an intervening empty grid.
    start(&g);for(unsigned i=0;i<32;i++) put(i,1320,704);copy=g;
    game_tick(&g,0);SurvivorGame once=g;
    start(&empty);game_tick(&empty,0);game_tick(&copy,0);
    assert(memcmp(&once,&copy,sizeof(g))==0);
    g.state=GAME_PAUSED;copy=g;game_tick(&g,0);assert(memcmp(&g,&copy,sizeof(g))==0);
    puts("ENEMY SEPARATION TESTS PASSED: empty/sparse, coincident pair, adjacent cells, dense270, corners, bounded displacement, pause and independent games");
    return 0;
}
