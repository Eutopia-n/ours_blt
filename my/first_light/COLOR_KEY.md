# RGB565 颜色键控拷贝：实现、运行时开关与验证

## 一次下载后的现场演示

当前待上板版本为 [`releases/color_key_key1_20260926/first_light.bit`](releases/color_key_key1_20260926/first_light.bit)。按一次开发板 KEY1 即翻转去背状态；屏幕左侧显示 `KEY ON`/`KEY OFF`，默认开启，再按一次恢复。串口小写 `c`/`h` 仍可强制选择 CPU/硬件绘制，原有每 4 秒自动切换 CPU/HW 的行为也保留。本版不再用串口 `k`/`o` 控制去背。

两种去背状态使用同一份启动时上传的 2048 字节 Sprite 和相同运动场景。`KEY ON` 时 CPU 跳过品红像素，硬件使用 `OPERATION=2`；`KEY OFF` 时 CPU 写入所有像素，硬件使用 `OPERATION=1`。有效按下经固件下一次轮询后生效，画面在帧边界换页后出现，无需重新配置 FPGA。去背关闭时品红外围形成 32×32 方形，开启时外沿露出深灰背景。这样同一 bitstream 就能展示功能开关及 CPU/HW 一致性。

板卡说明第 33 页给出 KEY1=`GPIOR_22`、封装 P14、BR Bank 3.3 V；官方按键示例按低电平识别按下。`key_toggle.v` 在 100 MHz 用户时钟域用两级寄存器同步 KEY1，按下和释放各持续 15 ms 才确认状态变化；只在有效按下时翻转一个保持位。该位送入 Sapphire GPIO 输入 bit0，固件每帧轮询其变化，因此短按即使发生在绘制期间也不会丢失，长按不会反复切换。显示、DDR 和换页时钟链路保持原样。首次加载当前版本 bitstream 需要一次 JTAG 配置；实板上仍须确认全透明 `WSTRB=0` 在官方 DDR 控制器上的效果。

## KEY1 版本的工具验证

- 固件编译通过：`text=3472`、`data=8`、`bss=24`，镜像 3480 字节，低于 3584 字节上限。
- KEY1 独立仿真 `KEY TOGGLE TEST PASSED`，覆盖短脉冲、按下抖动、长按、释放后再次按下、不完整释放与复位。
- 真实 Sapphire 联合仿真 `SOC TEST PASSED`：KEY1 通过 GPIO 让 CPU/HW 各自完成去背开/关/开切换；9 次换页，A/B 各 6 个完整扫描帧，提交画面与扫描均逐像素检查。硬件 `KEY OFF` 执行 32 次普通 Copy，`KEY ON` 执行 96 次键控 Copy，DDR 资源区始终保持 2048 字节不变。
- Efinity 2026.1 `map/interface/pnr/pgm` 均 PASS；管脚报告确认 `key1_n` 为 P14 / `GPIOR_22`、3.3 V 输入。核心 100 MHz setup slack `+2.127 ns`，全报告最小 setup `+0.339 ns`、hold `+0.026 ns`。启动脚本虽打印 Conda `ModuleNotFoundError`，完整编译仍以退出码 0 结束。

仿真画面：[硬件去背开启](reports/motion_5.png)、[硬件去背关闭](reports/motion_6.png)。文件与报告冻结在 [`releases/color_key_key1_20260926/`](releases/color_key_key1_20260926/)；这些画面不是实板照片。

## 历史串口可切换版本的验证记录

- 固件编译成功：`text=3464`、`data=8`、`bss=24`，片内初始化镜像 3472 字节，低于 3584 字节上限。
- 真实 Sapphire 联合仿真 `SOC TEST PASSED`：9 次换页、CPU 5 帧、硬件 4 帧；CPU 和硬件均完成去背开/关/开切换，提交画面按独立模型逐像素检查；A/B 两页各完成 6 个扫描帧，无扫描差异。
- 硬件关闭去背时执行 32 次普通 Copy；开启时执行 96 次键控 Copy。32→128 位桥传递 5376 个全零和 5136 个部分键控写掩码 beat；2048 字节图片仅上传一次且始终不变。
- 联合仿真串口测得 CPU 29 FPS / 28491 μs、HW 60 FPS / 4370 μs。这些是仿真回归数据，不是实板性能。
- Efinity 2026.1 `map/interface/pnr/pgm` 均 PASS；核心 100 MHz setup slack `+1.888 ns`，全报告最小 setup `+0.143 ns`、hold `+0.026 ns`。本机 Efinity 启动脚本仍打印 Conda `ModuleNotFoundError`，但四阶段完成且命令退出码为 0。

联合仿真实际扫描输出：[硬件去背开启](reports/motion_5.png)、[硬件去背关闭](reports/motion_6.png)；CPU 对应画面见 [开启](reports/motion_1.png)、[关闭](reports/motion_2.png)。这些是仿真截图，不是上板照片。固件、bitstream、日志和画面已另存于 [`releases/color_key_toggle_20260926/`](releases/color_key_toggle_20260926/)。

