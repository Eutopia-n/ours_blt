// Isolated basic-demo application, included after the existing game_view.h.
#include "basic_demo_data.h"
typedef char BasicDDRSeparation[(GAME_ASSET_BASE+GAME_FRAME_COUNT*2048u<=BASIC_IMAGE_BASE)?1:-1];
static BasicConfig basic_config;
static BasicSample basic_samples[2];
static uint32_t basic_assets_ready,basic_fields[2][20],basic_field_valid[2],basic_number_valid[2];
static uint32_t basic_swaps,basic_missed,basic_swap_us,basic_video_hz;
static uint32_t basic_completed_frame;
static uint32_t basic_bar_x[2],basic_scene_valid[2];
static void basic_reset_sample(BasicSample *s) {
    // Volatile stores keep this freestanding RV32 build independent of libc.
    volatile uint32_t *p=(volatile uint32_t *)s;
    for(uint32_t n=0;n<sizeof(*s)/sizeof(*p);++n)p[n]=0;
}

#define BASIC_COPY_INDEX_BYTES (BASIC_COPY_ASSET_W*BASIC_COPY_ASSET_H/2u)
static uint32_t basic_copy_texel(const volatile uint8_t *row,uint32_t x,
                                 const volatile uint16_t *palette) {
    return palette[(row[x/2u]>>((x&1u)*4u))&15u];
}
static uint32_t basic_copy_lerp(uint32_t a,uint32_t b,uint32_t fraction) {
    // Red and blue have enough space between them for 5-bit weights.
    uint32_t rb=(a&0xf81fu)*(32u-fraction)+(b&0xf81fu)*fraction;
    uint32_t g=(a&0x07e0u)*(32u-fraction)+(b&0x07e0u)*fraction;
    return ((rb>>5)&0xf81fu)|((g>>5)&0x07e0u);
}
static void basic_init_images(void) {
    if(basic_assets_ready)return;
    const volatile uint8_t *indices=(const volatile uint8_t *)(uintptr_t)BOOK_SCRATCH_BASE;
    const volatile uint16_t *palette=(const volatile uint16_t *)(indices+BASIC_COPY_INDEX_BYTES);
    for(uint32_t image=0;image<2u;++image) {
        book_unpack(basic_copy_stream[image][0],basic_copy_stream[image][1],BASIC_COPY_INDEX_BYTES+32u);
        volatile uint16_t *dst=(volatile uint16_t *)(uintptr_t)basic_source(image);
        for(uint32_t y=0;y<BASIC_IMAGE_H;++y) {
            uint32_t sy=y*(BASIC_COPY_ASSET_H*32u)/BASIC_IMAGE_H,y0=sy>>5;
            uint32_t y1=y0+1u<BASIC_COPY_ASSET_H ? y0+1u:y0;
            const volatile uint8_t *row0=indices+y0*(BASIC_COPY_ASSET_W/2u);
            const volatile uint8_t *row1=indices+y1*(BASIC_COPY_ASSET_W/2u);
            for(uint32_t x=0;x<BASIC_IMAGE_W;++x) {
                uint32_t sx=x*(BASIC_COPY_ASSET_W*32u)/BASIC_IMAGE_W,x0=sx>>5;
                uint32_t x1=x0+1u<BASIC_COPY_ASSET_W ? x0+1u:x0;
                uint32_t top=basic_copy_lerp(basic_copy_texel(row0,x0,palette),basic_copy_texel(row0,x1,palette),sx&31u);
                uint32_t bottom=basic_copy_lerp(basic_copy_texel(row1,x0,palette),basic_copy_texel(row1,x1,palette),sx&31u);
                *dst++=(uint16_t)basic_copy_lerp(top,bottom,sy&31u);
            }
        }
    }
    publish_pixels();book_cache_valid=0;basic_assets_ready=1;
}
static void basic_cpu_copy(uint32_t source) {
    for(uint32_t y=0;y<BASIC_IMAGE_H;++y) {
        const volatile uint32_t *s=(const volatile uint32_t *)(uintptr_t)(source+y*BASIC_IMAGE_STRIDE);
        volatile uint32_t *d=(volatile uint32_t *)(uintptr_t)
            (draw_buffer+(BASIC_IMAGE_Y+y)*FRAME_STRIDE+BASIC_COPY_X*2u);
        for(uint32_t x=0;x<BASIC_IMAGE_W/2u;++x)d[x]=s[x];
    }
}
static uint32_t basic_load(uint32_t demo) {
    return demo==DEMO_FILL ? basic_fill_counts[basic_config.load] : basic_copy_counts[basic_config.load];
}
static BasicRect basic_task_rect(uint32_t frame,uint32_t n) {
    BasicRect r=basic_rectangle(frame,n,basic_config.color);
    if(basic_config.view) {r.x=352u+(r.x-16u)%224u;r.y=176u+(r.y-176u)%168u;}
    return r;
}
// Measures only the named command batch. No clear, source upload or HUD writes.
// The same pre-drain is excluded and final write completion is included for
// both paths; FPGA drivers return after the final AXI B response.
static uint32_t basic_batch(uint32_t demo,uint32_t hw,uint32_t frame,BasicSample *result) {
    publish_pixels();
    uint32_t ar=mmio_read(GFX_BASE+GFX_BURST_READ),aw=mmio_read(GFX_BASE+GFX_BURST_WRITE);
    uint32_t rw=mmio_read(GFX_BASE+GFX_DDR_RWAIT),ww=mmio_read(GFX_BASE+GFX_DDR_WWAIT);
    uint32_t start=cycle_now(),count=basic_load(demo);
    for(uint32_t n=0;n<count;++n) {
        if(demo==DEMO_FILL) {
            BasicRect r=basic_task_rect(frame,n);
            paint(r.x,r.y,r.w,r.h,r.color,hw);
        } else if(hw) {
            if(copy_image(basic_source(basic_config.image),BASIC_IMAGE_STRIDE,
                BASIC_COPY_X,BASIC_IMAGE_Y,BASIC_IMAGE_W,BASIC_IMAGE_H))fail("FAIL basic copy");
        } else basic_cpu_copy(basic_source(basic_config.image));
    }
    publish_pixels();
    uint32_t cycles=cycle_now()-start;
    result->reads=mmio_read(GFX_BASE+GFX_BURST_READ)-ar;
    result->writes=mmio_read(GFX_BASE+GFX_BURST_WRITE)-aw;
    result->rwait=mmio_read(GFX_BASE+GFX_DDR_RWAIT)-rw;
    result->wwait=mmio_read(GFX_BASE+GFX_DDR_WWAIT)-ww;
    return cycles;
}
static uint32_t basic_payload(uint32_t demo) {
    return basic_load(demo)*(demo==DEMO_FILL ? 32u*24u*2u : BASIC_IMAGE_BYTES);
}
// format: 0 decimal, 2 ratio with two decimal places, 3 engine, 5 YES/NO.
// Cache values and sample validity independently for both display pages.
static void basic_field(uint32_t id,uint32_t x,uint32_t y,uint32_t width,
                        uint32_t value,uint32_t valid,uint32_t format) {
    uint32_t page=draw_page(),bit=1u<<id;
    if((basic_field_valid[page]&bit) && basic_fields[page][id]==value &&
        !!(basic_number_valid[page]&bit)==!!valid)return;
    basic_field_valid[page]|=bit;basic_fields[page][id]=value;
    if(valid)basic_number_valid[page]|=bit;else basic_number_valid[page]&=~bit;
    uint32_t metric=(x==262u || x==582u) && y>=54u && y<141u;
    uint16_t bg=metric ? UI_DESK:UI_BG;
    if(y<44u)bg=UI_HEADER;
    cpu_fill(metric ? x-66u:x,y,metric ? 108u:width,14,bg);
    if(format==3u){cpu_fill(554,13,65,19,UI_HEADER);demo_badge(554,13,value ? "FPGA":"CPU");return;}
    if(!valid){book_text(x,y,"--",y==148u ? UI_ICE:UI_GOLD,1);return;}
    if(format==2u) {
        char out[18],*end=decimal(out,value/100u);*end++='.';
        *end++=(char)('0'+value/10u%10u);*end++=(char)('0'+value%10u);*end=0;
        book_text(x,y,out,UI_ICE,book_text_width(out,1)>width ? 0u:1u);
    } else if(format==5u)book_text(x,y,value ? "YES":"NO",UI_GOLD,1);
    else if(metric) {
        // Keep the reference anchor for short values. Longer live timings grow
        // left into the reserved gap instead of losing significant digits.
        char out[11];decimal(out,value);uint32_t mode=book_text_width(out,1)>108u ? 0u:1u;
        uint32_t w=book_text_width(out,mode);
        book_text(w>width ? x+width-w:x,y,out,UI_GOLD,mode);
    } else demo_number(x,y,width,value,1,1,UI_GOLD,bg);
}
static void basic_hud(uint32_t demo,uint32_t hw) {
    if(demo==DEMO_BUFFER) {
        basic_field(2,176,84,120,basic_swaps,1,0);
        basic_field(4,176,110,120,basic_swap_us,1,0);
        basic_field(6,176,136,60,basic_video_hz,basic_video_hz!=0u,0);
        basic_field(5,496,84,120,basic_missed,1,0);
        basic_field(7,496,110,60,basic_config.paused,1,5);
        basic_field(8,496,136,60,8u<<basic_config.speed,1,0);
    } else {
        for(uint32_t n=0;n<2u;++n) {
            BasicSample *sample=&basic_samples[n];uint32_t x=16u+n*320u;
            basic_field(n*3u,x+246u,62,42,sample->fps,sample->valid,0);
            basic_field(n*3u+1u,x+246u,88,42,sample->op_cycles/(SYSTEM_CLINT_HZ/1000000u),sample->valid,0);
            basic_field(n*3u+2u,x+246u,114,42,sample->frame_us,sample->valid,0);
        }
        uint32_t valid=basic_samples[0].valid && basic_samples[1].valid && basic_samples[1].op_cycles;
        basic_field(6,112,148,192,basic_ratio100(basic_samples[0].op_cycles,basic_samples[1].op_cycles),valid,2);
        uint32_t us=basic_samples[hw].op_cycles/(SYSTEM_CLINT_HZ/1000000u);
        basic_field(7,396,148,120,us ? basic_payload(demo)/us:0,basic_samples[hw].valid && us,0);
        basic_field(8,554,13,65,hw,1,3);
        if(basic_config.view) {
            BasicSample *sample=&basic_samples[hw];
            basic_field(11,240,184,84,sample->reads,sample->valid && hw,0);
            basic_field(12,240,220,84,sample->writes,sample->valid && hw,0);
            basic_field(13,240,256,84,sample->rwait,sample->valid && hw,0);
            basic_field(14,240,292,84,sample->wwait,sample->valid && hw,0);
        }
    }
    publish_pixels();
}
static void basic_labels(uint32_t demo) {
    if(demo==DEMO_BUFFER) {
        book_text(16,56,basic_config.mode ? "双缓冲 / 后台绘制后换页":"单缓冲 / 扫描中写前台",UI_ICE,1);
        static const char *const labels[6]={"SWAPS","WAIT_US","OUT_HZ","MISSED","PAUSED","STEP"};
        for(uint32_t n=0;n<6u;++n)book_text(n<3u ? 16u:336u,84u+(n%3u)*26u,labels[n],UI_CREAM,1);
        book_text(16,430,basic_config.paused ? "W切换速度  S切换模式  ENTER继续":"W切换速度  S切换模式  ENTER暂停",UI_CREAM,1);
        book_text(16,454,"D参考线  A返回",UI_ICE,1);
    } else {
        for(uint32_t n=0;n<2u;++n) {
            uint32_t x=16u+n*320u;
            book_text(x+72u,62,"FPS",UI_CREAM,1);
            book_text(x+72u,88,demo==DEMO_FILL ? "FILL_US":"COPY_US",UI_CREAM,1);
            book_text(x+72u,114,"RENDER_US",UI_CREAM,1);
        }
        book_text(16,148,"SPEEDUP",UI_ICE,1);book_text(336,148,"MB/S",UI_ICE,1);
        if(basic_config.view) {
            static const char *const labels[5]={"AR","AW","RD WAIT","WR WAIT","LOAD"};
            for(uint32_t n=0;n<5u;++n)book_text(20,184u+n*36u,labels[n],UI_CREAM,1);
            demo_number(240,328,72,basic_load(demo),1,1,UI_GOLD,UI_BG);
            if(demo==DEMO_FILL)book_text(20,388,"AXI MAX 16 X 32BIT",UI_STONE,1);
        }
        if(demo==DEMO_FILL && !basic_config.view) {
            char load[11],out[40]="LOAD ";decimal(load,basic_load(demo));uint32_t at=5,k=0;
            while(load[k]){out[at++]=load[k++];}const char *tail=" / 32 X 24";while(*tail)out[at++]=*tail++;out[at]=0;
            book_text(16,402,out,UI_STONE,0);
        }
        if(demo==DEMO_COPY) {
            book_text(32,390,"图像",UI_STONE,1);demo_number(72,390,24,basic_config.image+1u,1,1,UI_STONE,UI_BG);
            book_text(106,390,basic_config.image ? "0 A.D.":"SUPERTUXKART",UI_STONE,1);
            book_text(352,390,"256 X 192 RGB565",UI_STONE,1);
        }
        book_text(16,430,demo==DEMO_COPY ? (basic_config.view ? "W复制次数  D换图  ENTER图像":"W复制次数  D换图  ENTER详情"):
                  basic_config.view ? "W方块数量  D换色  ENTER图像":"W方块数量  D换色  ENTER详情",UI_CREAM,1);
        book_text(16,454,"S切换 CPU/FPGA  A返回",UI_ICE,1);
    }
}
// Static backgrounds and source preview are initialized once in both pages.
// They are common setup, outside CPU/FPGA statistics; no game assets are changed.
static void basic_buffer_scene(uint32_t frame);
static void basic_prime(uint32_t demo) {
    basic_field_valid[0]=basic_field_valid[1]=basic_number_valid[0]=basic_number_valid[1]=0;
    basic_scene_valid[0]=basic_scene_valid[1]=0;
    for(uint32_t page=0;page<2u;++page) {
        demo_skin(demo,demo==DEMO_BUFFER ? "FPGA":"");
        if(demo!=DEMO_BUFFER)demo_metrics();
        
        if(demo==DEMO_FILL)demo_window(basic_config.view ? 352u:16u,176,
            basic_config.view ? 256u:608u,basic_config.view ? 192u:224u);
        if(demo==DEMO_COPY) {
            if(!basic_config.view)demo_window(32,176,256,192);
            demo_window(352,176,256,192);
        }
        if(demo==DEMO_BUFFER)demo_window(16,176,608,224);
        if(demo==DEMO_COPY && !basic_config.view) {
            if(copy_image(basic_source(basic_config.image),BASIC_IMAGE_STRIDE,
                BASIC_IMAGE_X,BASIC_IMAGE_Y,BASIC_IMAGE_W,BASIC_IMAGE_H))fail("FAIL basic preview");
        }
        if(demo==DEMO_BUFFER)basic_buffer_scene(0);
        basic_labels(demo);
        if(present_frame())fail("FAIL basic init");
    }
}
static void basic_buffer_scene(uint32_t frame) {
    uint32_t page=draw_page(),x=24u+basic_bounce(frame*(8u<<basic_config.speed),360u);
    if(!basic_scene_valid[page]) {
        paint(16,BASIC_VIEW_Y,608,BASIC_VIEW_H,0x084b,1);
        if(basic_config.grid)for(uint32_t y=200;y<400;y+=40u)paint(16,y,608,2,0x7bef,1);
    } else if(basic_bar_x[page]==x)return;
    else {
        // Restore only the previous bars. Avoid a full-viewport clear flashing
        // on the front page; the visible discontinuity is actual scan/write
        // overlap, never a pre-drawn split image or a fabricated tear counter.
        for(uint32_t n=0;n<3u;++n) {
            uint32_t old=basic_bar_x[page]+96u*n;
            paint(old,184,24,208,0x084b,1);
            if(basic_config.grid)for(uint32_t y=200;y<392;y+=40u)paint(old,y,24,2,0x7bef,1);
        }
    }
    for(uint32_t n=0;n<3u;++n)paint(x+96u*n,184,24,208,0xffff,1);
    basic_bar_x[page]=x;basic_scene_valid[page]=1;
    publish_pixels();
}
static void basic_buffer_target(uint32_t back) {
    uint32_t status=mmio_read(GFX_BASE+GFX_STATUS);
    uint32_t active=(status&GFX_ACTIVE_PAGE) ? 1u:0u;
    if(wait_display_page(active))fail("FAIL buffer target");
    uint32_t page=active^(back!=0u);
    draw_buffer=page ? FRAMEBUFFER_B:FRAMEBUFFER;select_draw_page();
}
static void basic_buffer_loop(void) {
    // Entry always starts in single-buffer/tearing mode. Only S changes mode.
    volatile uint32_t *words=(volatile uint32_t *)&basic_config;
    for(uint32_t n=0;n<sizeof(basic_config)/sizeof(*words);++n)words[n]=0;
    basic_config.grid=1u; // speed remains 0: always enter at the lowest step (8 px).
    basic_swaps=basic_missed=basic_swap_us=basic_video_hz=basic_completed_frame=0;
    basic_buffer_target(1);basic_prime(DEMO_BUFFER);
    uint32_t anchor=cycle_now(),hz_start=anchor;
    uint32_t video=mmio_read(GFX_BASE+GFX_FRAME_COUNT),hz_video=video,frame=1;
    for(;;) {
        uint32_t keys=button_event();if(keys==4u)return;
        if(basic_control(&basic_config,DEMO_BUFFER,keys) && (keys==2u || keys==8u)) {
            // Repaint only retired pages while changing mode/grid; a front-page
            // full-screen repaint would obscure the comparison with flicker.
            basic_buffer_target(1);basic_prime(DEMO_BUFFER);frame=1;
            basic_swaps=basic_missed=basic_swap_us=basic_video_hz=basic_completed_frame=0;
            anchor=cycle_now();hz_start=anchor;
            video=mmio_read(GFX_BASE+GFX_FRAME_COUNT);hz_video=video;
        }
        basic_buffer_target(basic_config.mode);
        while((uint32_t)(cycle_now()-anchor)<BASIC_BUFFER_PHASE_CYCLES) {}
        basic_buffer_scene(frame);basic_completed_frame=frame;
        basic_hud(DEMO_BUFFER,1);
        uint32_t start=cycle_now();
        // In single-buffer mode this is a SAME-page request used only to pace
        // the next mid-scan update. It cannot undo the current frame's tear.
        // Double-buffer mode presents the completed back page at vblank.
        if(present_frame())fail("FAIL buffer present");
        uint32_t now=cycle_now(),next_video=mmio_read(GFX_BASE+GFX_FRAME_COUNT);
        basic_swap_us=(now-start)/(SYSTEM_CLINT_HZ/1000000u);
        if(next_video-video>1u)basic_missed+=next_video-video-1u;
        video=next_video;anchor=now;
        if(basic_config.mode)++basic_swaps;
        if(!basic_config.paused)++frame;
        uint32_t elapsed=now-hz_start;
        if(elapsed>=SYSTEM_CLINT_HZ) {
            basic_video_hz=frame_measured_fps(next_video-hz_video,elapsed);
            hz_start=now;hz_video=next_video;
        }
    }
}
static void basic_return_to_menu(void) {
    publish_pixels();
    uint32_t active=(mmio_read(GFX_BASE+GFX_STATUS)&GFX_ACTIVE_PAGE) ? 1u : 0u;
    if(wait_display_page(active))fail("FAIL basic exit page");
    // Re-establish the retired back page from the acknowledged hardware state.
    draw_buffer=active ? FRAMEBUFFER : FRAMEBUFFER_B;select_draw_page();
    menu_repaint_pages=2u;
    puts_uart("BASIC EXIT -> MENU BOTH PAGES\r\n");
}
static void basic_report(uint32_t demo,uint32_t hw) {
    BasicSample *s=&basic_samples[hw];
    uart_number("BASIC ",demo);uart_number(" HW ",hw);uart_number(" LOAD ",basic_load(demo));
    uart_number(" FPS ",s->fps);uart_number(" OP_US ",s->op_cycles/(SYSTEM_CLINT_HZ/1000000u));
    uart_number(" FRAME_US ",s->frame_us);uart_number(" AR ",s->reads);uart_number(" AW ",s->writes);
    uart_number(" RWAIT ",s->rwait);uart_number(" WWAIT ",s->wwait);puts_uart("\r\n");
}
static void basic_demo_loop(uint32_t demo) {
    if(demo==DEMO_BUFFER) {basic_buffer_loop();return;}
    volatile uint32_t *config_words=(volatile uint32_t *)&basic_config;
    for(uint32_t n=0;n<sizeof(basic_config)/sizeof(*config_words);++n)config_words[n]=0;
    basic_config.speed=basic_config.grid=1u;
    basic_reset_sample(&basic_samples[0]);basic_reset_sample(&basic_samples[1]);
    basic_swaps=basic_missed=basic_swap_us=basic_video_hz=0;
    basic_completed_frame=0;
    if(demo==DEMO_COPY)basic_init_images();
    basic_prime(demo);
    uint32_t hw=demo==DEMO_BUFFER ? 1u : 0u,frame=0,count=0;
    uint32_t total_elapsed=0,total_op=0,total_render=0,ar=0,aw=0,rw=0,ww=0;
    uint32_t previous=cycle_now(),video=mmio_read(GFX_BASE+GFX_FRAME_COUNT);
    uint32_t hz_start=previous,hz_video=video;
    for(;;) {
        uint32_t keys=button_event();if(keys==4u)return;
        uint32_t old_mode=basic_config.mode;
        if(basic_control(&basic_config,demo,keys)) {
            // A mode change preserves comparable same-configuration readings.
            // Any workload/image/color/view change starts two fresh samples.
            if(demo!=DEMO_BUFFER && old_mode==basic_config.mode) {
                basic_reset_sample(&basic_samples[0]);basic_reset_sample(&basic_samples[1]);
            }
            if(demo!=DEMO_BUFFER) {
                hw=basic_config.mode;frame=0;
                basic_prime(demo);
            }
            count=total_elapsed=total_op=total_render=ar=aw=rw=ww=0;
            previous=cycle_now();video=mmio_read(GFX_BASE+GFX_FRAME_COUNT);
            hz_start=previous;hz_video=video;
        }
        uint32_t render_start=cycle_now();BasicSample batch;basic_reset_sample(&batch);
        if(demo==DEMO_BUFFER)basic_buffer_scene(frame);
        else {
            if(demo==DEMO_FILL) {
                if(basic_config.view)paint(352,176,256,192,0x0843,hw);
                else paint(16,BASIC_VIEW_Y,608,BASIC_VIEW_H,0x0843,hw);
            }
            batch.op_cycles=basic_batch(demo,hw,frame,&batch);
        }
        basic_completed_frame=frame;
        basic_hud(demo,hw);
        uint32_t render_cycles=cycle_now()-render_start;
        uint32_t swap_start=cycle_now();
        if(present_frame())fail("FAIL basic present");
        uint32_t now=cycle_now(),next_video=mmio_read(GFX_BASE+GFX_FRAME_COUNT);
        basic_swap_us=(now-swap_start)/(SYSTEM_CLINT_HZ/1000000u);
        if(next_video-video>1u)basic_missed+=next_video-video-1u;
        video=next_video;
        ++basic_swaps;
        total_elapsed+=now-previous;previous=now;
        total_op+=batch.op_cycles;total_render+=render_cycles;
        ar+=batch.reads;aw+=batch.writes;rw+=batch.rwait;ww+=batch.wwait;
        if(!basic_config.paused || demo!=DEMO_BUFFER)++frame;
        uint32_t hz_cycles=now-hz_start;
        if(hz_cycles>=SYSTEM_CLINT_HZ) {
            basic_video_hz=frame_measured_fps(next_video-hz_video,hz_cycles);
            hz_start=now;hz_video=next_video;
        }
        if(++count==BASIC_SAMPLE_FRAMES) {
            BasicSample *s=&basic_samples[hw];
            s->fps=frame_measured_fps(count,total_elapsed);s->op_cycles=total_op/count;
            s->frame_us=total_render/(count*(SYSTEM_CLINT_HZ/1000000u));
            s->reads=ar/count;s->writes=aw/count;s->rwait=rw/count;s->wwait=ww/count;s->valid=1;
            if(demo!=DEMO_BUFFER)basic_report(demo,hw);
            count=total_elapsed=total_op=total_render=ar=aw=rw=ww=0;
        }
    }
}
