#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../software/survivor_game.h"
#include "../software/demo_controls.h"
#include "../software/frame_metrics.h"
static SurvivorGame g,copy;
#define TEST_PLAYER_X (GAME_WORLD_WIDTH/2)
#define TEST_PLAYER_Y (GAME_WORLD_HEIGHT/2)
static void start(void) { game_reset(&g,12345); game_input(&g,0,16); assert(g.state==GAME_PLAY); }
static void isolate(void) {
    memset(g.enemies,0,sizeof(g.enemies)); memset(g.bolts,0,sizeof(g.bolts));
    memset(g.gems,0,sizeof(g.gems)); g.spawn_wait=60000; g.attack_wait=60000;
}
static void test_enemy_separation(void) {
    int32_t diagonal[2][2];
    for(unsigned i=0;i<2;++i) {
        start();isolate();g.ticks=3;
        g.enemies[0]=(GameEnemy){300*32,300*32,20,20,1,0};
        g.enemies[4]=(GameEnemy){317*32,317*32+(i ? 4 : -4),20,20,1,0};
        game_tick(&g,0);
        for(unsigned axis=0;axis<2;++axis) {
            diagonal[i][axis]=g.enemy_steer[0][axis];
            assert(diagonal[i][axis]<0 && diagonal[i][axis]>=-16);
            assert(g.enemy_steer[4][axis]==-diagonal[i][axis]);
        }
    }
    for(unsigned axis=0;axis<2;++axis) {
        int32_t change=diagonal[1][axis]-diagonal[0][axis];
        assert(change>=-1 && change<=1);
    }

    // The cached steering decays on each four-tick refresh after contact ends.
    g.enemies[4].hp=0;
    int32_t previous=g.enemy_steer[0][0];
    for(unsigned refresh=0;refresh<5;++refresh) {
        for(unsigned tick=0;tick<4;++tick) game_tick(&g,0);
        int32_t current=g.enemy_steer[0][0];
        assert(current==previous/2);
        previous=current;
    }
    assert(!g.enemy_steer[0][0] && !g.enemy_steer[0][1]);

    // Equal centres escape in opposite directions at the same refresh.
    start();isolate();g.ticks=3;
    g.enemies[0]=(GameEnemy){300*32,300*32,20,20,1,0};
    g.enemies[4]=g.enemies[0];
    game_tick(&g,0);
    assert(g.enemies[0].x!=g.enemies[4].x || g.enemies[0].y!=g.enemies[4].y);
    assert(g.enemy_steer[0][0]==-g.enemy_steer[4][0]);
    assert(g.enemy_steer[0][1]==-g.enemy_steer[4][1]);

    // Pack one body group at the world corner while all projectile slots run.
    start();isolate();g.orbit_count=0;g.invincible=1000;
    g.x=GAME_WORLD_X_MIN*256;g.y=GAME_WORLD_Y_MIN*256;
    for(unsigned i=0;i<GAME_MAX_ENEMIES;++i)
        g.enemies[i]=(GameEnemy){GAME_WORLD_X_MIN*32,GAME_WORLD_Y_MIN*32,20,20,1,0};
    for(unsigned i=0;i<GAME_MAX_BOLTS;++i)
        g.bolts[i]=(GameBolt){TEST_PLAYER_X*32,TEST_PLAYER_Y*32,0,0,120,1,0};
    for(unsigned tick=0;tick<96;++tick) {
        game_tick(&g,0);
        assert(g.enemy_count==GAME_MAX_ENEMIES && g.bolt_count==GAME_MAX_BOLTS);
        for(unsigned i=0;i<GAME_MAX_ENEMIES;++i) {
            assert(g.enemies[i].x>=GAME_WORLD_X_MIN*32);
            assert(g.enemies[i].y>=GAME_WORLD_Y_MIN*32);
        }
    }
    unsigned moved=0;
    for(unsigned i=0;i<GAME_MAX_ENEMIES;++i)
        if(g.enemies[i].x>GAME_WORLD_X_MIN*32 || g.enemies[i].y>GAME_WORLD_Y_MIN*32) ++moved;
    assert(moved>0);
    puts("ENEMY SEPARATION PASSED: diagonal continuity, steering decay, coincident pair, 384 enemies and 512 bolts at a world corner");
}
static void test_relics(void) {
    for(unsigned choice=0;choice<3;++choice) {
        start();isolate();g.orbit_count=0;g.x=GAME_CHEST_X*256;g.y=GAME_CHEST_Y*256;
        g.xp_target=1000;
        game_tick(&g,0);assert(g.state==GAME_PLAY && g.chest_state==CHEST_LOCKED);
        int32_t boss_x=(GAME_CHEST_X-82)*32,boss_y=GAME_CHEST_Y*32;
        g.enemies[0]=(GameEnemy){boss_x,boss_y,2,40,4,0};
        g.bolts[GAME_MAX_BOLTS-1]=(GameBolt){boss_x,boss_y,0,0,5,2,0};
        game_tick(&g,0);assert(g.kills==1 && g.chest_state==CHEST_KEY_DROPPED);
        g.x=g.key_x*256;g.y=g.key_y*256;
        game_tick(&g,0);assert(g.chest_state==CHEST_KEY_HELD && g.state==GAME_PLAY);
        g.x=GAME_CHEST_X*256;g.y=GAME_CHEST_Y*256;
        game_tick(&g,0);assert(g.state==GAME_UPGRADE && g.chest_state==CHEST_OFFER);
        uint32_t frozen=g.ticks;
        game_input(&g,0,8);assert(g.state==GAME_PAUSED);
        game_tick(&g,4);assert(g.ticks==frozen);
        game_input(&g,0,16);assert(g.state==GAME_UPGRADE && g.chest_state==CHEST_OFFER);
        for(unsigned i=0;i<choice;++i)game_input(&g,0,2);
        game_input(&g,0,16);
        assert(g.state==GAME_PLAY && g.chest_state==CHEST_OPEN && g.relic==choice+1);
        assert(g.level==1 && g.damage==2 && g.attack_period==24);
        game_tick(&g,0);assert(g.state==GAME_PLAY && g.chest_state==CHEST_OPEN);
    }

    start();isolate();g.relic=RELIC_ICE;g.chest_state=CHEST_OPEN;g.orbit_count=0;
    game_tick(&g,8);
    assert(g.relic_zones[0].x==TEST_PLAYER_X && g.relic_zones[0].until==91);
    g.enemies[0]=(GameEnemy){(TEST_PLAYER_X-14)*32,TEST_PLAYER_Y*32,8,8,0,0};
    copy=g;copy.relic=RELIC_NONE;
    game_tick(&g,8);game_tick(&copy,8);
    assert(g.enemies[0].x==(TEST_PLAYER_X-14)*32+14);
    assert(copy.enemies[0].x==g.enemies[0].x+14);
    memset(g.enemies,0,sizeof(g.enemies));
    for(unsigned i=0;i<44;++i)game_tick(&g,8);
    assert(g.relic_zones[0].until>g.ticks && g.relic_zones[1].until>g.ticks);
    for(unsigned i=0;i<90;++i)game_tick(&g,0);
    assert(g.ticks>=g.relic_zones[0].until && g.ticks>=g.relic_zones[1].until);

    start();isolate();g.relic=RELIC_SHIELD;g.xp_target=1000;
    for(unsigned i=0;i<GAME_SHIELD_PICKUPS;++i)
        g.gems[i]=(GameGem){TEST_PLAYER_X,TEST_PLAYER_Y,1,0,0};
    g.gems[GAME_SHIELD_PICKUPS]=(GameGem){TEST_PLAYER_X,TEST_PLAYER_Y,1,1,0};
    game_tick(&g,0);assert(g.relic_charge==GAME_SHIELD_PICKUPS);
    g.enemies[0]=(GameEnemy){(TEST_PLAYER_X+12)*32,TEST_PLAYER_Y*32,20,20,0,0};
    g.enemies[1]=(GameEnemy){(TEST_PLAYER_X+32)*32,TEST_PLAYER_Y*32,20,20,0,0};
    copy=g;copy.relic=RELIC_NONE;
    game_tick(&g,0);game_tick(&copy,0);
    assert(g.hp==100 && !g.damage_taken && !g.relic_charge && g.relic_at>g.ticks);
    assert(!memcmp(g.enemies,copy.enemies,sizeof(g.enemies))); // Shield consumes the hit only.
    g.invincible=0;g.enemies[0].x=(TEST_PLAYER_X+12)*32;
    game_tick(&g,0);assert(g.hp==92 && g.damage_taken==8);

    start();isolate();g.relic=RELIC_DECOY;g.orbit_count=0;
    g.kills=g.decoy_next_kills=GAME_DECOY_KILLS;
    game_tick(&g,0);assert(g.relic_zones[0].until==121 && g.decoy_next_kills==2*GAME_DECOY_KILLS);
    g.x=(TEST_PLAYER_X+80)*256;
    g.enemies[0]=(GameEnemy){(TEST_PLAYER_X+38)*32,TEST_PLAYER_Y*32,8,8,0,0};
    g.enemies[1]=(GameEnemy){(TEST_PLAYER_X+52)*32,TEST_PLAYER_Y*32,8,8,3,0};
    game_tick(&g,0);
    assert(g.enemies[0].x<(TEST_PLAYER_X+38)*32 && g.enemies[1].x>(TEST_PLAYER_X+52)*32);
    assert(!g.relic_zones[1].until);
    g.ticks=g.relic_zones[0].until;
    int32_t before=g.enemies[0].x;game_tick(&g,0);assert(g.enemies[0].x>before);
    game_reset(&g,1);assert(!g.relic && g.chest_state==CHEST_LOCKED && !g.relic_zones[0].until);
    puts("GAME RELICS PASSED: boss key, single chest and separate choices; two ice zones, shield blocks without knockback, one decoy and expiry");
}
static void test_crown_attacks(void) {
    start();isolate();g.orbit_count=0;
    g.enemies[0]=(GameEnemy){(TEST_PLAYER_X+100)*32,TEST_PLAYER_Y*32,40,40,4,0};
    g.enemies[1]=(GameEnemy){(TEST_PLAYER_X+180)*32,TEST_PLAYER_Y*32,40,40,4,0};
    g.enemies[2]=(GameEnemy){(TEST_PLAYER_X-12)*32,TEST_PLAYER_Y*32,40,40,4,0};
    g.enemies[3]=(GameEnemy){GAME_WORLD_X_MIN*32,TEST_PLAYER_Y*32,40,40,4,0};
    game_tick(&g,0);
    assert(g.crown[0].slot==1 && g.crown[1].slot==2 && g.hp==100);
    assert(g.crown[0].fire_at==g.ticks+GAME_CROWN_WARN_TICKS && !g.crown[0].bolt.life);
    for(unsigned t=0;t<GAME_CROWN_WARN_TICKS;++t)game_tick(&g,0);
    assert(g.crown[0].bolt.life && g.crown[1].bolt.life && g.crown[0].bolt.vx<0);
    for(unsigned t=0;t<30 && g.hp==100;++t)game_tick(&g,0);
    assert(g.hp==88 && g.damage_taken==12);
    g.enemies[0].x=GAME_WORLD_X_MIN*32;
    game_tick(&g,0);
    assert(!g.crown[0].slot && !g.crown[0].bolt.life);
    game_tick(&g,0);
    assert(g.crown[0].slot==3 && g.crown[1].slot==2 && !g.crown[0].bolt.life);

    start();isolate();g.orbit_count=0;
    g.enemies[0]=(GameEnemy){(TEST_PLAYER_X+150)*32,TEST_PLAYER_Y*32,40,40,4,0};
    g.enemies[1]=(GameEnemy){(TEST_PLAYER_X+200)*32,TEST_PLAYER_Y*32,40,40,4,0};
    g.crown[0]=(GameCrownAttack){{(TEST_PLAYER_X-100)*32,(TEST_PLAYER_Y-80)*32,64,0,1,12,0},1,132};
    g.crown[1]=(GameCrownAttack){{(TEST_PLAYER_X-100)*32,(TEST_PLAYER_Y+80)*32,64,0,1,12,0},2,132};
    g.enemies[0].hp=0;
    g.enemies[1].x=GAME_WORLD_X_MAX*32;
    for(unsigned i=0;i<80;++i)game_tick(&g,0);
    assert(!g.crown[0].slot && !g.crown[1].slot);
    assert(g.crown[0].bolt.life && g.crown[1].bolt.life);
    assert(g.crown[0].bolt.x==(TEST_PLAYER_X+60)*32);
    g.crown[0].bolt.x=(game_camera_x(&g)+GAME_X_MAX-GAME_X_MIN-1)*32;
    g.crown[0].bolt.vx=32;
    g.crown[1].bolt.x=TEST_PLAYER_X*32;
    g.crown[1].bolt.y=TEST_PLAYER_Y*32;
    g.invincible=8;
    game_tick(&g,0);
    assert(!g.crown[0].bolt.life && !g.crown[1].bolt.life && g.hp==100);
    puts("CROWN ATTACKS PASSED: two attackers, warning, aimed damage, owner-independent flight past 64 ticks, viewport exit and invulnerable hit");
}
static void test_max_skills_and_altar(void) {
    start();isolate();
    for(unsigned i=0;i<GAME_UPGRADE_COUNT;++i)g.upgrade_level[i]=(uint8_t)game_upgrade_max(i);
    g.upgrade_level[UPGRADE_HEAL]--;
    g.xp=g.xp_target;
    game_tick(&g,0);
    assert(g.state==GAME_UPGRADE && g.options[g.choice]==UPGRADE_HEAL);
    game_input(&g,0,16);
    assert(g.state==GAME_PLAY && g.upgrade_level[UPGRADE_HEAL]==game_upgrade_max(UPGRADE_HEAL));
    for(unsigned i=0;i<3;++i) {
        uint16_t level=g.level;
        g.xp=g.xp_target+2u;
        game_tick(&g,0);
        assert(g.state==GAME_PLAY && g.level==level+1u && g.xp==2u);
    }
    assert(game_near_altar(&g));
    uint32_t ticks=g.ticks;
    game_input(&g,0,16);assert(g.state==GAME_ALTAR);
    game_tick(&g,8);game_input(&g,8,8);
    assert(g.state==GAME_ALTAR && g.ticks==ticks && g.x==GAME_ALTAR_X*256);
    game_input(&g,0,16);assert(g.state==GAME_PLAY);
    g.x=(GAME_ALTAR_X+72)*256;
    assert(!game_near_altar(&g));
    game_input(&g,0,16);assert(g.state==GAME_PAUSED);
    game_input(&g,0,16);assert(g.state==GAME_PLAY);
    g.x=GAME_CHEST_X*256;g.chest_state=CHEST_KEY_HELD;
    game_tick(&g,0);assert(g.state==GAME_UPGRADE && g.chest_state==CHEST_OFFER);
    puts("ALTAR AND MAX SKILLS PASSED: final upgrade, continued XP, relic choice, proximity, frozen stats and resume");
}
int main(void) {
    test_enemy_separation();
    test_relics();
    test_crown_attacks();
    test_max_skills_and_altar();
    uint32_t count=1,repeat_at=0; int32_t repeat_direction=0;
    count=demo_bench_update(count,1,1,100,&repeat_at,&repeat_direction); assert(count==6);
    assert(demo_bench_update(count,0,1,repeat_at-1,&repeat_at,&repeat_direction)==6);
    count=demo_bench_update(count,0,1,repeat_at,&repeat_at,&repeat_direction); assert(count==11);
    assert(repeat_at==100+DEMO_BENCH_REPEAT_DELAY+DEMO_BENCH_REPEAT_PERIOD);
    count=demo_bench_update(count,0,1,repeat_at+100000000u,&repeat_at,&repeat_direction);
    assert(count==16); // A slow frame does not replay many repeats at once.
    assert(demo_bench_update(count,0,0,repeat_at,&repeat_at,&repeat_direction)==16 && !repeat_direction);
    count=demo_bench_update(count,2,2,500,&repeat_at,&repeat_direction); assert(count==11);
    count=demo_bench_update(count,0,2,repeat_at,&repeat_at,&repeat_direction); assert(count==6);
    assert(demo_bench_update(1,2,2,700,&repeat_at,&repeat_direction)==1);
    assert(demo_bench_update(UINT32_MAX,1,1,800,&repeat_at,&repeat_direction)==UINT32_MAX);
    assert(demo_bench_update(100,3,3,900,&repeat_at,&repeat_direction)==100 && !repeat_direction);
    assert(demo_bench_update(100,1,3,901,&repeat_at,&repeat_direction)==100);
    count=demo_bench_update(100,1,0,1000,&repeat_at,&repeat_direction); assert(count==105); // Retained short tap.
    count=demo_bench_update(count,1,1,0xfffffff0u,&repeat_at,&repeat_direction); assert(count==110);
    assert(demo_bench_update(count,0,1,repeat_at-1,&repeat_at,&repeat_direction)==110);
    count=demo_bench_update(count,0,1,repeat_at,&repeat_at,&repeat_direction); assert(count==115);
    assert(demo_bench_update(count,0,2,repeat_at,&repeat_at,&repeat_direction)==115); // Direction change rearms delay.

    FrameMax60 metrics={0};
    for(unsigned n=0;n<29;++n) frame_max60_sample(&metrics,FRAME_60_CYCLES,1,10+n);
    assert(metrics.maximum==0);
    frame_max60_sample(&metrics,FRAME_60_CYCLES,1,12); assert(metrics.maximum==38);
    for(unsigned n=0;n<30;++n) frame_max60_sample(&metrics,n==15 ? FRAME_60_CYCLES+1u : 1000,1,100);
    assert(metrics.maximum==38); // One slow render invalidates the whole window.
    for(unsigned n=0;n<30;++n) frame_max60_sample(&metrics,1000,n==12 ? 2u : 1u,200);
    assert(metrics.maximum==38); // 30 FPS must not certify its large load.
    for(unsigned n=0;n<30;++n) frame_max60_sample(&metrics,1000,n==12 ? 0u : 1u,250);
    assert(metrics.maximum==38);
    for(unsigned n=0;n<15;++n) frame_max60_sample(&metrics,1000,1,300);
    frame_max60_clear_window(&metrics); assert(metrics.maximum==38 && !metrics.frames);
    for(unsigned n=0;n<30;++n) frame_max60_sample(&metrics,1000,1,60);
    assert(metrics.maximum==60); // Clean samples recover, preserving the record across pauses.
    game_reset(&g,12345); game_input(&g,0,8); assert(g.state==GAME_READY);
    game_input(&g,0,4); assert(g.state==GAME_EXIT); // A returns from the ready page.
    game_reset(&g,12345); g.state=GAME_UPGRADE;
    game_input(&g,0,4); assert(g.state==GAME_UPGRADE); // A no longer exits an upgrade page.
    game_input(&g,0,8); assert(g.state==GAME_PAUSED && g.resume_state==GAME_UPGRADE);
    game_input(&g,0,16); assert(g.state==GAME_UPGRADE);
    start(); isolate();
    for(unsigned i=0;i<GAME_MAX_BOLTS;++i)
        g.bolts[i]=(GameBolt){TEST_PLAYER_X*32,TEST_PLAYER_Y*32,0,0,10,1,0};
    game_tick(&g,0); assert(g.bolt_count==GAME_MAX_BOLTS); // All 512 slots remain active.
    assert(sizeof(GameBolt)==12 && GAME_MAX_BOLTS==512);
    // A full pool rejects a shot without replacing a live bolt. Releasing only
    // the last slot must permit allocation beyond the former 256-slot limit.
    g.enemies[0]=(GameEnemy){(TEST_PLAYER_X+100)*32,TEST_PLAYER_Y*32,20,20,0,0};
    g.attack_wait=0;game_tick(&g,0);assert(!g.shots && g.bolt_count==GAME_MAX_BOLTS);
    g.bolts[GAME_MAX_BOLTS-1].life=0;g.attack_wait=0;game_tick(&g,0);
    assert(g.shots==1 && g.bolt_count==GAME_MAX_BOLTS);
    assert(g.bolts[GAME_MAX_BOLTS-1].life==89 && g.bolts[GAME_MAX_BOLTS-1].vx>0);
    isolate();g.enemies[0]=(GameEnemy){(TEST_PLAYER_X+100)*32,TEST_PLAYER_Y*32,20,20,0,0};
    g.bolts[GAME_MAX_BOLTS-1]=(GameBolt){(TEST_PLAYER_X+100)*32,TEST_PLAYER_Y*32,0,0,10,2,0};
    game_tick(&g,0);assert(g.enemies[0].hp==18 && !g.bolt_count);
    isolate();
    g.bolts[0]=(GameBolt){32766,20000,4,-3,10,1,0};game_tick(&g,0);
    assert(g.bolts[0].x==32770 && g.bolts[0].y==19997 && g.bolts[0].life==9);
    // Calculate in signed 32 bits before narrowing. Large test velocities must
    // expire rather than wrap into a valid coordinate on the opposite edge.
    const GameBolt edge_bolts[]={
        {GAME_WORLD_X_MIN*32,20000,-224,0,10,1,0},
        {GAME_WORLD_X_MAX*32-1,20000,224,0,10,1,0},
        {20000,GAME_WORLD_Y_MIN*32,0,-224,10,1,0},
        {20000,GAME_WORLD_Y_MAX*32-1,0,224,10,1,0},
        {GAME_WORLD_X_MAX*32-1,20000,32767,0,10,1,0},
        {GAME_WORLD_X_MIN*32,20000,-32768,0,10,1,0}};
    for(unsigned i=0;i<sizeof(edge_bolts)/sizeof(edge_bolts[0]);++i){
        isolate();g.bolts[GAME_MAX_BOLTS-1]=edge_bolts[i];game_tick(&g,0);assert(!g.bolt_count);
    }
    // Independent 32-bit trajectories preserve subpixel positions, velocities,
    // lifetimes and complete-pool counts for 100 ticks, including all 512 slots.
    static int32_t ref_x[GAME_MAX_BOLTS],ref_y[GAME_MAX_BOLTS];
    static uint16_t ref_life[GAME_MAX_BOLTS];
    isolate();
    for(unsigned i=0;i<GAME_MAX_BOLTS;++i){
        GameBolt b={(uint16_t)(600u+(i*121u)%64000u),(uint16_t)(600u+(i*79u)%43000u),
                    (int16_t)((int32_t)(i*53u%545u)-272),(int16_t)((int32_t)(i*37u%545u)-272),
                    (uint16_t)(1u+i%90u),1,0};
        g.bolts[i]=b;ref_x[i]=b.x;ref_y[i]=b.y;ref_life[i]=b.life;
    }
    for(unsigned t=0;t<100;++t){
        unsigned alive=0;game_tick(&g,0);
        for(unsigned i=0;i<GAME_MAX_BOLTS;++i){
            if(ref_life[i]){
                ref_x[i]+=g.bolts[i].vx;ref_y[i]+=g.bolts[i].vy;--ref_life[i];
                if(ref_x[i]<32*GAME_WORLD_X_MIN || ref_x[i]>=32*GAME_WORLD_X_MAX ||
                   ref_y[i]<32*GAME_WORLD_Y_MIN || ref_y[i]>=32*GAME_WORLD_Y_MAX)ref_life[i]=0;
            }
            assert(g.bolts[i].life==ref_life[i]);
            if(ref_life[i]){++alive;assert(g.bolts[i].x==ref_x[i] && g.bolts[i].y==ref_y[i]);}
        }
        assert(g.bolt_count==alive);
    }
    assert(!g.bolt_count);
    puts("BOLT CAPACITY PASSED: 256->512, 12-byte storage, full/reject/reuse/high-slot collision, signed edges, 512 independent Q5 trajectories");
    uint32_t alpha=128,next=0; int32_t direction=0;
    alpha=demo_alpha_update(alpha,1,1,100,&next,&direction); assert(alpha==133);
    assert(demo_alpha_update(alpha,0,1,next-1,&next,&direction)==133);
    alpha=demo_alpha_update(alpha,0,1,next,&next,&direction); assert(alpha==138);
    alpha=demo_alpha_update(alpha,4,4,500,&next,&direction); assert(alpha==133);
    alpha=demo_alpha_update(alpha,0,4,next,&next,&direction); assert(alpha==128);
    alpha=demo_alpha_update(254,1,1,700,&next,&direction); assert(alpha==255);
    alpha=demo_alpha_update(alpha,1,1,701,&next,&direction); assert(alpha==255);
    alpha=demo_alpha_update(1,4,4,800,&next,&direction); assert(alpha==0);
    alpha=demo_alpha_update(alpha,0,0,801,&next,&direction); assert(next==0 && direction==0);
    alpha=demo_alpha_update(128,1,1,0xfffffff0u,&next,&direction); assert(alpha==133);
    alpha=demo_alpha_update(alpha,0,1,next,&next,&direction); assert(alpha==138); // Timer wrap.
    start(); assert(g.hp==100 && g.x==TEST_PLAYER_X*256 && g.level==1);
    assert(game_camera_x(&g)==TEST_PLAYER_X-312 && game_camera_y(&g)==TEST_PLAYER_Y-180);
    isolate(); int32_t before=g.x;
    for(int i=0;i<10;++i) game_tick(&g,8);
    assert(g.x==before+10*512 && g.direction==2 && g.walk_frame==1);
    assert(game_camera_x(&g)==TEST_PLAYER_X-312+20);
    game_tick(&g,0); assert(!g.moving && !g.walk_frame);
    for(int i=0;i<1000;++i) game_tick(&g,10);
    assert(g.x==(GAME_WORLD_X_MAX-16)*256 && g.y==(GAME_WORLD_Y_MAX-16)*256);
    assert(game_camera_x(&g)==GAME_WORLD_WIDTH-(GAME_X_MAX-GAME_X_MIN));
    assert(game_camera_y(&g)==GAME_WORLD_HEIGHT-(GAME_Y_MAX-GAME_Y_MIN));
    game_input(&g,0,16); assert(g.state==GAME_PAUSED);
    before=g.ticks; game_tick(&g,8); assert((int32_t)g.ticks==before);
    game_input(&g,0,16); assert(g.state==GAME_PLAY);
    game_input(&g,0,16); assert(g.state==GAME_PAUSED);
    game_input(&g,0,16); assert(g.state==GAME_PLAY);
    game_input(&g,0,16); assert(g.state==GAME_PAUSED);
    game_input(&g,0,8); assert(g.state==GAME_PAUSED);
    game_input(&g,0,4); assert(g.state==GAME_EXIT);
    start(); isolate(); g.enemies[0]=(GameEnemy){TEST_PLAYER_X*32,TEST_PLAYER_Y*32,20,20,0,0};
    game_tick(&g,0); assert(g.hp==92 && g.invincible==GAME_INVINCIBLE_TICKS);
    game_tick(&g,0); assert(g.hp==92 && g.invincible==GAME_INVINCIBLE_TICKS-1);
    g.invincible=0; g.hp=1; g.ticks=GAME_DURATION_TICKS-1;
    game_tick(&g,0); assert(g.state==GAME_OVER); // Death precedence.
    game_input(&g,0,16); assert(g.state==GAME_PLAY && g.hp==100 && g.kills==0);
    isolate(); g.ticks=GAME_DURATION_TICKS-1; game_tick(&g,0); assert(g.state==GAME_WON);
    start(); isolate(); g.gems[0]=(GameGem){TEST_PLAYER_X,TEST_PLAYER_Y,22,0,0};
    game_tick(&g,0); assert(g.state==GAME_UPGRADE && g.level==2 && g.xp==2 && g.xp_target==32);
    assert(g.options[0]!=g.options[1] && g.options[1]!=g.options[2]);
    before=g.ticks; game_tick(&g,8); assert((int32_t)g.ticks==before);
    game_input(&g,0,8); assert(g.state==GAME_PAUSED && g.resume_state==GAME_UPGRADE);
    game_input(&g,0,16); assert(g.state==GAME_UPGRADE);
    for(unsigned kind=0;kind<6;++kind) {
        g.state=GAME_UPGRADE; g.choice=0; g.options[0]=(uint8_t)kind;
        uint16_t old_power=g.damage,old_period=g.attack_period,old_speed=g.speed;
        uint16_t old_magnet=g.magnet,old_hp=g.max_hp; uint8_t old_orbits=g.orbit_count;
        game_input(&g,0,16); assert(g.state==GAME_PLAY);
        if(kind==0) assert(g.damage==old_power+1 && g.upgrade_level[kind]==1);
        if(kind==1) assert(g.attack_period==old_period-2);
        if(kind==2) assert(g.orbit_count==old_orbits+1 && g.upgrade_level[kind]==1);
        if(kind==3) assert(g.speed==old_speed+64);
		if(kind==4) assert(g.magnet==old_magnet+24);
        if(kind==5) assert(g.max_hp==old_hp+10 && g.hp<=g.max_hp);
    }
	// Max levels add a distinct behavior, then stop upgrading at the cap.
	start(); isolate();
	for(unsigned n=0;n<5;++n) { g.state=GAME_UPGRADE; g.choice=0; g.options[0]=UPGRADE_POWER; game_input(&g,0,16); }
	assert(g.upgrade_level[UPGRADE_POWER]==5 && g.bolt_pierce==2 && g.damage>=9);
	g.state=GAME_UPGRADE; g.choice=0; g.options[0]=UPGRADE_POWER; game_input(&g,0,16);
	assert(g.state==GAME_PLAY && g.upgrade_level[UPGRADE_POWER]==5);
	for(unsigned n=0;n<5;++n) { g.state=GAME_UPGRADE; g.choice=0; g.options[0]=UPGRADE_RATE; game_input(&g,0,16); }
	assert(g.rapid_burst && g.upgrade_level[UPGRADE_RATE]==5);
	isolate(); g.attack_wait=0;
	g.enemies[0]=(GameEnemy){(TEST_PLAYER_X+80)*32,TEST_PLAYER_Y*32,20,20,0,0};
	game_tick(&g,0);
	assert(g.shots==2 && g.bolt_count==2 &&
	       g.bolts[0].vy==-g.bolts[1].vy && g.bolts[0].vy!=0);
	for(unsigned n=0;n<4;++n) { g.state=GAME_UPGRADE; g.choice=0; g.options[0]=UPGRADE_ORBIT; game_input(&g,0,16); }
	assert(g.orbit_count==4 && g.orbit_damage==2 && g.upgrade_level[UPGRADE_ORBIT]==4);
	for(unsigned n=0;n<5;++n) { g.state=GAME_UPGRADE; g.choice=0; g.options[0]=UPGRADE_SPEED; game_input(&g,0,16); }
	assert(g.dash && g.upgrade_level[UPGRADE_SPEED]==5);
	for(unsigned n=0;n<5;++n) { g.state=GAME_UPGRADE; g.choice=0; g.options[0]=UPGRADE_MAGNET; game_input(&g,0,16); }
	assert(g.magnet_all && g.magnet==240 && g.upgrade_level[UPGRADE_MAGNET]==5);
	for(unsigned n=0;n<3;++n) { g.state=GAME_UPGRADE; g.choice=0; g.options[0]=UPGRADE_HEAL; game_input(&g,0,16); }
	assert(g.regeneration && g.max_hp==150 && g.upgrade_level[UPGRADE_HEAL]==3);
	g.hp=80; g.state=GAME_PLAY; g.ticks=59; isolate(); game_tick(&g,0); assert(g.hp==81);
    start(); isolate(); g.hp=50; g.x=TEST_PLAYER_X*256; g.y=TEST_PLAYER_Y*256;
    g.gems[0]=(GameGem){TEST_PLAYER_X,TEST_PLAYER_Y,1,1,0}; game_tick(&g,0);
    assert(g.hp==75 && g.xp==1 && g.pickups==1); // Healing rune plus XP.
    g.gems[0]=(GameGem){TEST_PLAYER_X,TEST_PLAYER_Y,1,1,0}; g.hp=99; game_tick(&g,0); assert(g.hp==100);
    start(); isolate(); g.hp=1;
    g.enemies[0]=(GameEnemy){TEST_PLAYER_X*32,TEST_PLAYER_Y*32,20,20,0,0};
    g.gems[0]=(GameGem){TEST_PLAYER_X,TEST_PLAYER_Y,1,1,0}; game_tick(&g,0);
    assert(g.state==GAME_OVER && g.hp==0); // A pickup must not undo lethal collision.
    start(); isolate(); g.ticks=3599;
    for(int i=0;i<24;++i) { g.spawn_wait=0; game_tick(&g,0); }
    unsigned elites=0;
    for(int i=0;i<GAME_MAX_ENEMIES;++i) if(g.enemies[i].kind==3 && g.enemies[i].hp) {
        elites++; assert(g.enemies[i].hp<=g.enemies[i].max_hp && g.enemies[i].max_hp==12);
    }
    assert(elites>0);
    unsigned healing_drops=0;
    for(int trial=0;trial<32;++trial) {
        start(); isolate(); g.rng=(uint32_t)(trial+1);
        g.enemies[0]=(GameEnemy){(TEST_PLAYER_X+180)*32,(TEST_PLAYER_Y-60)*32,1,12,3,0};
        g.bolts[0]=(GameBolt){(TEST_PLAYER_X+180)*32,(TEST_PLAYER_Y-60)*32,0,0,5,2,0}; game_tick(&g,0);
        assert(g.kills==1 && g.gems[0].value==5);
        healing_drops+=g.gems[0].kind;
    }
    assert(healing_drops>0 && healing_drops<32);
	unsigned guardians=0;
	for(unsigned trial=0;trial<128 && !guardians;++trial) {
		start(); isolate(); g.ticks=8u*15u*60u-1u; g.rng=trial+1; g.spawn_wait=0;
		game_tick(&g,0);
		for(unsigned i=0;i<GAME_MAX_ENEMIES;++i) if(g.enemies[i].hp && g.enemies[i].kind==4) {
			guardians++; assert(g.enemies[i].max_hp>=28);
		}
	}
	assert(guardians>0); // The late wave includes rare high-HP guardians.
    start(); isolate(); g.attack_wait=0;
    g.enemies[0]=(GameEnemy){(TEST_PLAYER_X+60)*32,TEST_PLAYER_Y*32,2,2,0,0};
    g.enemies[1]=(GameEnemy){(TEST_PLAYER_X+260)*32,TEST_PLAYER_Y*32,20,20,1,0};
    game_tick(&g,0); assert(g.shots==1 && g.bolts[0].vx>0 && g.bolts[0].vy==0);
    for(int i=0;i<18 && !g.kills;++i) game_tick(&g,0);
    assert(g.kills>=1 && g.gem_count>=1);
    start(); isolate();
    g.enemies[0]=(GameEnemy){(TEST_PLAYER_X+100)*32,TEST_PLAYER_Y*32,20,20,0,0};
    g.bolts[0]=(GameBolt){(TEST_PLAYER_X+100)*32,TEST_PLAYER_Y*32,0,0,10,2,0};
    g.bolt_count=1; game_tick(&g,0);
    assert(g.enemies[0].hp==18 && g.enemies[0].flash==90);
    game_tick(&g,0); assert(g.enemies[0].flash==89);
    start(); isolate();
    for(int i=0;i<GAME_MAX_GEMS;++i) g.gems[i]=(GameGem){40,120,1,0,0};
    g.enemies[0]=(GameEnemy){(TEST_PLAYER_X+180)*32,(TEST_PLAYER_Y-60)*32,1,1,0,0};
    g.bolts[0]=(GameBolt){(TEST_PLAYER_X+180)*32,(TEST_PLAYER_Y-60)*32,0,0,5,2,0};
    game_tick(&g,0); unsigned total=0;
    for(int i=0;i<GAME_MAX_GEMS;++i) total+=g.gems[i].value;
    assert(total==GAME_MAX_GEMS+1 && g.kills==1); // Pool saturation preserves XP.
    start(); isolate();
    for(int i=0;i<GAME_MAX_ENEMIES;++i) g.enemies[i]=(GameEnemy){40*32,120*32,20,20,0,0};
    g.spawn_wait=0; game_tick(&g,0); assert(g.enemy_count==384 && g.spawned==0);
    start(); copy=g;
    unsigned deaths=0,levels=0,max_enemies=0;
    for(unsigned t=0;t<30000;++t) {
        uint32_t keys=(t/90)%4==0 ? 8 : (t/90)%4==1 ? 2 : (t/90)%4==2 ? 4 : 1;
        if(g.state==GAME_UPGRADE) { levels++; game_input(&g,0,16); game_input(&copy,0,16); }
        if(g.state==GAME_OVER || g.state==GAME_WON) { deaths++; game_input(&g,0,16); game_input(&copy,0,16); }
        game_tick(&g,keys); game_tick(&copy,keys); assert(memcmp(&g,&copy,sizeof(g))==0);
        if(g.enemy_count>max_enemies) max_enemies=g.enemy_count;
        assert(g.enemy_count<=GAME_MAX_ENEMIES && g.bolt_count<=GAME_MAX_BOLTS && g.gem_count<=GAME_MAX_GEMS);
    assert(g.hp<=g.max_hp && g.x>0 && g.y>0 && g.x/256<GAME_WORLD_WIDTH && g.y/256<GAME_WORLD_HEIGHT);
    }
	printf("GAME LOGIC TESTS PASSED: pressure +/-5 and hold/release/chord/saturation/timer wrap; MAX60 complete windows/render deadline/missed refresh/recovery/pause; Alpha +/-5; world/camera bounds, movement, diagonal, pause/return, nearest attack, collision/invulnerability, HP/max HP, healing/cap/lethal collision, elite spawn/drop, XP, all 6 capped upgrades and max effects, death/restart, 360s victory, full pools, 30000 deterministic ticks; upgrades=%u end_states=%u peak_enemies=%u\n",levels,deaths,max_enemies);
    return 0;
}
