/* Included after the existing dirty-rect marker; shares its per-page restore. */
#include "game_scenery.h"
static SceneryItem scenery_page_items[2][SCENERY_MAX_ITEMS];
static uint8_t scenery_page_count[2],scenery_page_valid[2];
static uint32_t scenery_assets_ready,scenery_commands;
static void init_scenery_assets(void) {
    for(uint32_t n=0;n<SCENERY_FRAME_COUNT;n++) {
        const SceneryFrame *f=&scenery_frames[n];
        volatile uint16_t *p=(volatile uint16_t *)(uintptr_t)(SCENERY_ASSET_BASE+f->offset);
        uint32_t out=0;
        for(uint32_t i=f->begin;i<f->end;i++) {
            uint32_t token=scenery_rle[i],count=token>>6;
            uint16_t color=scenery_palette[token&63u];
            while(count--)p[out++]=color;
        }
        if(out!=f->size*f->size)fail("FAIL scenery asset");
    }
    scenery_assets_ready=1;
}
static uint32_t scenery_changed(uint32_t page,const SceneryItem *items,uint32_t count) {
    if(!scenery_page_valid[page] || scenery_page_count[page]!=count)return 1;
    for(uint32_t n=0;n<count;n++) {
        const SceneryItem *a=&items[n],*b=&scenery_page_items[page][n];
        if(a->x!=b->x || a->y!=b->y || a->frame!=b->frame)return 1;
    }
    return 0;
}
static void scenery_mark_previous(uint32_t page) {
    if(!scenery_page_valid[page])return;
    uint32_t old_page=game_capture_page,old_capture=game_capture_dirty;
    game_capture_page=page;game_capture_dirty=1;
    for(uint32_t n=0;n<scenery_page_count[page];n++) {
        SceneryRect r;if(scenery_rect(&scenery_page_items[page][n],&r))
            game_record_dirty_rect(r.x,r.y,r.w,r.h);
    }
    game_capture_page=old_page;game_capture_dirty=old_capture;
}
static uint32_t scenery_hits_restore(const SceneryRect *r,const uint32_t *rows) {
    uint32_t first=(r->x-GAME_X_MIN)/GAME_DIRTY_TILE;
    uint32_t last=(r->x+r->w-1u-GAME_X_MIN)/GAME_DIRTY_TILE;
    uint32_t mask=((1u<<(last-first+1u))-1u)<<first;
    for(uint32_t y=(r->y-GAME_Y_MIN)/GAME_DIRTY_TILE;y<=(r->y+r->h-1u-GAME_Y_MIN)/GAME_DIRTY_TILE;y++)
        if(rows[y]&mask)return 1;
    return 0;
}
static void scenery_restore(uint32_t page,const SceneryItem *items,uint32_t count,uint32_t redraw,const uint32_t *rows) {
    scenery_commands=0;
    for(uint32_t n=0;n<count;n++) {
        SceneryRect r;if(!scenery_rect(&items[n],&r))continue;
        if(redraw || scenery_hits_restore(&r,rows)) {
            if(blend_image(r.source,r.stride,r.x,r.y,r.w,r.h,255,0,GFX_BLEND_KEY))fail("FAIL scenery draw");
            ++scenery_commands;
        }
        scenery_assign(&scenery_page_items[page][n],&items[n]);
    }
    scenery_page_count[page]=(uint8_t)count;scenery_page_valid[page]=1;
}
