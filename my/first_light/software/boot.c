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

/* The board's GD25LQ64 configuration Flash is also exposed through the
 * Sapphire SPI peripheral. Efinity writes the FPGA bitstream at 0x000000;
 * the local flash bundle tool writes this user image at 0x380000. */
#define FLASH_USER_BASE 0x00380000u
#define FLASH_SIZE 0x00800000u
#define FLASH_HEADER_BYTES 40u
#define FLASH_MAGIC 0x314c5446u /* "FTL1" in little-endian order */
#define FLASH_VERSION 1u
#define SPI_DATA 0x00u
#define SPI_BUFFER 0x04u
#define SPI_CONFIG 0x08u
#define SPI_CLK_DIVIDER 0x20u
#define SPI_SS_SETUP 0x24u
#define SPI_SS_HOLD 0x28u
#define SPI_SS_DISABLE 0x2cu
#define SPI_CMD_WRITE (1u<<8)
#define SPI_CMD_READ (1u<<9)
#define SPI_CMD_SS (1u<<11)
#define SPI_RSP_TIMEOUT 5000000u

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

static int spi_wait_command(void) {
    uint32_t start=tick();
    while(!(rd(SYSTEM_SPI_0_IO_CTRL+SPI_BUFFER)&0xffffu))
        if((uint32_t)(tick()-start)>SPI_RSP_TIMEOUT) return 0;
    return 1;
}
static int spi_wait_response(void) {
    uint32_t start=tick();
    while(!(rd(SYSTEM_SPI_0_IO_CTRL+SPI_BUFFER)>>16))
        if((uint32_t)(tick()-start)>SPI_RSP_TIMEOUT) return 0;
    return 1;
}
static int spi_command(uint32_t command) {
    if(!spi_wait_command()) return 0;
    wr(SYSTEM_SPI_0_IO_CTRL+SPI_DATA,command);
    return 1;
}
static int spi_write_byte(uint8_t value) {
    return spi_command((uint32_t)value|SPI_CMD_WRITE);
}
static int spi_read_byte(void) {
    if(!spi_command(SPI_CMD_READ) || !spi_wait_response()) return -1;
    return (int)(rd(SYSTEM_SPI_0_IO_CTRL+SPI_DATA)&255u);
}
static int spi_begin_read(uint32_t address) {
    if(!spi_command(SPI_CMD_SS|0x80u) || !spi_write_byte(0x03u) ||
       !spi_write_byte((uint8_t)(address>>16)) ||
       !spi_write_byte((uint8_t)(address>>8)) || !spi_write_byte((uint8_t)address)) return 0;
    return 1;
}
static void spi_end_read(void) { (void)spi_command(SPI_CMD_SS); }
static int flash_read_bytes(uint32_t offset,volatile uint8_t *destination,uint32_t length) {
    if(offset>FLASH_SIZE || length>FLASH_SIZE-offset || !spi_begin_read(FLASH_USER_BASE+offset)) return 0;
    for(uint32_t i=0;i<length;++i) {
        int value=spi_read_byte();
        if(value<0) { spi_end_read(); return 0; }
        destination[i]=(uint8_t)value;
    }
    spi_end_read();
    return 1;
}
static uint32_t little_word(const uint8_t *p) {
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static void spi_init(void) {
    /* Mode 3 is the setting used by the official Ti60F225 SPI Flash demo. */
    wr(SYSTEM_SPI_0_IO_CTRL+SPI_CONFIG,3u);
    wr(SYSTEM_SPI_0_IO_CTRL+SPI_CLK_DIVIDER,10u);
    wr(SYSTEM_SPI_0_IO_CTRL+SPI_SS_SETUP,5u);
    wr(SYSTEM_SPI_0_IO_CTRL+SPI_SS_HOLD,5u);
    wr(SYSTEM_SPI_0_IO_CTRL+SPI_SS_DISABLE,5u);
}
static int flash_boot(void) {
    uint8_t header[FLASH_HEADER_BYTES];
    if(!flash_read_bytes(0,header,FLASH_HEADER_BYTES)) return 0;
    uint32_t magic=little_word(header+0),version=little_word(header+4);
    uint32_t app_offset=little_word(header+8),app_len=little_word(header+12);
    uint32_t app_crc=little_word(header+16),asset_offset=little_word(header+20);
    uint32_t asset_len=little_word(header+24),asset_crc=little_word(header+28);
    uint32_t total_len=little_word(header+32);
    if(magic!=FLASH_MAGIC || version!=FLASH_VERSION || app_offset<FLASH_HEADER_BYTES ||
       !app_len || app_len>APP_MAX || asset_offset<app_offset+app_len ||
       asset_len<=PIXEL_START || asset_len>ASSET_MAX || (asset_len&1u) ||
       total_len<asset_offset+asset_len || FLASH_USER_BASE+total_len>FLASH_SIZE) return 0;
    volatile uint32_t *app_h=(volatile uint32_t *)(uintptr_t)APP_HEAD;
    volatile uint32_t *asset_h=(volatile uint32_t *)(uintptr_t)ASSET_BASE;
    app_h[0]=0; asset_h[0]=0;
    if(!flash_read_bytes(app_offset,(volatile uint8_t *)(uintptr_t)APP_BASE,app_len) ||
       region_crc(APP_BASE,app_len)!=app_crc) return 0;
    if(!flash_read_bytes(asset_offset,(volatile uint8_t *)(uintptr_t)ASSET_BASE,asset_len) ||
       asset_h[0]!=ASSET_MAGIC || asset_h[1]!=1u || asset_h[2]!=asset_len ||
       asset_h[3]!=asset_crc || region_crc(ASSET_BASE+16,asset_len-16)!=asset_crc) return 0;
    app_h[1]=app_len; app_h[2]=app_crc; app_h[3]=asset_crc;
    asset_h[1]=1u; asset_h[2]=asset_len; asset_h[3]=asset_crc; asset_h[0]=ASSET_MAGIC;
    app_h[0]=APP_MAGIC;
    drain_ddr();
    say("FLASH BOOT\r\n");
    return 1;
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
    spi_init();
    if(flash_boot()) { start_app(); }
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
