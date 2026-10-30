#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include "survivor_game.h"
void baseline_game_tick(SurvivorGame *,uint32_t);
void baseline_game_input(SurvivorGame *,uint32_t,uint32_t);
static SurvivorGame a,b,other,other_ref;
static uint32_t rng=0x7359c129u,checks;
static uint32_t rnd(void) {rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void equal(const SurvivorGame *x,const SurvivorGame *y,const char *label) {
    if(memcmp(x,y,sizeof(*x))) {
        const unsigned char *p=(const unsigned char *)x,*q=(const unsigned char *)y;
        for(size_t i=0;i<sizeof(*x);i++) if(p[i]!=q[i]) {
            fprintf(stderr,"MISMATCH %s check=%u byte=%u new=%u old=%u tick=%u\n",label,checks,(unsigned)i,p[i],q[i],x->ticks);break;
        }
        assert(0);
    }
    ++checks;
}
static void step(SurvivorGame *x,SurvivorGame *y,uint32_t held,const char *label) {
    game_tick(x,held);baseline_game_tick(y,held);equal(x,y,label);
}
static void reset(void) {
    game_reset(&a,12345);a.state=GAME_PLAY;a.orbit_count=0;
    a.spawn_wait=a.attack_wait=a.invincible=60000;
}
static void enemy(unsigned slot,int x,int y,unsigned hp) {
    a.enemies[slot]=(GameEnemy){x*32,y*32,(uint8_t)hp,(uint8_t)hp,(uint8_t)(slot%5),0};
}
static void bolt(unsigned slot,int x,int y,unsigned damage,unsigned pierce,unsigned life) {
    a.bolts[slot]=(GameBolt){x*32,y*32,0,0,(uint16_t)life,(uint8_t)damage,(uint8_t)pierce};
}
static void setup_random(unsigned trial) {
    reset();a.rng=rnd();a.ticks=rnd()%(GAME_DURATION_TICKS-10);
    a.orbit_count=(uint8_t)(rnd()%5);a.orbit_damage=(uint8_t)(rnd()%3);
    a.x=(32+(int32_t)(rnd()%(GAME_WORLD_WIDTH-64)))*256;
    a.y=(32+(int32_t)(rnd()%(GAME_WORLD_HEIGHT-64)))*256;
    a.damage=(uint16_t)(1+rnd()%16);a.bolt_pierce=(uint8_t)(rnd()%3);
    if(!(trial%7))a.spawn_wait=0;
    if(!(trial%5)){a.attack_wait=0;a.rapid_burst=1;}
    unsigned enemies=rnd()%(GAME_MAX_ENEMIES+1u),bolts=rnd()%(GAME_MAX_BOLTS+1u);
    if(!(trial%8)){enemies=GAME_MAX_ENEMIES;bolts=GAME_MAX_BOLTS;}
    for(unsigned i=0;i<enemies;i++) {
        int x=16+(int)(rnd()%(GAME_WORLD_WIDTH-31));
        int y=16+(int)(rnd()%(GAME_WORLD_HEIGHT-31));
        switch(trial%6) {
        case 1:x=1024+(int)(rnd()%65)-32;y=704+(int)(rnd()%65)-32;break;
        case 2:x=1024;y=704;break;
        case 3:x=(i&1)?GAME_WORLD_X_MAX:GAME_WORLD_X_MIN;y=(i&2)?GAME_WORLD_Y_MAX:GAME_WORLD_Y_MIN;break;
        case 4:x=992+(int)(i%3)*32;y=672+(int)(i%4)*32;break;
        default:break;
        }
        unsigned hp=1+rnd()%200;enemy(i,x,y,hp);
        a.enemies[i].x+=(int32_t)(rnd()%32);a.enemies[i].y+=(int32_t)(rnd()%32);
        a.enemies[i].flash=(uint8_t)(rnd()%91);
        if(!(rnd()%9))a.enemies[i].hp=0;
    }
    for(unsigned i=0;i<bolts;i++) {
        int x=(int)(rnd()%(GAME_WORLD_WIDTH+32))-16;
        int y=(int)(rnd()%(GAME_WORLD_HEIGHT+32))-16;
        if(enemies && (i%3)) {
            unsigned n=rnd()%enemies;
            x=a.enemies[n].x/32+(int)(rnd()%49)-24;
            y=a.enemies[n].y/32+(int)(rnd()%49)-24;
        }
        bolt(i,x,y,rnd()%32,rnd()%4,1+rnd()%90);
        a.bolts[i].vx=(int32_t)(rnd()%513)-256;a.bolts[i].vy=(int32_t)(rnd()%513)-256;
        if(!(i%11))a.bolts[i].life=1;
    }
    if(!(trial%3))for(unsigned i=0;i<GAME_MAX_GEMS;i++)
        a.gems[i]=(GameGem){(int16_t)(16+rnd()%(GAME_WORLD_WIDTH-31)),(int16_t)(16+rnd()%(GAME_WORLD_HEIGHT-31)),(uint16_t)(1+rnd()%60000),(uint8_t)(rnd()%2),0};
}
int main(void) {
    reset();b=a;step(&a,&b,0,"empty");
    // Opposite cells with index priority opposite spatial traversal order.
    reset();enemy(0,1030,704,20);enemy(1,1018,704,20);bolt(255,1024,704,2,0,10);
    b=a;step(&a,&b,0,"cross-cell-first-hit");assert(a.enemies[0].hp==18 && a.enemies[1].hp==20);
    // A high-index target alone, newly fired bolt, strict 15/16 pixel borders.
    for(unsigned distance=14;distance<=17;distance++) {
        reset();enemy(GAME_MAX_ENEMIES-1u,1100+(int)distance,704,20);bolt(255,1100,704,2,2,10);
        b=a;step(&a,&b,0,"strict-radius");
    }
    reset();enemy(GAME_MAX_ENEMIES-1u,1100,704,20);a.attack_wait=0;b=a;step(&a,&b,0,"new-bolt-with-stale-zero-count");
    // Max uint8 pierce permits 256 hits, including when 270 candidates exist.
    reset();for(unsigned i=0;i<GAME_MAX_ENEMIES;i++)enemy(i,1200,704,200);
    bolt(255,1200,704,1,255,10);b=a;step(&a,&b,0,"256-candidates");
    for(unsigned i=0;i<GAME_MAX_ENEMIES;i++)assert(a.enemies[i].hp==(i<256u?199:200));
    // Retiring killed links must preserve kill/drop/RNG/XP-merge order.
    reset();for(unsigned i=0;i<GAME_MAX_ENEMIES;i++)enemy(i,1200,704,1);
    for(unsigned i=0;i<GAME_MAX_BOLTS;i++)bolt(i,1200,704,2,i%3,10);
    for(unsigned i=0;i<GAME_MAX_GEMS;i++)a.gems[i]=(GameGem){1200,704,59000,0,0};
    b=a;step(&a,&b,0,"dense-dead-removal-full-gems");assert(a.kills==GAME_MAX_ENEMIES);
    reset();enemy(0,1500,704,20);bolt(255,GAME_WORLD_X_MAX-1,100,1,0,10);
    a.bolts[255].vx=32;b=a;step(&a,&b,0,"world-expiration");assert(!a.bolts[255].life);
    reset();enemy(0,1200,704,20);bolt(255,1200,704,1,0,1);b=a;
    step(&a,&b,0,"life1-before-collision");assert(a.enemies[0].hp==20);
    for(unsigned state=GAME_READY;state<=GAME_EXIT;state++)if(state!=GAME_PLAY) {
        reset();a.state=(uint8_t)state;bolt(255,1200,704,2,0,10);b=a;step(&a,&b,8,"non-play");
    }
    for(unsigned trial=0;trial<3000;trial++) {
        setup_random(trial);b=a;
        if(!(trial%17)){other=a;other_ref=b;}
        for(unsigned tick=0;tick<4;tick++) {
            step(&a,&b,rnd()%16,"random-full-state");
            if(!(trial%17))step(&other,&other_ref,tick&15,"interleaved-independent-game");
        }
    }
    // The natural loop also includes upgrades, restart, spawn, movement and RNG.
    game_reset(&a,12345);game_input(&a,0,16);b=a;
    for(unsigned t=0;t<30000;t++) {
        if(a.state==GAME_UPGRADE || a.state==GAME_OVER || a.state==GAME_WON) {
            game_input(&a,0,16);baseline_game_input(&b,0,16);equal(&a,&b,"input");
        }
        uint32_t keys=(t/90)%4==0?8:(t/90)%4==1?2:(t/90)%4==2?4:1;
        step(&a,&b,keys,"natural-30000");
    }
    printf("BULLET GRID DIFFERENTIAL TESTS PASSED: %u whole-state comparisons; 3000 randomized full-pool scenarios, 30000 natural ticks, enemy269/bolt255, strict radius, four-cell boundaries, ordered pierce, 270 candidates and unchanged 256-hit pierce maximum, death unlink/drop RNG/full XP pool, world/life expiry, pause/empty, lazy new-bolt build, interleaved games\n",checks);
    return 0;
}
