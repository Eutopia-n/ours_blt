
build/gpioDemo.elf:     file format elf32-littleriscv


Disassembly of section .init:

00001000 <_start>:

_start:
#ifdef USE_GP
.option push
.option norelax
	la gp, __global_pointer$
    1000:	00001197          	auipc	gp,0x1
    1004:	21018193          	addi	gp,gp,528 # 2210 <__global_pointer$>
.global smp_lottery_target
.global smp_lottery_lock
.global smp_slave


  sw x0, smp_lottery_lock, a1
    1008:	8201a023          	sw	zero,-2016(gp) # 1a30 <smp_lottery_lock>

0000100c <smp_tyranny>:

smp_tyranny:
  csrr a0, mhartid
    100c:	f1402573          	csrr	a0,mhartid
  beqz a0, init
    1010:	02050e63          	beqz	a0,104c <init>

00001014 <smp_slave>:

smp_slave:
	lw a0, smp_lottery_lock
    1014:	8201a503          	lw	a0,-2016(gp) # 1a30 <smp_lottery_lock>
	beqz a0, smp_slave
    1018:	fe050ee3          	beqz	a0,1014 <smp_slave>

	fence r, r
    101c:	0220000f          	fence	r,r
    1020:	0000100f          	fence.i
	//li a1, -1
	//amoadd.w x0, a1,(a0)

	.word(0x100F) //i$ flush
	lw a5, smp_lottery_target
    1024:	81c1a783          	lw	a5,-2020(gp) # 1a2c <__bss_start>
	li a0, 0
    1028:	00000513          	li	a0,0
	li a1, 0
    102c:	00000593          	li	a1,0
	li a2, 0
    1030:	00000613          	li	a2,0
	jr a5
    1034:	00078067          	jr	a5

00001038 <smp_unlock>:

.global   smp_unlock
.type    smp_unlock,%function
smp_unlock:
	sw a0, smp_lottery_target, a1
    1038:	80a1ae23          	sw	a0,-2020(gp) # 1a2c <__bss_start>
	fence w, w
    103c:	0110000f          	fence	w,w
	li a0, 1
    1040:	00100513          	li	a0,1
	sw a0, smp_lottery_lock, a1
    1044:	82a1a023          	sw	a0,-2016(gp) # 1a30 <smp_lottery_lock>
    ret
    1048:	00008067          	ret

0000104c <init>:
#endif

init:
	la sp, _sp
    104c:	00002117          	auipc	sp,0x2
    1050:	9f410113          	addi	sp,sp,-1548 # 2a40 <__freertos_irq_stack_top>

	/* Load data section */
	la a0, _data_lma
    1054:	00001517          	auipc	a0,0x1
    1058:	87450513          	addi	a0,a0,-1932 # 18c8 <_data>
	la a1, _data
    105c:	00001597          	auipc	a1,0x1
    1060:	86c58593          	addi	a1,a1,-1940 # 18c8 <_data>
	la a2, _edata
    1064:	81c18613          	addi	a2,gp,-2020 # 1a2c <__bss_start>
	bgeu a1, a2, 2f
    1068:	00c5fc63          	bgeu	a1,a2,1080 <init+0x34>
1:
	lw t0, (a0)
    106c:	00052283          	lw	t0,0(a0)
	sw t0, (a1)
    1070:	0055a023          	sw	t0,0(a1)
	addi a0, a0, 4
    1074:	00450513          	addi	a0,a0,4
	addi a1, a1, 4
    1078:	00458593          	addi	a1,a1,4
	bltu a1, a2, 1b
    107c:	fec5e8e3          	bltu	a1,a2,106c <init+0x20>
2:

	/* Clear bss section */
	la a0, __bss_start
    1080:	81c18513          	addi	a0,gp,-2020 # 1a2c <__bss_start>
	la a1, _end
    1084:	82818593          	addi	a1,gp,-2008 # 1a38 <_end>
	bgeu a0, a1, 2f
    1088:	00b57863          	bgeu	a0,a1,1098 <init+0x4c>
1:
	sw zero, (a0)
    108c:	00052023          	sw	zero,0(a0)
	addi a0, a0, 4
    1090:	00450513          	addi	a0,a0,4
	bltu a0, a1, 1b
    1094:	feb56ce3          	bltu	a0,a1,108c <init+0x40>
2:

#ifndef NO_LIBC_INIT_ARRAY
	call __libc_init_array
    1098:	010000ef          	jal	ra,10a8 <__libc_init_array>
#endif

	call main
    109c:	708000ef          	jal	ra,17a4 <main>

000010a0 <mainDone>:
mainDone:
    j mainDone
    10a0:	0000006f          	j	10a0 <mainDone>

000010a4 <_init>:


	.globl _init
_init:
    ret
    10a4:	00008067          	ret

Disassembly of section .text:

000010a8 <__libc_init_array>:
    10a8:	ff010113          	addi	sp,sp,-16
    10ac:	00812423          	sw	s0,8(sp)
    10b0:	01212023          	sw	s2,0(sp)
    10b4:	00001417          	auipc	s0,0x1
    10b8:	81440413          	addi	s0,s0,-2028 # 18c8 <_data>
    10bc:	00001917          	auipc	s2,0x1
    10c0:	80c90913          	addi	s2,s2,-2036 # 18c8 <_data>
    10c4:	40890933          	sub	s2,s2,s0
    10c8:	00112623          	sw	ra,12(sp)
    10cc:	00912223          	sw	s1,4(sp)
    10d0:	40295913          	srai	s2,s2,0x2
    10d4:	00090e63          	beqz	s2,10f0 <__libc_init_array+0x48>
    10d8:	00000493          	li	s1,0
    10dc:	00042783          	lw	a5,0(s0)
    10e0:	00148493          	addi	s1,s1,1
    10e4:	00440413          	addi	s0,s0,4
    10e8:	000780e7          	jalr	a5
    10ec:	fe9918e3          	bne	s2,s1,10dc <__libc_init_array+0x34>
    10f0:	00000417          	auipc	s0,0x0
    10f4:	7d840413          	addi	s0,s0,2008 # 18c8 <_data>
    10f8:	00000917          	auipc	s2,0x0
    10fc:	7d090913          	addi	s2,s2,2000 # 18c8 <_data>
    1100:	40890933          	sub	s2,s2,s0
    1104:	40295913          	srai	s2,s2,0x2
    1108:	00090e63          	beqz	s2,1124 <__libc_init_array+0x7c>
    110c:	00000493          	li	s1,0
    1110:	00042783          	lw	a5,0(s0)
    1114:	00148493          	addi	s1,s1,1
    1118:	00440413          	addi	s0,s0,4
    111c:	000780e7          	jalr	a5
    1120:	fe9918e3          	bne	s2,s1,1110 <__libc_init_array+0x68>
    1124:	00c12083          	lw	ra,12(sp)
    1128:	00812403          	lw	s0,8(sp)
    112c:	00412483          	lw	s1,4(sp)
    1130:	00012903          	lw	s2,0(sp)
    1134:	01010113          	addi	sp,sp,16
    1138:	00008067          	ret

