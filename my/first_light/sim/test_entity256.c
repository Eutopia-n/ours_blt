#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "survivor_game.h"

static struct { uint32_t before; SurvivorGame game; uint32_t after; } guarded;
#define g guarded.game

static void start(void) {
    guarded.before=0x12345678u; guarded.after=0xabcdef01u;
    game_reset(&g,12345); g.state=GAME_PLAY; g.orbit_count=0;
    g.spawn_wait=g.attack_wait=g.invincible=60000;
}
static void guards(void) {
    assert(guarded.before==0x12345678u && guarded.after==0xabcdef01u);
}
static void target(void) {
    g.enemies[GAME_MAX_ENEMIES-1u]=(GameEnemy){g.x/8+128*32,g.y/8+64*32,200,200,0,0};
}
static void fill_bolts(void) {
    for(unsigned i=0;i<GAME_MAX_BOLTS;i++)
        g.bolts[i]=(GameBolt){100*32+(int32_t)i,100*32,0,0,100,1,0};
}
int main(void) {
    assert(GAME_MAX_ENEMIES==270 && GAME_MAX_BOLTS==256);
    assert(sizeof(GameBolt)==20);
    start(); game_tick(&g,0); assert(!g.enemy_count && !g.bolt_count); guards();
    start(); fill_bolts(); target(); g.attack_wait=0;
    game_tick(&g,0);
    assert(g.bolt_count==256 && g.shots==0);
    for(unsigned i=0;i<GAME_MAX_BOLTS;i++) {
        assert(g.bolts[i].x==100*32+(int32_t)i && g.bolts[i].life==99);
    }
    guards();
    // The last slot can be allocated; a full pool rejects another shot safely.
    g.bolts[255].life=0; g.attack_wait=0; game_tick(&g,0);
    assert(g.bolt_count==256 && g.shots==1 && g.bolts[255].life==89);
    assert(g.bolts[255].x>g.x/8); guards();
    start(); fill_bolts(); target(); g.bolts[255].life=0;
    g.rapid_burst=1; g.attack_wait=0; game_tick(&g,0);
    assert(g.bolt_count==256 && g.shots==1); guards();
    // Every slot, including 255, expires and is recounted without uint8 wrap.
    start(); fill_bolts();
    for(unsigned i=0;i<GAME_MAX_BOLTS;i++) g.bolts[i].life=1;
    game_tick(&g,0); assert(g.bolt_count==0); guards();
    start(); target(); g.enemies[GAME_MAX_ENEMIES-1u].hp=1;
    g.bolts[255]=(GameBolt){g.enemies[GAME_MAX_ENEMIES-1u].x,g.enemies[GAME_MAX_ENEMIES-1u].y,0,0,10,2,0};
    game_tick(&g,0);
    assert(g.kills==1 && !g.enemies[GAME_MAX_ENEMIES-1u].hp && !g.bolts[255].life); guards();
    start();
    g.bolts[255]=(GameBolt){GAME_WORLD_X_MAX*32-1,100*32,1,0,10,1,0};
    game_tick(&g,0); assert(!g.bolts[255].life && !g.bolt_count); guards();
    start(); fill_bolts(); g.state=GAME_PAUSED;
    game_tick(&g,8); assert(!g.ticks && g.bolts[255].life==100); guards();
    // Full enemy pool rejects a spawn; a free high slot can be refilled.
    start();
    for(unsigned i=0;i<GAME_MAX_ENEMIES;i++)
        g.enemies[i]=(GameEnemy){1300*32,704*32,200,200,1,0};
    g.spawn_wait=0;uint32_t rng=g.rng;game_tick(&g,0);
    assert(g.enemy_count==270 && !g.spawned && g.rng==rng);guards();
    g.enemies[269].hp=0;g.spawn_wait=0;game_tick(&g,0);
    assert(g.enemy_count==270 && g.spawned==1 && g.enemies[269].hp);guards();
    // More than 256 occupied cells exercise all 270 used-cell/next entries.
    start();fill_bolts();
    for(unsigned i=0;i<GAME_MAX_ENEMIES;i++)
        g.enemies[i]=(GameEnemy){(64+(int32_t)(i%40)*48)*32,(80+(int32_t)(i/40)*128)*32,200,200,1,0};
    game_tick(&g,0);assert(g.enemy_count==270 && g.bolt_count==256 && g.spawn_slow);guards();
    for(unsigned i=0;i<GAME_MAX_ENEMIES;i++)g.enemies[i].hp=0;
    game_tick(&g,0);assert(!g.enemy_count);guards();
    printf("ENEMY270 POOL TESTS PASSED: 270 enemies + 256 bolts, enemy269 spawn/refill/target/collision, 270 occupied cells, bolt255 allocation/expiry, burst saturation, world boundary, pause, empty, canaries; GameBolt=%u SurvivorGame=%u\n",
           (unsigned)sizeof(GameBolt),(unsigned)sizeof(SurvivorGame));
    return 0;
}
