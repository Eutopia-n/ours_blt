# 2026-09-26 KEY1 颜色键控待上板版本

`first_light.bit` 包含 3480 字节片内固件。一次 JTAG 配置后，每按一次开发板 KEY1 即切换去背状态；屏幕显示 `KEY ON`/`KEY OFF`。串口小写 `c`/`h` 仍可选择 CPU/硬件绘制。本版不再使用串口 `k`/`o` 控制去背，尚未在实板验证。

- KEY1：`GPIOR_22`，封装 P14，BR Bank 3.3 V，低电平按下；100 MHz 域同步并做 15 ms 消抖。
- `first_light.bit` SHA-256：`D2A7E67DE04D63805D2C077A4C5931E6F10D4CCD55E3713F62D64DC9A76080AD`。
- `first_light.elf`、`first_light.bin`、`first_light.map` 与本 bitstream 对应。
- `reports/` 保存按键单元仿真、真实 Sapphire 联合仿真、编译、管脚与时序报告及开/关扫描画面。

按键单元仿真通过；联合仿真验证 CPU/HW 各自去背开/关、9 次换页、A/B 各 6 帧完整扫描，结果为 `SOC TEST PASSED`。Efinity `map/interface/pnr/pgm` 均 PASS；最小 setup slack `+0.339 ns`、hold slack `+0.026 ns`。工具验证不等同于上板验证。

完整接口与上板检查步骤见工程的 [`COLOR_KEY.md`](../../COLOR_KEY.md)。
