#ifndef SPRITE_CRC32_H
#define SPRITE_CRC32_H
#include <stdint.h>
static uint32_t sprite_crc_table[256];
static void sprite_crc_init(void) {
    for(uint32_t n=0;n<256u;++n) {
        uint32_t value=n;
        for(uint32_t bit=0;bit<8u;++bit)
            value=(value>>1)^((value&1u) ? 0xedb88320u : 0u);
        sprite_crc_table[n]=value;
    }
}
static inline uint32_t sprite_crc_byte(uint32_t crc,uint8_t value) {
    return (crc>>8)^sprite_crc_table[(crc^value)&255u];
}
#endif
