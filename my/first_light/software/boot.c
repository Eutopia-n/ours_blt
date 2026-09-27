#include <stdint.h>
#include "soc.h"
#include "crc32.h"

#define APP_BASE 0x01400000u
#define APP_MAX 65536u
#define APP_HEAD 0x013ffff0u
#define APP_MAGIC 0x37505041u /* APP7 */
#define ASSET_BASE 0x01200000u
#define ASSET_MAX 0x00100000u
#define ASSET_MAGIC 0x37375341u /* AS77 */
#define ASSET_TABLE 616u
#define PIXEL_START (16u+ASSET_TABLE)

static inline uint32_t rd(uint32_t address) {
    uint32_t v=*(volatile uint32_t *)(uintptr_t)address;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    return v;
}
static inline void wr(uint32_t address,uint32_t value) {
    *(volatile uint32_t *)(uintptr_t)address=value;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}
static uint32_t tick(void) { return rd(SYSTEM_CLINT_CTRL+0xbff8u); }
static void putc_uart(char c) {
    while(((rd(SYSTEM_UART_0_IO_CTRL+4)>>16)&255u)==0) {}
    wr(SYSTEM_UART_0_IO_CTRL,(uint32_t)c);
}
static void say(const char *s) { while(*s) putc_uart(*s++); }
void fatal_trap(uint32_t cause,uint32_t pc) {
    (void)cause; (void)pc;
    say("BOOT TRAP\r\n");
    for(;;) {}
}
static int get_byte(void) {
    uint32_t start=tick();
    for(;;) {
        uint32_t v=rd(SYSTEM_UART_0_IO_CTRL);
        if(v&0x10000u) return (int)(v&255u);
        if((uint32_t)(tick()-start)>200000000u) return -1;
    }
}
static int get_word(uint32_t *result) {
    uint32_t value=0;
    for(uint32_t i=0;i<4;++i) {
        int b=get_byte();
        if(b<0) return 0;
        value|=(uint32_t)b<<(8*i);
    }
    *result=value;
    return 1;
}
static uint32_t region_crc(uint32_t start,uint32_t size) {
    const volatile uint32_t *p=(const volatile uint32_t *)(uintptr_t)start;
    uint32_t crc=~0u;
    uint32_t words=size/4u;
    for(uint32_t i=0;i<words;++i) {
        uint32_t value=*p++;
        crc=sprite_crc_byte(crc,(uint8_t)value);
        crc=sprite_crc_byte(crc,(uint8_t)(value>>8));
        crc=sprite_crc_byte(crc,(uint8_t)(value>>16));
        crc=sprite_crc_byte(crc,(uint8_t)(value>>24));
    }
    const volatile uint8_t *tail=(const volatile uint8_t *)(uintptr_t)(start+words*4u);
    for(uint32_t i=words*4u;i<size;++i) crc=sprite_crc_byte(crc,*tail++);
    return ~crc;
}
static void drain_ddr(void) {
    __asm__ volatile ("fence iorw, iorw\n.word 0x500f" ::: "memory");
    (void)*(volatile uint32_t *)(uintptr_t)APP_BASE;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}
