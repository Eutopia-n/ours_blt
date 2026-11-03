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
int main(void) {
    uint32_t count=1,repeat_at=0; int32_t repeat_direction=0;
    count=demo_bench_update(count,1,1,100,&repeat_at,&repeat_direction); assert(count==2);
    assert(demo_bench_update(count,0,1,repeat_at-1,&repeat_at,&repeat_direction)==2);
    count=demo_bench_update(count,0,1,repeat_at,&repeat_at,&repeat_direction); assert(count==3);
    assert(repeat_at==100+DEMO_BENCH_REPEAT_DELAY+DEMO_BENCH_REPEAT_PERIOD);
    count=demo_bench_update(count,0,1,repeat_at+100000000u,&repeat_at,&repeat_direction);
    assert(count==4); // A slow frame does not replay many repeats at once.
    assert(demo_bench_update(count,0,0,repeat_at,&repeat_at,&repeat_direction)==4 && !repeat_direction);
    count=demo_bench_update(count,2,2,500,&repeat_at,&repeat_direction); assert(count==3);
    count=demo_bench_update(count,0,2,repeat_at,&repeat_at,&repeat_direction); assert(count==2);
    assert(demo_bench_update(1,2,2,700,&repeat_at,&repeat_direction)==1);
    assert(demo_bench_update(UINT32_MAX,1,1,800,&repeat_at,&repeat_direction)==UINT32_MAX);
    assert(demo_bench_update(100,3,3,900,&repeat_at,&repeat_direction)==100 && !repeat_direction);
    assert(demo_bench_update(100,1,3,901,&repeat_at,&repeat_direction)==100);
    count=demo_bench_update(100,1,0,1000,&repeat_at,&repeat_direction); assert(count==101); // Retained short tap.
    count=demo_bench_update(count,1,1,0xfffffff0u,&repeat_at,&repeat_direction); assert(count==102);
    assert(demo_bench_update(count,0,1,repeat_at-1,&repeat_at,&repeat_direction)==102);
    count=demo_bench_update(count,0,1,repeat_at,&repeat_at,&repeat_direction); assert(count==103);
    assert(demo_bench_update(count,0,2,repeat_at,&repeat_at,&repeat_direction)==103); // Direction change rearms delay.

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
    game_tick(&g,0); assert(g.bolt_count==GAME_MAX_BOLTS); // Full 256-projectile pool remains active.
    uint32_t alpha=128,next=0; int32_t direction=0;
    alpha=demo_alpha_update(alpha,1,1,100,&next,&direction); assert(alpha==129);
    assert(demo_alpha_update(alpha,0,1,next-1,&next,&direction)==129);
    alpha=demo_alpha_update(alpha,0,1,next,&next,&direction); assert(alpha==130);
    alpha=demo_alpha_update(alpha,4,4,500,&next,&direction); assert(alpha==129);
    alpha=demo_alpha_update(alpha,0,4,next,&next,&direction); assert(alpha==128);
    alpha=demo_alpha_update(254,1,1,700,&next,&direction); assert(alpha==255);
    alpha=demo_alpha_update(alpha,1,1,701,&next,&direction); assert(alpha==255);
    alpha=demo_alpha_update(1,4,4,800,&next,&direction); assert(alpha==0);
    alpha=demo_alpha_update(alpha,0,0,801,&next,&direction); assert(next==0 && direction==0);
    alpha=demo_alpha_update(128,1,1,0xfffffff0u,&next,&direction); assert(alpha==129);
    alpha=demo_alpha_update(alpha,0,1,next,&next,&direction); assert(alpha==130); // Timer wrap.
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
    g.spawn_wait=0; game_tick(&g,0); assert(g.enemy_count==256 && g.spawned==0);
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
	printf("GAME LOGIC TESTS PASSED: pressure +/-1 and hold/release/chord/saturation/timer wrap; MAX60 complete windows/render deadline/missed refresh/recovery/pause; Alpha +/-1; world/camera bounds, movement, diagonal, pause/return, nearest attack, collision/invulnerability, HP/max HP, healing/cap/lethal collision, elite spawn/drop, XP, all 6 capped upgrades and max effects, death/restart, 180s victory, full pools, 30000 deterministic ticks; upgrades=%u end_states=%u peak_enemies=%u\n",levels,deaths,max_enemies);
    return 0;
}
