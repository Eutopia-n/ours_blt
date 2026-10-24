# 压力页进入卡死修复（2026-10-23）

本报告记录入口修复时的构建；后续文字布局、长按和游戏 MAX60 修改与最新下载文件见 `ui_controls_max60_check_20261023.md`，下方文件哈希属于历史版本。

用户反馈：进入 Sprite 压力页后卡死，尚未显示方块；没有可见串口日志。本次没有实板复现，不能将下面的代码排查结论当作已测定的板上根因。

## 排查结论

原 `bench_prime_framebuffers()` 在 HDMI 持续从 DDR 扫描的同时，填充两张帧缓冲并由 CPU 上传整页文字。方块要等初始化完全结束后的主循环才绘制。`wait_display_page()` 发现任何一次显示欠载就返回错误，随后 `fail()` 无限停机；欠载标志原来只能通过复位清除。因此初始化阶段的短暂欠载会令画面一直停在进入压力页之前，且始终看不到 Sprite。这是与反馈吻合的明确停机路径，但因无串口日志，尚不能确认板上触发的就是此路径。

## 最小修复

- `software/main.c` 的 `bench_prime_framebuffers()`：关闭显示取数后，先等一次帧边界换页确认，确保旧页取数已经结束；再初始化两张缓冲页，包含静态文字、数值及第一个 24×24 Sprite；两页都准备好后恢复显示，并等待换页确认。HDMI 时钟和同步持续运行，准备阶段短暂黑屏属于正常现象。初始化和预热均在 FPS 采样窗口之前。
- `rtl/framebuffer_video.v`：仅在显示已停止且关闭信号已同步时清除欠载标志；正常显示期间仍然锁存欠载，不掩盖压力过程中的异常。AXI 读错误、渲染错误与超时处理保留。
- `software/main.c` 的 `wait_display_page()`：关闭显示期间允许等待旧欠载标志退出，避免刚发关闭命令就因旧标志停机；显示启用时仍检查欠载。
- `software/game_view.h`：24 个 HUD 数值缓存共 96 字节移回片内 RAM，避免每帧比较数字时访问 DDR；数字像素改为按扫描行连续写入，减少来回跨行访问。字形、字号、字段位置与数值缓存机制保留。
- `software/main.c` 的 `fail()`：在原错误原因后追加 `STATUS`、`OP`、`DST` 寄存器值；压力页入口输出 `BENCH INIT`，恢复显示后输出 `BENCH RUN`，便于后续直接区分初始化与运行阶段。

## 保留的压力规则

W 每次加 1，S 每次减 1，A/D 切换 4×4、16×16、24×24、32×32，Enter 返回。硬件 Alpha=128 与黑色 Color Key 同时开启；不减 Sprite、不人为封顶、不把 FPS 强制写成 60。逐帧完整渲染预算和实际显示刷新间隔的 MAX60 判断保留。

## 已完成检查

- 固件 GCC 编译通过：text=52428 B，data=12 B，bss=5516 B，总计 57956 B。
- 链接结果 `__bss_end=0xF900E264`，栈顶 `0xF9010000`，剩余 7580 B，满足至少 4096 B 的链接断言。
- 本次修改文件的 Git 空白检查通过。
- 8 份固件 RAM lane 文件与当前 ELF 导出的二进制逐字节一致；19 处 HUD 数字字段的地址对齐、字符宽度和帧缓冲边界检查通过。
- Efinity map、interface、pnr、pgm 全部 PASS；最终 setup/hold 时序汇总全部为正余量，core_clk 100 MHz 的 setup 余量 2.064 ns，hold 余量 0.026 ns。
- 不运行 ModelSim，不连接板卡下载，不上传 GitHub。

## 本次下载文件

- 临时 JTAG 下载：`S:\Ti60F225_DemoBoard_v4\my\first_light\outflow\first_light.bit`。
- 掉电保留配置：`S:\Ti60F225_DemoBoard_v4\my\first_light\outflow\first_light.hex`，使用原有 Active/JTAG bridge（SPI Flash）方式，详见 `FLASH_PROGRAMMING.md`。
- 生成时间：2026-10-23 17:28:01（本地文件时间）。
- bit 文件大小：2373573 字节。
- bit 文件 SHA-256：`F8CBC99694A1694770DAB458E3420D526DE19E75AA93BBCB25F2C29B02F81081`。

## 下载后预期与继续定位

用新 bitstream 下载后，进入高阶演示的 SPRITE 压力页；短暂准备后应出现一个移动的 24×24 Sprite，再开始实际 FPS 统计。低负载目标为约 60 FPS，实际是否达成仍需下载后的显示结果确认。

若仍异常，下一步读取 115200、8N1 串口：`BENCH INIT` 后未出现 `BENCH RUN` 表示初始化阶段未结束；`FAIL bench pause/init/resume` 可进一步定位换页阶段，`FAIL bench sprite` 指向 Sprite 命令，`TRAP` 带 cause/pc 用于定位 CPU 异常。`STATUS` 中 bit 2 为渲染错误，bit 4 为显示欠载，bit 5 为显示 AXI 读错误，bit 7 为换页等待。
