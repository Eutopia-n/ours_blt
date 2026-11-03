OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY { ocr (rwx) : ORIGIN = 0xf9000000, LENGTH = 128K }
SECTIONS {
    .init : { KEEP(*(.init)) } > ocr
    .text : { *(.text .text.*) *(.rodata .rodata.*) } > ocr
    .data : { *(.data .data.*) *(.sdata .sdata.*) } > ocr
    .bss (NOLOAD) : {
        . = ALIGN(4); __bss_start = .;
        *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON)
        . = ALIGN(4); __bss_end = .;
    } > ocr
    _stack_top = ORIGIN(ocr) + LENGTH(ocr);
    ASSERT(__bss_end <= _stack_top - 4096, "On-chip firmware leaves less than 4096 bytes of stack")
}
