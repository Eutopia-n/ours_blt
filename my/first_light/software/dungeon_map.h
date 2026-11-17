/* Immutable perimeter bands. The map interior is the original solid colour. */
#ifndef DUNGEON_MAP_H
#define DUNGEON_MAP_H
#include "survivor_game.h"
#include "dungeon_assets.h"
#define DUNGEON_WALL_BASE (ASSET_BASE+0x40000u)
#define DUNGEON_WALL_BYTES 434176u
#define DUNGEON_WALL_BANDS 4u
#define DUNGEON_BACKGROUND 0x1085u
typedef struct {uint16_t x,y,w,h;uint32_t offset,stride;} DungeonWallBand;
static const DungeonWallBand dungeon_wall_bands[DUNGEON_WALL_BANDS]={
    {0,0,2048,32,0,4096},
    {0,1376,2048,32,131072,4096},
    {0,32,32,1344,262144,64},
    {2016,32,32,1344,348160,64}
};
static inline uint32_t dungeon_view_has_walls(int32_t x,int32_t y) {
    return x<32 || y<32 || x+GAME_X_MAX-GAME_X_MIN>GAME_WORLD_WIDTH-32 ||
           y+GAME_Y_MAX-GAME_Y_MIN>GAME_WORLD_HEIGHT-32;
}
static uint16_t dungeon_pixel(uint32_t x,uint32_t y,const volatile uint16_t *tiles) {
    uint32_t tile,tx=x&31u,ty=y&31u;
    if(y<32u)tile=x<32u ? 4u : x>=GAME_WORLD_WIDTH-32u ? 5u : 0u;
    else if(y>=GAME_WORLD_HEIGHT-32u)tile=x<32u ? 6u : x>=GAME_WORLD_WIDTH-32u ? 7u : 1u;
    else if(x<32u)tile=2u;
    else if(x>=GAME_WORLD_WIDTH-32u)tile=3u;
    else return DUNGEON_BACKGROUND;
    return tiles[tile*1024u+ty*32u+tx];
}
#endif
