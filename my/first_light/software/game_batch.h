#ifndef GAME_BATCH_H
#define GAME_BATCH_H
/* Game-only DDR queue, mutually exclusive with menu/effect/pressure scratch.
 * Every flush is blocking through the final B response. CPU overlays follow
 * game_batch_end(), so alpha order and the draw-page ownership are retained. */
static struct {
    uint32_t count,positions,caps,source,side,alpha,flags,run;
} game_batch;

static void game_batch_flush(void) {
    if(game_batch.count) {
        int result=game_batch.positions ?
            gfx_positions_submit(game_batch.source,game_batch.side,GFX_BATCH_BASE,game_batch.count,
                                 (uint8_t)game_batch.alpha,0,game_batch.flags):
            gfx_batch_submit(GFX_BATCH_BASE,game_batch.count);
        if(result)fail("FAIL game batch");
    }
    game_batch.count=0;game_batch.positions=0;game_batch.side=0;game_batch.run=0;
}
static void game_batch_begin(void) {
    uint32_t caps=mmio_read(GFX_BASE+GFX_CAPABILITIES);
    game_batch.caps=(caps&GFX_CAP_BATCH) ? caps:0;
    game_batch.count=0;game_batch.positions=0;game_batch.side=0;game_batch.run=0;
}
static void game_batch_end(void) {
    game_batch_flush();game_batch.caps=0;
}
static void game_batch_command(uint32_t source,uint32_t pitch,uint32_t x,uint32_t y,
                               uint32_t width,uint32_t height,uint32_t alpha,
                               uint32_t flags,uint32_t fill) {
    uint32_t destination=draw_buffer+y*FRAME_STRIDE+x*2u;
    uint32_t side=!fill && width==height && pitch==width*2u && !(source&3u) &&
        (width==4u || width==16u || width==24u || width==32u) ? width:0;
    uint32_t same=side && game_batch.side==side && game_batch.source==source &&
        game_batch.alpha==alpha && game_batch.flags==flags;
    volatile uint32_t *positions=(volatile uint32_t *)(uintptr_t)GFX_BATCH_BASE;
    if(game_batch.positions) {
        if(same && game_batch.count<GFX_POSITION_CAPACITY) {
            positions[game_batch.count++]=destination;return;
        }
        game_batch_flush();
    } else if(same && game_batch.run>=7u && (game_batch.caps&GFX_CAP_POSITIONS)) {
        // Short runs stay in the mixed list to avoid tiny DMA submissions.
        // A proven consecutive run of eight becomes packed positions. The
        // tail's forward 32->4-byte compaction cannot overwrite unread entries.
        uint32_t run=game_batch.run,first=game_batch.count-run;
        game_batch.count=first;game_batch_flush();
        const volatile GfxBatchCommand *old=(const volatile GfxBatchCommand *)(uintptr_t)GFX_BATCH_BASE;
        for(uint32_t i=0;i<run;++i)positions[i]=old[first+i].destination;
        positions[run]=destination;
        game_batch.positions=1;game_batch.count=run+1u;
        game_batch.source=source;game_batch.side=side;
        game_batch.alpha=alpha;game_batch.flags=flags;return;
    }
    if(game_batch.count==GFX_BATCH_CAPACITY)game_batch_flush();
    volatile GfxBatchCommand *list=(volatile GfxBatchCommand *)(uintptr_t)GFX_BATCH_BASE;
    volatile GfxBatchCommand *c=&list[game_batch.count++];
    c->source=source;c->destination=destination;c->extent=width|(height<<16);
    c->source_stride=pitch;c->colors=fill ? GAME_BACKGROUND_COLOR:0;
    c->control=fill ? 0u:2u|(flags<<2)|(alpha<<8);c->reserved0=c->reserved1=0;
    game_batch.run=side ? (same ? game_batch.run+1u:1u):0u;
    game_batch.source=source;game_batch.side=side;game_batch.alpha=alpha;game_batch.flags=flags;
}
#endif
