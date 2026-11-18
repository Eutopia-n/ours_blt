#ifndef REFERENCE_GAME_UI_H
#define REFERENCE_GAME_UI_H
/* Fullscreen game pages follow the local HTML. All values remain live game
 * data; this file changes presentation only. No game background is allocated. */
static uint32_t game_ui_key[2]={0xffffffffu,0xffffffffu};
static void game_ui_frame(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint32_t selected) {
    for(uint32_t row=0;row<h;++row) {
        uint32_t inset=row<4u ? 4u-row:row>h-5u ? row-(h-5u):0u;
        cpu_fill(x+inset,y+row,w-inset*2u,1,0x6a87);
    }
    cpu_fill(x+2,y+2,w-4,h-4,selected ? 0x2c55:0x3a0c);
    cpu_fill(x+4,y+4,w-8,h-8,0x18e6);cpu_fill(x+6,y+2,w-12,1,0xe651);
    for(uint32_t i=0;i<4u;++i) {
        uint32_t xx=(i&1u) ? x+w-4u:x+3u,yy=(i&2u) ? y+h-4u:y+3u;
        cpu_fill((i&1u) ? xx-8u:xx,yy,9,1,0xac2a);
        cpu_fill(xx,(i&2u) ? yy-8u:yy,1,9,0xac2a);
    }
}
static void game_ui_base(const char *title) {
    paint(0,0,640,480,0x1084,1);cpu_fill(0,0,640,44,0x18e6);
    cpu_fill(0,44,640,1,0x6a87);book_stamp(BOOK_ICON_GAME,16,6,1,0);
    book_text(60,9,title,0xf759,2);
    cpu_fill(554,13,41,19,0x296a);book_text(560,15,"硬件",0xe651,1);
    cpu_fill(16,416,608,1,0x3a0c);
}
static void game_ui_footer(const char *left,const char *right) {
    cpu_fill(16,450,608,28,0x1084); // Retire the previous page's longer key hints.
    cpu_fill(16,444,608,1,0x3a0c);
    book_text(16,456,left,0xf759,1);book_text(352,456,right,0x9f1c,1);
}
static void game_ui_skill(uint32_t frame,uint32_t x,uint32_t y,uint32_t size) {
    const uint8_t *b=game_frame_bounds[frame];uint32_t w=b[2]-b[0],h=b[3]-b[1];
    uint32_t maximum=size>32u ? 64u:24u,k=maximum/(w>h ? w:h);if(!k)k=1;
    const volatile uint16_t *p=(const volatile uint16_t *)(uintptr_t)(GAME_ASSET_BASE+frame*2048u);
    x+=(size-w*k)/2u;y+=(size-h*k)/2u;
    for(uint32_t row=0;row<h;++row)for(uint32_t col=0;col<w;++col) {
        uint16_t color=p[(b[1]+row)*32u+b[0]+col];
        if(color)cpu_fill(x+col*k,y+row*k,k,k,color);
    }
}
static void game_ui_illustration(const SurvivorGame *g) {
    book_transient=BOOK_GAME_ORNAMENT;
    book_stamp(BOOK_GAME_ORNAMENT,66,144,2,0);
    if(g->state==GAME_UPGRADE)game_ui_skill(game_upgrade_icon(g->options[g->choice]),118,192,96);
    else book_hero(118,192,3);
}
static void game_ui_entry(uint32_t y,const char *title,const char *detail,uint32_t icon,uint32_t active,uint32_t skill) {
    game_ui_frame(342,y,254,76,active);
    if(skill)game_ui_skill(icon,354,y+20,32);else book_stamp(BOOK_ICON_GAME,354,y+20,1,0);
    book_text(398,y+11,title,active ? 0x9f1c:0xf759,book_text_width(title,2)<=198 ? 2u:1u);
    book_text(398,y+49,detail,active ? 0xe651:0x63b1,book_text_width(detail,1)>198u ? 0u:1u);
    if(active)book_stamp(BOOK_CURSOR,326,y+26,1,0);
}
static void game_ui_time(char *out,uint32_t seconds) {
    out[0]=(char)('0'+seconds/600u%10u);out[1]=(char)('0'+seconds/60u%10u);out[2]=':';
    out[3]=(char)('0'+seconds/10u%6u);out[4]=(char)('0'+seconds%10u);out[5]=0;
}
static void game_ui_number(uint32_t x,uint32_t y,uint32_t value,uint16_t color,uint32_t width) {
    char out[11];decimal(out,value);book_text(x,y,out,color,book_text_width(out,1)>width ? 0u:1u);
}
static void game_ui_page(const SurvivorGame *g) {
    uint32_t relic_offer=g->state==GAME_UPGRADE && g->chest_state==CHEST_OFFER;
    game_ui_base(relic_offer ? "选择遗物":g->state==GAME_UPGRADE ? "选择强化":g->state==GAME_READY ? "冰霜幸存者":
                 g->state==GAME_WON ? "你已生存":"游戏结束");game_ui_illustration(g);
    if(g->state==GAME_UPGRADE) {
        char level[11],heading[40]="等级提升 / ";if(g->level<10u){level[0]='0';level[1]=(char)('0'+g->level);level[2]=0;}else decimal(level,g->level);
        uint32_t at=0,n=0;while(heading[at])++at;while(level[n])heading[at++]=level[n++];heading[at]=0;
        book_center(320,70,relic_offer ? "秘库宝箱 / 三选一":heading,0xe651,1);
        book_center(166,344,game_upgrade_name(g->options[g->choice]),0x9f1c,1);
        book_center(166,374,game_upgrade_detail(g->options[g->choice]),0x63b1,book_text_width(game_upgrade_detail(g->options[g->choice]),1)>280u ? 0u:1u);
        for(uint32_t i=0;i<3u;++i) {
            uint32_t skill=g->options[i];
            game_ui_entry(126+i*88u,game_upgrade_name(skill),game_upgrade_detail(skill),game_upgrade_icon(skill),i==g->choice,1);
        }
        game_ui_footer(relic_offer ? "W/S 选择遗物":"W/S 选择强化","D 暂停  ENTER 选择");return;
    }
    uint32_t ready=g->state==GAME_READY,won=g->state==GAME_WON;
    book_center(320,70,ready ? "冰霜幸存者":won ? "生存胜利":"本局结束",ready||won ? 0xe651:0xab0c,1);
    book_center(166,344,ready||won ? "生存360秒":"冰霜幸存者",0x9f1c,1);
    if(ready)book_center(166,374,"技能自动释放",0x63b1,1);
    for(uint32_t i=0;i<3u;++i) {
        uint32_t y=128u+i*(ready ? 64u:66u);
        const char *label=ready ? (i==0 ? "时间":i==1 ? "技能":"移动"):(i==0 ? "时间":i==1 ? "击杀":"等级");
        book_text(356,y,label,0x63b1,1);
        if(ready)book_text(438,y,i==0 ? "360秒":i==1 ? "自动释放":"W/S/A/D",0xf759,1);
        else if(!i){char out[6];game_ui_time(out,g->ticks/60u);book_text(476,y,out,0xe651,1);}
        else game_ui_number(476,y,i==1 ? g->kills:g->level,0xe651,120);
        cpu_fill(354,y+(ready ? 36u:38u),233,1,0x2a2a);
    }
    game_ui_entry(330,ready ? "开始游戏":"再来一局","ENTER",0,1,0);
    game_ui_footer("A 返回菜单","ENTER 开始");
}
static void game_ui_bar(uint32_t x,uint32_t y,uint32_t w,uint32_t value,uint32_t maximum,uint16_t color) {
    cpu_fill(x,y,w,12,0x6a87);cpu_fill(x+1,y+1,w-2,10,0x18e6);
    uint32_t fill=maximum ? (w-4u)*value/maximum:0;if(fill>w-4u)fill=w-4u;
    if(fill){cpu_fill(x+2,y+2,fill,8,color);cpu_fill(x+2,y+2,fill,1,color==0xab0c ? 0xe651:0x9f1c);}
}
static void game_ui_altar(const SurvivorGame *g) {
    static const char *const enemies[]={"霜晶史莱姆","白骨学徒","暮晶蝙蝠","寒霜守卫","鎏金统领"};
    static const uint8_t icons[]=GAME_ART_ENEMY_IDLE;
    uint16_t alive[5]={0};
    for(uint32_t i=0;i<GAME_MAX_ENEMIES;++i) {
        const GameEnemy *e=&g->enemies[i];
        if(e->hp && e->kind<5u)++alive[e->kind];
    }
    game_ui_base("祭坛战况");
    game_ui_frame(22,68,292,300,0);
    game_ui_frame(326,68,292,300,0);
    book_text(40,86,"技能等级",0xe651,1);
    book_text(344,86,"存活怪物",0xe651,1);
    for(uint32_t i=0;i<GAME_UPGRADE_COUNT;++i) {
        uint32_t y=112+i*40u,level=g->upgrade_level[i],maximum=game_upgrade_max(i);
        char rank[4]={(char)('0'+level),'/',(char)('0'+maximum),0};
        game_ui_skill(game_upgrade_icon(i),38,y+2,32);
        book_text(80,y+2,game_upgrade_name(i),0xf759,1);
        book_text(256,y+2,rank,level>=maximum ? 0xe651:0x9f1c,1);
        game_ui_bar(80,y+20,208,level,maximum,0x2c55);
    }
    for(uint32_t i=0;i<5u;++i) {
        uint32_t y=112+i*40u;
        game_ui_skill(icons[i],344,y+2,32);
        book_text(388,y+9,enemies[i],0xf759,1);
        game_ui_number(554,y+9,alive[i],0x9f1c,48);
        cpu_fill(344,y+38,252,1,0x2a2a);
    }
    book_text(344,322,"全图存活",0xf759,1);
    game_ui_number(554,322,g->enemy_count,0xe651,48);
    book_text(32,388,"遗物",0x9f1c,1);
    book_text(70,388,g->relic ? game_upgrade_name(GAME_UPGRADE_COUNT+g->relic-1u):"未获得",0xf759,1);
    book_text(322,388,"击杀",0x9f1c,1);
    game_ui_number(366,388,g->kills,0xf759,64);
    book_text(472,388,"宝石",0x9f1c,1);
    game_ui_number(516,388,g->gem_count,0xf759,64);
    game_ui_footer("","ENTER 继续游戏");
}
static void game_ui_hud(const SurvivorGame *g,uint32_t fps,uint32_t page,uint32_t page_bit) {
    uint32_t fresh=!(game_hud_pages&page_bit);
    if(fresh) {
        game_ui_base("");book_text(60,14,"冰霜幸存者",0xf759,1);
        const volatile uint16_t *heart=(const volatile uint16_t *)(uintptr_t)(GAME_ASSET_BASE+GAME_ART_HEAL*2048u);
        for(uint32_t y=0;y<16;++y)for(uint32_t x=0;x<16;++x)if(heart[y*64+x*2])cpu_fill(200+x,12+y,1,1,heart[y*64+x*2]);

        cpu_fill(16,450,608,28,0x1084);cpu_fill(16,444,608,1,0x3a0c);
        book_text(16,456,"W/S/A/D 移动",0xf759,1);
        book_text(350,456,"击杀",0xf759,1);
        book_text(486,456,"存活弹数",0x63b1,1);
        book_text(80,54,"经验",0x63b1,1);
        book_text(280,54,"60帧纪录",0xe651,1);
        book_text(400,54,"屏内",0x9f1c,1);
        book_text(524,54,"帧率",0x9f1c,1);
        game_hud_pages|=page_bit;
        game_hud_number_valid[page]=0;
    }
    uint32_t altar_nearby=game_near_altar(g);
    if(fresh || game_hud_numbers[page][10]!=altar_nearby) {
        cpu_fill(176,456,168,14,0x1084);
        book_text(176,456,altar_nearby ? "ENTER 祭坛":"ENTER 暂停",0x9f1c,1);
        game_hud_numbers[page][10]=altar_nearby;
    }
    (void)fps;
    uint32_t values[2]={g->hp,g->level};
    for(uint32_t i=0;i<2;++i) {
        if(!fresh && (game_hud_number_valid[page]&(1u<<i)) && game_hud_numbers[page][i]==values[i])continue;
        if(i==0){cpu_fill(390,14,72,14,0x18e6);game_ui_number(390,14,g->hp,0xf759,72);game_ui_bar(226,16,144,g->hp,g->max_hp,0xab0c);}
        if(i==1){cpu_fill(16,54,64,14,0x1084);book_text(16,54,"等级",0xf759,1);char level[11];if(g->level<10u){level[0]='0';level[1]=(char)('0'+g->level);level[2]=0;}else decimal(level,g->level);book_text(44,54,level,0xf759,1);}
        game_hud_numbers[page][i]=values[i];game_hud_number_valid[page]|=1u<<i;
    }
    if((game_hud_number_valid[page]&12u)!=12u || game_hud_numbers[page][2]!=g->xp ||
       game_hud_numbers[page][3]!=g->xp_target) {
        static char out[24];
        decimal(out,g->xp);uint32_t n=0;
        while(out[n])++n;
        out[n++]='/';decimal(out+n,g->xp_target);
        game_ui_bar(108,56,156,g->xp,g->xp_target,0x2c55);
        book_center(186,58,out,0xf759,0);
        game_hud_numbers[page][2]=g->xp;game_hud_numbers[page][3]=g->xp_target;
        game_hud_number_valid[page]|=12u;
    }
    uint32_t second=g->ticks/60u;
    if(fresh || game_hud_numbers[page][6]!=second){char out[6];game_ui_time(out,second);cpu_fill(476,14,72,14,0x18e6);book_text(476,14,out,0xe651,1);game_hud_numbers[page][6]=second;}
}
/* Read the live counters after drawing this frame. Per-page caches avoid DDR
 * writes when the published number is the same as that page's last value. */
