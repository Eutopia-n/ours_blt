# Sprite 压力页 60 FPS 流程修正（2026-10-23）

后续用户反馈进入压力页卡死，另见 `pressure_entry_fix_20261023.md`。下面的固件大小、bitstream 时间和 SHA-256 属于本次入口修复之前的版本，请以该后续报告记录的新文件为准。

用户实测旧版：32×32、1 个 Sprite 时 FPS=30，RENDER_US=5597，DDR_RD=80，DDR_WR=14768；其他尺寸也固定约 30 FPS，4×4 增至 1500 个仍约 30 FPS。这些是用户提供的旧版数据，不是本次新版本的实测结果。

## 问题与修改

旧压力页每帧先填满 640×480，再填 640×256 测试区，随后 CPU 重画全部 HUD。旧 RENDER_US 只计场景，遗漏 HUD；整帧一旦错过下一次 60 Hz 换页机会，会等待至后一次刷新，显示约 30 FPS。因此 5597 us 不能证明旧版整帧在 16.6667 ms 内完成。本次没有重新上板逐段测量，不能据此宣称已实测恢复 60 FPS。

- `software/main.c`：新增 `bench_prime_framebuffers()`，进入压力页时只初始化两次静态布局，覆盖两个后缓冲页；新增 `bench_hud()`，通过每页缓存只更新变化数值。正式采样每帧只清原有 640×256 活动区域，不再额外清整屏。Sprite 数量、运动区域、四档尺寸与 FPGA Alpha + Color Key 路径保留。
- `software/game_view.h`：`game_hud_number()` 改为成对像素的连续 32 位写入，清旧数字和写新数字合成一次遍历。游戏与压力页顺序运行，复用现有两页缓存；进入各自页面时重置有效标志。
- `rtl/render_subsystem.v`、`rtl/render_regs.v`、`software/render.h`：新增只读 `GFX_FRAME_COUNT`，偏移 `0x6C`，完整地址 `0xF810006C`。在现有 VSYNC 更新 toggle 同步到 APB 时钟域后累计计数，不直接跨域传输多位计数值。
- `software/main.c`：菜单四方向图片从已经解码的游戏图集首帧复制到原菜单 DDR 地址，避免固件重复携带相同人物的 RLE 和调色板。旧素材文件保留，菜单像素不变。

## 测量口径

- FPS：实际呈现次数 / CLINT 实际时间，包含 HUD、换页等待与 UART 报告耗时。保留相邻呈现时间戳，不把显示刷新计数直接当作渲染 FPS，也没有将输出强行设为 60。
- 压力页 RENDER_US：场景、坐标计算、HUD 数字更新的平均微秒数，排除换页等待。普通独立功能页仍沿用场景时间口径。
- MAX_US：30 帧窗口中最长的一次完整渲染微秒数。
- MISSED：窗口内每次成功呈现之间，超过一次的显示刷新累计数。计数检查不受 APB 轮询返回时间轻微抖动影响。
- MAX60：同一尺寸、同一数量的连续 30 帧，每帧完整渲染不超过 1,666,667 个 100 MHz 周期，且相邻呈现之间显示刷新计数增量恰好为 1，才更新该尺寸的历史最高通过数量。每个窗口重新判定，之前失败后允许新窗口恢复。
- DDR_RD/WR：仍仅统计渲染引擎 AXI 读写 burst，排除 CPU HUD 写入及 HDMI 扫描；UART DDR_AR/AW 为同一窗口累计数。去掉重复整屏填充后，固定清屏写入量应下降。

按键：W 加 1、S 减 1（最低 1），A/D 双向循环 4×4、16×16、24×24、32×32，Enter 返回；切换尺寸保留数量并重开采样。

## 已完成的检查

- 固件编译通过：text=51996 B，data=12 B，bss=5420 B，总占用 57428 B；4 KiB 栈预留断言通过。
- 资源检查通过：四档压力素材和现有资源地址互不重叠；菜单复用的 4096 个 RGB565 像素与原独立参考完全一致；19 处数字区域满足成对写入对齐、完整字符宽度及帧缓冲边界条件。
- Efinity map、interface、pnr、pgm 全部 PASS。最终 setup/hold 时序汇总均为正余量；core_clk 100 MHz 的 setup 余量为 1.748 ns，hold 余量为 0.026 ns。
- 没有运行 ModelSim 仿真，没有下载板卡，没有上传 GitHub。

生成文件：`S:\Ti60F225_DemoBoard_v4\my\first_light\outflow\first_light.bit`。

- 生成时间：2026-10-23 17:06:22（本地文件时间）。
- 大小：2389263 字节。
- SHA-256：`0AAC5DB8D71BCA4C2890252178421C74FD91542672851F530C4F8B7D1FB8B8B2`。

## 下载后的判定

用 Efinity Programmer 的原有 JTAG 配置加载上述最新 bitstream。若需要掉电保留，按 `FLASH_PROGRAMMING.md` 写 SPI Flash。进入高阶演示的 Sprite 压力页，先在 32×32、1 个 Sprite 下观察完整采样窗口；低负载预期恢复约 60 FPS。达到 60 FPS 后再逐个加压，以各尺寸 MAX60 为实际通过记录。

115200、8N1 的 UART 报告保留原指标并附带 MAX_US、MISSED。低负载理想状态为 FPS 约 60、MISSED=0、MAX_US 不超过 16666 us、PASS；若仍约 30 FPS，结合 MAX_US 和 MISSED 判断是完整渲染超预算，还是换页漏过刷新。编译和静态检查不能替代这次实板结果。
