OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY { ddr (rwx) : ORIGIN = 0x01400000, LENGTH = 64K }
SECTIONS {
    .init : { KEEP(*(.init)) } > ddr
    .text : { *(.text .text.*) *(.rodata .rodata.*) } > ddr
    .data : { *(.data .data.*) *(.sdata .sdata.*) } > ddr
    .bss (NOLOAD) : {
        . = ALIGN(4); __bss_start = .;
        *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON)
        . = ALIGN(4); __bss_end = .;
    } > ddr
    _stack_top = ORIGIN(ddr) + LENGTH(ddr);
    ASSERT(__bss_end <= _stack_top - 1024, "DDR application leaves less than 1 KiB stack")
}
