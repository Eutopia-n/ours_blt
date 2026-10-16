# 独立功能演示验证（2026-10-06）

## 修改范围

固件将原来的综合基础/高阶画面拆成两级菜单与 8 个独立功能页。前 7 页默认固定 HW 路径，Sprite 性能页默认自动比较 CPU/HW。单独测试 Alpha 时关闭 Color Key，单独测试 Color Key 时关闭 Alpha。保留大字库、屏幕操作说明、FPS、渲染时间及 DDR burst 统计。

上一版综合场景备份：`../releases/menu_combined_20261006`。

## 构建

- `python tools/build.py firmware`：通过，启用 `-Wall -Wextra -Werror`。
- 固件 text = 9600 B，data = 8 B，bss = 64 B；程序/数据共 9672 B，位于 16 KiB 片内 RAM，链接脚本另保留至少 1 KiB 栈。
- `python tools/build.py compile`：map、interface、pnr、pgm 全部 PASS。pgm 指生成 bitstream，没有向开发板下载。
- 时序：100 MHz core 的 setup slack 为 +1.990 ns；400 MHz DDR 为 +0.266 ns；约 25.209 MHz HDMI 像素时钟为 +35.173 ns。报告列出的 setup / hold 裕量均为正。
- `../outflow/first_light.bit`：2,113,704 字节。
- SHA-256：`22AC414D5A2E57EE97B8C259B343C7646B4DD8B685B20EC3C7910FA2A96A278E`。

## 联合仿真

`python tools/build.py sim-soc`：通过，日志输出 `SOC TEST PASSED`，Errors = 0、Warnings = 0。80 张提交页面全部完成逐像素核对，其中 22 张菜单、8 帧 CPU 场景、50 帧 FPGA 场景。HDMI 共扫描 119 个完整帧（A 页 63、B 页 56），无像素不一致、前台页写入、扫描下溢或读错误。

覆盖范围：两级菜单、循环选择和逐级返回；8 个独立功能；各页 KEY0 操作；5 档 Alpha；Color Key 开关；碰撞/分离/重置；块拷贝与 Alpha 的 CPU 对照；64/128/256 Sprite 的 FPGA 图像和统计；64 Sprite 的 CPU 统计；手动及自动 CPU/HW 切换。图片仅启动上传一次，共 2048 字节，之后跨帧保持不变。

验证使用真实 Sapphire 核、固件、DDR AXI 模型和 640×480 HDMI 扫描时序，检查每次提交的整帧像素、最终扫描像素、按钮导航、各功能的渲染命令和 UART 测量数据。仅缩短按键消抖时间，不更改 CPU 或像素时钟。

已收到并核对的性能页第一组 UART 记录如下。数值包含新场景和 HUD 的实际开销，不应与上一版综合场景混为同一测试。

| 路径 | Sprite 数 | FPS | 渲染时间 μs/帧 | 4 帧 DDR_AR | 4 帧 DDR_AW |
|---|---:|---:|---:|---:|---:|
| CPU | 64 | 10 | 87707 | 0 | 0 |
| FPGA | 64 | 60 | 8494 | 20584 | 71272 |
| FPGA | 128 | 60 | 11643 | 41230 | 83726 |
| FPGA | 256 | 30 | 17749 | 82336 | 108448 |

屏幕 R/W 为上表 burst 总数除以 4 后取整。CPU 的 0 表示未调用硬件渲染引擎，不表示 CPU 或整个 DDR 控制器没有流量。本次不报告未测量的 CPU 128/256 性能。

预览：[分类菜单](individual_menu.png)、[基础子菜单](individual_basic_menu.png)、[高阶子菜单](individual_advanced_menu.png)、[填充](individual_fill.png)、[拷贝](individual_copy.png)、[双缓冲](individual_buffer.png)、[HDMI](individual_video.png)、[Color Key](individual_key.png)、[Alpha](individual_alpha.png)、[碰撞](individual_collision.png)、[64 Sprite CPU/HW 对比](individual_bench_64.png)、[128 Sprite](individual_bench_128.png)、[256 Sprite](individual_bench_256.png)。以上为仿真扫描输出，不是实板照片。

## 实板验收

尚未下载开发板。本文件中的模拟性能不能作为实板测量值。请使用本次 bitstream，按 [操作说明](../MENU_DEMO.md) 逐页验收。若画面仍是旧综合演示，核对下载路径及上述 SHA-256；若按键无响应，观察 `button_input.pending` 和 `button_ack[0]`；若无 HDMI 画面，检查 DDR `cal_done`、HDMI PLL `hdmi_tx_locked` 以及 UART 的 FAIL / TRAP 输出。
