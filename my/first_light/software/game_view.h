/* Game presentation reuses main.c's existing renderer, font and frame swap.
 * Logic stays in survivor_game.c so it can be tested without FPGA registers.
 */
#include "survivor_game.h"
#include "game_assets.h"
#define GAME_ASSET_BASE (ASSET_BASE+0x4000u)
#define GAME_BACKGROUND (ASSET_BASE+0x20000u)
#define GAME_MAX_DRAW_ENEMIES 64u
#define GAME_MAX_DRAW_GEMS 20u
#define GAME_MAX_DRAW_BOLTS GAME_MAX_BOLTS
#define GAME_MAX_DRAW_LANDMARKS 4u
#define GAME_FLOOR_TEXTURE (GAME_BACKGROUND+640u*480u*2u)
static SurvivorGame survivor;
static uint32_t game_background_ready;
static uint32_t game_assets_ready;
static uint32_t game_hud_pages,game_hud_number_valid[2],game_hud_bar_valid[2];
/* Game and pressure pages share these 24 HUD number cache entries. The atlas
 * reuse in main.c now leaves enough on-chip RAM for this 96-byte CPU-only
 * cache, avoiding DDR reads/stores while the video engine is fetching lines. */
static uint32_t game_hud_numbers[2][12];
static FrameMax60 game_max60;
static uint32_t game_hud_bar_value[2][2],game_hud_bar_max[2][2];
static uint16_t game_hud_bar_color[2][2];
static uint32_t game_sprite(uint32_t frame,int32_t x,int32_t y,uint32_t alpha);
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
    // A bullet is only 5x5/7x7 pixels.  Writing this tiny solid primitive
    // directly to the back buffer avoids one APB command and one wait per
    // bullet; the single publish at the end of game_draw makes all 48 bullets
    // visible together while leaving the raster engine for larger sprites.
    cpu_fill(x,y,size,size,b->pierce ? 0xffe0 : 0x07ff);
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
    publish_pixels();
    game_assets_ready=1;
}
static void game_background(void) {
    // Store a reusable, borderless sci-fi panel background in DDR once.  The
    // reference board image is intentionally reduced to a few large panels
    // and neutral gray service marks so the playfield remains readable under Alpha.
    if(game_background_ready) return;
    volatile uint16_t *p=(volatile uint16_t *)(uintptr_t)GAME_BACKGROUND;
    for(uint32_t y=0;y<480;++y) for(uint32_t x=0;x<640;++x) {
        uint32_t tx=x/80u,ty=y/80u,px=x%80u,py=y%80u;
        uint32_t tone=(tx*5u+ty*3u+(tx^ty))&7u;
        uint16_t c=tone<2u ? 0x1082 : tone<6u ? 0x18c3 : 0x2104;
        // Thin seams give the panel layout without drawing a screen frame.
        if(px==0u || py==0u) c=0x0841;
        else if(px==1u || py==1u) c=0x2945;
        // A few repeated service marks echo the supplied sci-fi reference.
        if(((tx+2u*ty)%7u)==0u && py>=17u && py<20u && px>=12u && px<34u)
            c=0x3186;
        if(((2u*tx+ty)%9u)==0u && px>=54u && px<57u && py>=30u && py<54u)
            c=0x3186;
        // Small dark vents keep the pattern from becoming a uniform grid.
        if(((tx+ty)%5u)==0u && px>=31u && px<39u && py>=48u && py<59u &&
           ((py-48u)&1u)==0u) c=0x0000;
        p[y*640+x]=c;
    }
    publish_pixels();

    // Reusable 256x256 world tile. The camera copies wrapped pieces into the
    // visible arena, so both floor seams and landmarks travel with the world.
    volatile uint16_t *tile=(volatile uint16_t *)(uintptr_t)GAME_FLOOR_TEXTURE;
    for(uint32_t y=0;y<256;++y) for(uint32_t x=0;x<256;++x) {
        uint32_t tx=x/64u,ty=y/64u,px=x&63u,py=y&63u;
        uint32_t tone=(tx*13u+ty*7u+(tx^ty))&7u;
        uint16_t c=tone<2u ? 0x1082 : tone<6u ? 0x18c3 : 0x2104;
        if(px==0u || py==0u) c=0x0841;
        else if(px==1u || py==1u) c=0x2945;
        if(((tx+2u*ty)%7u)==0u && py>=13u && py<16u && px>=9u && px<27u)
            c=0x3186;
        if(((2u*tx+ty)%9u)==0u && px>=43u && px<46u && py>=23u && py<44u)
            c=0x3186;
        if(((tx+ty)%5u)==0u && px>=25u && px<33u && py>=38u && py<50u &&
           ((py-38u)&1u)==0u) c=0x0000;
        tile[y*256u+x]=c;
    }
    publish_pixels();
    game_background_ready=1;
}
static void game_draw_world_floor(int32_t camera_x,int32_t camera_y) {
    uint32_t sx=(uint32_t)camera_x&255u,sy=(uint32_t)camera_y&255u;
    // Repaint the whole gameplay viewport. This clears the previous frame's
    // sprites while keeping the static outer HUD margins resident in each page.
    uint32_t dst_y=GAME_Y_MIN,remaining_h=GAME_Y_MAX-GAME_Y_MIN;
    while(remaining_h) {
        uint32_t h=256u-sy; if(h>remaining_h) h=remaining_h;
        uint32_t dst_x=GAME_X_MIN,remaining_w=GAME_X_MAX-GAME_X_MIN;
        uint32_t src_x=sx;
        while(remaining_w) {
            uint32_t w=256u-src_x; if(w>remaining_w) w=remaining_w;
            uint32_t source=GAME_FLOOR_TEXTURE+(sy*256u+src_x)*2u;
            if(copy_image(source,512u,dst_x,dst_y,w,h)) fail("FAIL game floor");
            dst_x+=w; remaining_w-=w; src_x=0;
        }
        dst_y+=h; remaining_h-=h; sy=0;
    }
}
static void game_prime_framebuffers(void) {
    // Seed both ping-pong pages once. Later frames only refresh the HUD strips
    // and scrolling playfield instead of copying all 640x480 pixels.
    for(uint32_t page=0;page<2;++page) {
        if(copy_image(GAME_BACKGROUND,FRAME_STRIDE,0,0,640,480)) fail("FAIL game page init");
        if(present_frame()) fail("FAIL game page present");
    }
    game_hud_pages=0;
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
    // Clip partially visible effects at arena edges. Source remains in its own frame.
    int32_t left=x-16,top=y-16,right=x+16,bottom=y+16;
    int32_t x0=left<GAME_X_MIN ? GAME_X_MIN : left;
    int32_t y0=top<GAME_Y_MIN ? GAME_Y_MIN : top;
    int32_t x1=right>GAME_X_MAX ? GAME_X_MAX : right;
    int32_t y1=bottom>GAME_Y_MAX ? GAME_Y_MAX : bottom;
    if(x0>=x1 || y0>=y1) return 0;
    uint32_t source=GAME_ASSET_BASE+frame*2048u+(uint32_t)(y0-top)*64u+(uint32_t)(x0-left)*2u;
    if(blend_image(source,64,(uint32_t)x0,(uint32_t)y0,(uint32_t)(x1-x0),(uint32_t)(y1-y0),
                   (uint8_t)alpha,0,GFX_BLEND_ALPHA|GFX_BLEND_KEY)) fail("FAIL game sprite");
    return 1;
}
static void game_bar(uint32_t x,uint32_t y,uint32_t width,uint32_t value,uint32_t maximum,uint16_t color) {
    uint32_t page=draw_page(),index=x<280u ? 0u : 1u,bit=1u<<index;
    if((game_hud_bar_valid[page]&bit) && game_hud_bar_value[page][index]==value &&
       game_hud_bar_max[page][index]==maximum && game_hud_bar_color[page][index]==color) return;
    // These small dynamic bars are cheaper as packed CPU stores than as four
    // separately fenced FPGA fill commands on every frame.
    cpu_fill(x,y,width,8,0x2128);
    uint32_t w=maximum ? value*width/maximum : 0;
    if(w>width) w=width;
    if(w) cpu_fill(x,y,w,8,color);
    game_hud_bar_value[page][index]=value;
    game_hud_bar_max[page][index]=maximum;
    game_hud_bar_color[page][index]=color;
    game_hud_bar_valid[page]|=bit;
}
static void game_hud_number(uint32_t page,uint32_t index,uint32_t x,uint32_t y,
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
static void game_panel(const SurvivorGame *g) {
	uint32_t panel_height=g->state==GAME_READY ? 288u : 256u;
	paint(72,136,496,panel_height,0x10a6,1); paint(72,136,496,3,0x07ff,1);
    if(g->state==GAME_UPGRADE) {
        text_at(96,154,"升级 - 选择符文",0xffff);
        for(uint32_t n=0;n<3;++n) {
            uint32_t y=180+n*54;
            paint(88,y,464,48,n==g->choice ? 0x22ae : 0x10c7,1);
            if(n==g->choice) paint(88,y,4,48,0x07ff,1);
            uint32_t skill=g->options[n],level=g->upgrade_level[skill],maximum=game_upgrade_max(skill);
            game_sprite(game_upgrade_icon(skill),120,y+24,255);
            text_at_width(148,y+5,game_upgrade_name(skill),0xffff,272);
            text_at_width(148,y+24,game_upgrade_detail(skill),0x07ff,388);
            if(level>=maximum) text_at(444,y+5,"满级",0xffe0);
			else {
				text_at(432,y+5,"级",0x9cf3); number_at(456,y+5,level,0xffff);
				text_at(468,y+5,"/",0x9cf3); number_at(480,y+5,maximum,0xffff);
			}
        }
        text_at(96,362,"W/S选择  ENTER确认",0xffe0);
    } else if(g->state==GAME_READY) {
        text_at(96,160,"冰霜幸存者",0xffff);
        text_at(96,194,"生存180秒",0x07ff);
        text_at(96,224,"W上    S下",0xffff);
        text_at(96,248,"A左    D右",0xffff);
        text_at(96,278,"技能自动释放",0x9cf3);
        text_at(96,302,"ENTER暂停",0x9cf3);
        text_at(96,326,"RISC-V负责移动 碰撞 自动攻击",0xffff);
        text_at(96,350,"FPGA负责透明 颜色键 DDR3绘制",0x07ff);
        text_at(96,374,"ENTER开始  D返回",0xffe0);
        text_at(96,398,"地图可扩展 摄像机居中",0x9cf3);
    } else {
        text_at(96,164,g->state==GAME_PAUSED ? "已暂停" : g->state==GAME_WON ? "你已生存" : "游戏结束",0xffff);
        text_at(96,208,"时间",0x07ff); number_at(168,208,g->ticks/60,0xffff);
        text_at(288,208,"击杀",0x07ff); number_field_at(372,208,144,g->kills,0xffff);
        text_at(96,240,"等级",0x07ff); number_at(180,240,g->level,0xffff);
        text_at(288,240,"MAX60",0x07ff); number_field_at(360,240,72,game_max60.maximum,0xffff);
        text_at(96,294,g->state==GAME_PAUSED ? "ENTER继续" : "ENTER再来一局",0xffe0);
        text_at(96,326,"D返回菜单",0x9cf3);
    }
}
static uint32_t game_draw(const SurvivorGame *g,uint32_t measured_fps,uint32_t us,uint32_t ar,uint32_t aw) {
    __asm__ volatile (".word 0x500f" ::: "memory");
    uint32_t page=draw_page(),page_bit=1u<<page,drawn=0;
    int32_t camera_x=game_camera_x(g),camera_y=game_camera_y(g);
    game_draw_world_floor(camera_x,camera_y);
    // A few world runes make the expanded map visible without spending a
    // raster command on every landmark in the 2048x1408 playfield.
    uint32_t landmark_drawn=0;
    for(int32_t y=352;y<GAME_WORLD_HEIGHT && landmark_drawn<GAME_MAX_DRAW_LANDMARKS;y+=352) for(int32_t x=512;x<GAME_WORLD_WIDTH && landmark_drawn<GAME_MAX_DRAW_LANDMARKS;x+=512) {
        int32_t sx=GAME_X_MIN+x-camera_x,sy=GAME_Y_MIN+y-camera_y;
        if(sx>=GAME_X_MIN+16 && sx<GAME_X_MAX-16 && sy>=GAME_Y_MIN+16 && sy<GAME_Y_MAX-16) {
            drawn+=game_sprite(22,sx,sy,96); landmark_drawn++;
        }
    }
    /* The draw budget grows to 64 only after the rolling measurement confirms
     * near-60 FPS with render headroom. This raises the visible horde while
     * backing off automatically if a dense scene threatens frame pacing. */
    uint32_t enemy_draw_budget=measured_fps>=59u && us<12000u ? GAME_MAX_DRAW_ENEMIES : 32u;
    // Small bullets use one write burst each instead of a 32x32 Alpha/Key
    // image read. Draw all 48 logic slots first so projectile count has priority
    // when the scene is crowded.
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
    uint32_t gem_drawn=0;
    for(uint32_t i=0;i<GAME_MAX_GEMS && gem_drawn<GAME_MAX_DRAW_GEMS;++i) {
        if(!g->gems[i].value) continue;
        int32_t sx=GAME_X_MIN+g->gems[i].x-camera_x;
        int32_t sy=GAME_Y_MIN+g->gems[i].y-camera_y;
        if(sx<GAME_X_MIN-16 || sx>=GAME_X_MAX+16 || sy<GAME_Y_MIN-16 || sy>=GAME_Y_MAX+16) continue;
        uint32_t visible=game_world_sprite(g,g->gems[i].kind ? 23 : 19,g->gems[i].x,g->gems[i].y,220);
        drawn+=visible; gem_drawn+=visible;
    }
    /* Select nearest visible enemies first. The old rotating slot limit could
     * spend all 24 image commands on off-screen objects, making an on-screen
     * enemy look as if its image had not loaded. */
    uint16_t enemy_draw_list[GAME_MAX_DRAW_ENEMIES];
    int32_t enemy_draw_distance[GAME_MAX_DRAW_ENEMIES];
    for(uint32_t n=0;n<GAME_MAX_DRAW_ENEMIES;++n) {
        enemy_draw_list[n]=GAME_MAX_ENEMIES; enemy_draw_distance[n]=0x7fffffff;
    }
    for(uint32_t i=0;i<GAME_MAX_ENEMIES;++i) if(g->enemies[i].hp) {
        const GameEnemy *e=&g->enemies[i];
        int32_t sx=GAME_X_MIN+e->x/32-camera_x,sy=GAME_Y_MIN+e->y/32-camera_y;
        if(sx<GAME_X_MIN-16 || sx>=GAME_X_MAX+16 || sy<GAME_Y_MIN-16 || sy>=GAME_Y_MAX+16) continue;
        int32_t dx=e->x/32-g->x/256,dy=e->y/32-g->y/256,d=dx*dx+dy*dy;
        for(uint32_t n=0;n<GAME_MAX_DRAW_ENEMIES;++n) if(d<enemy_draw_distance[n]) {
            for(uint32_t k=GAME_MAX_DRAW_ENEMIES-1;k>n;--k) {
                enemy_draw_list[k]=enemy_draw_list[k-1]; enemy_draw_distance[k]=enemy_draw_distance[k-1];
            }
            enemy_draw_list[n]=(uint16_t)i; enemy_draw_distance[n]=d; break;
        }
    }
    for(uint32_t n=0;n<enemy_draw_budget && enemy_draw_list[n]<GAME_MAX_ENEMIES;++n) {
        uint32_t i=enemy_draw_list[n]; const GameEnemy *e=&g->enemies[i];
        int32_t bob=((g->ticks/12+i)&1u) ? 1 : 0;
        drawn+=game_world_sprite(g,e->kind>=3 ? 24 : 16+e->kind,e->x/32,e->y/32+bob,
                         e->flash>84 ? 160 : 255);
    }
    for(uint32_t i=0;i<g->orbit_count;++i) {
        int32_t x,y; game_orbit_position(g,i,&x,&y); drawn+=game_world_sprite(g,21,x,y,160);
    }
    if(!g->invincible || (g->ticks&4u))
        drawn+=game_world_sprite(g,g->direction*4+g->walk_frame,g->x/256,g->y/256,g->invincible ? 160 : 255);
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
        }
    }
    if(!(game_hud_pages&page_bit)) {
        text_at(16,10,"冰霜",0x07ff);
        text_at(164,10,"生命",0xffff); text_at(276,10,"等级",0xffff);
        text_at(360,10,"经验",0xffff); text_at(432,10,"时间",0xffff);
        text_at(16,56,"KILLS",0x9cf3); text_at(152,56,"ENEMY",0x9cf3);
        text_at(264,56,"SPRITES",0x9cf3); text_at(400,56,"MAX60",0x9cf3);
        text_at(524,56,"FPS",0x9cf3);
        text_at(16,460,"RENDER_US",0x07ff); text_at(224,460,"DDR_RD",0x07ff);
        text_at(420,460,"DDR_WR",0x07ff);
        text_at(16,442,"W/S上/下 A/D左/右 ENTER暂停",0x9cf3);
        game_hud_pages|=page_bit;
    }
    game_hud_number(page,0,200,10,48,g->hp,0xffe0);
    game_hud_number(page,1,312,10,36,g->level,0xffe0);
    game_hud_number(page,2,492,10,48,g->ticks/60,0xffe0);
    uint16_t hp_color=g->hp*4u<=g->max_hp ? 0xf800 : g->hp*2u<=g->max_hp ? 0xffe0 : 0x07e0;
    game_bar(16,34,248,g->hp,g->max_hp,hp_color);
    game_bar(280,34,352,g->xp,g->xp_target,0x07ff);
    game_hud_number(page,3,80,56,60,g->kills,0xffff);
    game_hud_number(page,4,216,56,36,g->enemy_count,0xffff);
    game_hud_number(page,5,352,56,36,drawn,0xffff);
    game_hud_number(page,6,568,56,36,measured_fps,0xffff);
    game_hud_number(page,7,468,56,36,game_max60.maximum,0xffff);
    game_hud_number(page,8,136,460,84,us,0xffff);
    game_hud_number(page,9,308,460,84,ar,0xffff);
    game_hud_number(page,10,504,460,84,aw,0xffff);
    if(g->state!=GAME_PLAY) game_panel(g);
    publish_pixels();
    return drawn;
}
static void game_loop(void) {
    game_background(); game_prime_framebuffers(); game_reset(&survivor,0x6d2b79f5u);
    game_max60.maximum=0; frame_max60_clear_window(&game_max60);
    uint32_t last=cycle_now(),accumulator=0,previous_held=mmio_read(GFX_BASE+GFX_BUTTON_HELD);
    uint32_t measured_fps=0,us=0,ar=0,aw=0,frames=0,render=0,reads=0,writes=0,window_start=last;
    uint32_t old_state=255,previous_video=mmio_read(GFX_BASE+GFX_FRAME_COUNT),drawn=0;
    while(survivor.state!=GAME_EXIT) {
        uint32_t start=cycle_now();
        uint32_t held=mmio_read(GFX_BASE+GFX_BUTTON_HELD)&31u;
        uint32_t pressed=button_event()|(held&~previous_held); previous_held=held;
        uint32_t state_before=survivor.state;
        game_input(&survivor,held,pressed);
        if(survivor.state==GAME_PLAY && (state_before==GAME_OVER || state_before==GAME_WON))
            game_max60.maximum=0;
        uint32_t now=cycle_now(),delta=now-last; last=now;
        uint32_t r0=mmio_read(GFX_BASE+GFX_BURST_READ),w0=mmio_read(GFX_BASE+GFX_BURST_WRITE);
        if(delta>25000000u) delta=25000000u; // Bound catch-up after a debugger stall.
        if(state_before==GAME_PLAY && survivor.state==GAME_PLAY) {
            accumulator+=delta;
            while(accumulator>=1666667u && survivor.state==GAME_PLAY) {
                game_tick(&survivor,held); accumulator-=1666667u;
            }
        } else accumulator=0;
        if(survivor.state==GAME_EXIT) break;
        if(survivor.state!=old_state) {
            measured_fps=us=ar=aw=frames=render=reads=writes=0; window_start=start;
            frame_max60_clear_window(&game_max60);
        }
        drawn=game_draw(&survivor,measured_fps,us,ar,aw);
        uint32_t frame_render=cycle_now()-start;
        render+=frame_render;
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
            measured_fps=elapsed ? (3000000000u+elapsed/2u)/elapsed : 0; us=render/3000u; ar=reads/30; aw=writes/30;
            window_start=end;
            uart_number("GAME FPS ",measured_fps); uart_number(" RENDER_US ",us);
            uart_number(" SPRITES ",drawn);
            uart_number(" MAX60 ",game_max60.maximum); uart_number(" ENEMIES ",survivor.enemy_count);
            uart_number(" DDR_AR ",reads); uart_number(" DDR_AW ",writes);
            uart_number(" LEVEL ",survivor.level); uart_number(" KILLS ",survivor.kills);
            puts_uart("\r\n"); frames=render=reads=writes=0;
        }
        // Wall-clock FPS includes UART, HUD and frame-swap waiting; logic uses fixed ticks.
    }
    // A chord used to leave the game must not navigate the restored menu.
    while(mmio_read(GFX_BASE+GFX_BUTTON_HELD)&31u) (void)button_event();
    (void)button_event();
}
