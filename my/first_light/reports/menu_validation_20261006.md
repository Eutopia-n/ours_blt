# 菜单版验证记录（2026-10-06）

固件、按键专项仿真、真实 Sapphire 联合仿真及 FPGA 编译通过。未执行开发板下载，以下性能值均为仿真数据。

## 已通过

- 固件：text 6984 B、data 8 B、bss 52 B，共 7044 B；片内 RAM 16 KiB，链接脚本保留至少 1024 B 栈。
- `simulation_buttons.log`：ALL BUTTON TESTS PASSED；同时覆盖原有重复模式和本次 ENABLE_REPEAT=0 的按住不重复模式。
- `simulation_soc.log`：SOC TEST PASSED，Errors: 0、Warnings: 0；实际 CPU 执行当前固件，未用仿真专用固件替换。
- 7 个 CPU 场景帧、19 个 HW 场景帧，另有 4 个菜单页；每次提交均比较完整 307200 个 RGB565 像素，包括静态字形、数字、合成样例和随机运动区域。
- 29 次完成换页；扫描完成 A 页 38 帧、B 页 42 帧（包括重复显示），无前台写入、扫描不一致、欠载或读错误。最后一张返回菜单页已完成提交和像素校验。
- 基础 CPU/HW、64 档高阶 CPU/HW、128/256 档高阶 HW、256 档回切 CPU均通过；64 档 CPU 与三档 HW 的 UART 四帧统计均与模型吻合。
- 10 次板载按键事件，覆盖进入基础页、手动切换、返回菜单、选择高阶、负载切换、开启自动比较以及回切后的返回操作。
- 图片资源仅启动上传一次，共 2048 B，所有清屏/换页之后保持不变。
- `compile.log`：map/interface/pnr/pgm 均 PASS。XLR 20073/60800，RAM 98/256，DSP 18/160。
- 时序：核心 100 MHz setup +1.990 ns；全部已约束时钟最小 setup +0.254 ns，最小 hold +0.026 ns。

## UART 原始统计

以下是高阶场景。DDR_AR/AW 为四帧渲染引擎 burst 总数，屏幕显示除以 4 后的每帧均值。CPU 的 0 不代表 CPU 没有 DDR 流量。固定对比样例和背景也计入渲染负载；HUD 不计入 RENDER_US，但包含在呈现 FPS 中。

| 路径 | 移动 Sprite 数 | FPS | RENDER_US / 帧 | DDR_AR / 4 帧 | DDR_AW / 4 帧 | HIT 累计 |
|---|---:|---:|---:|---:|---:|---:|
| CPU | 64 | 10 | 89462 | 0 | 0 | 8 |
| HW | 64 | 60 | 8697 | 21872 | 71512 | 19 |
| HW | 128 | 60 | 11893 | 42518 | 83966 | 36 |
| HW | 256 | 30 | 18089 | 83624 | 108688 | 81 |
| HW | 256 | 30 | 18083 | 83630 | 108694 | 109 |

256 档约 18.1 ms 的场景渲染超过一个约 16.66 ms 的刷新周期，换页等待使呈现 FPS 约为 30。此结果包含本版对比样例，不应直接与旧版无 HUD 的负载数据比较。128/256 档 CPU 未完成四帧计时采样，表中不补造结果。

## 下载产物与预览

- bitstream：`../outflow/first_light.bit`，2107344 B。
- SHA256：`8A468499BC9016E70DC38C4172E5ABED8A16BAF927D6241D7DE6C6053015B23A`。
- 本次运行的原始扫描图：`motion_1.png` 至 `motion_29.png`，有效清单见 `preview_soc.log`。
- 菜单：`menu_screen.png`（motion_1）；CPU/HW 对比：`advanced_compare.png`（motion_15）；256 档：`advanced_256.png`（motion_28）。以上均为实际仿真扫描输出，不是上板照片。
- 操作和计时口径：`../MENU_DEMO.md`。
