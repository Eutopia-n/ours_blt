# 800x600 RISC-V FPGA 2D Rendering Engine - R4B

本目录是 2026-10-05 成功上板的 Ti60F225 R4B 工程。菜单、BASIC 和 ADVANCED 固定为 800×600；HDMI 像素时钟 40 MHz，设计刷新率约 60.317 Hz。

工程入口保持 `first_light.xml`，内部名称保持 `spi_flash_autoboot_5x7_font`，与已验证的 bitstream 一致。不要根据 README 标题改动内部工程名。

## 下载已验证版本

用 Efinity Programmer 通过 JTAG 下载 [fixed800_directpll_scan64_fill64_R4B.bit](releases/fixed800_directpll_scan64_fill64_R4B.bit)。这是本次上板成功的原文件，未因上传仓库而重新编译。

SHA-256：`4D5BAA389AE1B9820EF8FAFE4D47B37EFBDDACCBA1F51398E94790495CA8B83F`。

当前应用已嵌入 bitstream 中的 ROM。启动时将应用复制到 DDR，并从 SPI Flash `0x380000` 的既有 FTL1 用户镜像读取 77 帧素材；旧镜像内的旧应用会被忽略。

- 已写入兼容素材的现有板卡：只需下载本次 bit，无需每次通过串口重新上传。
- 全新或已擦除素材区的板卡：先将随附 [flash_user.hex](software/build/flash_user.hex) 写入 SPI Flash 起始地址 `0x380000`，再下载本次 bit。该文件每行一个字节，对应二进制为 [flash_user.bin](software/build/flash_user.bin)。不要把素材文件写到 FPGA 配置区 `0x000000`。
- JTAG 配置掉电丢失。要实现上电自动配置 FPGA，需另用 Active SPI 将对应 FPGA 配置写入配置区，并保留素材区；本次记录验证的是下载 R4B bit 后的运行效果。

串口为 115200、8N1，COM 号因电脑而异。正常启动示例：

```text
FLASH BOOT
Ti60 FIXED 800X600 R4B DIRECTPLL SCAN64 FILL64
VIDEO CLOCK READY MODE=00000005 CLOCK=7CF9000D STATUS=00000008
```

`CLOCK` 高 16 位为运行计数，不要求每次相同。如果启动失败，保留完整的 `FAIL ... MODE=... CLOCK=...` 行用于定位。此前可运行的 [R3 bit](releases/fixed800_burst64_ui800_R3.bit) 保留作为回退版本。

## 操作

| 场景 | KEY0 | KEY1 | KEY2 | KEY3 |
|---|---|---|---|---|
| 菜单 | 选择 BASIC | 选择 ADVANCED | 确认进入 | 无操作 |
| BASIC | 切换 CPU/HW | 数量 32 → 128 → 256 → 32 | 无操作 | 返回菜单 |
| ADVANCED | 无操作 | 开关颜色键控 | 透明度短按 +2%，长按连加，0～100% 循环 | 返回菜单 |

ADVANCED 每约 4 秒交替 CPU/HW 路径，UART 小写 `c` / `h` 也可指定模式。屏幕显示 CPU/HW FPS、场景渲染耗时和实测有效分辨率。`US` 不包含 HUD 绘制及等待换帧，不能直接用 `1000000/US` 当作最终显示帧率。

## 赛题对应

按《2026FPGA-易灵思-赛题二》两页题目核对：

| 要求 | 当前实现及证据 | 状态 |
|---|---|---|
| RISC-V 下发操作类型、源/目的地址、宽高 | `software/render.h`、`main.c` 配置 APB 寄存器；`rtl/render_regs.v` 解析 | 已覆盖 |
| Block Copy、Solid Fill | `rtl/fill_engine.v`；BASIC 混合绘制随机移动的实心方块和棋盘格块 | 已覆盖 |
| 至少 640×480 @ 60 Hz 的 VGA/HDMI 输出 | 800×600 HDMI，40 MHz，1056×628 总时序，约 60.317 Hz | 已覆盖 |
| 总线直接访问 DDR、Burst 和 FIFO | AXI 主接口；扫描与 Fill 最多 64 beat，Copy/Alpha 最多 16 beat；Copy/Alpha 保留 16 项写 FIFO | 已覆盖 |
| C 驱动、双缓冲防撕裂 | 两页 RGB565 framebuffer，CPU/硬件写后台页，在帧边界握手换页 | 已覆盖 |
| 基础 Demo、屏幕实时对比 CPU/HW FPS | BASIC 32/128/256 个活动元素，屏幕两列统计 | 已覆盖，已有实板记录 |
| 高阶 1：硬件 Alpha 混合 | `rtl/alpha_blend.v` 读取前景和背景，按 0～256 不透明度混合；综合报告列出 `graphics/fill/blend/*` 的 DSP48 | 已实现 |
| 高阶 2：颜色键控 | 可配置 RGB565 键色，跳过键色像素；77 帧不规则 Sprite 展示 | 已实现 |
| 高阶 3：高负载互动游戏与同时开启 Alpha + Keying 的 Sprite 极限 | BASIC 是 Fill/普通 Copy 压力演示，256 档结果不代表该挑战的极限 | 尚未实现，本次不涉及 |

