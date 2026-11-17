/* Game presentation reuses main.c's existing renderer, font and frame swap.
 * Logic stays in survivor_game.c so it can be tested without FPGA registers.
 */
#include "survivor_game.h"
#include "game_assets.h"
#include "game_frame_bounds.h"
#include "game_art_ids.h"
#define GAME_ASSET_BASE (ASSET_BASE+0x4000u)
#define GAME_BACKGROUND_COLOR 0x1085u
#define GAME_MAX_DRAW_ENEMIES GAME_MAX_ENEMIES
#define GAME_MAX_DRAW_GEMS 20u
#define GAME_MAX_DRAW_BOLTS GAME_MAX_BOLTS
#define GAME_VIEW_WIDTH (GAME_X_MAX-GAME_X_MIN)
#define GAME_VIEW_HEIGHT (GAME_Y_MAX-GAME_Y_MIN)
#define GAME_DIRTY_TILE 32u
#define GAME_DIRTY_COLS ((GAME_VIEW_WIDTH+GAME_DIRTY_TILE-1u)/GAME_DIRTY_TILE)
#define GAME_DIRTY_ROWS ((GAME_VIEW_HEIGHT+GAME_DIRTY_TILE-1u)/GAME_DIRTY_TILE)
typedef struct { uint8_t first,last,top,bottom; } GameDirtyRect;
static SurvivorGame survivor;
static uint32_t game_assets_ready;
static uint8_t game_page_valid[2],game_page_playing[2],game_dirty_valid[2];
/* One bit per 32x32 tile. Keeping separated runs avoids clearing the empty
 * space between distant sprites in the same scanline. */
static uint32_t game_page_dirty[2][GAME_DIRTY_ROWS];
static uint32_t game_capture_page,game_capture_dirty;
static uint32_t game_hud_pages,game_hud_number_valid[2],game_hud_bar_valid[2];
/* Game and pressure pages share these 24 HUD number cache entries. The atlas
 * reuse in main.c now leaves enough on-chip RAM for this 96-byte CPU-only
 * cache, avoiding DDR reads/stores while the video engine is fetching lines. */
static uint32_t game_hud_numbers[2][12];
static FrameMax60 game_max60;
static uint32_t game_draw_floor_cycles,game_draw_sprite_cycles,game_draw_other_cycles;
static uint32_t game_draw_enemy_count;
// One shared selection for both framebuffer pages; no per-page alternation.
static uint32_t game_gem_selected[(GAME_MAX_GEMS+31u)/32u];
static uint32_t game_sprite(uint32_t frame,int32_t x,int32_t y,uint32_t alpha);
static void game_record_dirty_rect(uint32_t x,uint32_t y,uint32_t width,uint32_t height) {
    if(!game_capture_dirty || !width || !height) return;
    if(x<GAME_X_MIN || y<GAME_Y_MIN || x>=GAME_X_MAX || y>=GAME_Y_MAX) return;
    uint32_t first_row=(y-GAME_Y_MIN)/GAME_DIRTY_TILE;
    uint32_t last_row=(y+height-1u-GAME_Y_MIN)/GAME_DIRTY_TILE;
    uint32_t first_col=(x-GAME_X_MIN)/GAME_DIRTY_TILE;
    uint32_t last_col=(x+width-1u-GAME_X_MIN)/GAME_DIRTY_TILE;
    if(last_col>=GAME_DIRTY_COLS) last_col=GAME_DIRTY_COLS-1u;
    if(last_row>=GAME_DIRTY_ROWS) last_row=GAME_DIRTY_ROWS-1u;
    uint32_t col_mask=((1u<<(last_col-first_col+1u))-1u)<<first_col;
    for(uint32_t row=first_row;row<=last_row;++row) {
        game_page_dirty[game_capture_page][row]|=col_mask;
    }
    game_dirty_valid[game_capture_page]=1;
}
static uint32_t game_bolt(const GameBolt *b,int32_t camera_x,int32_t camera_y) {
    int32_t sx=GAME_X_MIN+b->x/32-camera_x,sy=GAME_Y_MIN+b->y/32-camera_y;
    uint32_t size=b->pierce ? 7u : 5u;
    if(sx<(int32_t)GAME_X_MIN || sx>=(int32_t)GAME_X_MAX ||
       sy<(int32_t)GAME_Y_MIN || sy>=(int32_t)GAME_Y_MAX) return 0;
    int32_t left=sx-(int32_t)(size/2u),top=sy-(int32_t)(size/2u);
    if(left<(int32_t)GAME_X_MIN) left=GAME_X_MIN;
    if(top<(int32_t)GAME_Y_MIN) top=GAME_Y_MIN;
    if(left+(int32_t)size>(int32_t)GAME_X_MAX) left=GAME_X_MAX-(int32_t)size;
    if(top+(int32_t)size>(int32_t)GAME_Y_MAX) top=GAME_Y_MAX-(int32_t)size;
    uint32_t x=(uint32_t)left,y=(uint32_t)top;
    // Concentric RGB565 fills keep a white core and fade to the original
    // cyan/yellow edge without a texture or background reads. Keep the tiny
    // 5x5/7x7 bodies on the packed CPU-store path; game_draw publishes once
    // after all bullets, leaving the raster engine for larger sprites.
    cpu_fill(x,y,size,size,b->pierce ? 0xffe0 : 0x07ff);
    cpu_fill(x+1u,y+1u,size-2u,size-2u,b->pierce ? 0xffea : 0x87ff);
    if(b->pierce) cpu_fill(x+2u,y+2u,3u,3u,0xfff5);
    cpu_fill(x+size/2u,y+size/2u,1u,1u,0xffff);
    game_record_dirty_rect(x,y,size,size);
    return 1;
}