static void game_ui_metrics(uint32_t visible,uint32_t active,uint32_t maximum,
                            uint32_t kills,uint32_t fps,uint32_t page) {
    const uint32_t values[5]={visible,active,maximum,kills,fps};
    static const uint16_t positions[5]={434u,550u,350u,384u,566u};
    static const uint8_t indices[5]={7u,8u,9u,4u,5u};
    static const uint8_t widths[5]={48u,74u,36u,84u,66u};
    for(uint32_t n=0;n<5u;++n) {
        uint32_t index=indices[n],bit=1u<<index,y=(n==1u || n==3u) ? 456u:54u;
        if((game_hud_number_valid[page]&bit) && game_hud_numbers[page][index]==values[n])continue;
        uint16_t color=n==2u ? 0xe651:n==3u ? 0xf759:0x9f1c;
        cpu_fill(positions[n],y,widths[n],14,0x1084);
        game_ui_number(positions[n],y,values[n],color,widths[n]);
        game_hud_numbers[page][index]=values[n];game_hud_number_valid[page]|=bit;
    }
}
static void game_ui_pause(void) {
    /* Shade through the existing scanline engine; CPU emits one solid span. */
    book_capture();book_command_count=0;book_command(0,0,0,0,640,480,0,0,110,255,0,0x0842);
    book_submit(BOOK_CACHE_BASE,0);
    init_game_assets(); // The descriptor area shares the retired player atlas.
    game_ui_frame(100,178,440,174,1);book_center(320,194,"已暂停",0xf759,2);
    book_center(320,248,"ENTER 继续游戏",0x9f1c,1);book_center(320,284,"A 返回菜单",0xe651,1);
    game_ui_footer("A 返回菜单","ENTER 继续");
}
#endif
