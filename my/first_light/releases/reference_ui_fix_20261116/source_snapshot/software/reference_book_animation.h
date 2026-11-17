#ifndef REFERENCE_BOOK_ANIMATION_H
#define REFERENCE_BOOK_ANIMATION_H
/* The prototype uses 154 curved strips, separate cover/paper delays and a
 * 5200-pixel perspective distance. CPU builds descriptors; FPGA draws pixels. */
static uint32_t book_command_count;
static int32_t book_abs(int32_t x){return x<0 ? -x:x;}
static int32_t book_ease(int32_t t) {
    if(t<=0)return 0;
    if(t>=65536)return 65536;
    int32_t t2=(int32_t)((int64_t)t*t>>16),t3=(int32_t)((int64_t)t2*t>>16);
    return (int32_t)((int64_t)t3*(655360-15*t+6*t2)>>16);
}
static int32_t book_phase(int32_t t,int32_t start,int32_t duration) {
    return book_ease((t-start)*4096/duration*16);
}
/* Angle has 1024 steps per revolution, with eight fractional bits. */
static int32_t book_sin(int32_t a) {
    uint32_t u=(uint32_t)a&262143u,n=u>>8;
    return book_sine[n]+(book_sine[n+1u]-book_sine[n])*(int32_t)(u&255u)/256;
}
static void book_command(uint32_t source,uint32_t pitch,int32_t x,int32_t y,
                         int32_t w,int32_t h,uint32_t sw,uint32_t sh,
                         uint32_t alpha,uint32_t shade,uint32_t flags,uint16_t color) {
    if(w<=0 || h<=0 || x>=640 || y>=480 || x+w<=0 || y+h<=0 || !alpha)return;
    if(book_command_count>=512u)fail("FAIL UI list");
    volatile uint32_t *c=(volatile uint32_t *)(uintptr_t)(BOOK_COMMAND_BASE+32u*book_command_count++);
    c[0]=source;c[1]=pitch;c[2]=(uint16_t)x|((uint32_t)w<<16);
    c[3]=(uint16_t)y|((uint32_t)h<<16);
    c[4]=sw ? ((sw*4096u+(uint32_t)w/2u)/(uint32_t)w)<<4:0;
    c[5]=sh ? ((sh*4096u+(uint32_t)h/2u)/(uint32_t)h)<<4:0;
    c[6]=color|(alpha<<16)|(flags<<24);c[7]=shade|(sw<<8)|(sh<<18);
}
static void book_submit(uint32_t background,uint16_t color) {
    if(!book_command_count)book_command(0,0,0,0,1,1,0,0,255,255,0,color);
    publish_pixels();
#ifdef UI_NATIVE_REFERENCE
    extern void book_native_submit(uint32_t,uint16_t,uint32_t);
    book_native_submit(background,color,book_command_count);
#else
    select_draw_page();mmio_write(GFX_BASE+GFX_OPERATION,3);
    mmio_write(GFX_BASE+GFX_SRC,BOOK_COMMAND_BASE);mmio_write(GFX_BASE+GFX_SRC_STRIDE,background);
    mmio_write(GFX_BASE+GFX_DST,draw_buffer);mmio_write(GFX_BASE+GFX_WIDTH,640);
    mmio_write(GFX_BASE+GFX_HEIGHT,480);mmio_write(GFX_BASE+GFX_STRIDE,1280);
    mmio_write(GFX_BASE+GFX_COLOR,0xa000u|book_command_count);
    mmio_write(GFX_BASE+GFX_COLOR_KEY,color);mmio_write(GFX_BASE+GFX_COMMAND,1);
    if(wait_render())fail("FAIL UI projection");
#endif
}
static void book_capture(void) {
    publish_pixels();
    const volatile uint32_t *src=(const volatile uint32_t *)(uintptr_t)draw_buffer;
    volatile uint32_t *dst=(volatile uint32_t *)(uintptr_t)BOOK_CACHE_BASE;
    for(uint32_t n=0;n<FRAMEBUFFER_BYTES/4u;++n)dst[n]=src[n];
    publish_pixels();book_cache_valid=1;book_cache_key=book_menu_key();
}
typedef struct {int32_t x,y,w,h,z;uint16_t u,sw;uint8_t back,flip,light;} BookStrip;
static BookStrip book_mesh[154];
static int32_t book_round_div(int32_t n,int32_t d){return n>=0 ? (n+d/2)/d:-((-n+d/2)/d);}
static void book_shadow(int32_t hinge,int32_t top,int32_t height,int32_t free_x,int32_t free_z) {
    if(free_z<4)return;
    int32_t shadow_x=hinge+free_x+free_z/10;
    int32_t y0=top+(free_z*35/1000>4 ? free_z*35/1000:4);
    int32_t y1=top+height+(free_z*65/1000>4 ? free_z*65/1000:4);
    for(int32_t band=0;band<3;++band) {
        int32_t pad=6-band*3,x0=hinge-2,x1=shadow_x+pad;
        int32_t low=y0-pad<top+4 ? y0-pad:top+4,high=y1+pad>top+height+2 ? y1+pad:top+height+2;
        int32_t left=x0<x1 ? x0:x1,right=x0>x1 ? x0:x1;
        for(int32_t n=0;n<24;++n) {
            int32_t xx=left+(right-left)*n/24,end=left+(right-left)*(n+1)/24;
            if(end<=xx)continue;
            int32_t fraction=x1==x0 ? 0:(xx-x0)*1024/(x1-x0);
            int32_t yy=top+4+(y0-pad-top-4)*fraction/1024;
            int32_t bottom=top+height+2+(y1+pad-top-height-2)*fraction/1024;
            book_command(0,0,xx,yy,end-xx,bottom-yy+1,0,0,
                         band==0 ? 12u:band==1 ? 6u:9u,255,0,0x0842u);
        }
        (void)low;(void)high;
    }
}
static void book_sheet(uint32_t paper,int32_t hinge,int32_t top,int32_t width,int32_t height,
                       int32_t angle,int32_t bend) {
    int32_t x=0,z=0;
    for(uint32_t n=0;n<154u;++n) {
        int32_t normal=angle+bend*book_sin((int32_t)((n*2u+1u)*131072u/308u))/16384;
        int32_t cosine=book_sin(normal+65536),sine=book_sin(normal);
        int32_t nx=x+width*cosine/(154*64),nz=z+width*sine/(154*64);
        int32_t a=hinge+book_round_div(x*5200,1331200-z);
        int32_t b=hinge+book_round_div(nx*5200,1331200-nz);
        int32_t h0=book_round_div(height*1331200,1331200-z),h1=book_round_div(height*1331200,1331200-nz);
        BookStrip *s=&book_mesh[n];
        s->x=a<b ? a:b;s->w=book_abs(b-a);s->h=(h0+h1+1)/2;
        s->y=top+height/2-(z+nz)/20480-s->h/2;s->z=z+nz;
        s->back=cosine<0;s->flip=b<a;
        uint32_t source_w=s->back ? (paper ? 306u:153u):paper ? 158u:278u;
        uint32_t first=(n*source_w+77u)/154u,last=((n+1u)*source_w+77u)/154u;
        s->u=(uint16_t)first;s->sw=(uint16_t)(last>first ? last-first:1u);
        int32_t light=book_round_div(819*16384+205*book_abs(cosine),16384*32);
        s->light=(uint8_t)(light*255/32);x=nx;z=nz;
    }
    book_shadow(hinge,top,height,x/256,z/256);
    /* Insertion sort is stable, as in the prototype's depth ordering. */
    for(uint32_t n=1;n<154u;++n) {
        BookStrip s=book_mesh[n];uint32_t k=n;
        while(k && book_mesh[k-1u].z>s.z){book_mesh[k]=book_mesh[k-1u];--k;}book_mesh[k]=s;
    }
    for(uint32_t n=0;n<154u;++n) {
        const BookStrip *s=&book_mesh[n];uint32_t source,pitch,sh,sw=s->sw,flags=1u;
        if(s->back) {
            uint32_t source_w=paper ? 306u:153u,col=source_w-s->u-sw;
            source=paper ? BOOK_CACHE_BASE+18u*1280u+(14u+col)*2u:
                ASSET_BASE+book_resources[BOOK_BLANK].base+9u*320u+(7u+col);
            pitch=paper ? 1280u:320u;sh=paper ? 462u:231u;flags|=2u|8u;if(!paper)flags|=16u;
        } else if(paper) {
            source=ASSET_BASE+book_resources[BOOK_LEAF].base+s->u;
            pitch=158;sh=231;flags|=16u;
        } else {source=ASSET_BASE+book_resources[BOOK_FRONT].base+s->u;pitch=278;sh=396;flags|=16u;}
        if(s->flip)flags^=2u;
        book_command(source,pitch,s->x,s->y,s->w,s->h,sw,sh,255,s->light,flags,0);
    }
    if(!paper && angle>1043 && angle<130029) {
        int32_t xx=hinge+book_round_div(x*5200,1331200-z),hh=book_round_div(height*1331200,1331200-z);
        int32_t yy=top+height/2-z/10240-hh/2;
        book_command(0,0,xx-1,yy,3,hh,0,0,255,255,0,0x6a87u);
        book_command(0,0,xx-1,yy,1,hh,0,0,255,255,0,0xd5afu);
    }
}
static void book_open_pose(uint32_t frame) {
    int32_t t=(int32_t)(frame*65536u/120u);
    int32_t pose=book_phase(t,8520,48497),cp=book_phase(t,7864,41943),lp=book_phase(t,18350,40632);
    int32_t hinge=174+146*book_phase(t,12452,43909)/65536,top=32-14*pose/65536;
    int32_t width=278+28*pose/65536,height=396+66*pose/65536;
    int32_t ca=cp*2,la=lp*2;
    if(t>58982){int32_t sine=book_sin((t-58982)*20);la-=sine*sine/357913;}
    int32_t bend=15855LL*book_sin(la)/16384;
    book_command_count=0;
    book_command(BOOK_CACHE_BASE+18u*1280u+640u,1280,hinge,top,
        298+18*pose/65536,416+46*pose/65536,316,462,255,255,9,0);
    int32_t cover_depth=width*book_sin(ca),paper_depth=width*book_sin(la)+1638;
    if(cover_depth<paper_depth){book_sheet(0,hinge,top,width,height,ca,0);book_sheet(1,hinge+1,top,width,height,la,bend);}
    else {book_sheet(1,hinge+1,top,width,height,la,bend);book_sheet(0,hinge,top,width,height,ca,0);}
    int32_t bridge=book_phase(t,7864,4588);
    if(bridge<65536) {
        uint32_t opacity=(uint32_t)(255-255*bridge/65536);
        book_command(ASSET_BASE+book_resources[BOOK_DESK].base,128,0,0,640,480,320,240,opacity,255,32,0);
        book_command(ASSET_BASE+book_resources[BOOK_COVER].base,155,170,32,310,416,155,208,opacity,255,17,0);
        book_command(ASSET_BASE+book_resources[BOOK_FRONT].base,278,174,32,278,396,278,396,opacity,255,17,0);
    }
    if(t<19661) {
        int32_t a=82575LL*book_phase(t,0,10486)/65536,cosine=book_sin(a+65536);
        int32_t cw=54*book_abs(cosine)/16384;if(cw<2)cw=2;
        int32_t opacity=255-255*book_phase(t,13107,6554)/65536;
        int32_t anchor=472+(hinge-174)*3/10,xx=cosine>=0 ? anchor-cw:anchor;
        book_command(0,0,xx+cw/2,238,book_abs(anchor-3-xx-cw/2)+1,4,0,0,opacity,255,0,0x6a87);
        book_command(ASSET_BASE+book_resources[BOOK_CLASP].base,108,xx,222-3*book_sin(a)/16384,
                     cw,40,54,40,opacity,255,cosine<0 ? 3u:1u,0);
    }
    if(t>60293)book_command(BOOK_CACHE_BASE,1280,0,0,640,480,640,480,
                           255*book_phase(t,60293,5243)/65536,255,0,0);
    book_submit((ASSET_BASE+book_resources[BOOK_DESK].base)|1u,0);
}
static void book_animate(uint32_t closing) {
    if(closing){book_cover();publish_pixels();if(present_frame())fail("FAIL cover present");return;}
    book_menu_frame();book_load(BOOK_CLASP);book_capture();
    uint32_t start=cycle_now();book_anim_frames=0;
    for(uint32_t frame=1;frame<=120u;) {
        if(frame==120u){if(copy_image(BOOK_CACHE_BASE,1280,0,0,640,480))fail("FAIL opening final");}
        else book_open_pose(frame);
        if(present_frame())fail("FAIL book present");
        ++book_anim_frames;
        while((uint32_t)(cycle_now()-start)<frame*(SYSTEM_CLINT_HZ/50u)){}
        if(frame==120u)break;
        uint32_t next=(cycle_now()-start)/(SYSTEM_CLINT_HZ/50u);
        frame=next>frame ? next:frame+1u;if(frame>120u)frame=120u;
    }
    book_anim_ms=(cycle_now()-start)/(SYSTEM_CLINT_HZ/1000u);
    uart_number("BOOK FRAMES ",book_anim_frames);uart_number(" MS ",book_anim_ms);puts_uart("\r\n");
}
static void book_turn(void) {
    uint32_t backward=!menu_level,old=draw_buffer==FRAMEBUFFER ? FRAMEBUFFER_B:FRAMEBUFFER;
    book_menu_frame();book_capture();
    /* Save the turning face at native resolution. The stationary old face is
     * sampled at 2x in transient storage; the final target remains native. */
    volatile uint16_t *face=(volatile uint16_t *)(uintptr_t)(ASSET_BASE+0x8000u);
    volatile uint16_t *still=(volatile uint16_t *)(uintptr_t)(ASSET_BASE+0x42800u);
    const volatile uint16_t *src=(const volatile uint16_t *)(uintptr_t)old;
    uint32_t fold_x=backward ? 22u:326u,still_x=backward ? 326u:22u;
    for(uint32_t y=0;y<410u;++y)for(uint32_t x=0;x<292u;++x)face[y*292u+x]=src[(y+38u)*640u+fold_x+x];
    for(uint32_t y=0;y<205u;++y)for(uint32_t x=0;x<146u;++x)still[y*146u+x]=src[(y*2u+38u)*640u+still_x+x*2u];
    publish_pixels();uint32_t start=cycle_now();
    for(uint32_t frame=0;frame<=32u;) {
        int32_t progress=book_ease(frame*65536u/32u),theta=progress*2;
        int32_t hinge=backward ? 314+12*progress/65536:326-12*progress/65536;
        int32_t x=0,z=0;book_command_count=0;
        book_command(ASSET_BASE+0x42800u,292,still_x,38,292,410,146,205,255,255,0,0);
        for(uint32_t n=0;n<146u;++n) {
            int32_t normal=theta+(12516LL*book_sin(theta)/16384)*book_sin((n*2u+1u)*131072u/292u)/16384;
            int32_t cosine=book_sin(normal+65536),nx=x+cosine/32,nz=z+book_sin(normal)/32;
            int32_t a=hinge+(backward ? -1:1)*book_round_div(x*5200,1331200-z);
            int32_t b=hinge+(backward ? -1:1)*book_round_div(nx*5200,1331200-nz);
            BookStrip *s=&book_mesh[n];s->x=a<b ? a:b;s->w=book_abs(b-a);
            s->h=(book_round_div(410*1331200,1331200-z)+book_round_div(410*1331200,1331200-nz)+1)/2;
            s->y=243-s->h/2-(z+nz)/20480;s->z=z;s->back=cosine<0;s->u=n;
            s->light=255-(16*(16384-book_abs(cosine))*255/1638400);x=nx;z=nz;
        }
        for(uint32_t n=1;n<146u;++n){BookStrip s=book_mesh[n];uint32_t k=n;while(k && book_mesh[k-1].z>s.z){book_mesh[k]=book_mesh[k-1];--k;}book_mesh[k]=s;}
        for(uint32_t k=0;k<146u;++k) {
            const BookStrip *s=&book_mesh[k];uint32_t source,pitch;
            if(s->back){uint32_t col=backward ? 326u+s->u*2u:312u-s->u*2u;source=BOOK_CACHE_BASE+38u*1280u+col*2u;pitch=1280;}
            else {uint32_t col=backward ? 290u-s->u*2u:s->u*2u;source=ASSET_BASE+0x8000u+col*2u;pitch=584;}
            book_command(source,pitch,s->x,s->y,s->w,s->h,2,410,255,s->light,0,0);
        }
        if(frame==32u)book_command(BOOK_CACHE_BASE,1280,0,0,640,480,640,480,255,255,0,0);
        book_submit(BOOK_CACHE_BASE,0);if(present_frame())fail("FAIL chapter present");
        while((uint32_t)(cycle_now()-start)<frame*(SYSTEM_CLINT_HZ/50u)){}
        if(frame==32u)break;
        uint32_t next=(cycle_now()-start)/(SYSTEM_CLINT_HZ/50u);
        frame=next>frame ? next:frame+1u;if(frame>32u)frame=32u;
    }
    book_assets_ready=0;book_transient=0xffffffffu;
}
#endif