static uint32_t game_world_sprite(const SurvivorGame *g,uint32_t frame,int32_t x,int32_t y,uint32_t alpha) {
    return game_sprite(frame,GAME_X_MIN+x-game_camera_x(g),GAME_Y_MIN+y-game_camera_y(g),alpha);
}

static void init_game_assets(void) {
    for(uint32_t frame=0;frame<GAME_FRAME_COUNT;++frame) {
        volatile uint16_t *p=(volatile uint16_t *)(uintptr_t)(GAME_ASSET_BASE+frame*2048u);
        uint32_t out=0;
        for(uint32_t at=game_offsets[frame];at<game_offsets[frame+1];++at) {
            uint32_t token=game_rle[at],count=token>>10;
            uint16_t color=game_palette[token&1023u];
            while(count--) p[out++]=color;
        }
        if(out!=32u*32u) fail("FAIL game asset");
    }
    // The game uses a solid fill; no scenery, wall cache or background tiles
    // are decompressed into DDR or linked into the on-chip firmware.
    publish_pixels();
    game_assets_ready=1;
}
static void game_fill_background_rect(uint32_t x,uint32_t y,uint32_t width,uint32_t height) {
    if(!width || !height)return;
    paint(x,y,width,height,GAME_BACKGROUND_COLOR,1);
}
static void game_restore_dirty_tiles(uint32_t page) {
    GameDirtyRect active[GAME_DIRTY_COLS],next[GAME_DIRTY_COLS];
    uint32_t active_count=0;
    for(uint32_t row=0;row<GAME_DIRTY_ROWS;++row) {
        uint32_t bits=game_page_dirty[page][row],used=0,next_count=0;
        while(bits) {
            uint32_t first=0;
            while(first<GAME_DIRTY_COLS && !(bits&(1u<<first))) ++first;
            if(first==GAME_DIRTY_COLS) break;
            uint32_t last=first;
            while(last+1u<GAME_DIRTY_COLS && (bits&(1u<<(last+1u)))) ++last;
            uint32_t run=((1u<<(last-first+1u))-1u)<<first;
            uint32_t match=active_count;
            for(uint32_t i=0;i<active_count;++i)
                if(active[i].first==first && active[i].last==last) { match=i; break; }
            if(match<active_count) {
                next[next_count]=active[match];
                next[next_count].bottom=(uint8_t)(row+1u);
                used|=1u<<match;
            } else {
                next[next_count]=(GameDirtyRect){(uint8_t)first,(uint8_t)last,
                                                  (uint8_t)row,(uint8_t)(row+1u)};
            }
            ++next_count;
            bits&=~run;
        }
        for(uint32_t i=0;i<active_count;++i) if(!(used&(1u<<i))) {
            uint32_t x=GAME_X_MIN+(uint32_t)active[i].first*GAME_DIRTY_TILE;
            uint32_t right=GAME_X_MIN+((uint32_t)active[i].last+1u)*GAME_DIRTY_TILE;
            uint32_t y=GAME_Y_MIN+(uint32_t)active[i].top*GAME_DIRTY_TILE;
            uint32_t bottom=GAME_Y_MIN+(uint32_t)active[i].bottom*GAME_DIRTY_TILE;
            if(right>GAME_X_MAX) right=GAME_X_MAX;
            if(bottom>GAME_Y_MAX) bottom=GAME_Y_MAX;
            game_fill_background_rect(x,y,right-x,bottom-y);
        }
        for(uint32_t i=0;i<next_count;++i) active[i]=next[i];
        active_count=next_count;
    }
    for(uint32_t i=0;i<active_count;++i) {
        uint32_t x=GAME_X_MIN+(uint32_t)active[i].first*GAME_DIRTY_TILE;
        uint32_t right=GAME_X_MIN+((uint32_t)active[i].last+1u)*GAME_DIRTY_TILE;
        uint32_t y=GAME_Y_MIN+(uint32_t)active[i].top*GAME_DIRTY_TILE;
        uint32_t bottom=GAME_Y_MIN+(uint32_t)active[i].bottom*GAME_DIRTY_TILE;
        if(right>GAME_X_MAX) right=GAME_X_MAX;
        if(bottom>GAME_Y_MAX) bottom=GAME_Y_MAX;
        game_fill_background_rect(x,y,right-x,bottom-y);
    }
}
static void game_draw_world_floor(uint32_t page,int32_t camera_x,int32_t camera_y,uint32_t playing,uint32_t ticks) {
    // Camera movement cannot change a uniform background. Keep per-page dirty
    // restoration so moving and translucent sprites still leave no trails.
    (void)camera_x;(void)camera_y;(void)ticks;
    uint32_t full=!game_page_valid[page] || (playing && !game_page_playing[page]);
    uint32_t area=0;
    if(!full && game_dirty_valid[page]) {
        for(uint32_t row=0;row<GAME_DIRTY_ROWS;++row) {
            uint32_t bits=game_page_dirty[page][row];
            uint32_t y=GAME_Y_MIN+row*GAME_DIRTY_TILE;
            uint32_t height=y+GAME_DIRTY_TILE>GAME_Y_MAX ? GAME_Y_MAX-y : GAME_DIRTY_TILE;
            for(uint32_t col=0;col<GAME_DIRTY_COLS;++col) if(bits&(1u<<col)) {
                uint32_t x=GAME_X_MIN+col*GAME_DIRTY_TILE;
                uint32_t width=x+GAME_DIRTY_TILE>GAME_X_MAX ? GAME_X_MAX-x : GAME_DIRTY_TILE;
                area+=width*height;
            }
        }
        if(area*4u>=(GAME_VIEW_WIDTH*GAME_VIEW_HEIGHT*3u)) full=1;
    }
    if(full) {
        game_fill_background_rect(GAME_X_MIN,GAME_Y_MIN,GAME_VIEW_WIDTH,GAME_VIEW_HEIGHT);
    } else if(game_dirty_valid[page]) {
        game_restore_dirty_tiles(page);
    }
    game_page_valid[page]=1; game_page_playing[page]=(uint8_t)(playing!=0);
    game_dirty_valid[page]=0;
    for(uint32_t row=0;row<GAME_DIRTY_ROWS;++row) game_page_dirty[page][row]=0;
    // Track foreground pixels even while paused/upgrading. Re-blending alpha
    // sprites over an uncleared old page otherwise accumulates their colors.
    game_capture_page=page; game_capture_dirty=1;
}
static void game_prime_framebuffers(void) {
    // Seed both pages with a solid navy-gray base before the game starts.
    for(uint32_t page=0;page<2;++page) {
        paint(0,0,640,480,GAME_BACKGROUND_COLOR,1);
        if(present_frame()) fail("FAIL game page present");
    }
    game_page_valid[0]=game_page_valid[1]=0;
    game_page_playing[0]=game_page_playing[1]=0;
    game_dirty_valid[0]=game_dirty_valid[1]=0;
    game_hud_pages=0;
    for(uint32_t word=0;word<(GAME_MAX_GEMS+31u)/32u;++word)game_gem_selected[word]=0;
    for(uint32_t page=0;page<2;++page) {
        game_hud_number_valid[page]=0;
        game_hud_bar_valid[page]=0;
    }
}
static uint32_t game_sprite(uint32_t frame,int32_t x,int32_t y,uint32_t alpha) {
    /* Keep an invalid animation index from turning into an apparently missing
     * enemy. All current enemy and player frames are in this atlas; the guard
     * also protects future wave additions from reading outside DDR. */
    if(!game_assets_ready) return 0;
    if(frame>=GAME_FRAME_COUNT) frame=16u;
    // Keep the original centre/scale and 64-byte atlas pitch. Only submit the
    // rectangle containing non-key pixels; outer transparent rows/columns never
    // need to reach DDR/Alpha. Empty frames and clipped bounds issue no command.
    const uint8_t *bounds=game_frame_bounds[frame];
    int32_t frame_left=x-16,frame_top=y-16;
    int32_t left=frame_left+bounds[0],top=frame_top+bounds[1];
    int32_t right=frame_left+bounds[2],bottom=frame_top+bounds[3];
    int32_t x0=left<GAME_X_MIN ? GAME_X_MIN : left;
    int32_t y0=top<GAME_Y_MIN ? GAME_Y_MIN : top;
    int32_t x1=right>GAME_X_MAX ? GAME_X_MAX : right;
    int32_t y1=bottom>GAME_Y_MAX ? GAME_Y_MAX : bottom;
    if(x0>=x1 || y0>=y1) return 0;
    uint32_t source=GAME_ASSET_BASE+frame*2048u+(uint32_t)(y0-frame_top)*64u+(uint32_t)(x0-frame_left)*2u;
    if(blend_image(source,64,(uint32_t)x0,(uint32_t)y0,(uint32_t)(x1-x0),(uint32_t)(y1-y0),
                   (uint8_t)alpha,0,GFX_BLEND_ALPHA|GFX_BLEND_KEY)) fail("FAIL game sprite");
    game_record_dirty_rect((uint32_t)x0,(uint32_t)y0,(uint32_t)(x1-x0),(uint32_t)(y1-y0));
    return 1;
}
static void __attribute__((unused)) game_hud_number(uint32_t page,uint32_t index,uint32_t x,uint32_t y,
                            uint32_t width,uint32_t value,uint16_t color) {
    uint32_t bit=1u<<index;
    if((game_hud_number_valid[page]&bit) && game_hud_numbers[page][index]==value) return;
    // Draw an opaque digit cell with aligned 32-bit stores, clearing old digits
    // in the same pass. All callers use an even x and a multiple-of-12 width.
    char number[11]; decimal_field(number,value,width/12u);
    uint32_t ink=(uint32_t)color|((uint32_t)color<<16);
    // Finish each scanline before moving to the next one. Alternating two DDR
    // rows for every pixel pair causes unnecessary cache/bus traffic at entry.
    for(uint32_t row=0;row<14;++row) {
        volatile uint32_t *dst=(volatile uint32_t *)(uintptr_t)
            (draw_buffer+(y+row)*FRAME_STRIDE+x*2u);
        const char *digit=number;
        for(uint32_t cell=0;cell<width/12u;++cell) {
            uint32_t c=(uint32_t)(uint8_t)*digit;
            if(c) ++digit;
            for(uint32_t col=0;col<6;++col) {
                uint32_t pixel=col<5 && (font_column(c,col)&(1u<<(row/2u))) ? ink : 0x10a610a6u;
                dst[cell*6u+col]=pixel;
            }
        }
    }
    game_hud_numbers[page][index]=value;
    game_hud_number_valid[page]|=bit;
}
#include "reference_game_ui.h"
static uint32_t game_enemy_frame(uint32_t kind,uint32_t ticks,uint32_t slot) {
    // Shared two-frame animation: no animation state per enemy and no new pool.
    static const uint8_t frames[2][5]={GAME_ART_ENEMY_IDLE,GAME_ART_ENEMY_STEP};
    uint32_t phase=kind==2u ? ticks/6u:ticks/12u;
    return frames[(phase+slot)&1u][kind<5u ? kind:4u];
}
static uint32_t game_gem_frame(const GameGem *gem) {
    if(gem->kind)return GAME_ART_HEAL;
    return gem->value>=10u ? GAME_ART_XP_CROWN : gem->value>=5u ? GAME_ART_XP_CLUSTER:GAME_ART_XP;
}
static uint32_t game_gem_visible(const GameGem *gem,int32_t camera_x,int32_t camera_y) {
    if(!gem->value)return 0;
    const uint8_t *bounds=game_frame_bounds[game_gem_frame(gem)];
    int32_t left=GAME_X_MIN+gem->x-camera_x-16;
    int32_t top=GAME_Y_MIN+gem->y-camera_y-16;
    return left+bounds[0]<GAME_X_MAX && left+bounds[2]>GAME_X_MIN &&
           top+bounds[1]<GAME_Y_MAX && top+bounds[3]>GAME_Y_MIN;
}
static void game_select_gems(const SurvivorGame *g,int32_t camera_x,int32_t camera_y) {
    uint32_t count=0;
    // Retain drops already on screen. New low slots never evict a live visible
    // drop just because their indices are smaller.
    for(uint32_t i=0;i<GAME_MAX_GEMS;++i) {
        uint32_t bit=1u<<(i&31u),word=i>>5;
        if(!(game_gem_selected[word]&bit))continue;
        if(game_gem_visible(&g->gems[i],camera_x,camera_y))++count;
        else game_gem_selected[word]&=~bit;
    }
    // A pickup or off-screen drop releases one of the fixed 20 display slots.
    for(uint32_t i=0;i<GAME_MAX_GEMS && count<GAME_MAX_DRAW_GEMS;++i) {
        uint32_t bit=1u<<(i&31u),word=i>>5;
        if((game_gem_selected[word]&bit) || !game_gem_visible(&g->gems[i],camera_x,camera_y))continue;
        game_gem_selected[word]|=bit;++count;
    }
}
static uint32_t game_draw_gems(const SurvivorGame *g,int32_t camera_x,int32_t camera_y) {
    game_select_gems(g,camera_x,camera_y);
    uint32_t drawn=0;
    // Ascending draw order remains deterministic for overlapping alpha pixels.
    for(uint32_t i=0;i<GAME_MAX_GEMS && drawn<GAME_MAX_DRAW_GEMS;++i) {
        if(!(game_gem_selected[i>>5]&(1u<<(i&31u))))continue;
        int32_t sx=GAME_X_MIN+g->gems[i].x-camera_x;
        int32_t sy=GAME_Y_MIN+g->gems[i].y-camera_y;
        drawn+=game_sprite(game_gem_frame(&g->gems[i]),sx,sy,220);
    }
    return drawn;
}
static uint32_t game_draw(const SurvivorGame *g,uint32_t measured_fps,uint32_t us,uint32_t ar,uint32_t aw) {
    __asm__ volatile (".word 0x500f" ::: "memory");
    uint32_t draw_start=cycle_now();
    game_draw_floor_cycles=game_draw_sprite_cycles=game_draw_other_cycles=0;
    uint32_t page=draw_page(),page_bit=1u<<page,drawn=0;
    (void)us;(void)ar;(void)aw;
    uint32_t ui_key=g->state|(g->choice<<8);
    if(g->state!=GAME_PLAY && g->state!=GAME_PAUSED) {
        if(game_ui_key[page]!=ui_key){game_ui_page(g);game_ui_key[page]=ui_key;game_page_valid[page]=0;game_hud_pages&=~page_bit;}
        publish_pixels();return 0;
    }
    if(g->state==GAME_PAUSED && game_ui_key[page]==ui_key)return 0;
    if(game_ui_key[page]!=ui_key){game_hud_pages&=~page_bit;game_page_valid[page]=0;}
    game_ui_key[page]=ui_key;
    game_ui_hud(g,measured_fps,page,page_bit);
    int32_t camera_x=game_camera_x(g),camera_y=game_camera_y(g);
    uint32_t floor_start=cycle_now();
    game_capture_dirty=0;
    game_draw_world_floor(page,camera_x,camera_y,g->state==GAME_PLAY,g->ticks);
    game_draw_floor_cycles=cycle_now()-floor_start;
    uint32_t sprite_start;
    // Draw every visible bolt in the 256-slot pool using the existing glow.
    uint32_t bolt_drawn=0,bolt_start=(g->ticks>>2)%GAME_MAX_BOLTS;
    for(uint32_t n=0;n<GAME_MAX_BOLTS && bolt_drawn<GAME_MAX_DRAW_BOLTS;++n) {
        uint32_t i=(bolt_start+n)%GAME_MAX_BOLTS;
        if(!g->bolts[i].life) continue;
        bolt_drawn+=game_bolt(&g->bolts[i],camera_x,camera_y);
    }
    drawn+=bolt_drawn;
    // Retire CPU bullet stores before the raster engine reads the destination
    // pixels to composite gems and enemies over them.
    if(bolt_drawn) publish_pixels();
    sprite_start=cycle_now();
    drawn+=game_draw_gems(g,camera_x,camera_y);
    game_draw_sprite_cycles+=cycle_now()-sprite_start;
    // Every live, on-screen enemy is eligible. With a 256-enemy pool and
    // matching draw limit there is no need for a quadratic nearest-N sort or
    // a large temporary draw list on the 4 KiB stack.
    sprite_start=cycle_now();
    game_draw_enemy_count=0;
    for(uint32_t i=0;i<GAME_MAX_ENEMIES && game_draw_enemy_count<GAME_MAX_DRAW_ENEMIES;++i) {
        const GameEnemy *e=&g->enemies[i];
        if(!e->hp) continue;
        int32_t sx=GAME_X_MIN+e->x/32-camera_x,sy=GAME_Y_MIN+e->y/32-camera_y;
        if(sx<GAME_X_MIN-16 || sx>=GAME_X_MAX+16 || sy<GAME_Y_MIN-16 || sy>=GAME_Y_MAX+16) continue;
        int32_t bob=((g->ticks/12+i)&1u) ? 1 : 0;
        uint32_t visible=game_world_sprite(g,game_enemy_frame(e->kind,g->ticks,i),
                         e->x/32,e->y/32+bob,e->flash>84 ? 160 : 255);
        drawn+=visible; game_draw_enemy_count+=visible;
    }
    game_draw_sprite_cycles+=cycle_now()-sprite_start;
    sprite_start=cycle_now();
    for(uint32_t i=0;i<g->orbit_count;++i) {
        int32_t x,y; game_orbit_position(g,i,&x,&y);
        drawn+=game_world_sprite(g,((g->ticks/8u+i)&1u) ? GAME_ART_ORBIT_STEP:GAME_ART_ORBIT,x,y,160);
    }
    if(!g->invincible || (g->ticks&4u))
        drawn+=game_world_sprite(g,g->direction*4+g->walk_frame,g->x/256,g->y/256,g->invincible ? 160 : 255);
    game_draw_sprite_cycles+=cycle_now()-sprite_start;
    // Keep the eight closest health bars legible without issuing a rectangle
    // fill for every off-screen or distant enemy in a crowded wave.
    uint16_t shown[8]; int32_t shown_distance[8];
    for(uint32_t n=0;n<8;++n) { shown[n]=GAME_MAX_ENEMIES; shown_distance[n]=0x7fffffff; }
    for(uint32_t i=0;i<GAME_MAX_ENEMIES;++i) if(g->enemies[i].hp && g->enemies[i].flash) {
        int32_t sx=GAME_X_MIN+g->enemies[i].x/32-camera_x;
        int32_t sy=GAME_Y_MIN+g->enemies[i].y/32-camera_y;
        if(sx<GAME_X_MIN-16 || sx>=GAME_X_MAX+16 || sy<GAME_Y_MIN-16 || sy>=GAME_Y_MAX+16) continue;
        int32_t dx=g->enemies[i].x/32-g->x/256,dy=g->enemies[i].y/32-g->y/256;
        int32_t d=dx*dx+dy*dy;
        for(uint32_t n=0;n<8;++n) if(d<shown_distance[n]) {
            for(uint32_t k=7;k>n;--k) { shown[k]=shown[k-1]; shown_distance[k]=shown_distance[k-1]; }
            shown[n]=(uint16_t)i; shown_distance[n]=d; break;
        }
    }
    for(uint32_t n=0;n<8 && shown[n]<GAME_MAX_ENEMIES;++n) {
        const GameEnemy *e=&g->enemies[shown[n]];
        uint32_t bar_width=e->kind==4 ? 44u : 30u;
        uint32_t width=e->max_hp ? (bar_width*e->hp/e->max_hp) : 0;
        if(width) {
            uint16_t color=e->kind==4 ? 0xffe0 : e->hp*2u<=e->max_hp ? 0xf800 : e->hp*2u<=e->max_hp*3u/2u ? 0xff80 : 0x07e0;
            int32_t bx=GAME_X_MIN+e->x/32-camera_x-(int32_t)bar_width/2,by=GAME_Y_MIN+e->y/32-camera_y-21;
            if(bx< GAME_X_MIN) bx=GAME_X_MIN;
            if(by< GAME_Y_MIN+1) by=GAME_Y_MIN+1;
            if(bx+(int32_t)bar_width>GAME_X_MAX) bx=GAME_X_MAX-(int32_t)bar_width;
            if(bx+(int32_t)width>GAME_X_MAX) width=(uint32_t)(GAME_X_MAX-bx);
            paint((uint32_t)bx,(uint32_t)by,bar_width,4,0x2128,0);
            paint((uint32_t)bx,(uint32_t)by,width,4,color,0);
            game_record_dirty_rect((uint32_t)bx,(uint32_t)by,bar_width,4);
        }
    }
    if(g->state==GAME_PAUSED)game_ui_pause();
    publish_pixels();
    uint32_t draw_cycles=cycle_now()-draw_start;
    uint32_t measured_parts=game_draw_floor_cycles+game_draw_sprite_cycles;
    game_draw_other_cycles=draw_cycles>measured_parts ? draw_cycles-measured_parts : 0;
    return drawn;
}
static void game_loop(void) {
    book_init_assets();book_load(BOOK_GAME_ORNAMENT);book_transient=BOOK_GAME_ORNAMENT;
    init_game_assets();book_assets_ready=0;book_cache_valid=0;
    game_ui_key[0]=game_ui_key[1]=0xffffffffu;
    game_prime_framebuffers(); game_reset(&survivor,0x6d2b79f5u);
    game_max60.maximum=0;
    frame_max60_clear_window(&game_max60);
    uint32_t last=cycle_now(),accumulator=0,previous_held=mmio_read(GFX_BASE+GFX_BUTTON_HELD);
    uint32_t measured_fps=0,us=0,ar=0,aw=0,frames=0,render=0,reads=0,writes=0,window_start=last;
    uint32_t logic_total=0,floor_total=0,sprite_total=0,other_total=0,enemy_draw_total=0;
    uint32_t read_wait_total=0,write_wait_total=0,diagnostic_frames=0;
    uint32_t read_wait_base=mmio_read(GFX_BASE+GFX_DDR_RWAIT);
    uint32_t write_wait_base=mmio_read(GFX_BASE+GFX_DDR_WWAIT);
    uint32_t old_state=255,previous_video=mmio_read(GFX_BASE+GFX_FRAME_COUNT),drawn=0;
    while(survivor.state!=GAME_EXIT) {
        uint32_t start=cycle_now();
        uint32_t logic_start=cycle_now();
        uint32_t held=mmio_read(GFX_BASE+GFX_BUTTON_HELD)&31u;
        uint32_t pressed=button_event()|(held&~previous_held); previous_held=held;
        uint32_t state_before=survivor.state;
        game_input(&survivor,held,pressed);
        if(survivor.state==GAME_PLAY && (state_before==GAME_OVER || state_before==GAME_WON)) {
            game_max60.maximum=0;
        }
        uint32_t now=cycle_now(),delta=now-last; last=now;
        uint32_t r0=mmio_read(GFX_BASE+GFX_BURST_READ),w0=mmio_read(GFX_BASE+GFX_BURST_WRITE);
        if(delta>(SYSTEM_CLINT_HZ/4u)) delta=(SYSTEM_CLINT_HZ/4u); // Bound catch-up after a debugger stall.
        if(state_before==GAME_PLAY && survivor.state==GAME_PLAY) {
            accumulator+=delta;
            while(accumulator>=FRAME_60_CYCLES && survivor.state==GAME_PLAY) {
                game_tick(&survivor,held); accumulator-=FRAME_60_CYCLES;
            }
        } else accumulator=0;
        if(survivor.state==GAME_EXIT) break;
        if(survivor.state!=old_state) {
            measured_fps=us=ar=aw=frames=render=reads=writes=0; window_start=start;
            logic_total=floor_total=sprite_total=other_total=0;
            enemy_draw_total=0;
            read_wait_total=write_wait_total=diagnostic_frames=0;
            read_wait_base=mmio_read(GFX_BASE+GFX_DDR_RWAIT);
            write_wait_base=mmio_read(GFX_BASE+GFX_DDR_WWAIT);
            frame_max60_clear_window(&game_max60);
        }
        uint32_t logic_cycles=cycle_now()-logic_start;
        drawn=game_draw(&survivor,measured_fps,us,ar,aw);
        uint32_t frame_render=cycle_now()-start;
        render+=frame_render;
        logic_total+=logic_cycles;
        floor_total+=game_draw_floor_cycles;
        sprite_total+=game_draw_sprite_cycles;
        other_total+=game_draw_other_cycles;
        enemy_draw_total+=game_draw_enemy_count;
        reads+=mmio_read(GFX_BASE+GFX_BURST_READ)-r0;
        writes+=mmio_read(GFX_BASE+GFX_BURST_WRITE)-w0;
        if(present_frame()) fail("FAIL game present");
        mmio_write(GFX_BASE+GFX_DISPLAY,1);
        uint32_t video=mmio_read(GFX_BASE+GFX_FRAME_COUNT);
        if(survivor.state==GAME_PLAY)
            frame_max60_sample(&game_max60,frame_render,video-previous_video,drawn);
        previous_video=video;
        if(survivor.state!=old_state) {
            uart_number("GAME STATE ",survivor.state); puts_uart("\r\n"); old_state=survivor.state;
        }
        if(++frames==30) {
            uint32_t end=cycle_now(),elapsed=end-window_start;
            measured_fps=frame_measured_fps(30u,elapsed); us=render/(30u*(SYSTEM_CLINT_HZ/1000000u)); ar=reads/30; aw=writes/30;
            uint32_t read_wait_now=mmio_read(GFX_BASE+GFX_DDR_RWAIT);
            uint32_t write_wait_now=mmio_read(GFX_BASE+GFX_DDR_WWAIT);
            read_wait_total+=read_wait_now-read_wait_base;
            write_wait_total+=write_wait_now-write_wait_base;
            read_wait_base=read_wait_now; write_wait_base=write_wait_now;
            window_start=end;
            uart_number("GAME FPS ",measured_fps); uart_number(" RENDER_US ",us);
            uart_number(" SPRITES ",drawn);
            uart_number(" ENEMY_DRAWN ",enemy_draw_total/30u);
            uart_number(" ENEMY_BUDGET ",GAME_MAX_DRAW_ENEMIES);
            uart_number(" MAX60 ",game_max60.maximum); uart_number(" ENEMIES ",survivor.enemy_count);
            uart_number(" DDR_AR ",reads); uart_number(" DDR_AW ",writes);
            uart_number(" LEVEL ",survivor.level); uart_number(" KILLS ",survivor.kills);
            puts_uart("\r\n"); frames=render=reads=writes=enemy_draw_total=0;
            if(++diagnostic_frames==10u) {
                // Emit the longer phase breakdown every 300 frames so UART
                // traffic has little effect on the live frame pacing.
                uart_number("GAME_PHASE LOGIC_US ",logic_total/(300u*(SYSTEM_CLINT_HZ/1000000u)));
                uart_number(" FLOOR_US ",floor_total/(300u*(SYSTEM_CLINT_HZ/1000000u)));
                uart_number(" SPRITE_US ",sprite_total/(300u*(SYSTEM_CLINT_HZ/1000000u)));
                uart_number(" OTHER_US ",other_total/(300u*(SYSTEM_CLINT_HZ/1000000u)));
                uart_number(" GFX_RWAIT_US ",read_wait_total/(300u*(SYSTEM_CLINT_HZ/1000000u)));
                uart_number(" GFX_WWAIT_US ",write_wait_total/(300u*(SYSTEM_CLINT_HZ/1000000u)));
                puts_uart("\r\n");
                logic_total=floor_total=sprite_total=other_total=0;
                read_wait_total=write_wait_total=diagnostic_frames=0;
            }
        }
        // Wall-clock FPS includes UART, HUD and frame-swap waiting; logic uses fixed ticks.
    }
    // A chord used to leave the game must not navigate the restored menu.
    while(mmio_read(GFX_BASE+GFX_BUTTON_HELD)&31u) (void)button_event();
    (void)button_event();
}