纯色 Fill 直接生成重复颜色数据；图像拷贝和 Alpha 仍使用内部 FIFO。这一优化保留了题目要求的 Burst 与 FIFO 机制。

## 本次实板结果和验证范围

用户提供的 [串口记录](releases/r4b_validation/board_uart_20261005.log) 与“无黑条”反馈对应本版 R4B。下表 FPS 取稳定记录；US 为各档全部记录的均值，切档后第一条 FPS 可能轻微波动。

| BASIC 元素数 | CPU FPS | HW FPS | HW 平均 US | BASIC UF 最大值 |
|---|---:|---:|---:|---:|
| 32 | 15.0 | 60.3 | 5555.9 | 0 |
| 128 | 12.0 | 60.3 | 8738.2 | 0 |
| 256 | 10.0 | 60.3 | 13004.6 | 0 |

ADVANCED 的记录为 CPU 约 15 FPS、HW 约 60 FPS。ADVANCED 日志没有输出 UF，不能据此声称它单独测得 UF=0。此次日志也不记录逐次透明度/键控按键状态，不代表本版本已重新逐项验证所有 Alpha 端点组合。

R3 的 256 档约 30.1 FPS / 16.5 ms，R4B 约 60.3 FPS / 13.0 ms。渲染时间缩短后有余量赶上每次显示刷新。

- [FPGA 全流程日志](releases/r4b_validation/compile.log)：map / interface / pnr / pgm 全部 PASS。
- [时序报告](releases/r4b_validation/spi_flash_autoboot_5x7_font.timing.rpt)：最小 setup slack +0.221 ns，hold slack +0.026 ns。
- [DSP 综合报告](releases/r4b_validation/spi_flash_autoboot_5x7_font.map.rpt)：Alpha 的 DSP 映射证据。
- [800×600 专项仿真](releases/r4b_validation/r4b_fixed800_result.txt)：初始同页换帧、完整像素帧、同步时序、失锁恢复、整屏填充及非法尺寸检查通过；独立时钟控制仿真通过启动重试和失锁重锁检查。
- 旧综合渲染回归耗时较长，已停止，未记为本次通过；多次冷启动和长时间稳定性仍需补充记录。

历史 `reports/` 和旧发布目录包含旧版本结果；判断本版以 `releases/r4b_validation/` 和 [版本清单](releases/fixed800_directpll_scan64_fill64_R4B.json) 为准。

## 编译源码

在当前目录执行。无需重跑全部仿真，也无需运行 `prepare`；仓库已含板级依赖。`prepare.py` 是历史随板资料导入工具，不属于本次 R4B 快速复现流程。

```powershell
python tools/build.py firmware --efinity C:/Efinity/efinity-riscv-ide-2026.1
python tools/build.py compile --efinity C:/Efinity/2026.1
```

路径按实际安装位置替换。`firmware` 使用 RISC-V 工具链目录，`compile` 使用 FPGA Efinity 安装目录，两者可以分开安装。先构建 firmware 再构建 FPGA，生成文件为 `outflow/spi_flash_autoboot_5x7_font.bit`。

仓库保留本版 `software/build/embedded_app.memh`、`embedded_app.h`、固件 bin 与四路 RAM 初始化文件，因此从本次提交打开 `first_light.xml` 也具备所需 ROM 输入。修改 C 代码后必须先运行 `firmware` 更新这些输入。应用本次为 13796 字节，上限 16 KiB；片内 bootloader 为 2855 字节。

## 文件入口

- `rtl/competition_top.v`：RISC-V、DDR、渲染器和 HDMI 连接。
- `rtl/video_clock_control.v`、`tools/config_video_modes.py`：固定 800×600 的 PLL 控制与配置；R4B 由 core_clk 100 MHz 直接参考，产生 40/200 MHz。
- `rtl/framebuffer_video.v`：64-beat 扫描读取、双行缓存、视频时序及帧边界换页。
- `rtl/render_subsystem.v`：仲裁、行级写节流、欠载计数和像素时钟诊断。
- `rtl/fill_engine.v`、`alpha_blend.v`、`sync_fifo.v`：Fill/Copy/Key/Alpha 和写 FIFO。
- `software/main.c`、`render.h`、`boot.c`：C 驱动、场景、HUD 和 ROM/Flash 启动。
- `assets/`：77 帧素材和原图；`vendor/`：原厂依赖，保留来源与许可说明。
- [历史工程说明](README_PRE_R4B.md)：旧版本设计过程，不作为本次下载入口。
