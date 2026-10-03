#ifndef SPRITE_CRC32_H
#define SPRITE_CRC32_H
#include <stdint.h>
/* A 16-entry nibble table keeps the 4 KiB on-chip bootloader's BSS small.
 * The previous 256-entry byte table consumed 1024 bytes by itself. */
static uint32_t sprite_crc_table[16];
static void sprite_crc_init(void) {
    for(uint32_t n=0;n<16u;++n) {
        uint32_t value=n;
        for(uint32_t bit=0;bit<4u;++bit)
            value=(value>>1)^((value&1u) ? 0xedb88320u : 0u);
        sprite_crc_table[n]=value;
    }
}
static inline uint32_t sprite_crc_byte(uint32_t crc,uint8_t value) {
    crc=(crc>>4)^sprite_crc_table[(crc^value)&15u];
    return (crc>>4)^sprite_crc_table[(crc^(value>>4))&15u];
}
#endif