## 行为与接口

- `OPERATION` (`0x30`)：`0` 为 Fill，`1` 为普通 Copy，`2` 为键控 Copy；`3` 在 APB 访问时拒绝。
- 键控 Copy 将 `COLOR` (`0x1C`) 的低 16 位作为 RGB565 透明色。命令启动时锁存键色；只有源像素与键色完全相等才保留目标像素。普通 Copy 不受 `COLOR` 影响。
- `SRC`、`SRC_STRIDE`、`DST`、`WIDTH`、`HEIGHT`、`STRIDE`、`DRAW_PAGE` 的地址限制与普通 Copy 相同。资源区或当前绘制页可作源，目标只能位于当前绘制页；同页重叠仍按原方向处理。
- C 接口 `copy_image_keyed(source, source_stride, dst_x, dst_y, width, height, key)` 返回约定与 `copy_image()` 相同。演示使用 `0xF81F` 作为品红键色，CPU/HW 两条路径使用相同的 32×32 菱形资源和同样的透明规则。

## 为什么在写选通处键控

`render_regs` 接收 Sapphire 的 APB 命令；`fill_engine` 在 `user_clk` 约 100 MHz 域拥有 AXI 写地址/数据/响应通道。它先读完一行源 RGB565 像素，经过同步行 RAM 对齐后，向 16 项写 FIFO 送入 `{WLAST,WSTRB,WDATA}`。显示读与拷贝读在 `render_subsystem` 按完整 burst 仲裁，显示端在独立像素时钟域扫描双缓冲页。

键控比较位于行 RAM 输出与写 FIFO 输入之间。一个 32 位 AXI beat 有两个 RGB565 像素，各占两个字节：低半字透明清 `WSTRB[1:0]`，高半字透明清 `WSTRB[3:2]`。该掩码再与矩形首尾边界掩码相与。这样保留原背景而不增加 DDR 背景读取，也不改变 FIFO 容量、burst 长度、读仲裁、跨时钟路径或帧边界换页。全透明 beat 仍发送 `WSTRB=0`，保留 `WLAST` 和最终 B 响应完成语义。

## 2026-09-26 初版固定去背验证记录

以下是本次版本的工具结果，均非实板观测：

| 项目 | 结果 |
|---|---|
| 固件 | `text=3328`、`data=4`、`bss=24`；镜像 3332 字节，低于构建脚本 3584 字节上限 |
| RTL 仿真 | `ALL TESTS PASSED`；8 组键控拷贝覆盖可配置键色、源/目标半字对齐、行距、4 KiB 边界、同页重叠、全透明、无效命令和双缓冲后台页；普通 Copy 能照常复制品红 |
| Sapphire 联合仿真 | `SOC TEST PASSED`；CPU/HW/CPU 共 9 次换页、12 个完整 A/B 扫描帧，逐像素场景一致；32→128 位桥输出 7168 个全零和 6848 个部分键控写掩码 beat |
| 仿真性能 | CPU 29 FPS / 27175 μs；HW 60 FPS / 4366 μs。仅供仿真回归，不能作为实板性能 |
| Efinity 2026.1 | `map/interface/pnr/pgm` 均 PASS；核心时钟 setup slack `+1.888 ns`，全报告最小 setup `+0.143 ns`、hold `+0.026 ns` |

复现命令（从仓库根目录运行）：

```powershell
python my/first_light/tools/build.py firmware --efinity C:/Efinity/efinity-riscv-ide-2026.1
python my/first_light/tools/build.py sim --modelsim D:/modelsim/win64
python my/first_light/tools/build.py sim-soc --modelsim D:/modelsim/win64
python my/first_light/tools/build.py compile --efinity C:/Efinity/2026.1
```

构建输出会覆盖当前工程的报告及片内 RAM 初始化文件。初版固定去背的 bitstream、固件和关键报告冻结在 [`releases/color_key_20260926/`](releases/color_key_20260926/)；历史串口可切换版本另存于 `releases/color_key_toggle_20260926/`。本机启动 Efinity 时曾打印 Conda `ModuleNotFoundError`，但四个 Efinity 阶段随后均报告 PASS，脚本退出码为 0；以完整阶段结果和时序报告判断本次编译状态。

## 实板待验

官方 DDR 控制器的部分 RTL 受保护；SoC 联合仿真验证了写掩码经过 32→128 位桥，仍需在真实 DDR 上确认全零 `WSTRB` beat 会保留背景。用易失性 JTAG 加载本次 bitstream，检查青/黄菱形外缘露出深灰背景、重叠处不擦除已有图形、CPU/HW 模式画面一致且无撕裂；记录两模式 FPS/US、串口有无 `FAIL`/`TRAP`、持续运行现象和照片或视频。未完成这一步前不标记为板级通过。
