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
    cpu_fill(554,13,41,19,0x296a);book_text(562,19,"FPGA",0xe651,0);
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
    game_ui_base(g->state==GAME_UPGRADE ? "选择强化":g->state==GAME_READY ? "冰霜幸存者":
                 g->state==GAME_WON ? "你已生存":"游戏结束");game_ui_illustration(g);
    if(g->state==GAME_UPGRADE) {
        char level[11],heading[32]="LEVEL UP / ";if(g->level<10u){level[0]='0';level[1]=(char)('0'+g->level);level[2]=0;}else decimal(level,g->level);
        uint32_t at=11,n=0;while(level[n])heading[at++]=level[n++];heading[at]=0;
        book_center(320,70,heading,0xe651,1);
        book_center(166,344,game_upgrade_name(g->options[g->choice]),0x9f1c,1);
        book_center(166,374,game_upgrade_detail(g->options[g->choice]),0x63b1,book_text_width(game_upgrade_detail(g->options[g->choice]),1)>280u ? 0u:1u);
        for(uint32_t i=0;i<3u;++i) {
            uint32_t skill=g->options[i];
            game_ui_entry(126+i*88u,game_upgrade_name(skill),game_upgrade_detail(skill),game_upgrade_icon(skill),i==g->choice,1);
        }
        game_ui_footer("W/S 选择强化","D 暂停  ENTER 选择");return;
    }
    uint32_t ready=g->state==GAME_READY,won=g->state==GAME_WON;
    book_center(320,70,ready ? "FROST SURVIVOR":won ? "VICTORY":"END OF RUN",ready||won ? 0xe651:0xab0c,1);
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
static void game_ui_hud(const SurvivorGame *g,uint32_t fps,uint32_t page,uint32_t page_bit) {
    uint32_t fresh=!(game_hud_pages&page_bit);
    if(fresh) {
        game_ui_base("");book_text(60,14,"冰霜幸存者",0xf759,1);
        const volatile uint16_t *heart=(const volatile uint16_t *)(uintptr_t)(GAME_ASSET_BASE+GAME_ART_HEAL*2048u);
        for(uint32_t y=0;y<16;++y)for(uint32_t x=0;x<16;++x)if(heart[y*64+x*2])cpu_fill(200+x,12+y,1,1,heart[y*64+x*2]);

        game_ui_footer("W/S/A/D 移动","ENTER 暂停");game_hud_pages|=page_bit;
        game_hud_number_valid[page]=0;
    }
    uint32_t values[6]={g->hp,g->level,g->xp,g->xp_target,g->kills,fps};
    for(uint32_t i=0;i<6;++i) {
        if(!fresh && (game_hud_number_valid[page]&(1u<<i)) && game_hud_numbers[page][i]==values[i])continue;
        if(i==0){cpu_fill(390,14,72,14,0x18e6);game_ui_number(390,14,g->hp,0xf759,72);game_ui_bar(226,16,144,g->hp,g->max_hp,0xab0c);}
        if(i==1){cpu_fill(16,54,88,14,0x1084);book_text(16,54,"等级",0xf759,1);char level[11];if(g->level<10u){level[0]='0';level[1]=(char)('0'+g->level);level[2]=0;}else decimal(level,g->level);book_text(44,54,level,0xf759,1);}
        if(i==2 || i==3) {
            char a[11],b[11],out[24];decimal(a,g->xp);decimal(b,g->xp_target);uint32_t n=0,k=0;
            while(a[k]){out[n++]=a[k++];}out[n++]='/';k=0;while(b[k])out[n++]=b[k++];out[n]=0;
            cpu_fill(300,54,96,14,0x1084);book_text(300,54,out,0x63b1,book_text_width(out,1)>96u ? 0u:1u);game_ui_bar(108,56,168,g->xp,g->xp_target,0x2c55);
        }
        if(i==4){cpu_fill(396,54,120,14,0x1084);book_text(396,54,"击杀",0xf759,1);game_ui_number(424,54,g->kills,0xf759,92);}
        if(i==5){cpu_fill(518,54,114,14,0x1084);book_text(518,54,"FPS",0x9f1c,1);game_ui_number(566,54,fps,0x9f1c,66);}
        game_hud_numbers[page][i]=values[i];game_hud_number_valid[page]|=1u<<i;
    }
    uint32_t second=g->ticks/60u;
    if(fresh || game_hud_numbers[page][6]!=second){char out[6];game_ui_time(out,second);cpu_fill(476,14,72,14,0x18e6);book_text(476,14,out,0xe651,1);game_hud_numbers[page][6]=second;}
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
