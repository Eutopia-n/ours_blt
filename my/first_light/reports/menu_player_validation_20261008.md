# 菜单与人物资源验证（2026-10-08）

## 修改与预期现象

`software/main.c` 的两级菜单改为深蓝灰背景、简洁卡片和青色左侧选择标记，底部集中显示按键说明，顶部显示用户提供的蓝色兜帽人物。首页只有基础、高阶两个分类，子菜单仍各有四个功能。KEY0 上一项、KEY1 下一项、KEY2 进入、KEY3 返回。

新增 `draw_player()` 从独立 DDR 玩家资源区取帧；`cpu_blend_copy_source()` 支持指定图像源地址；`init_assets()` 解压四方向代表帧。FPGA 使用 Color Key 去除透明背景，菜单绘制在性能采样区间之外。原有独立功能、性能 Sprite、FPS/时间/burst 统计口径及板级引脚继续沿用。

附件原图保存于 `assets/player/source.png`，SHA-256 为 `129219333FC94585C079187FC4AF0242A13F5CE2D019BAC2AD49DAD17B8695AB`，与原附件逐字节相同。完整四方向 × 四动作帧保存为 32×32 透明图集和 32768 字节 RGB565 文件；生成脚本、方向约定和地址见 [人物资源说明](../assets/player/README.md)。固件先嵌入四方向各第一帧，共 8192 字节展开数据，调色板 + RLE 为 4624 字节（另有 10 字节偏移表）。当前只显示正面预览，未接入游戏人物移动或走路动画。

## 构建

- `python tools/build.py firmware` 通过，启用 `-Wall -Wextra -Werror`。链接器保留原片内 RAM 的 RWX 段提示。
- text = 14924 B，data = 8 B，bss = 64 B，共 14996 B；二进制 14932 B。16 KiB 片内 RAM 留出 1388 B 栈空间，通过链接脚本的至少 1024 B 检查。
- 已核对四个 RAM 初始化 lane 与固件二进制一致，工程根目录及 `vendor/soc` 两处副本一致。
- `python tools/build.py compile` 通过：map、interface、pnr、pgm 全部 PASS；pgm 表示生成 bitstream，未执行上板下载或 Flash 编程。
- 时序报告：100 MHz core setup slack +1.990 ns，400 MHz DDR +0.266 ns，约 25.209 MHz HDMI +35.173 ns；报告中列出的 setup/hold 路径均无负 slack。
- 当前 `outflow/first_light.bit`：2124387 字节。
- SHA-256：`75BF7CE7F4B8243D2F2419CE07CE2157AF961506ECB6F9141FB5C38385E5A871`。

## 本次联合仿真

`python tools/build.py sim-soc --ui-smoke` 通过，`reports/simulation_soc_ui.log` 输出 `SOC UI TEST PASSED`，Errors = 0、Warnings = 0。

真实 Sapphire 核执行当前固件，完成 19 张菜单、5 张功能页面，共 24 张提交页面的整帧像素核对、24 次换页，以及 27 个完整扫描帧的像素核对。覆盖分类菜单双向循环、基础子菜单前向循环、高阶子菜单反向循环、进入和逐级返回、填充及颜色切换、Alpha 参数切换和 CPU/HW 对照。无前台页写入、扫描下溢或读错误。

四个方向的 4096 个 RGB565 像素均与源图片直接生成的未压缩参考一致，并跨清屏/换页保持不变。测试图片和玩家资源仅在启动时上传一次，共 10240 字节；解压数据、完整图集的代表帧和仿真参考一致。

本次为菜单/人物修改的定向回归，没有重测 64/128/256 性能，也没有完成新的完整 8 功能回归。上一版完整回归及性能数据见 [2026-10-06 记录](individual_validation_20261006.md)，不能将其当作本次固件或实板的新测量结果。不带 `--ui-smoke` 的 `sim-soc` 仍可运行完整测试。仿真只缩短按键消抖，CPU、DDR 和 HDMI 时钟保持原设计；实际工程使用 20 ms 消抖。

预览：[分类菜单](menu_player_home.png)、[基础菜单](menu_player_basic.png)、[高阶菜单](menu_player_advanced.png)。预览取自本次通过像素核对的 HDMI 扫描输出，不是显示器照片。

## 上板与后续排查

下载本次 bitstream 后，应先看到上述菜单与右上角人物，按键进入各独立功能。实板观感及性能尚需下载后验收。

若仍显示旧画面，核对下载路径及 SHA-256；若人物异常，核对 `0x01200800` 的 2048 字节与 `sim/player_expected.hex` 第一帧，以及渲染寄存器源地址、64 字节行距、Color Key = 0；若按键不响应，观察 `button_input.pending` 与 GPIO `button_ack[0]`；若 HDMI 无画面，检查 DDR `cal_done`、HDMI PLL `hdmi_tx_locked` 和 UART 的 FAIL/TRAP 日志。