0000113c <uart_writeAvailability>:
#include "type.h"
#include "soc.h"


    static inline u32 read_u32(u32 address){
        return *((volatile u32*) address);
    113c:	00452503          	lw	a0,4(a0)
*          of available spaces for writing data from bits 23 to 16. It then
*          returns this value after masking with 0xFF.
*
******************************************************************************/
    static u32 uart_writeAvailability(u32 reg){
        return (read_u32(reg + UART_STATUS) >> 16) & 0xFF;
    1140:	01055513          	srli	a0,a0,0x10
    }
    1144:	0ff57513          	andi	a0,a0,255
    1148:	00008067          	ret

0000114c <uart_write>:
* @note    The function waits until there is available space in the UART buffer
*          for writing data. Once space is available, it writes the character
*          data to the UART data register.
*
******************************************************************************/
    static void uart_write(u32 reg, char data){
    114c:	ff010113          	addi	sp,sp,-16
    1150:	00112623          	sw	ra,12(sp)
    1154:	00812423          	sw	s0,8(sp)
    1158:	00912223          	sw	s1,4(sp)
    115c:	00050413          	mv	s0,a0
    1160:	00058493          	mv	s1,a1
        while(uart_writeAvailability(reg) == 0);
    1164:	00040513          	mv	a0,s0
    1168:	fd5ff0ef          	jal	ra,113c <uart_writeAvailability>
    116c:	fe050ce3          	beqz	a0,1164 <uart_write+0x18>
    }
    
    static inline void write_u32(u32 data, u32 address){
        *((volatile u32*) address) = data;
    1170:	00942023          	sw	s1,0(s0)
        write_u32(data, reg + UART_DATA);
    }
    1174:	00c12083          	lw	ra,12(sp)
    1178:	00812403          	lw	s0,8(sp)
    117c:	00412483          	lw	s1,4(sp)
    1180:	01010113          	addi	sp,sp,16
    1184:	00008067          	ret

00001188 <uart_applyConfig>:
*          value using data length, parity, and stop bit settings from the configuration
*          structure, and writes this value to the UART frame configuration register.
*
******************************************************************************/
    static void uart_applyConfig(u32 reg, Uart_Config *config){
        write_u32(config->clockDivider, reg + UART_CLOCK_DIVIDER);
    1188:	00c5a783          	lw	a5,12(a1)
    118c:	00f52423          	sw	a5,8(a0)
        write_u32(((config->dataLength-1) << 0) | (config->parity << 8) | (config->stop << 16), reg + UART_FRAME_CONFIG);
    1190:	0005a783          	lw	a5,0(a1)
    1194:	fff78793          	addi	a5,a5,-1
    1198:	0045a703          	lw	a4,4(a1)
    119c:	00871713          	slli	a4,a4,0x8
    11a0:	00e7e7b3          	or	a5,a5,a4
    11a4:	0085a703          	lw	a4,8(a1)
    11a8:	01071713          	slli	a4,a4,0x10
    11ac:	00e7e7b3          	or	a5,a5,a4
    11b0:	00f52623          	sw	a5,12(a0)
    }
    11b4:	00008067          	ret

000011b8 <clint_uDelay>:
*          and the time limit is non-negative, indicating that the delay has
*          not yet elapsed.
*
******************************************************************************/
    static void clint_uDelay(u32 usec, u32 hz, u32 reg){
        u32 mTimePerUsec = hz/1000000;
    11b8:	000f47b7          	lui	a5,0xf4
    11bc:	24078793          	addi	a5,a5,576 # f4240 <__freertos_irq_stack_top+0xf1800>
    11c0:	02f5d5b3          	divu	a1,a1,a5
    readReg_u32 (clint_getTimeLow , CLINT_TIME_ADDR)
    11c4:	0000c7b7          	lui	a5,0xc
    11c8:	ff878793          	addi	a5,a5,-8 # bff8 <__freertos_irq_stack_top+0x95b8>
    11cc:	00f60633          	add	a2,a2,a5
        return *((volatile u32*) address);
    11d0:	00062783          	lw	a5,0(a2)
        u32 limit = clint_getTimeLow(reg) + usec*mTimePerUsec;
    11d4:	02a58533          	mul	a0,a1,a0
    11d8:	00f50533          	add	a0,a0,a5
    11dc:	00062783          	lw	a5,0(a2)
        while((int32_t)(limit-(clint_getTimeLow(reg))) >= 0);
    11e0:	40f507b3          	sub	a5,a0,a5
    11e4:	fe07dce3          	bgez	a5,11dc <clint_uDelay+0x24>
    11e8:	00008067          	ret

000011ec <_putchar>:
#include <math.h>
#include <string.h>
#include "bsp.h"

#if (ENABLE_BSP_PRINTF)
    static void _putchar(char character){
    11ec:	ff010113          	addi	sp,sp,-16
    11f0:	00112623          	sw	ra,12(sp)
        #if (ENABLE_SEMIHOSTING_PRINT == 1)
            sh_writec(character);
        #else
            bsp_putChar(character);
    11f4:	00050593          	mv	a1,a0
    11f8:	f8010537          	lui	a0,0xf8010
    11fc:	f51ff0ef          	jal	ra,114c <uart_write>
        #endif // (ENABLE_SEMIHOSTING_PRINT == 1)
    }
    1200:	00c12083          	lw	ra,12(sp)
    1204:	01010113          	addi	sp,sp,16
    1208:	00008067          	ret

0000120c <_putchar_s>:

    static void _putchar_s(char *p)
    {
    120c:	ff010113          	addi	sp,sp,-16
    1210:	00112623          	sw	ra,12(sp)
    1214:	00812423          	sw	s0,8(sp)
    1218:	00050413          	mv	s0,a0
    #if (ENABLE_SEMIHOSTING_PRINT == 1)
        sh_write0(p);
    #else
        while (*p)
    121c:	00044503          	lbu	a0,0(s0)
    1220:	00050863          	beqz	a0,1230 <_putchar_s+0x24>
            _putchar(*(p++));
    1224:	00140413          	addi	s0,s0,1
    1228:	fc5ff0ef          	jal	ra,11ec <_putchar>
    122c:	ff1ff06f          	j	121c <_putchar_s+0x10>
    #endif // (ENABLE_SEMIHOSTING_PRINT == 1)
    }
    1230:	00c12083          	lw	ra,12(sp)
    1234:	00812403          	lw	s0,8(sp)
    1238:	01010113          	addi	sp,sp,16
    123c:	00008067          	ret

00001240 <bsp_printHex>:

        static void bsp_printHex(uint32_t val)
    {
    1240:	ff010113          	addi	sp,sp,-16
    1244:	00112623          	sw	ra,12(sp)
    1248:	00812423          	sw	s0,8(sp)
    124c:	00912223          	sw	s1,4(sp)
    1250:	00050493          	mv	s1,a0
        uint32_t digits;
        digits =8;

        for (int i = (4*digits)-4; i >= 0; i -= 4) {
    1254:	01c00413          	li	s0,28
    1258:	0240006f          	j	127c <bsp_printHex+0x3c>
            _putchar("0123456789ABCDEF"[(val >> i) % 16]);
    125c:	0084d7b3          	srl	a5,s1,s0
    1260:	00f7f713          	andi	a4,a5,15
    1264:	000027b7          	lui	a5,0x2
    1268:	8c878793          	addi	a5,a5,-1848 # 18c8 <_data>
    126c:	00e787b3          	add	a5,a5,a4
    1270:	0007c503          	lbu	a0,0(a5)
    1274:	f79ff0ef          	jal	ra,11ec <_putchar>
        for (int i = (4*digits)-4; i >= 0; i -= 4) {
    1278:	ffc40413          	addi	s0,s0,-4
    127c:	fe0450e3          	bgez	s0,125c <bsp_printHex+0x1c>
        }
    }
    1280:	00c12083          	lw	ra,12(sp)
    1284:	00812403          	lw	s0,8(sp)
    1288:	00412483          	lw	s1,4(sp)
    128c:	01010113          	addi	sp,sp,16
    1290:	00008067          	ret

00001294 <bsp_printHex_lower>:

    static void bsp_printHex_lower(uint32_t val)
    {
    1294:	ff010113          	addi	sp,sp,-16
    1298:	00112623          	sw	ra,12(sp)
    129c:	00812423          	sw	s0,8(sp)
    12a0:	00912223          	sw	s1,4(sp)
    12a4:	00050493          	mv	s1,a0
        uint32_t digits;
        digits =8;

        for (int i = (4*digits)-4; i >= 0; i -= 4) {
    12a8:	01c00413          	li	s0,28
    12ac:	0240006f          	j	12d0 <bsp_printHex_lower+0x3c>
            _putchar("0123456789abcdef"[(val >> i) % 16]);
    12b0:	0084d7b3          	srl	a5,s1,s0
    12b4:	00f7f713          	andi	a4,a5,15
    12b8:	000027b7          	lui	a5,0x2
    12bc:	8dc78793          	addi	a5,a5,-1828 # 18dc <_data+0x14>
    12c0:	00e787b3          	add	a5,a5,a4
    12c4:	0007c503          	lbu	a0,0(a5)
    12c8:	f25ff0ef          	jal	ra,11ec <_putchar>
        for (int i = (4*digits)-4; i >= 0; i -= 4) {
    12cc:	ffc40413          	addi	s0,s0,-4
    12d0:	fe0450e3          	bgez	s0,12b0 <bsp_printHex_lower+0x1c>

        }
    }
    12d4:	00c12083          	lw	ra,12(sp)
    12d8:	00812403          	lw	s0,8(sp)
    12dc:	00412483          	lw	s1,4(sp)
    12e0:	01010113          	addi	sp,sp,16
    12e4:	00008067          	ret

000012e8 <bsp_printf_c>:
*
* @param c: The character to be output.
*
******************************************************************************/
    static void bsp_printf_c(int c)
    {
    12e8:	ff010113          	addi	sp,sp,-16
    12ec:	00112623          	sw	ra,12(sp)
        _putchar(c);
    12f0:	0ff57513          	andi	a0,a0,255
    12f4:	ef9ff0ef          	jal	ra,11ec <_putchar>
    }
    12f8:	00c12083          	lw	ra,12(sp)
    12fc:	01010113          	addi	sp,sp,16
    1300:	00008067          	ret

00001304 <bsp_printf_s>:
*
* @param s: A pointer to the null-terminated string to be output.
*
*******************************************************************************/
    static void bsp_printf_s(char *p)
    {
    1304:	ff010113          	addi	sp,sp,-16
    1308:	00112623          	sw	ra,12(sp)
        _putchar_s(p);
    130c:	f01ff0ef          	jal	ra,120c <_putchar_s>
    }
    1310:	00c12083          	lw	ra,12(sp)
    1314:	01010113          	addi	sp,sp,16
    1318:	00008067          	ret

0000131c <bsp_printf_d>:
* - Handles negative numbers by printing a '-' sign.
* - Uses the 'bsp_printf_c' function to print each character.
*
******************************************************************************/
    static void bsp_printf_d(int val)
    {
    131c:	fd010113          	addi	sp,sp,-48
    1320:	02112623          	sw	ra,44(sp)
    1324:	02812423          	sw	s0,40(sp)
    1328:	02912223          	sw	s1,36(sp)
    132c:	00050493          	mv	s1,a0
        char buffer[32];
        char *p = buffer;
        if (val < 0) {
    1330:	00054663          	bltz	a0,133c <bsp_printf_d+0x20>
    {
    1334:	00010413          	mv	s0,sp
    1338:	02c0006f          	j	1364 <bsp_printf_d+0x48>
            bsp_printf_c('-');
    133c:	02d00513          	li	a0,45
    1340:	fa9ff0ef          	jal	ra,12e8 <bsp_printf_c>
            val = -val;
    1344:	409004b3          	neg	s1,s1
    1348:	fedff06f          	j	1334 <bsp_printf_d+0x18>
        }
        while (val || p == buffer) {
            *(p++) = '0' + val % 10;
    134c:	00a00713          	li	a4,10
    1350:	02e4e7b3          	rem	a5,s1,a4
    1354:	03078793          	addi	a5,a5,48
    1358:	00f40023          	sb	a5,0(s0)
            val = val / 10;
    135c:	02e4c4b3          	div	s1,s1,a4
            *(p++) = '0' + val % 10;
    1360:	00140413          	addi	s0,s0,1
        while (val || p == buffer) {
    1364:	fe0494e3          	bnez	s1,134c <bsp_printf_d+0x30>
    1368:	00010793          	mv	a5,sp
    136c:	fef400e3          	beq	s0,a5,134c <bsp_printf_d+0x30>
    1370:	0100006f          	j	1380 <bsp_printf_d+0x64>
        }
        while (p != buffer)
            bsp_printf_c(*(--p));
    1374:	fff40413          	addi	s0,s0,-1
    1378:	00044503          	lbu	a0,0(s0)
    137c:	f6dff0ef          	jal	ra,12e8 <bsp_printf_c>
        while (p != buffer)
    1380:	00010793          	mv	a5,sp
    1384:	fef418e3          	bne	s0,a5,1374 <bsp_printf_d+0x58>
    }
    1388:	02c12083          	lw	ra,44(sp)
    138c:	02812403          	lw	s0,40(sp)
    1390:	02412483          	lw	s1,36(sp)
    1394:	03010113          	addi	sp,sp,48
    1398:	00008067          	ret

0000139c <bsp_printf_x>:
* - Calls 'bsp_printHex_lower' to print the hexadecimal representation.
* - Determines the number of leading zeros to be printed based on the value.
*
******************************************************************************/
    static void bsp_printf_x(int val)
    {
    139c:	ff010113          	addi	sp,sp,-16
    13a0:	00112623          	sw	ra,12(sp)
        int i,digi=2;

        for(i=0;i<8;i++)
    13a4:	00000713          	li	a4,0
    13a8:	00700793          	li	a5,7
    13ac:	02e7c063          	blt	a5,a4,13cc <bsp_printf_x+0x30>
        {
            if((val & (0xFFFFFFF0 <<(4*i))) == 0)
    13b0:	00271693          	slli	a3,a4,0x2
    13b4:	ff000793          	li	a5,-16
    13b8:	00d797b3          	sll	a5,a5,a3
    13bc:	00f577b3          	and	a5,a0,a5
    13c0:	00078663          	beqz	a5,13cc <bsp_printf_x+0x30>
        for(i=0;i<8;i++)
    13c4:	00170713          	addi	a4,a4,1
    13c8:	fe1ff06f          	j	13a8 <bsp_printf_x+0xc>
            {
                digi=i+1;
                break;
            }
        }
        bsp_printHex_lower(val);
    13cc:	ec9ff0ef          	jal	ra,1294 <bsp_printHex_lower>
    }
    13d0:	00c12083          	lw	ra,12(sp)
    13d4:	01010113          	addi	sp,sp,16
    13d8:	00008067          	ret

000013dc <bsp_printf_X>:
* - Calls 'bsp_printHex' to print the uppercase hexadecimal representation.
* - Determines the number of leading zeros to be printed based on the value.
*
******************************************************************************/
    static void bsp_printf_X(int val)
        {
    13dc:	ff010113          	addi	sp,sp,-16
    13e0:	00112623          	sw	ra,12(sp)
            int i,digi=2;

            for(i=0;i<8;i++)
    13e4:	00000713          	li	a4,0
    13e8:	00700793          	li	a5,7
    13ec:	02e7c063          	blt	a5,a4,140c <bsp_printf_X+0x30>
            {
                if((val & (0xFFFFFFF0 <<(4*i))) == 0)
    13f0:	00271693          	slli	a3,a4,0x2
    13f4:	ff000793          	li	a5,-16
    13f8:	00d797b3          	sll	a5,a5,a3
    13fc:	00f577b3          	and	a5,a0,a5
    1400:	00078663          	beqz	a5,140c <bsp_printf_X+0x30>
            for(i=0;i<8;i++)
    1404:	00170713          	addi	a4,a4,1
    1408:	fe1ff06f          	j	13e8 <bsp_printf_X+0xc>
                {
                    digi=i+1;
                    break;
                }
            }
            bsp_printHex(val);
    140c:	e35ff0ef          	jal	ra,1240 <bsp_printHex>
        }
    1410:	00c12083          	lw	ra,12(sp)
    1414:	01010113          	addi	sp,sp,16
    1418:	00008067          	ret

0000141c <bsp_init>:
    *   1. UART baudrate
    *   2. 
    */
////////////////////////////////////////////////////////////////////////////////
    static void bsp_init()
    {
    141c:	fe010113          	addi	sp,sp,-32
    1420:	00112e23          	sw	ra,28(sp)
        Uart_Config uartConfig;
        uartConfig.dataLength   = BITS_8;
    1424:	00800793          	li	a5,8
    1428:	00f12023          	sw	a5,0(sp)
        uartConfig.parity       = NONE;
    142c:	00012223          	sw	zero,4(sp)
        uartConfig.stop         = ONE;
    1430:	00012423          	sw	zero,8(sp)
        uartConfig.clockDivider = BSP_CLINT_HZ/(BSP_UART_BAUDRATE*BSP_UART_DATA_LEN)-1;
    1434:	06b00793          	li	a5,107
    1438:	00f12623          	sw	a5,12(sp)
        uart_applyConfig(BSP_UART_TERMINAL, &uartConfig);    
    143c:	00010593          	mv	a1,sp
    1440:	f8010537          	lui	a0,0xf8010
    1444:	d45ff0ef          	jal	ra,1188 <uart_applyConfig>
    }
    1448:	01c12083          	lw	ra,28(sp)
    144c:	02010113          	addi	sp,sp,32
    1450:	00008067          	ret

00001454 <plic_set_priority>:
*          specified priority value to the calculated address, effectively
*          setting the priority for the specified interrupt gateway in the PLIC.
*
******************************************************************************/
    static void plic_set_priority(u32 plic, u32 gateway, u32 priority){
        write_u32(priority, plic + PLIC_PRIORITY_BASE + gateway*4);
    1454:	00259593          	slli	a1,a1,0x2
    1458:	00a585b3          	add	a1,a1,a0
        *((volatile u32*) address) = data;
    145c:	00c5a023          	sw	a2,0(a1)
    }
    1460:	00008067          	ret

00001464 <plic_set_enable>:
*          to the enable register.
*
******************************************************************************/

    static void plic_set_enable(u32 plic, u32 target,u32 gateway, u32 enable){
        u32 word = plic + PLIC_ENABLE_BASE + target * PLIC_ENABLE_PER_HART + (gateway / 32 * 4);
    1464:	00759593          	slli	a1,a1,0x7
    1468:	00a58533          	add	a0,a1,a0
    146c:	00565593          	srli	a1,a2,0x5
    1470:	00259593          	slli	a1,a1,0x2
    1474:	00b50533          	add	a0,a0,a1
    1478:	000025b7          	lui	a1,0x2
    147c:	00b50533          	add	a0,a0,a1
        u32 mask = 1 << (gateway % 32);
    1480:	00100793          	li	a5,1
    1484:	00c797b3          	sll	a5,a5,a2
        if (enable)
    1488:	00068a63          	beqz	a3,149c <plic_set_enable+0x38>
        return *((volatile u32*) address);
    148c:	00052603          	lw	a2,0(a0) # f8010000 <__freertos_irq_stack_top+0xf800d5c0>
            write_u32(read_u32(word) | mask, word);
    1490:	00c7e7b3          	or	a5,a5,a2
        *((volatile u32*) address) = data;
    1494:	00f52023          	sw	a5,0(a0)
    1498:	00008067          	ret
        return *((volatile u32*) address);
    149c:	00052603          	lw	a2,0(a0)
        else
            write_u32(read_u32(word) & ~mask, word);
    14a0:	fff7c793          	not	a5,a5
    14a4:	00c7f7b3          	and	a5,a5,a2
        *((volatile u32*) address) = data;
    14a8:	00f52023          	sw	a5,0(a0)
    }
    14ac:	00008067          	ret

000014b0 <plic_set_threshold>:
*          to the calculated address, effectively setting the threshold for the
*          specified target in the PLIC.
*
******************************************************************************/   
    static void plic_set_threshold(u32 plic, u32 target, u32 threshold){
        write_u32(threshold, plic + PLIC_THRESHOLD_BASE + target*PLIC_CONTEXT_PER_HART);
    14b0:	00c59593          	slli	a1,a1,0xc
    14b4:	00a585b3          	add	a1,a1,a0
    14b8:	00200537          	lui	a0,0x200
    14bc:	00a585b3          	add	a1,a1,a0
    14c0:	00c5a023          	sw	a2,0(a1) # 2000 <_end+0x5c8>
    }
    14c4:	00008067          	ret

000014c8 <plic_claim>:
*          value from the calculated address, effectively claiming an interrupt
*          for the specified target in the PLIC.
*
******************************************************************************/
    static u32 plic_claim(u32 plic, u32 target){
        return read_u32(plic + PLIC_CLAIM_BASE + target*PLIC_CONTEXT_PER_HART);
    14c8:	00c59593          	slli	a1,a1,0xc
    14cc:	00a585b3          	add	a1,a1,a0
    14d0:	00200537          	lui	a0,0x200
    14d4:	00450513          	addi	a0,a0,4 # 200004 <__freertos_irq_stack_top+0x1fd5c4>
    14d8:	00a585b3          	add	a1,a1,a0
        return *((volatile u32*) address);
    14dc:	0005a503          	lw	a0,0(a1)
    }
    14e0:	00008067          	ret

000014e4 <plic_release>:
*          to the calculated address, effectively releasing the claimed interrupt
*          for the specified target in the PLIC.
*
******************************************************************************/
    static void plic_release(u32 plic, u32 target, u32 gateway){
        write_u32(gateway,plic + PLIC_CLAIM_BASE + target*PLIC_CONTEXT_PER_HART);
    14e4:	00c59593          	slli	a1,a1,0xc
    14e8:	00a585b3          	add	a1,a1,a0
    14ec:	00200537          	lui	a0,0x200
    14f0:	00450513          	addi	a0,a0,4 # 200004 <__freertos_irq_stack_top+0x1fd5c4>
    14f4:	00a585b3          	add	a1,a1,a0
        *((volatile u32*) address) = data;
    14f8:	00c5a023          	sw	a2,0(a1)
    }
    14fc:	00008067          	ret

00001500 <bsp_printf>:
* - Handles each format specifier by calling the appropriate helper function.
* - If floating-point support is disabled, prints a warning for the 'f' specifier.
*
******************************************************************************/
    static void bsp_printf(const char *format, ...)
    {
    1500:	fc010113          	addi	sp,sp,-64
    1504:	00112e23          	sw	ra,28(sp)
    1508:	00812c23          	sw	s0,24(sp)
    150c:	00912a23          	sw	s1,20(sp)
    1510:	00050493          	mv	s1,a0
    1514:	02b12223          	sw	a1,36(sp)
    1518:	02c12423          	sw	a2,40(sp)
    151c:	02d12623          	sw	a3,44(sp)
    1520:	02e12823          	sw	a4,48(sp)
    1524:	02f12a23          	sw	a5,52(sp)
    1528:	03012c23          	sw	a6,56(sp)
    152c:	03112e23          	sw	a7,60(sp)
        int i;
        va_list ap;

        va_start(ap, format);
    1530:	02410793          	addi	a5,sp,36
    1534:	00f12623          	sw	a5,12(sp)

        for (i = 0; format[i]; i++)
    1538:	00000413          	li	s0,0
    153c:	01c0006f          	j	1558 <bsp_printf+0x58>
            if (format[i] == '%') {
                while (format[++i]) {
                    if (format[i] == 'c') {
                        bsp_printf_c(va_arg(ap,int));
    1540:	00c12783          	lw	a5,12(sp)
    1544:	00478713          	addi	a4,a5,4
    1548:	00e12623          	sw	a4,12(sp)
    154c:	0007a503          	lw	a0,0(a5)
    1550:	d99ff0ef          	jal	ra,12e8 <bsp_printf_c>
        for (i = 0; format[i]; i++)
    1554:	00140413          	addi	s0,s0,1
    1558:	008487b3          	add	a5,s1,s0
    155c:	0007c503          	lbu	a0,0(a5)
    1560:	0c050263          	beqz	a0,1624 <bsp_printf+0x124>
            if (format[i] == '%') {
    1564:	02500793          	li	a5,37
    1568:	06f50663          	beq	a0,a5,15d4 <bsp_printf+0xd4>
                        break;
                    }
#endif //#if (ENABLE_FLOATING_POINT_SUPPORT)
                }
            } else
                bsp_printf_c(format[i]);
    156c:	d7dff0ef          	jal	ra,12e8 <bsp_printf_c>
    1570:	fe5ff06f          	j	1554 <bsp_printf+0x54>
                        bsp_printf_s(va_arg(ap,char*));
    1574:	00c12783          	lw	a5,12(sp)
    1578:	00478713          	addi	a4,a5,4
    157c:	00e12623          	sw	a4,12(sp)
    1580:	0007a503          	lw	a0,0(a5)
    1584:	d81ff0ef          	jal	ra,1304 <bsp_printf_s>
                        break;
    1588:	fcdff06f          	j	1554 <bsp_printf+0x54>
                        bsp_printf_d(va_arg(ap,int));
    158c:	00c12783          	lw	a5,12(sp)
    1590:	00478713          	addi	a4,a5,4
    1594:	00e12623          	sw	a4,12(sp)
    1598:	0007a503          	lw	a0,0(a5)
    159c:	d81ff0ef          	jal	ra,131c <bsp_printf_d>
                        break;
    15a0:	fb5ff06f          	j	1554 <bsp_printf+0x54>
                        bsp_printf_X(va_arg(ap,int));
    15a4:	00c12783          	lw	a5,12(sp)
    15a8:	00478713          	addi	a4,a5,4
    15ac:	00e12623          	sw	a4,12(sp)
    15b0:	0007a503          	lw	a0,0(a5)
    15b4:	e29ff0ef          	jal	ra,13dc <bsp_printf_X>
                        break;
    15b8:	f9dff06f          	j	1554 <bsp_printf+0x54>
                        bsp_printf_x(va_arg(ap,int));
    15bc:	00c12783          	lw	a5,12(sp)
    15c0:	00478713          	addi	a4,a5,4
    15c4:	00e12623          	sw	a4,12(sp)
    15c8:	0007a503          	lw	a0,0(a5)
    15cc:	dd1ff0ef          	jal	ra,139c <bsp_printf_x>
                        break;
    15d0:	f85ff06f          	j	1554 <bsp_printf+0x54>
                while (format[++i]) {
    15d4:	00140413          	addi	s0,s0,1
    15d8:	008487b3          	add	a5,s1,s0
    15dc:	0007c783          	lbu	a5,0(a5)
    15e0:	f6078ae3          	beqz	a5,1554 <bsp_printf+0x54>
                    if (format[i] == 'c') {
    15e4:	06300713          	li	a4,99
    15e8:	f4e78ce3          	beq	a5,a4,1540 <bsp_printf+0x40>
                    else if (format[i] == 's') {
    15ec:	07300713          	li	a4,115
    15f0:	f8e782e3          	beq	a5,a4,1574 <bsp_printf+0x74>
                    else if (format[i] == 'd') {
    15f4:	06400713          	li	a4,100
    15f8:	f8e78ae3          	beq	a5,a4,158c <bsp_printf+0x8c>
                    else if (format[i] == 'X') {
    15fc:	05800713          	li	a4,88
    1600:	fae782e3          	beq	a5,a4,15a4 <bsp_printf+0xa4>
                    else if (format[i] == 'x') {
    1604:	07800713          	li	a4,120
    1608:	fae78ae3          	beq	a5,a4,15bc <bsp_printf+0xbc>
                    else if (format[i] == 'f') {
    160c:	06600713          	li	a4,102
    1610:	fce792e3          	bne	a5,a4,15d4 <bsp_printf+0xd4>
                        bsp_printf_s("<Floating point printing not enable. Please Enable it at bsp.h first...>");
    1614:	00002537          	lui	a0,0x2
    1618:	8f050513          	addi	a0,a0,-1808 # 18f0 <_data+0x28>
    161c:	ce9ff0ef          	jal	ra,1304 <bsp_printf_s>
                        break;
    1620:	f35ff06f          	j	1554 <bsp_printf+0x54>

        va_end(ap);
    }
    1624:	01c12083          	lw	ra,28(sp)
    1628:	01812403          	lw	s0,24(sp)
    162c:	01412483          	lw	s1,20(sp)
    1630:	04010113          	addi	sp,sp,64
    1634:	00008067          	ret

00001638 <crash>:
*
* @brief This function handles the system crash scenario by printing a crash message
* 		 and entering an infinite loop.
*
******************************************************************************/
void crash(){
    1638:	ff010113          	addi	sp,sp,-16
    163c:	00112623          	sw	ra,12(sp)
    bsp_printf("\r\n*** CRASH ***\r\n");
    1640:	00002537          	lui	a0,0x2
    1644:	93c50513          	addi	a0,a0,-1732 # 193c <_data+0x74>
    1648:	eb9ff0ef          	jal	ra,1500 <bsp_printf>
    while(1);
    164c:	0000006f          	j	164c <crash+0x14>

00001650 <gpioIsr>:
    } else {
        crash();
    }
}

void gpioIsr(){
    1650:	ff010113          	addi	sp,sp,-16
    1654:	00112623          	sw	ra,12(sp)
    bsp_printf("Entering gpio interrupt routine .. \r\n");
    1658:	00002537          	lui	a0,0x2
    165c:	95050513          	addi	a0,a0,-1712 # 1950 <_data+0x88>
    1660:	ea1ff0ef          	jal	ra,1500 <bsp_printf>
    bsp_uDelay(100);
    1664:	f8b00637          	lui	a2,0xf8b00
    1668:	05f5e5b7          	lui	a1,0x5f5e
    166c:	10058593          	addi	a1,a1,256 # 5f5e100 <__freertos_irq_stack_top+0x5f5b6c0>
    1670:	06400513          	li	a0,100
    1674:	b45ff0ef          	jal	ra,11b8 <clint_uDelay>
    count++;
    1678:	8241a583          	lw	a1,-2012(gp) # 1a34 <count>
    167c:	00158593          	addi	a1,a1,1
    1680:	82b1a223          	sw	a1,-2012(gp) # 1a34 <count>
    bsp_printf("Count:%d .. Done \r\n",count);
    1684:	00002537          	lui	a0,0x2
    1688:	97850513          	addi	a0,a0,-1672 # 1978 <_data+0xb0>
    168c:	e75ff0ef          	jal	ra,1500 <bsp_printf>
}
    1690:	00c12083          	lw	ra,12(sp)
    1694:	01010113          	addi	sp,sp,16
    1698:	00008067          	ret

0000169c <isrRoutine>:
*        source. If an interrupt from an unknown source is detected, it 
*        calls a crash function to handle the error.
*
******************************************************************************/

void isrRoutine(){
    169c:	ff010113          	addi	sp,sp,-16
    16a0:	00112623          	sw	ra,12(sp)
    16a4:	00812423          	sw	s0,8(sp)
    uint32_t claim;
    // While there is pending interrupts
    while(claim = plic_claim(BSP_PLIC, BSP_PLIC_CPU_0)){
    16a8:	00000593          	li	a1,0
    16ac:	f8c00537          	lui	a0,0xf8c00
    16b0:	e19ff0ef          	jal	ra,14c8 <plic_claim>
    16b4:	00050413          	mv	s0,a0
    16b8:	02050463          	beqz	a0,16e0 <isrRoutine+0x44>
        switch(claim){
    16bc:	00c00793          	li	a5,12
    16c0:	00f41e63          	bne	s0,a5,16dc <isrRoutine+0x40>
        case SYSTEM_PLIC_SYSTEM_GPIO_0_IO_INTERRUPTS_0: gpioIsr(); break;
    16c4:	f8dff0ef          	jal	ra,1650 <gpioIsr>
        default: crash(); break;
        }
        // Unmask the claimed interrupt
        plic_release(BSP_PLIC, BSP_PLIC_CPU_0, claim); 
    16c8:	00040613          	mv	a2,s0
    16cc:	00000593          	li	a1,0
    16d0:	f8c00537          	lui	a0,0xf8c00
    16d4:	e11ff0ef          	jal	ra,14e4 <plic_release>
    16d8:	fd1ff06f          	j	16a8 <isrRoutine+0xc>
        default: crash(); break;
    16dc:	f5dff0ef          	jal	ra,1638 <crash>
    }
}
    16e0:	00c12083          	lw	ra,12(sp)
    16e4:	00812403          	lw	s0,8(sp)
    16e8:	01010113          	addi	sp,sp,16
    16ec:	00008067          	ret

000016f0 <trap>:
void trap(){
    16f0:	ff010113          	addi	sp,sp,-16
    16f4:	00112623          	sw	ra,12(sp)
    int32_t mcause = csr_read(mcause);
    16f8:	342027f3          	csrr	a5,mcause
    if(interrupt){
    16fc:	0207d263          	bgez	a5,1720 <trap+0x30>
    1700:	00f7f713          	andi	a4,a5,15
        switch(cause){
    1704:	00b00793          	li	a5,11
    1708:	00f71a63          	bne	a4,a5,171c <trap+0x2c>
        case CAUSE_MACHINE_EXTERNAL: isrRoutine(); break;
    170c:	f91ff0ef          	jal	ra,169c <isrRoutine>
}
    1710:	00c12083          	lw	ra,12(sp)
    1714:	01010113          	addi	sp,sp,16
    1718:	00008067          	ret
        default: crash(); break;
    171c:	f1dff0ef          	jal	ra,1638 <crash>
        crash();
    1720:	f19ff0ef          	jal	ra,1638 <crash>

00001724 <isrInit>:
*
* @brief This function initializes GPIO interrupts and enables external interrupts
*        by setting up the machine trap vector. 
*
******************************************************************************/
void isrInit(){
    1724:	ff010113          	addi	sp,sp,-16
    1728:	00112623          	sw	ra,12(sp)
    // Configure PLIC
    // Cpu 0 accept all interrupts with priority above 0
    plic_set_threshold(BSP_PLIC, BSP_PLIC_CPU_0, 0); 
    172c:	00000613          	li	a2,0
    1730:	00000593          	li	a1,0
    1734:	f8c00537          	lui	a0,0xf8c00
    1738:	d79ff0ef          	jal	ra,14b0 <plic_set_threshold>
    plic_set_enable(BSP_PLIC, BSP_PLIC_CPU_0, SYSTEM_PLIC_SYSTEM_GPIO_0_IO_INTERRUPTS_0, 1);
    173c:	00100693          	li	a3,1
    1740:	00c00613          	li	a2,12
    1744:	00000593          	li	a1,0
    1748:	f8c00537          	lui	a0,0xf8c00
    174c:	d19ff0ef          	jal	ra,1464 <plic_set_enable>
    plic_set_priority(BSP_PLIC, SYSTEM_PLIC_SYSTEM_GPIO_0_IO_INTERRUPTS_0, 1);
    1750:	00100613          	li	a2,1
    1754:	00c00593          	li	a1,12
    1758:	f8c00537          	lui	a0,0xf8c00
    175c:	cf9ff0ef          	jal	ra,1454 <plic_set_priority>
    1760:	f80157b7          	lui	a5,0xf8015
    1764:	00100713          	li	a4,1
    1768:	02e7a023          	sw	a4,32(a5) # f8015020 <__freertos_irq_stack_top+0xf80125e0>
    // Enable rising edge interrupts
    gpio_setInterruptRiseEnable(GPIO0, 1); 
    // Enable interrupts
    // Set the machine trap vector (../common/trap.S)
    csr_write(mtvec, trap_entry); 
    176c:	000027b7          	lui	a5,0x2
    1770:	83878793          	addi	a5,a5,-1992 # 1838 <trap_entry>
    1774:	30579073          	csrw	mtvec,a5
    //Enable external interrupts
    csr_set(mie, MIE_MEIE); 
    1778:	000017b7          	lui	a5,0x1
    177c:	80078793          	addi	a5,a5,-2048 # 800 <CUSTOM2+0x7a5>
    1780:	3047a073          	csrs	mie,a5
    csr_write(mstatus, csr_read(mstatus) | MSTATUS_MPP | MSTATUS_MIE);
    1784:	300027f3          	csrr	a5,mstatus
    1788:	00002737          	lui	a4,0x2
    178c:	80870713          	addi	a4,a4,-2040 # 1808 <main+0x64>
    1790:	00e7e7b3          	or	a5,a5,a4
    1794:	30079073          	csrw	mstatus,a5
}
    1798:	00c12083          	lw	ra,12(sp)
    179c:	01010113          	addi	sp,sp,16
    17a0:	00008067          	ret

000017a4 <main>:
*        and release various onboard buttons (sw4, sw6, sw7) corresponding to
*        different timer intervals.
*
******************************************************************************/

void main() {
    17a4:	ff010113          	addi	sp,sp,-16
    17a8:	00112623          	sw	ra,12(sp)
    17ac:	00812423          	sw	s0,8(sp)
    bsp_init();
    17b0:	c6dff0ef          	jal	ra,141c <bsp_init>
    bsp_printf("***Starting GPIO Demo*** \r\n");
    17b4:	00002537          	lui	a0,0x2
    17b8:	98c50513          	addi	a0,a0,-1652 # 198c <_data+0xc4>
    17bc:	d45ff0ef          	jal	ra,1500 <bsp_printf>
    bsp_printf("Configure GPIOs to blink .. \r\n");
    17c0:	00002537          	lui	a0,0x2
    17c4:	9a850513          	addi	a0,a0,-1624 # 19a8 <_data+0xe0>
    17c8:	d39ff0ef          	jal	ra,1500 <bsp_printf>
    17cc:	f80157b7          	lui	a5,0xf8015
    17d0:	00e00713          	li	a4,14
    17d4:	00e7a423          	sw	a4,8(a5) # f8015008 <__freertos_irq_stack_top+0xf80125c8>
    17d8:	0007a223          	sw	zero,4(a5)
    // Set GPIO to output
    gpio_setOutputEnable(GPIO0, 0xe);
    gpio_setOutput(GPIO0, 0x0);
    for (int i=0; i<50; i=i+1) {
    17dc:	00000413          	li	s0,0
    17e0:	0300006f          	j	1810 <main+0x6c>
        return *((volatile u32*) address);
    17e4:	f8015737          	lui	a4,0xf8015
    17e8:	00472783          	lw	a5,4(a4) # f8015004 <__freertos_irq_stack_top+0xf80125c4>
        gpio_setOutput(GPIO0, gpio_getOutput(GPIO0) ^ 0xe);
    17ec:	00e7c793          	xori	a5,a5,14
        *((volatile u32*) address) = data;
    17f0:	00f72223          	sw	a5,4(a4)
        bsp_uDelay(LOOP_UDELAY);
    17f4:	f8b00637          	lui	a2,0xf8b00
    17f8:	05f5e5b7          	lui	a1,0x5f5e
    17fc:	10058593          	addi	a1,a1,256 # 5f5e100 <__freertos_irq_stack_top+0x5f5b6c0>
    1800:	00018537          	lui	a0,0x18
    1804:	6a050513          	addi	a0,a0,1696 # 186a0 <__freertos_irq_stack_top+0x15c60>
    1808:	9b1ff0ef          	jal	ra,11b8 <clint_uDelay>
    for (int i=0; i<50; i=i+1) {
    180c:	00140413          	addi	s0,s0,1
    1810:	03100793          	li	a5,49
    1814:	fc87d8e3          	bge	a5,s0,17e4 <main+0x40>
    }   
    bsp_printf("***Starting GPIO Interrupt Demo*** \r\n");
    1818:	00002537          	lui	a0,0x2
    181c:	9c850513          	addi	a0,a0,-1592 # 19c8 <_data+0x100>
    1820:	ce1ff0ef          	jal	ra,1500 <bsp_printf>
    bsp_printf("Press and release onboard button sw4 .. \r\n");
    1824:	00002537          	lui	a0,0x2
    1828:	9f050513          	addi	a0,a0,-1552 # 19f0 <_data+0x128>
    182c:	cd5ff0ef          	jal	ra,1500 <bsp_printf>
    isrInit();
    1830:	ef5ff0ef          	jal	ra,1724 <isrInit>
    while(1); 
    1834:	0000006f          	j	1834 <main+0x90>

00001838 <trap_entry>:
.global  trap_entry
.align(2) //mtvec require 32 bits allignement
trap_entry:
  addi sp,sp, -16*4
    1838:	fc010113          	addi	sp,sp,-64
  sw x1,   0*4(sp)
    183c:	00112023          	sw	ra,0(sp)
  sw x5,   1*4(sp)
    1840:	00512223          	sw	t0,4(sp)
  sw x6,   2*4(sp)
    1844:	00612423          	sw	t1,8(sp)
  sw x7,   3*4(sp)
    1848:	00712623          	sw	t2,12(sp)
  sw x10,  4*4(sp)
    184c:	00a12823          	sw	a0,16(sp)
  sw x11,  5*4(sp)
    1850:	00b12a23          	sw	a1,20(sp)
  sw x12,  6*4(sp)
    1854:	00c12c23          	sw	a2,24(sp)
  sw x13,  7*4(sp)
    1858:	00d12e23          	sw	a3,28(sp)
  sw x14,  8*4(sp)
    185c:	02e12023          	sw	a4,32(sp)
  sw x15,  9*4(sp)
    1860:	02f12223          	sw	a5,36(sp)
  sw x16, 10*4(sp)
    1864:	03012423          	sw	a6,40(sp)
  sw x17, 11*4(sp)
    1868:	03112623          	sw	a7,44(sp)
  sw x28, 12*4(sp)
    186c:	03c12823          	sw	t3,48(sp)
  sw x29, 13*4(sp)
    1870:	03d12a23          	sw	t4,52(sp)
  sw x30, 14*4(sp)
    1874:	03e12c23          	sw	t5,56(sp)
  sw x31, 15*4(sp)
    1878:	03f12e23          	sw	t6,60(sp)
  call trap
    187c:	e75ff0ef          	jal	ra,16f0 <trap>
  lw x1 ,  0*4(sp)
    1880:	00012083          	lw	ra,0(sp)
  lw x5,   1*4(sp)
    1884:	00412283          	lw	t0,4(sp)
  lw x6,   2*4(sp)
    1888:	00812303          	lw	t1,8(sp)
  lw x7,   3*4(sp)
    188c:	00c12383          	lw	t2,12(sp)
  lw x10,  4*4(sp)
    1890:	01012503          	lw	a0,16(sp)
  lw x11,  5*4(sp)
    1894:	01412583          	lw	a1,20(sp)
  lw x12,  6*4(sp)
    1898:	01812603          	lw	a2,24(sp)
  lw x13,  7*4(sp)
    189c:	01c12683          	lw	a3,28(sp)
  lw x14,  8*4(sp)
    18a0:	02012703          	lw	a4,32(sp)
  lw x15,  9*4(sp)
    18a4:	02412783          	lw	a5,36(sp)
  lw x16, 10*4(sp)
    18a8:	02812803          	lw	a6,40(sp)
  lw x17, 11*4(sp)
    18ac:	02c12883          	lw	a7,44(sp)
  lw x28, 12*4(sp)
    18b0:	03012e03          	lw	t3,48(sp)
  lw x29, 13*4(sp)
    18b4:	03412e83          	lw	t4,52(sp)
  lw x30, 14*4(sp)
    18b8:	03812f03          	lw	t5,56(sp)
  lw x31, 15*4(sp)
    18bc:	03c12f83          	lw	t6,60(sp)
  addi sp,sp, 16*4
    18c0:	04010113          	addi	sp,sp,64
  mret
    18c4:	30200073          	mret
