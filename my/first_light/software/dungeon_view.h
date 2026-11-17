#include "dungeon_map.h"
static uint32_t dungeon_assets_ready;
static int32_t dungeon_camera_x,dungeon_camera_y;
static int16_t dungeon_page_camera[2][2];

static void init_dungeon_assets(void) {
    volatile uint16_t *tiles=(volatile uint16_t *)(uintptr_t)DUNGEON_TILE_BASE;
    for(uint32_t n=0;n<DUNGEON_TILE_COUNT;n++) {
        uint32_t out=0;
        for(uint32_t i=dungeon_offsets[n];i<dungeon_offsets[n+1u];i++) {
            uint32_t token=dungeon_rle[i],count=token>>6;
            uint16_t color=dungeon_palette[token&63u];
            while(count--)tiles[n*1024u+out++]=color;
        }
        if(out!=1024u)fail("FAIL dungeon asset");
    }
    // Cache only the four perimeter bands (424KiB), without a full world image.
    for(uint32_t n=0;n<DUNGEON_WALL_BANDS;n++) {
        const DungeonWallBand *band=&dungeon_wall_bands[n];
        volatile uint32_t *dst=(volatile uint32_t *)(uintptr_t)(DUNGEON_WALL_BASE+band->offset);
        for(uint32_t y=0;y<band->h;y++)for(uint32_t x=0;x<band->w;x+=2u) {
            uint32_t lo=dungeon_pixel(band->x+x,band->y+y,tiles);
            uint32_t hi=dungeon_pixel(band->x+x+1u,band->y+y,tiles);
            dst[y*(band->w/2u)+x/2u]=lo|(hi<<16);
        }
    }
    // init_game_assets publishes all CPU stores before renderer access.
    dungeon_assets_ready=1;
}
static void dungeon_draw_walls(uint32_t x,uint32_t y,uint32_t width,uint32_t height) {
    if(!dungeon_assets_ready)return;
    int32_t wx=dungeon_camera_x+(int32_t)x-GAME_X_MIN,wy=dungeon_camera_y+(int32_t)y-GAME_Y_MIN;
    for(uint32_t n=0;n<DUNGEON_WALL_BANDS;n++) {
        const DungeonWallBand *band=&dungeon_wall_bands[n];
        int32_t left=wx>band->x ? wx : band->x,top=wy>band->y ? wy : band->y;
        int32_t right=wx+(int32_t)width,bottom=wy+(int32_t)height;
        if(right>band->x+band->w)right=band->x+band->w;
        if(bottom>band->y+band->h)bottom=band->y+band->h;
        if(left>=right || top>=bottom)continue;
        uint32_t source=DUNGEON_WALL_BASE+band->offset+(uint32_t)(top-band->y)*band->stride+(uint32_t)(left-band->x)*2u;
        if(copy_image(source,band->stride,x+(uint32_t)(left-wx),y+(uint32_t)(top-wy),
                      (uint32_t)(right-left),(uint32_t)(bottom-top)))fail("FAIL wall copy");
    }
}
