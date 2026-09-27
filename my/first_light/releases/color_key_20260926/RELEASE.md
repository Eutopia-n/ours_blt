# 2026-09-26 颜色键控待上板版本

此目录冻结一次通过固件、RTL 仿真、真实 Sapphire 联合仿真和 Efinity 完整编译的构建结果。`first_light.bit` 含本次 3332 字节片内固件；尚未下载或在实板验证。

- `first_light.bit` SHA-256：`463A626249BA6F7C8E3BD8AA42A5B57FD6DC596600B474F66422E02020F697C9`
- `first_light.elf`、`first_light.bin`、`first_light.map`：固件调试与大小核对。
- `reports/`：仿真、编译、时序记录及硬件模式仿真预览。`motion_5.png` 不是显示器照片。

验证范围、接口与实板待验步骤见工程根目录的 [`COLOR_KEY.md`](../../COLOR_KEY.md)。上板时使用易失性 JTAG 配置，并记录实际画面、串口指标、运行时间和异常状态。