static int cached(void) {
    const volatile uint32_t *app=(const volatile uint32_t *)(uintptr_t)APP_HEAD;
    const volatile uint32_t *asset=(const volatile uint32_t *)(uintptr_t)ASSET_BASE;
    uint32_t app_len=app[1],asset_len=asset[2];
    if(app[0]!=APP_MAGIC || !app_len || app_len>APP_MAX ||
       asset[0]!=ASSET_MAGIC || asset[1]!=1u ||
       asset_len<=PIXEL_START || asset_len>ASSET_MAX || (asset_len&1u)) return 0;
    return app[2]==region_crc(APP_BASE,app_len) &&
           asset[3]==region_crc(ASSET_BASE+16,asset_len-16);
}
static void start_app(void) {
    __asm__ volatile ("fence iorw, iorw\n.word 0x500f\nfence.i" ::: "memory");
    ((void (*)(void))(uintptr_t)APP_BASE)();
    for(;;) {}
}
static int receive(void) {
    uint32_t app_len,app_crc,magic,length,packed,expected;
    if(!get_word(&app_len) || !get_word(&app_crc) ||
       !app_len || app_len>APP_MAX) return 0;
    volatile uint32_t *app_h=(volatile uint32_t *)(uintptr_t)APP_HEAD;
    volatile uint32_t *asset_h=(volatile uint32_t *)(uintptr_t)ASSET_BASE;
    app_h[0]=0; asset_h[0]=0;
    volatile uint8_t *app=(volatile uint8_t *)(uintptr_t)APP_BASE;
    uint32_t crc=~0u;
    for(uint32_t i=0;i<app_len;++i) {
        int b=get_byte();
        if(b<0) return 0;
        app[i]=(uint8_t)b;
        crc=sprite_crc_byte(crc,(uint8_t)b);
    }
    if(~crc!=app_crc || !get_word(&magic) || magic!=0x55373753u ||
       !get_word(&length) || !get_word(&packed) || !get_word(&expected) ||
       length<=PIXEL_START || length>ASSET_MAX || (length&1u) ||
       !packed || packed>ASSET_MAX) return 0;
    volatile uint8_t *table=(volatile uint8_t *)(uintptr_t)(ASSET_BASE+16);
    crc=~0u;
    for(uint32_t i=0;i<ASSET_TABLE;++i) {
        int b=get_byte();
        if(b<0) return 0;
        table[i]=(uint8_t)b;
        crc=sprite_crc_byte(crc,(uint8_t)b);
    }
    volatile uint16_t *pixels=(volatile uint16_t *)(uintptr_t)(ASSET_BASE+PIXEL_START);
    uint32_t words=(length-PIXEL_START)/2u,used=0,received=0;
    while(received<packed) {
        int tag=get_byte();
        if(tag<0) return 0;
        ++received;
        uint32_t count=(uint32_t)(tag&127)+1u;
        if(count>words-used) return 0;
        if(tag&128) {
            for(uint32_t i=0;i<count;++i) {
                *pixels++=0xf81f; ++used;
                crc=sprite_crc_byte(sprite_crc_byte(crc,0x1f),0xf8);
            }
        } else {
            if(count>(packed-received)/2u) return 0;
            for(uint32_t i=0;i<count;++i) {
                int lo=get_byte(),hi=get_byte();
                if(lo<0 || hi<0) return 0;
                received+=2;
                *pixels++=(uint16_t)((uint32_t)lo|((uint32_t)hi<<8)); ++used;
                crc=sprite_crc_byte(sprite_crc_byte(crc,(uint8_t)lo),(uint8_t)hi);
            }
        }
    }
    if(used!=words || ~crc!=expected) return 0;
    drain_ddr();
    if(region_crc(APP_BASE,app_len)!=app_crc ||
       region_crc(ASSET_BASE+16,length-16)!=expected) return 0;
    app_h[1]=app_len;app_h[2]=app_crc;app_h[3]=expected;
    asset_h[1]=1;asset_h[2]=length;asset_h[3]=expected;
    app_h[0]=APP_MAGIC;asset_h[0]=ASSET_MAGIC;
    drain_ddr();
    return 1;
}
int main(void) {
    wr(SYSTEM_UART_0_IO_CTRL+8,SYSTEM_CLINT_HZ/(115200u*8u)-1u);
    wr(SYSTEM_UART_0_IO_CTRL+12,7u);
    sprite_crc_init();
    if(cached()) { say("ASSET CACHED\r\n"); start_app(); }
    for(;;) {
        say("ASSET READY\r\n");
        uint32_t magic=0;
        while(magic!=0x42373753u) {
            int b=get_byte();
            if(b>=0) magic=(magic>>8)|((uint32_t)b<<24);
            else { magic=0; say("ASSET READY\r\n"); }
        }
        if(receive()) { say("ASSET OK\r\n"); start_app(); }
        say("ASSET ERR\r\n");
    }
}
