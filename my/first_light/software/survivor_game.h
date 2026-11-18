#ifndef SURVIVOR_GAME_H
#define SURVIVOR_GAME_H
#include <stdint.h>

#define GAME_MAX_ENEMIES 384
#define GAME_MAX_BOLTS 512
#define GAME_SPAWN_SLOW_ENTER 512u
#define GAME_SPAWN_SLOW_EXIT 448u
#define GAME_SPAWN_SLOW_FACTOR 2u
#define GAME_MAX_GEMS 96
#define GAME_MAX_ORBITS 4u
#define GAME_CROWN_ATTACKERS 2u
#define GAME_CROWN_WARN_TICKS 24u
#define GAME_MAX_SPRITES (1u+GAME_MAX_ENEMIES+GAME_MAX_BOLTS+GAME_MAX_GEMS+GAME_MAX_ORBITS+2u*GAME_CROWN_ATTACKERS)
// 640x480 (4:3) stretched to a full 16:9 monitor: vertical motion x4/3.
// Set both to 1 for an aspect-preserving 4:3 display.
#define GAME_MOTION_Y_NUM 4u
#define GAME_MOTION_Y_DEN 3u
#define GAME_TICKS_PER_SECOND 60u
#define GAME_DURATION_TICKS (360u*GAME_TICKS_PER_SECOND)
#define GAME_INITIAL_XP_TARGET 20u
#define GAME_INVINCIBLE_TICKS 18u
#define GAME_X_MIN 8
#define GAME_X_MAX 632
#define GAME_Y_MIN 80
#define GAME_Y_MAX 440
#define GAME_WORLD_WIDTH 2048
#define GAME_WORLD_HEIGHT 1408
#define GAME_WORLD_X_MIN 16
#define GAME_WORLD_X_MAX (GAME_WORLD_WIDTH-16)
#define GAME_WORLD_Y_MIN 16
#define GAME_WORLD_Y_MAX (GAME_WORLD_HEIGHT-16)
enum { GAME_READY, GAME_PLAY, GAME_UPGRADE, GAME_PAUSED, GAME_OVER, GAME_WON, GAME_EXIT, GAME_ALTAR };
enum { UPGRADE_POWER, UPGRADE_RATE, UPGRADE_ORBIT, UPGRADE_SPEED, UPGRADE_MAGNET, UPGRADE_HEAL, GAME_UPGRADE_COUNT };
enum { RELIC_NONE, RELIC_ICE, RELIC_SHIELD, RELIC_DECOY };
enum { CHEST_LOCKED, CHEST_KEY_DROPPED, CHEST_KEY_HELD, CHEST_OFFER, CHEST_OPEN };
#define GAME_ALTAR_X (GAME_WORLD_WIDTH/2)
#define GAME_ALTAR_Y (GAME_WORLD_HEIGHT/2)
#define GAME_CHEST_X (GAME_WORLD_WIDTH/2+216)
#define GAME_CHEST_Y (GAME_WORLD_HEIGHT/2)
#define GAME_SHIELD_PICKUPS 8u
#define GAME_DECOY_KILLS 12u

/* flash is a short hit flash followed by a longer health-bar display window. */
typedef struct { uint16_t x,y; uint8_t hp,max_hp,kind,flash; } GameEnemy;
typedef char GameEnemyStorageSize[(sizeof(GameEnemy)==8u)?1:-1];
/* Q5 world positions fit unsigned 16 bits (the 2048-pixel world needs bit 15).
 * Velocity remains signed Q5. Tick arithmetic uses int32_t before bounds checks,
 * so crossing a world edge cannot wrap a live bolt to the opposite edge. */
typedef struct { uint16_t x,y; int16_t vx,vy; uint16_t life; uint8_t damage,pierce; } GameBolt;
typedef struct { GameBolt bolt; uint16_t slot,fire_at; } GameCrownAttack;
typedef char GameBoltStorageSize[(sizeof(GameBolt)==12u)?1:-1];
typedef char GameBoltWorldBounds[(GAME_WORLD_X_MIN>=0 && GAME_WORLD_Y_MIN>=0 &&
    GAME_WORLD_X_MAX*32<=65535 && GAME_WORLD_Y_MAX*32<=65535)?1:-1];
/* kind 0 is XP; kind 1 is a healing rune. World coordinates fit signed 16-bit. */
typedef struct { int16_t x,y; uint16_t value; uint8_t kind,pad; } GameGem;
typedef struct { int16_t x,y; uint16_t until; } GameRelicZone;
/* The pressure demo and gameplay run in separate scene loops. */
typedef union {
    uint16_t enemy_used_cells[GAME_MAX_ENEMIES];
    uint32_t bench_tile_cursor[180];
} SceneScratch;
extern SceneScratch scene_scratch;
typedef struct {
    GameEnemy enemies[GAME_MAX_ENEMIES];
    GameBolt bolts[GAME_MAX_BOLTS];
    GameCrownAttack crown[GAME_CROWN_ATTACKERS];
    GameGem gems[GAME_MAX_GEMS];
    int32_t x,y; // Q8 fixed point centres. No FPU, dynamic allocation or sqrt.
    uint32_t ticks,rng,kills,spawned,damage_taken,shots,pickups;
    uint16_t hp,max_hp,level,xp,xp_target,invincible,attack_wait,spawn_wait;
    uint16_t speed,damage,attack_period,magnet;
    uint16_t enemy_count,bolt_count,gem_count,peak_enemies,peak_sprites;
    uint8_t state,resume_state,direction,walk_frame,orbit_count,choice,options[3],moving;
    uint8_t upgrade_level[GAME_UPGRADE_COUNT],bolt_pierce,orbit_damage,regeneration,magnet_all,dash,rapid_burst;
    uint8_t spawn_slow; // Spawn-rate hysteresis, independent of drawing.
    uint8_t chest_state,relic,relic_charge,relic_slot;
    int16_t key_x,key_y;
    uint16_t relic_at;
    uint32_t decoy_next_kills;
    GameRelicZone relic_zones[2];
    // Cached Q5 separation steering, recomputed in four interleaved groups.
    int8_t enemy_steer[GAME_MAX_ENEMIES][2];
} SurvivorGame;

void game_reset(SurvivorGame *g,uint32_t seed);
void game_input(SurvivorGame *g,uint32_t held,uint32_t pressed);
void game_tick(SurvivorGame *g,uint32_t held);
void game_orbit_position(const SurvivorGame *g,uint32_t index,int32_t *x,int32_t *y);
int32_t game_camera_x(const SurvivorGame *g);
int32_t game_camera_y(const SurvivorGame *g);
int game_near_altar(const SurvivorGame *g);
uint32_t game_sprite_count(const SurvivorGame *g);
const char *game_upgrade_name(uint32_t upgrade);
const char *game_upgrade_detail(uint32_t upgrade);
uint32_t game_upgrade_max(uint32_t upgrade);
uint32_t game_upgrade_icon(uint32_t upgrade);
#endif
