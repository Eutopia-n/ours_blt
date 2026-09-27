# 2026-09-26 可切换颜色键控待上板版本

`first_light.bit` 含 3472 字节片内固件。一次 JTAG 配置后，串口 115200、8N1 发送小写 `k`/`o`，即可开启/关闭去背；屏幕显示 `KEY ON`/`KEY OFF`。小写 `c`/`h` 可选择 CPU/硬件绘制，原有自动切换仍生效。本版本尚未上板验证。

- `first_light.bit` SHA-256：`BC7D9AAF73D2C87FD5B3557B34D2B4EF5625465885E93A17E2EEE2C98639862F`
- `first_light.elf`、`first_light.bin`、`first_light.map` 为该 bitstream 对应固件。
- `reports/` 保存构建、时序、联合仿真与两种去背状态的扫描画面。

固件构建与 Sapphire 联合仿真通过：CPU/HW/CPU 共 9 次换页；CPU、硬件各自验证去背开/关，硬件有 32 次普通 Copy 和 96 次键控 Copy；A/B 各完成 6 帧扫描。Efinity 的 map/interface/pnr/pgm 均 PASS，最小 setup slack `+0.143 ns`、hold slack `+0.026 ns`。以上为工具验证，尚无本版本实板结果。

完整接口、复现命令及实板待验事项见工程根目录的 [`COLOR_KEY.md`](../../COLOR_KEY.md)。
