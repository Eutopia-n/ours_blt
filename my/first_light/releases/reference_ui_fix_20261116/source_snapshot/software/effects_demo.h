// Hardware-only Alpha / Color Key demonstrations. No changes to the shared
// blend driver, render engine, game assets or Sprite pressure-test workload.
#define EFFECT_SIZE 128u
#define EFFECT_STRIDE (EFFECT_SIZE*2u)
#define EFFECT_BYTES (EFFECT_SIZE*EFFECT_STRIDE)
#define EFFECT_BASE (ASSET_BASE+0xB0000u)
typedef char EffectsDDRBounds[(GAME_ASSET_BASE+GAME_FRAME_COUNT*2048u<=EFFECT_BASE &&
    EFFECT_BASE+2u*EFFECT_BYTES<=BASIC_IMAGE_BASE)?1:-1];
static uint32_t effects_assets_ready;
typedef struct {uint32_t transparency,key_index,enabled,background;} EffectsConfig;
static uint16_t effects_key(uint32_t index) {return index ? 0xf81fu : 0u;}
static uint16_t effects_pixel(uint32_t index,uint32_t x,uint32_t y) {
    uint32_t dx=x>63u ? x-63u : 63u-x,dy=y>63u ? y-63u : 63u-y;
    if(dx+dy>60u)return effects_key(index);
    return y<43u ? 0x07ffu : y<86u ? 0xf800u : 0xffe0u;
}
static uint16_t effects_background(uint32_t index,uint32_t x,uint32_t y) {
    uint32_t cell=((x/16u)^(y/16u))&1u;
    return index ? (cell ? 0x7befu : 0x2945u) : (cell ? 0x0514u : 0xfca0u);
}
static void effects_init_assets(void) {
    if(effects_assets_ready)return;
    for(uint32_t image=0;image<2u;++image) {
        volatile uint32_t *dst=(volatile uint32_t *)(uintptr_t)(EFFECT_BASE+image*EFFECT_BYTES);
        for(uint32_t y=0;y<EFFECT_SIZE;++y)for(uint32_t x=0;x<EFFECT_SIZE;x+=2u)
            dst[y*EFFECT_SIZE/2u+x/2u]=(uint32_t)effects_pixel(image,x,y)|
                ((uint32_t)effects_pixel(image,x+1u,y)<<16);
    }
    publish_pixels();effects_assets_ready=1;
}
static void effects_draw_scene(uint32_t demo,const EffectsConfig *c) {
    for(uint32_t panel=0;panel<2u;++panel) {
        uint32_t left=48u+panel*304u;
        for(uint32_t y=0;y<192u;y+=16u)for(uint32_t x=0;x<240u;x+=16u)
            paint(left+x,192u+y,16,16,effects_background(c->background,x,y),1);
        uint32_t image=demo==DEMO_KEY ? c->key_index : 0u;
        uint32_t source=EFFECT_BASE+image*EFFECT_BYTES;
        uint32_t flags=panel ? (demo==DEMO_ALPHA ? GFX_BLEND_ALPHA : c->enabled ? GFX_BLEND_KEY : 0u) : 0u;
        int result=flags ? blend_image(source,EFFECT_STRIDE,left+56u,224u,EFFECT_SIZE,EFFECT_SIZE,
            (uint8_t)alpha_value(c->transparency),effects_key(image),flags) :
            copy_image(source,EFFECT_STRIDE,left+56u,224u,EFFECT_SIZE,EFFECT_SIZE);
        if(result)fail("FAIL hardware effect");
    }
    publish_pixels();
}
static uint32_t effects_verify(uint32_t demo,const EffectsConfig *c) {
    static const uint8_t points[8][2]={{0,0},{127,127},{64,64},{32,64},{64,32},{64,100},{0,127},{96,64}};
    uint32_t image=demo==DEMO_KEY ? c->key_index : 0u;
    uint32_t flags=demo==DEMO_ALPHA ? GFX_BLEND_ALPHA : c->enabled ? GFX_BLEND_KEY : 0u;
    uint32_t passed=0;
    for(uint32_t n=0;n<8u;++n) {
        uint32_t x=points[n][0],y=points[n][1];
        uint16_t fg=effects_pixel(image,x,y),bg=effects_background(c->background,56u+x,32u+y);
        uint16_t expected=blend_rgb565(fg,bg,alpha_value(c->transparency),effects_key(image),flags);
        uint16_t actual=*(const volatile uint16_t *)(uintptr_t)(draw_buffer+(224u+y)*FRAME_STRIDE+(408u+x)*2u);
        if(actual==expected)++passed;
    }
    return passed;
}
// Build the two live fractions without moving the reference text anchors.
static void effects_fraction(uint32_t x,uint32_t y,const char *label,uint32_t value,uint16_t color) {
    char out[48],number[11];uint32_t n=0,k=0;while(*label)out[n++]=*label++;
    out[n++]=' ';decimal(number,value);while(number[k])out[n++]=number[k++];
    const char *tail="/255";while(*tail)out[n++]=*tail++;out[n]=0;book_text(x,y,out,color,1);
}
static void effects_labels(uint32_t demo,const EffectsConfig *c,uint32_t passed) {
    if(demo==DEMO_ALPHA) {
        effects_fraction(24,60,"透明度",c->transparency,UI_CREAM);
        effects_fraction(328,60,"前景权重",alpha_value(c->transparency),UI_ICE);
        book_text(24,92,"前景与背景混合  透明度越大 越透明",UI_STONE,1);
    } else {
        book_text(24,60,c->key_index ? "透明色 品红色 F81F":"透明色 黑色 0000",UI_CREAM,1);
        book_text(328,60,c->enabled ? "颜色键开":"颜色键关",UI_ICE,1);
        book_text(24,92,"匹配透明色的像素跳过写入",UI_STONE,1);
    }
    char check[48]="采样像素核对 ",number[11];decimal(number,passed);uint32_t n=19,k=0;
    // The UTF-8 label is six Chinese glyphs followed by one ASCII space.
    while(number[k]){check[n++]=number[k++];}check[n++]='/';check[n++]='8';check[n]=0;
    book_text(24,124,check,UI_GOLD,1);
    book_text(48,164,demo==DEMO_ALPHA ? "不透明参考":"原图 颜色键关",UI_CREAM,1);
    book_text(352,164,demo==DEMO_ALPHA ? "硬件混合结果":c->enabled ? "颜色键开":"颜色键关",UI_CREAM,1);
    book_text(16,430,demo==DEMO_ALPHA ? "W透明度+5  D透明度-5":"W开关去背  D切换透明色",UI_CREAM,1);
    book_text(16,454,demo==DEMO_ALPHA ? "ENTER预设  S换背景  A返回":"S换背景  A返回",UI_ICE,1);
    publish_pixels();
}
static void effects_redraw(uint32_t demo,const EffectsConfig *c) {
    for(uint32_t page=0;page<2u;++page) {
        demo_skin(demo,"FPGA");
        demo_window(48,192,240,192);demo_window(352,192,240,192);
        effects_draw_scene(demo,c);
        uint32_t passed=effects_verify(demo,c);
        effects_labels(demo,c,passed);
        if(present_frame())fail("FAIL effect present");
    }
}
static void effects_demo_loop(uint32_t demo) {
    EffectsConfig c;volatile uint32_t *initial=(volatile uint32_t *)&c;
    initial[0]=demo==DEMO_ALPHA ? 255u:128u;initial[1]=0u;initial[2]=1u;initial[3]=0u;
    uint32_t next_repeat=0;int32_t repeat_direction=0;
    effects_init_assets();effects_redraw(demo,&c);
    for(;;) {
        uint32_t keys=button_event(),changed=0;
        if(keys==4u)return;
        if(demo==DEMO_ALPHA) {
            uint32_t held=mmio_read(GFX_BASE+GFX_BUTTON_HELD);
            uint32_t value=demo_alpha_update(c.transparency,(keys&1u)|((keys&8u)?4u:0u),
                (held&1u)|((held&8u)?4u:0u),cycle_now(),&next_repeat,&repeat_direction);
            if(keys==16u) {value=c.transparency==0u ? 128u : c.transparency==128u ? 255u : 0u;next_repeat=0;repeat_direction=0;}
            changed=value!=c.transparency;c.transparency=value;
        } else {
            if(keys==1u) {c.enabled^=1u;changed=1;}
            if(keys==8u) {c.key_index^=1u;changed=1;}
        }
        if(keys==2u) {c.background^=1u;changed=1;}
        if(changed)effects_redraw(demo,&c);
    }
}
