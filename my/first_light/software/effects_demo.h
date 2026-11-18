// Hardware Alpha / Color Key demonstrations. Key animation reuses the player's
// four existing walk frames; Alpha retains its independent static test image.
#define EFFECT_SIZE 128u
#define EFFECT_STRIDE (EFFECT_SIZE*2u)
#define EFFECT_BYTES (EFFECT_SIZE*EFFECT_STRIDE)
#define EFFECT_BASE (ASSET_BASE+0xB0000u)
typedef char EffectsDDRBounds[(GAME_ASSET_BASE+GAME_FRAME_COUNT*2048u<=EFFECT_BASE &&
    EFFECT_BASE+2u*EFFECT_BYTES<=BASIC_IMAGE_BASE)?1:-1];
static uint32_t effects_assets_ready;
#define EFFECT_WALK_SIZE 64u
#define EFFECT_WALK_FRAMES 4u
#define EFFECT_WALK_BYTES (EFFECT_WALK_SIZE*EFFECT_WALK_SIZE*2u)
#define EFFECT_WALK_PERIOD (SYSTEM_CLINT_HZ/10u)
#define EFFECT_WALK_X 88u
#define EFFECT_WALK_Y 64u
typedef char EffectsWalkBounds[(2u*EFFECT_WALK_FRAMES*EFFECT_WALK_BYTES==2u*EFFECT_BYTES)?1:-1];
static uint32_t effects_tick,effects_key_paused;
static uint32_t effects_key_valid[2];
static uint32_t effects_check_valid[2],effects_check_value[2];
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
    if(effects_assets_ready==1u)return;
    for(uint32_t image=0;image<2u;++image) {
        volatile uint32_t *dst=(volatile uint32_t *)(uintptr_t)(EFFECT_BASE+image*EFFECT_BYTES);
        for(uint32_t y=0;y<EFFECT_SIZE;++y)for(uint32_t x=0;x<EFFECT_SIZE;x+=2u)
            dst[y*EFFECT_SIZE/2u+x/2u]=(uint32_t)effects_pixel(image,x,y)|
                ((uint32_t)effects_pixel(image,x+1u,y)<<16);
    }
    publish_pixels();effects_assets_ready=1;
}
static uint32_t effects_walk_source(uint32_t key,uint32_t frame) {
    return EFFECT_BASE+(key*EFFECT_WALK_FRAMES+(frame&3u))*EFFECT_WALK_BYTES;
}
static void effects_init_key_assets(void) {
    if(effects_assets_ready==2u)return;
    // The retired alpha image/second walk bank is scratch while the first
    // four frames are uploaded. The second bank then derives from those pixels.
    volatile uint8_t *scratch=(volatile uint8_t *)(uintptr_t)(EFFECT_BASE+EFFECT_BYTES);
    typedef char KeyScratchBounds[(GAME_RLE_BYTES<=EFFECT_BYTES)?1:-1];
    (void)sizeof(KeyScratchBounds);
    game_decode_runs(scratch);
    const volatile uint16_t *tokens=(const volatile uint16_t *)scratch;
    for(uint32_t frame=0;frame<EFFECT_WALK_FRAMES;++frame) {
        volatile uint32_t *dst=(volatile uint32_t *)(uintptr_t)effects_walk_source(0,frame);
        uint32_t out=0;
        for(uint32_t at=game_walk_offsets[frame];at<game_walk_offsets[frame+1u];++at) {
            uint32_t token=tokens[at],count=token>>10;
            uint16_t color=game_palette[token&1023u];
            uint32_t pair=(uint32_t)color|((uint32_t)color<<16);
            while(count--) {
                if(out>=1024u)fail("FAIL key frame");
                uint32_t x=out&31u,y=out>>5;++out;
                dst[y*64u+x]=pair;dst[y*64u+32u+x]=pair;
            }
        }
        if(out!=1024u)fail("FAIL key frame");
    }
    for(uint32_t frame=0;frame<EFFECT_WALK_FRAMES;++frame) {
        const volatile uint32_t *src=(const volatile uint32_t *)(uintptr_t)effects_walk_source(0,frame);
        volatile uint32_t *dst=(volatile uint32_t *)(uintptr_t)effects_walk_source(1,frame);
        for(uint32_t i=0;i<EFFECT_WALK_BYTES/4u;++i) {
            uint16_t color=(uint16_t)src[i];
            if(!color)color=effects_key(1);
            else if(color==effects_key(1))color^=1u;
            dst[i]=(uint32_t)color|((uint32_t)color<<16);
        }
    }
    publish_pixels();effects_assets_ready=2;
    effects_key_valid[0]=effects_key_valid[1]=0;
}
// Use the original checkerboard in both panels. Only the walk-frame changes;
// the character remains centred, and keyed pixels reveal this real backdrop.
static uint16_t effects_key_background(uint32_t scene,uint32_t x,uint32_t y) {
    return effects_background(scene,x,y);
}
static void effects_restore_key(uint32_t scene,uint32_t left,uint32_t x,uint32_t y,uint32_t w,uint32_t h) {
    for(uint32_t row=y;row<y+h;) {
        uint32_t rh=16u-(row&15u);if(rh>y+h-row)rh=y+h-row;
        for(uint32_t col=x;col<x+w;) {
            uint32_t cw=16u-(col&15u);if(cw>x+w-col)cw=x+w-col;
            paint(left+col,192u+row,cw,rh,effects_key_background(scene,col,row),1);
            col+=cw;
        }
        row+=rh;
    }
}
static void effects_draw_key(const EffectsConfig *c) {
    effects_init_key_assets();
    uint32_t page=draw_page(),x=EFFECT_WALK_X;
    for(uint32_t panel=0;panel<2u;++panel) {
        uint32_t left=48u+panel*304u;
        if(!effects_key_valid[page])effects_restore_key(c->background,left,0,0,240,192);
        else effects_restore_key(c->background,left,x,EFFECT_WALK_Y,64,64);
        uint32_t source=effects_walk_source(c->key_index,effects_tick);
        int result=panel && c->enabled ? blend_image(source,128,left+x,192u+EFFECT_WALK_Y,64,64,255,
            effects_key(c->key_index),GFX_BLEND_KEY):copy_image(source,128,left+x,192u+EFFECT_WALK_Y,64,64);
        if(result)fail("FAIL key animation");
    }
    effects_key_valid[page]=1;publish_pixels();
}
static void effects_draw_scene(uint32_t demo,const EffectsConfig *c) {
    if(demo==DEMO_KEY){effects_draw_key(c);return;}
    effects_init_assets();
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
    if(demo==DEMO_KEY) {
        static const uint8_t points[8][2]={{0,0},{63,63},{32,32},{24,32},{40,32},{32,48},{8,8},{48,48}};
        const volatile uint16_t *source=(const volatile uint16_t *)(uintptr_t)effects_walk_source(c->key_index,effects_tick);
        uint32_t passed=0,position=EFFECT_WALK_X;
        for(uint32_t n=0;n<8u;++n) {
            uint32_t x=points[n][0],y=points[n][1];uint16_t fg=source[y*64u+x];
            uint16_t bg=effects_key_background(c->background,position+x,EFFECT_WALK_Y+y);
            uint16_t expected=c->enabled && fg==effects_key(c->key_index) ? bg:fg;
            uint16_t actual=*(const volatile uint16_t *)(uintptr_t)(draw_buffer+(192u+EFFECT_WALK_Y+y)*FRAME_STRIDE+(352u+position+x)*2u);
            if(actual==expected)++passed;
        }
        return passed;
    }
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
static void effects_check_label(uint32_t passed) {
    uint32_t page=draw_page();
    if(effects_check_valid[page] && effects_check_value[page]==passed)return;
    cpu_fill(24,124,256,14,UI_BG);
    char check[48]="采样像素核对 ",number[11];decimal(number,passed);uint32_t n=19,k=0;
    while(number[k]){check[n++]=number[k++];}check[n++]='/';check[n++]='8';check[n]=0;
    book_text(24,124,check,UI_GOLD,1);
    effects_check_valid[page]=1;effects_check_value[page]=passed;
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
    effects_check_valid[draw_page()]=0;effects_check_label(passed);
    book_text(48,164,demo==DEMO_ALPHA ? "不透明参考":"原图 颜色键关",UI_CREAM,1);
    book_text(352,164,demo==DEMO_ALPHA ? "硬件混合结果":c->enabled ? "颜色键开":"颜色键关",UI_CREAM,1);
    book_text(16,430,demo==DEMO_ALPHA ? "W透明度+5  D透明度-5":"W开关去背  D切换透明色",UI_CREAM,1);
    book_text(16,454,demo==DEMO_ALPHA ? "ENTER预设  S换背景  A返回":effects_key_paused ?
        "ENTER继续  S换背景  A返回":"ENTER暂停  S换背景  A返回",UI_ICE,1);
    publish_pixels();
}
static void effects_redraw(uint32_t demo,const EffectsConfig *c) {
    effects_key_valid[0]=effects_key_valid[1]=0;
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
    effects_tick=effects_key_paused=0;effects_redraw(demo,&c);
    uint32_t next_frame=cycle_now()+EFFECT_WALK_PERIOD;
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
            if(keys==16u) {effects_key_paused^=1u;changed=1;next_frame=cycle_now()+EFFECT_WALK_PERIOD;}
        }
        if(keys==2u) {c.background^=1u;changed=1;}
        if(changed)effects_redraw(demo,&c);
        if(demo==DEMO_KEY && !effects_key_paused) {
            uint32_t now=cycle_now();
            if((int32_t)(now-next_frame)>=0) {
                uint32_t steps=1u+(now-next_frame)/EFFECT_WALK_PERIOD;
                effects_tick+=steps;next_frame+=steps*EFFECT_WALK_PERIOD;
                effects_draw_key(&c);effects_check_label(effects_verify(demo,&c));publish_pixels();
                if(present_frame())fail("FAIL key present");
            }
        }
    }
}
