#ifndef DEMO_SKIN_H
#define DEMO_SKIN_H
/* Fullscreen experiment skin. Static decoration is prepared outside the
 * measured workload; all original test pixels and viewports stay intact. */
#define UI_BG 0x1084u
#define UI_HEADER 0x18e6u
#define UI_PANEL 0x10a6u
#define UI_CREAM 0xf759u
#define UI_ICE 0x9f1cu
#define UI_GOLD 0xe651u
#define UI_DESK 0x10a4u
#define UI_STONE 0x63b1u
static void demo_window(uint32_t x,uint32_t y,uint32_t w,uint32_t h) {
    if(x>=3u && x+w+3u<=640u) {
        paint(x-3u,y-3u,w+6u,1,UI_STONE,1);paint(x-3u,y+h+2u,w+6u,1,UI_STONE,1);
        paint(x-3u,y-3u,1,h+6u,UI_STONE,1);paint(x+w+2u,y-3u,1,h+6u,UI_STONE,1);
    } else {
        paint(x,y-3u,w,1,UI_STONE,1);paint(x,y+h+2u,w,1,UI_STONE,1);
    }
}
// Draw a badge and bounded numeric field with the reference bitmap fonts.
static void demo_badge(uint32_t x,uint32_t y,const char *engine) {
    uint32_t w=book_text_width(engine,0)+17u;
    cpu_fill(x,y,w,19,0x296a);book_text(x+8,y+6,engine,UI_GOLD,0);
}
static void demo_number(uint32_t x,uint32_t y,uint32_t width,uint32_t value,
                        uint32_t valid,uint32_t mode,uint16_t color,uint16_t background) {
    char out[11];uint32_t pitch=mode==2u ? 18u:mode ? 12u:6u;
    if(!valid){out[0]='-';out[1]='-';out[2]=0;}
    else decimal_field(out,value,width/pitch);
    cpu_fill(x,y,width,mode==2u ? 28u:14u,background);
    book_text(x,y,out,color,mode);
}
static void demo_skin(uint32_t demo,const char *engine) {
    static const uint8_t icons[6]={BOOK_ICON_FILL,BOOK_ICON_COPY,BOOK_ICON_BUFFER,
        BOOK_ICON_KEY,BOOK_ICON_ALPHA,BOOK_ICON_PRESSURE};
    paint(0,0,640,480,UI_BG,1);paint(0,0,640,44,UI_HEADER,1);
    paint(0,44,640,1,0x6a87,1);book_stamp(icons[demo],16,6,1,0);
    book_text(60,9,demo==DEMO_BENCH ? "SPRITE压力":demo_names[demo],UI_CREAM,2);
    demo_badge(554,13,engine[0] ? engine:"CPU");
    paint(16,416,608,1,0x3a0c,1);
}
static void demo_metrics(void) {
    for(uint32_t x=16;x<640u;x+=320u) {
        paint(x,54,288,87,UI_DESK,1);
        demo_badge(x+8,60,x==16u ? "CPU":"FPGA");
    }
}
#endif
