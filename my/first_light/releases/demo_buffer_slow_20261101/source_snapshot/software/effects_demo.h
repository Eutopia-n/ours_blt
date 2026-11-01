// Hardware-only Alpha / Color Key demonstrations. No changes to the shared
// blend driver, render engine, game assets or Sprite pressure-test workload.
#define EFFECT_SIZE 128u
#define EFFECT_STRIDE (EFFECT_SIZE*2u)
#define EFFECT_BYTES (EFFECT_SIZE*EFFECT_STRIDE)
#define EFFECT_BASE (ASSET_BASE+0xB0000u)
typedef char EffectsDDRBounds[(DUNGEON_WALL_BASE+DUNGEON_WALL_BYTES<=EFFECT_BASE &&
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
static void effects_labels(uint32_t demo,const EffectsConfig *c,uint32_t passed) {
    text_at(16,10,demo_names[demo],0x07ff);text_at(400,10,"FPGA 硬件",0x07ff);
    if(demo==DEMO_ALPHA) {
        text_at(24,44,"透明度",0xffff);number_field_at(136,44,36,c->transparency,0xffe0);text_at(184,44,"/255",0xffff);
        text_at(328,44,"前景权重",0xffff);number_field_at(440,44,36,alpha_value(c->transparency),0xffe0);text_at(488,44,"/255",0xffff);
        text_at(24,76,"前景×权重 + 背景×反向权重",0x9cf3);
        text_at(48,164,"不透明参考",0xffff);text_at(352,164,"硬件混合结果",0xffff);
        text_at(24,402,"颜色键关 透明度越大 越透明",0x9cf3);
        text_at(24,430,"W透明度+5 D透明度-5",0xffff);
        text_at(24,454,"ENTER预设 S换背景 A返回",0x07ff);
    } else {
        text_at(24,44,"透明色",0xffff);text_at(136,44,c->key_index ? "品红色 F81F" : "黑色 0000",0xffe0);
        text_at(24,76,"匹配透明色的像素跳过写入",0x9cf3);
        text_at(48,164,"原图 颜色键关",0xffff);
        text_at(352,164,c->enabled ? "颜色键开" : "颜色键关",0xffff);
        text_at(24,402,"匹配色保留原背景 其他像素直接复制",0x9cf3);
        text_at(24,430,"W开关去背 D切换透明色",0xffff);
        text_at(24,454,"S换背景 A返回",0x07ff);
    }
    text_at(24,112,"采样像素核对",0xffff);number_field_at(220,112,24,passed,0xffe0);text_at(256,112,"/8",0xffff);
    text_at(344,112,passed==8u ? "通过" : "失败",passed==8u ? 0x07e0 : 0xf800);
    publish_pixels();
}
static void effects_redraw(uint32_t demo,const EffectsConfig *c) {
    for(uint32_t page=0;page<2u;++page) {
        paint(0,0,640,480,0x10a6,1);
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
