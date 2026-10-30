#include <assert.h>
#include <stdio.h>
#include <string.h>
// Include the real policy to test separation independently from chase motion.
#include "../software/survivor_game.c"
static SurvivorGame g,ref,empty;
static void start(SurvivorGame *s) {
    game_reset(s,12345);s->state=GAME_PLAY;s->orbit_count=0;
    s->spawn_wait=s->attack_wait=s->invincible=60000;
}
static GameEnemy target(unsigned kind,int x,int y) {
    return (GameEnemy){x*32,y*32,200,200,(uint8_t)kind,0};
}
static void fill(unsigned enemies,unsigned bolts) {
    start(&g);
    for(unsigned i=0;i<enemies;i++)g.enemies[i]=target(i%5,1300,704);
    for(unsigned i=0;i<bolts;i++)g.bolts[i]=(GameBolt){100*32,100*32,0,0,1000,1,0};
}
int main(void) {
    // Exhaustive symmetric interaction matrix: A-A and C-C collide;
    // B/D/E collide with one another; all remaining pairs pass through.
    for(unsigned first=0;first<5;first++)for(unsigned second=0;second<5;second++) {
        start(&g);g.enemies[0]=target(first,1320,704);g.enemies[4]=target(second,1320,704);
        for(unsigned tick=0;tick<4;tick++){g.ticks=tick;separate_enemies(&g);}
        unsigned compatible=(first==second) ||
            ((first==1 || first>=3) && (second==1 || second>=3));
        unsigned moved=g.enemies[0].x!=g.enemies[4].x || g.enemies[0].y!=g.enemies[4].y;
        assert(moved==compatible);
    }
    // A dense incompatible crowd must not consume the neighbor budget and
    // hide a same-species pair. Verify all four recomputation groups.
    for(unsigned kind=0;kind<=2;kind+=2)for(unsigned tick=0;tick<4;tick++) {
        start(&g);g.ticks=tick;
        for(unsigned i=0;i<GAME_MAX_ENEMIES;i++)g.enemies[i]=target(1,1320,704);
        g.enemies[tick]=target(kind,1320,704);g.enemies[tick+4]=target(kind,1320,704);
        ref=g;for(unsigned i=0;i<GAME_MAX_ENEMIES;i++)if(i!=tick && i!=tick+4)ref.enemies[i].hp=0;
        separate_enemies(&g);separate_enemies(&ref);
        assert(!memcmp(&g.enemies[tick],&ref.enemies[tick],sizeof(GameEnemy)));
        assert(!memcmp(&g.enemies[tick+4],&ref.enemies[tick+4],sizeof(GameEnemy)));
        assert(g.enemies[tick].x!=1320*32 || g.enemies[tick].y!=704*32);
    }
    for(unsigned kind=0;kind<=2;kind+=2) {
        start(&g);g.enemies[0]=target(kind,-100,-100);
        g.enemies[GAME_MAX_ENEMIES-1u]=target(kind,GAME_WORLD_WIDTH+100,GAME_WORLD_HEIGHT+100);
        separate_enemies(&g);
        assert(g.enemies[0].x==GAME_WORLD_X_MIN*32 && g.enemies[0].y==GAME_WORLD_Y_MIN*32);
        assert(g.enemies[GAME_MAX_ENEMIES-1u].x==GAME_WORLD_X_MAX*32 && g.enemies[GAME_MAX_ENEMIES-1u].y==GAME_WORLD_Y_MAX*32);
        start(&g);g.enemies[GAME_MAX_ENEMIES-1u]=target(kind,1024,704);g.invincible=0;
        game_tick(&g,0);assert(g.hp==92 && g.damage_taken==8);
        start(&g);g.enemies[GAME_MAX_ENEMIES-1u]=target(kind,1320,704);g.enemies[GAME_MAX_ENEMIES-1u].hp=1;
        g.bolts[255]=(GameBolt){1320*32,704*32,0,0,10,2,0};
        game_tick(&g,0);assert(g.kills==1 && !g.enemies[GAME_MAX_ENEMIES-1u].hp && !g.bolts[255].life);
        start(&g);g.ticks=14;g.orbit_count=1;int32_t x,y;
        g.ticks=15;game_orbit_position(&g,0,&x,&y);g.ticks=14;
        g.enemies[GAME_MAX_ENEMIES-1u]=target(kind,x,y);g.enemies[GAME_MAX_ENEMIES-1u].hp=1;
        game_tick(&g,0);assert(g.kills==1);
    }
    // Actual chasing of A/C is the same with/without a wall of other bodies.
    for(unsigned kind=0;kind<=2;kind+=2) {
        start(&g);g.enemies[0]=target(kind,1320,704);ref=g;
        for(unsigned i=1;i<GAME_MAX_ENEMIES;i++)g.enemies[i]=target(1,1320,704);
        for(unsigned t=0;t<90;t++) {
            game_tick(&g,0);game_tick(&ref,0);
            assert(!memcmp(&g.enemies[0],&ref.enemies[0],sizeof(GameEnemy)));
        }
    }
    // Packed full-pool slime / bat populations must spread from coincidence,
    // including a corner, while staying inside the world and displacement cap.
    for(unsigned kind=0;kind<=2;kind+=2)for(unsigned corner=0;corner<2;corner++) {
        start(&g);
        for(unsigned i=0;i<GAME_MAX_ENEMIES;i++)g.enemies[i]=target(kind,corner?16:1320,corner?16:704);
        for(unsigned t=0;t<180;t++) {
            ref=g;game_tick(&g,0);
            for(unsigned i=0;i<GAME_MAX_ENEMIES;i++) {
                assert(g.enemies[i].x>=GAME_WORLD_X_MIN*32 && g.enemies[i].x<=GAME_WORLD_X_MAX*32);
                assert(g.enemies[i].y>=GAME_WORLD_Y_MIN*32 && g.enemies[i].y<=GAME_WORLD_Y_MAX*32);
                assert(magnitude(g.enemies[i].x-ref.enemies[i].x)<=80);
                assert(magnitude(g.enemies[i].y-ref.enemies[i].y)<=96);
            }
        }
        unsigned pairs=0;
        for(unsigned i=0;i<GAME_MAX_ENEMIES;i++)for(unsigned j=i+1;j<GAME_MAX_ENEMIES;j++)
            if(magnitude(g.enemies[i].x-g.enemies[j].x)<6*32 && magnitude(g.enemies[i].y-g.enemies[j].y)<6*32)pairs++;
        printf("FAST SAME-KIND kind=%u corner=%u close_pairs=%u initial=%u\n",kind,corner,pairs,GAME_MAX_ENEMIES*(GAME_MAX_ENEMIES-1u)/2u);
        assert(g.enemy_count==GAME_MAX_ENEMIES && pairs<(GAME_MAX_ENEMIES*(GAME_MAX_ENEMIES-1u)/2u)/4u);
    }
    fill(256,255);g.spawn_wait=50;recount(&g);assert(!g.spawn_slow);
    g.bolts[255]=g.bolts[0];recount(&g);assert(g.spawn_slow && g.spawn_wait==101);
    recount(&g);assert(g.spawn_wait==101); // No repeated doubling.
    for(unsigned i=0;i<63;i++)g.bolts[i].life=0;
    recount(&g);assert(g.enemy_count+g.bolt_count==449 && g.spawn_slow);
    g.bolts[63].life=0;recount(&g);assert(!g.spawn_slow && g.spawn_wait==50);
    fill(256,256);g.spawn_wait=65535;recount(&g);assert(g.spawn_slow && g.spawn_wait==65535);
    // Compare real spawn scheduling, including the decrement/else extra tick.
    fill(224,225);g.spawn_slow=1;g.spawn_wait=0;
    game_tick(&g,0);assert(g.spawned==2 && g.spawn_wait==101 && g.spawn_slow);
    for(unsigned t=0;t<101;t++)game_tick(&g,0);
    assert(g.spawned==2);game_tick(&g,0);assert(g.spawned==4);
    fill(0,0);g.spawn_wait=0;game_tick(&g,0);assert(g.spawned==2 && g.spawn_wait==50);
    for(unsigned t=0;t<50;t++)game_tick(&g,0);
    assert(g.spawned==2);game_tick(&g,0);assert(g.spawned==4);
    fill(256,256);g.bolts[0].life=1;game_tick(&g,0);
    assert(g.enemy_count+g.bolt_count==511 && !g.spawn_slow); // Uses surviving objects.
    fill(256,256);game_tick(&g,0);assert(g.spawn_slow);
    g.state=GAME_PAUSED;ref=g;game_tick(&g,8);assert(!memcmp(&g,&ref,sizeof(g)));
    start(&empty);game_tick(&empty,0);assert(!empty.spawn_slow);
    game_reset(&g,12345);assert(!g.spawn_slow);
    puts("ALTAR PASS POLICY TESTS PASSED: 25 ordered body pairs, A-A/C-C separation amid 268 incompatible bodies, B/D/E separation, boundary/contact/bolt/orbit, dense chase, 511/512 entry, 449/448 recovery, exact 2x spawn interval, saturation, pause/reset/independent states");
    return 0;
}
