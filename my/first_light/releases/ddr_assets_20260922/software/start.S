    .section .init,"ax",@progbits
    .globl _start
_start:
    csrw mie, zero
    csrw mstatus, zero
    la sp, _stack_top
    la t0, trap
    csrw mtvec, t0
    la t0, __bss_start
    la t1, __bss_end
1:  bgeu t0, t1, 2f
    sw zero, 0(t0)
    addi t0, t0, 4
    j 1b
2:  call main
3:  j 3b
    .balign 4
trap:
    csrr a0, mcause
    csrr a1, mepc
    call fatal_trap
    j trap
