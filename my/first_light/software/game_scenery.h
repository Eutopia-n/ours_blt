#ifndef GAME_SCENERY_H
#define GAME_SCENERY_H
#include "survivor_game.h"
#include "scenery_assets.h"
#define SCENERY_MAX_ITEMS 1u
typedef struct {int16_t x,y;uint16_t frame;} SceneryItem;
typedef struct {uint16_t x,y,w,h;uint32_t source,stride;} SceneryRect;
static void scenery_assign(SceneryItem *to,const SceneryItem *from) {
    // Explicit scalar stores avoid an implicit libc memcpy in freestanding RV32.
    volatile SceneryItem *p=to;p->x=from->x;p->y=from->y;p->frame=from->frame;
}
static uint32_t scenery_rect(const SceneryItem *item,SceneryRect *r) {
    const SceneryFrame *f=&scenery_frames[item->frame];
    int32_t origin_x=item->x-f->size/2,origin_y=item->y-f->size/2;
    int32_t left=origin_x+f->left,top=origin_y+f->top;
    int32_t right=origin_x+f->right,bottom=origin_y+f->bottom;
    if(left<GAME_X_MIN)left=GAME_X_MIN;
    if(top<GAME_Y_MIN)top=GAME_Y_MIN;
    if(right>GAME_X_MAX)right=GAME_X_MAX;
    if(bottom>GAME_Y_MAX)bottom=GAME_Y_MAX;
    if(left>=right || top>=bottom)return 0;
    r->x=(uint16_t)left;r->y=(uint16_t)top;r->w=(uint16_t)(right-left);r->h=(uint16_t)(bottom-top);
    r->stride=f->size*2u;
    r->source=SCENERY_ASSET_BASE+f->offset+(uint32_t)(top-origin_y)*r->stride+(uint32_t)(left-origin_x)*2u;
    return 1;
}
static uint32_t scenery_select(int32_t camera_x,int32_t camera_y,uint32_t ticks,SceneryItem *items) {
    (void)ticks;uint32_t count=0;
    SceneryItem altar={(int16_t)(GAME_X_MIN+GAME_WORLD_WIDTH/2-camera_x),
                       (int16_t)(GAME_Y_MIN+GAME_WORLD_HEIGHT/2-camera_y),SCENERY_ALTAR};
    SceneryRect rect;if(scenery_rect(&altar,&rect))scenery_assign(&items[count++],&altar);
    return count;
}
#endif
