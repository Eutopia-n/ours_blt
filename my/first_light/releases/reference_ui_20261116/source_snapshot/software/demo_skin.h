#ifndef DEMO_SKIN_H
#define DEMO_SKIN_H
/* Fullscreen experiment skin. Static decoration is prepared outside the
 * measured workload; all original test pixels and viewports stay intact. */
#define UI_BG 0x1084u
#define UI_HEADER 0x18e6u
#define UI_PANEL 0x10a6u
#define UI_CREAM 0xf759u
#define UI_ICE 0x9f1cu
#define UI_GOLD 0xe631u
#define UI_STONE 0x63b1u
static void demo_window(uint32_t x,uint32_t y,uint32_t w,uint32_t h) {
    if(x>=3u && x+w+3u<=640u) {
        paint(x-3u,y-3u,w+6u,1,UI_STONE,1);paint(x-3u,y+h+2u,w+6u,1,UI_STONE,1);
        paint(x-3u,y-3u,1,h+6u,UI_STONE,1);paint(x+w+2u,y-3u,1,h+6u,UI_STONE,1);
    } else {
        paint(x,y-2u,w,1,UI_STONE,1);paint(x,y+h+2u,w,1,UI_STONE,1);
    }
}
static void demo_skin(uint32_t demo,const char *engine) {
    static const uint8_t icons[6]={BOOK_ICON_FILL,BOOK_ICON_COPY,BOOK_ICON_BUFFER,
        BOOK_ICON_KEY,BOOK_ICON_ALPHA,BOOK_ICON_PRESSURE};
    paint(0,0,640,480,UI_BG,1);paint(0,0,640,44,UI_HEADER,1);
    paint(0,44,640,1,0x6a87,1);
    book_stamp(icons[demo],16,6,1,0);
    book_text(60,9,demo_names[demo],UI_CREAM,2);
    if(demo==DEMO_BENCH)book_text(316,28,demo_details[demo],UI_STONE,0);
    uint32_t badge_width=book_text_width(engine,0)+17u;
    paint(554,13,badge_width,19,0x296a,1);book_text(562,19,engine,0xe651,0);
    paint(16,416,608,1,0x3a0cu,1);
}
static void demo_metrics(void) {
    for(uint32_t x=16;x<640u;x+=320u) {
        paint(x,52,288,100,UI_PANEL,1);paint(x,52,288,2,0x3a0cu,1);
        paint(x,52,2,100,BOOK_GOLD,1);
    }
}
#endif
