# 初级 / 高级功能菜单

本工程把 32×32 RGB565 随机运动、混合显示的 Fill/Copy 演示和
`Basic-functions-and-irregular-sprite-sheets` 分支的 77 帧不规则 Sprite、
颜色键控演示放入同一个 DDR 应用、同一个 FPGA 配置文件。上电配置 FPGA 后，
仍需通过 UART 上传 `software/build/animation.bin` 和 `assets/sprite77.upload`；
上传完成才显示一级菜单。旧的 `releases/sprite77_20260927/` 是历史发布包，
其中的 bitstream 和应用程序不含本菜单。

## 操作

- KEY0（C4 / GPIOL_07）：在一级菜单选左侧“BASIC”。
- KEY1（P14 / GPIOR_22）：在一级菜单选右侧“ADVANCED”。进入高级演示后，继续用于切换颜色键控。
- KEY2（N14 / GPIOR_21）：确认当前方形按钮，进入相应展示。
- KEY3（A3 / GPIOL_03）：从任一展示返回一级菜单；在一级菜单按下无操作。
- BASIC 内 KEY0 切换 CPU/FPGA 渲染，KEY1 按 32 → 128 → 256 → 512 → 32 循环切换数量。
  KEY2 无操作；同时按 KEY0/KEY1 时分别切换模式和数量。按键在当前帧绘制完后处理。

初级展示默认从 32 档开始，一半为随机颜色的 32×32 实心方块，一半为
32×32 白边棋盘格图像块，两类对象共用活动区域。总数为 N 时，CPU 基线逐像素填充/拷贝；硬件模式每帧提交
N/2+1 次 Fill（包括全屏背景）和 N/2 次普通 Copy（读取独立 DDR 图像资源）。
每帧执行全部操作后才换页，方块重叠也不跳过绘制。例如 512 档每帧执行 257 次 Fill 和 256 次 Copy。
棋盘格中的品红色在基础展示中保留，不使用颜色键控。
所有档位均允许重叠，绘制顺序为 Fill[0]、Copy[0]、Fill[1]、Copy[1]……，后绘制者覆盖前者。
两类方块均在 X=12..627、Y=160..423 的活动区域运动，避开 HUD 和操作提示。
随机初始化每个方块的位置、两个轴的方向和速度；各轴速度为 24..96 像素/秒。
每个渲染帧按 CLINT 实际经过时间更新位置，碰到边界后镜像反弹。
Q8 坐标和保留余数的 1/256 秒时间步确保不同帧率下，相同累计时间得到相同位置；
低帧率或长间隔内发生多次反弹时仍在边界内，无需浮点运算。
随机数由进入 BASIC 时的计时器值作为种子生成，属于伪随机。
基础展示由 KEY0 手动切换 CPU/HW，UART `c`/`h` 也可指定模式，切换均保留运动轨迹、数量和统计。
从菜单重新进入 BASIC 时从 32 档、CPU 模式开始，重新随机初始化并清空两边旧统计。
KEY1 换档时重新生成布局、清空统计，并保留当前 CPU/HW 模式。
性能对比使用相同对象、数量、资源、尺寸和绘制顺序，各窗口的实际坐标随时间变化。
高级展示沿用 77 帧不规则 Sprite 与颜色键控的 CPU/HW 对比。
高级展示继续每 4 秒自动交替 CPU/HW 路径，UART `c`/`h` 可提前切换。
菜单文字使用现有像素字体，初版采用英文 `BASIC` / `ADVANCED` 标签。

四路按键均为低电平有效，先在 100 MHz `user_clk` 域双触发器同步、
15 ms 消抖，再以翻转位送入 Sapphire GPIO 输入位 `[3:0]`。
CPU 对上次 GPIO 值做异或，只把变化解释为一次按下事件。
图像写入后台 framebuffer，视频在帧边界换页；未改变 DDR IP、PLL、HDMI 编码器或 SDC。

板卡 PDF 的“八、用户 IO”给出四个 KEY 引脚。原厂
`08_ti60f225_soc_demo/09_Ti60F225_co_debug_demo/rtl/ddr3_example_top.v`
顶层为 `ddr3_example_top`，输入包含 100 MHz `core_clk`、DDR 时钟、
PLL 锁定信号，输出为 DDR 总线，`sys_rst` 由两个 PLL 锁定信号组成。
原厂 `03_hdmi_tx_demo/hdmi_tx_demo_v2/rtl/hdmi_src/dvi_tx/dvi_encoder.v`
以 `pixelclk`、`rstin`、RGB、HS/VS/DE 为输入，输出 TMDS 数据。
当前组合顶层 `competition_top` 把 KEY 输入接入 `user_clk` 域；
CPU 与渲染器共用 DDR，原有 AXI 握手和写 FIFO 反压路径保持不变。

77 帧素材占用 `0x01200000` 开始的资源区。初级展示在该资源区尾部
`0x012F0000` 初始化自己的 2048 字节 Sprite，并在启动时校验两个资源不重叠。
DDR 应用从 `0x01400000` 运行，片内 4 KiB 引导程序不变。

## 构建与验证

在 `my/first_light` 目录运行：

```powershell
python tools/build.py firmware --efinity C:/Efinity/efinity-riscv-ide-2026.1
python tools/build.py sim-menu-keys --modelsim D:/modelsim/win64
python tools/build.py sim-menu-soc --modelsim D:/modelsim/win64
python tools/build.py sim-basic-soc --modelsim D:/modelsim/win64
python tools/build.py sim-stress-soc --modelsim D:/modelsim/win64
python tools/build.py sim-moving-soc --modelsim D:/modelsim/win64
python tools/build.py sim-perf-soc --modelsim D:/modelsim/win64
python tools/build.py sim-controls-soc --modelsim D:/modelsim/win64
python tools/build.py sim-soc --modelsim D:/modelsim/win64
python tools/build.py compile --efinity C:/Efinity/2026.1
python tools/test_sprite77_upload.py
```

实际工具目录可用 `--efinity`、`--modelsim` 替换。构建输出为
`outflow/first_light.bit`、`software/build/animation.bin`、片内 RAM 初始化文件。
上板时先配置当前 `outflow/first_light.bit`，再运行
`python tools/upload_sprite77.py --list-ports` 查询端口，接着用
`python tools/upload_sprite77.py --port COMx` 上传当前应用与素材。
`COMx` 需替换为本机实际串口号。

## 本次验证（2026-09-29）

- RISC-V 固件以 `-Wall -Wextra -Werror` 编译通过；DDR 应用为 5888 字节，片内引导固件仍在 4 KiB 限额内。
- `sim-menu-keys` 通过短脉冲、长按、四键独立事件和复位检查。
- `sim-menu-soc` 在真实 Sapphire 模型中通过默认 BASIC、进入初级、KEY3 返回、右选 ADVANCED、进入高级首帧的检查。
- `sim-soc` 通过 77 帧循环、KEY1 两态、CPU/HW/CPU 切换、12 次换页和 26 帧完整扫描；ModelSim 0 错误、0 警告。
- Efinity `compile` 的 map、interface、pnr、pgm 均通过；pinout 为 C4/P14/N14/A3。最小 setup slack 为 +0.195 ns，最小 hold slack 为 +0.026 ns。

上述是编译与仿真结果；菜单整合版尚未在开发板上按键验收。

## 随机基础展示更新（2026-10-01）

源代码：`software/basic_layout.h` 生成随机布局与棋盘格资源，
`software/main.c` 调用原有 Fill/Copy 驱动并保持一组 CPU/HW 对比期间的布局。
本次为 DDR 应用更新，片内 UART 引导二进制重新编译前后 SHA256 相同：
`ca7cdf126179badc79754e1339d673b18f72c010139bfea0fb13ca2b0ebff674`。
发布包复用 `releases/menu_20260929/first_light.bit`，其 SHA256 为
`7936b9a0d9d62e0a7bb5ecb4012d486c90c3ef409e7aac4ea7c51b5772eb3ea2`。
本次没有重新综合 FPGA。当前 `outflow/` 可能包含用户另一次构建，不作为本次打包输入。

布局边界与随机性检查（本机 MinGW GCC）：

```powershell
gcc -std=c11 -O2 -Wall -Wextra -Werror tools/test_basic_layout.c -o software/build/test_basic_layout.exe
.\software\build\test_basic_layout.exe
```

`sim-basic-soc` 运行实际 Sapphire 核和真实应用二进制，通过 UART `h` 加速切换到硬件，
检查两组随机布局的完整绘制区域、每组 CPU/HW 逐像素一致、硬件命令类型/数量/源地址、
双缓冲扫描、返回菜单、重新进入 BASIC 以及进入高级首帧。自动 4 秒切换沿用应用计时逻辑，
该快速仿真不等待完整 8 秒实时时段。

本次验证结果：

- 新 DDR 应用编译通过（`-Wall -Wextra -Werror`），二进制 6500 字节，BSS 412 字节。
- `test_basic_layout` 通过 10000 个种子的复现性、新布局、边界、不重叠、奇偶 X 和边缘偏移检查。
- `sim-basic-soc` 通过：两组 CPU/HW 图像逐像素一致，两组之间变化 55072 个像素；
  两帧硬件合计 34 次 Fill / 32 次普通 Copy，复制源为专用 32×32 DDR 资源。
  菜单返回、重新进入 BASIC、进入高级首帧、扫描像素及前后台页写入检查均通过。
  ModelSim 日志 `reports/simulation_basic_soc.log`：0 错误、0 警告。
- `tools/test_sprite77_upload.py` 的 4 项测试通过。
- 仿真扫描预览 `reports/basic_random_1.png`～`basic_random_4.png` 已输出，第二张已做视觉检查。
- 本次为软件更新，实板效果、4 秒自动切换及帧率仍需上板确认。

上述固定 32 块版本已归档在 `releases/menu_random_20261001/`。

## 可调负载与吞吐量更新（2026-10-01）

2026-10-01 的上板包为 `releases/menu_stress_20261001/`（历史静态布局版）。
使用包内 `.bit` 与上传脚本，按该包 README 操作；旧包保留供回退。FPGA 配置仍复用
`releases/menu_20260929/first_light.bit`，本次仅更新 DDR 软件，未重新综合 FPGA。

`software/basic_layout.h` 保存最多每侧 512 个绘制描述符，支持五档数量和按键端点处理；
`software/basic_metrics.h` 统计已完成帧的性能，使用 64 位中间值避免高负载乘法溢出。
应用链接 libgcc 以支持 RV32 上的 64 位整数除法，仍由原有 64 KiB DDR 应用区运行。

屏幕统计口径：

- BLOCKS=N、FILL=N/2、COPY=N/2，清屏另计；计入被后续方块覆盖的已执行操作。
- FPS=完成帧数/实际用时，保留一位小数；OPS/S=N×完成帧数/实际用时，直接计算，不使用取整后的 FPS 相乘。
- 实际用时包含渲染、HUD、统计开销及等待显示换页；US 是场景渲染耗时，包含清屏和全部方块，排除 HUD 和换页等待。
- CPU/HW 为同一负载、同一布局的两侧平均 US 之比。缺少任一侧数据时显示 -。
- 每个完成帧更新，最多 4 帧或约 1 秒为一组，低帧率也能显示统计。
  切换负载或自动生成新布局时清空两边统计；手动 c/h 保留当前布局的统计。

`sim-stress-soc` 使用真实应用二进制、Sapphire 模型和渲染 RTL，按 KEY0/KEY1 从 32 逐档升至 1024、
检查端点、在 1024 档切换 CPU/HW、再降至 512 并返回菜单进入高级展示。
每帧根据 DDR 中的全部描述符独立生成参考图，检查重叠顺序、像素、硬件命令数量/源地址、
HUD 数量、统计清零、耗时比、双缓冲扫描和前台页写保护。
该专项仿真使用一帧真实素材由 77 个描述符共享，以缩短无关的启动 CRC 校验；
发布包仍包含完整原始 77 帧素材。专项仿真不覆盖完整动画序列或实板性能。
本次验证结果：

- 固件编译通过：DDR 应用二进制 9820 字节，BSS 12408 字节，满足 64 KiB 区域及预留栈约束。
  片内引导二进制 SHA256 仍为 `ca7cdf126179badc79754e1339d673b18f72c010139bfea0fb13ca2b0ebff674`。
- 主机检查通过 10000 组布局（每档 2000 个种子），覆盖边界、复现、新布局、奇偶 X、
  最低档不重叠、按键端点与同时按键抵消；统计检查覆盖准确 OPS/S、低于 1 FPS、
  64 位中间计算、耗时比以及换档清零。
- `sim-stress-soc` 通过 9 个基础帧与菜单/高级入口：32、128、256、512、1024 档，
  最大档 CPU/HW 逐像素一致，两帧硬件合计 1026 次 Fill（包含两次清屏）和 1024 次 Copy。
  确认最低/最高档不循环、最高档不重置布局或统计、降档回到 CPU 并清空统计；
  屏幕 BLOCKS/FILL/COPY 和 CPU/HW 比值均与实际数据吻合。
  日志 `reports/simulation_stress_soc.log`：0 错误、0 警告。
- `tools/test_sprite77_upload.py` 的 4 项测试通过。
- `reports/basic_stress_2.png` 和 `reports/basic_stress_8.png` 为实际仿真扫描画面，已检查布局。
  图中 FPS、US、OPS/S 和耗时比属于仿真结果，不代表实板性能。
- 本次没有重新运行完整 77 帧回归或等待 4 秒自动切换；沿用既有自动切换流程，
  上板时仍需确认实际帧率、按键响应和自动轮换。

顶层按键与 SoC GPIO 连线由 `tools/prepare.py` 重建；直接修改
`rtl/competition_top.v` 或 `first_light.peri.xml` 后再次运行 prepare 会被覆盖。

## 随机移动与混合区域更新（2026-10-02）

该次随机移动上板包归档在 `releases/menu_moving_20261002/`。
应用新增运动状态；每帧先更新位置，再清屏并绘制所有 Fill/Copy，后台页绘制后换页。
CPU/HW 切换和档位端点操作均保持位置、方向、速度及时间余数。
换档及重新进入 BASIC 才生成新的一组对象；不再定时重新随机位置。
US 只统计清屏、方块绘制和 DDR 发布，排除运动计算、HUD 及显示等待；
FPS、OPS/S 的实际用时包含运动计算等软件开销。
本版只更新 DDR 应用，复用菜单版 bitstream 和原有 UART 协议。

验证：

- RISC-V 编译通过，应用二进制 11424 字节、BSS 24696 字节，满足 64 KiB 与预留栈约束。
- 主机检查通过 10000 组初始化，覆盖五档、两类对象跨越左右区域、四种轴向组合、
  随机速度范围、活动区域边界、零时间步、墙角反弹、多次反弹，以及 4 FPS/60 FPS
  在相同累计时间的轨迹一致性；保留按键端点、吞吐量及统计重置检查。
- `sim-moving-soc` 通过 9 个基础帧、菜单返回/右选以及高级入口，五档均逐像素比对。
  32 档连续两帧变化 15456 个像素；1024 档 CPU→HW 及最高档端点操作保留速度、
  展开坐标和时间余数，按实际经过时间持续移动，所有帧均避开 HUD/底部提示。
  两帧硬件共执行 1026 次 Fill（含清屏）和 1024 次 Copy；数量、统计清零与耗时比检查通过。
  参考图按 Fill/Copy 交替顺序生成，覆盖两类对象之间的重叠。
  日志 `reports/simulation_moving_soc.log`：0 错误、0 警告，耗时 35 分 11 秒。
- `tools/test_sprite77_upload.py` 的 9 项测试通过，发布包沿用已修复的串口重连上传器。
- `reports/basic_moving_2.png`、`reports/basic_moving_8.png` 是实际扫描截图，已检查混合布局。
  图中的性能属于仿真结果；本轮使用一帧真实素材共享 77 个描述符加速启动验证，
  发布包仍使用完整 77 帧。没有重跑完整动画序列或等待 4 秒自动切换；实板运动、
  自动切换和实际性能仍需验收。

此前各日期的验证记录属于当时版本。当前版本的混合区域不再保证最低档对象互不重叠。

## 基础功能性能优化（2026-10-02）

该轮性能包归档在 `releases/menu_perf_20261002/`。
按用户要求取消 1024 档，只保留 32、128、256、512；按 KEY1 到 512 后继续按仍保持 512。
每类对象存储上限由 512 缩减为 256，最高档的 256 次 Fill 和 256 次 Copy 都真实执行。
仅更新 DDR 应用，仍复用已验证的 `releases/menu_20260929/first_light.bit`；
无需重新综合 FPGA。保留所有档位的 32×32 尺寸、随机运动、碰边反弹和混合区域，
每帧实际执行全部 Fill/Copy，清屏和双缓冲换页也保留。

主要修改：

- BASIC 清屏后一次设置方块的固定宽高、行距和拷贝源，复用当前绘制页。
  每个 Fill 由 8 次寄存器写入减至 4 次，每个普通 Copy 由 9 次减至 3 次（均包含 START）。
  START 前后仍执行 MMIO fence，随后等待真实 DONE；通用矩形和高级精灵驱动保留完整参数校验。
- 运动展开坐标未跨完整周期时跳过取模；长时间间隔仍走原有取模，轨迹与速度保持一致。
- BASIC HUD 在已清屏的背景上使用对齐的 32 位成对像素写入，保留原有字体和内容。
  菜单按钮和高级展示继续使用通用文字绘制。
- BASIC 串口统计改为分帧填入 TX FIFO，渲染不等待整行串口发送。
  FIFO 未腾出空间时可合并统计消息，屏幕统计仍按已完成帧更新；返回菜单前发完待发送消息。
- BASIC 不再计算仅供高级动画使用的姿势插值。

性能验证入口 `sim-perf-soc` 使用实际应用二进制、真实 Sapphire 模型及现有渲染 RTL。
通过 GPIO/UART 加速切换档位及 CPU/HW，检查 31 个基础帧、最低/最高档端点、
从 512 降至 256 后统计清零、返回菜单、右选和高级首帧。
四档各执行 6 帧硬件渲染，512 档再执行一次最高档 KEY1 端点操作，
以连续显示换页确认间隔计算 FPS，并要求每个稳态间隔不超过 16.667 ms；
CPU→HW 首帧不计入稳态样本。每帧独立检查全部绘制像素、随机运动状态、
硬件命令数、Copy 源地址、HUD 数量/耗时比、前台页写保护及扫描输出。
专项仿真素材仍为一帧真实图像共享 77 个描述符，发布包包含完整 77 帧。

本轮验证结果：

- 固件以 `-Wall -Wextra -Werror` 编译通过，DDR 应用二进制 11928 字节，BSS 12520 字节。
  片内引导 SHA256 保持 `ca7cdf126179badc79754e1339d673b18f72c010139bfea0fb13ca2b0ebff674`。
- 主机测试通过 8000 组初始化（四档各 2000 个种子），保留混合区域、边界、
  四种轴向组合、速度范围、零时间步、墙角/多次反弹、4 FPS/60 FPS 轨迹一致性、
  按键端点和统计检查；档位越界查询也限制在最大 512。
- `sim-perf-soc` 通过 31 个基础帧、35 次换页请求及菜单/高级入口。
  硬件共执行 3065 次 Fill（含 25 次清屏）和 3040 次 Copy；所有基础帧逐像素一致，
  连续运动、最高档端点保留统计、降档清空统计、扫描输出及前台页写保护均通过。
  ModelSim 0 错误、0 警告，耗时 28 分 28 秒。
- 四档稳态 FPS 均为 60.019，最大换页间隔均为 16661 微秒。
  32、128、256 各采到 5 个稳态间隔，512 采到 6 个。
  512 档硬件忙碌 14380～14568 微秒，首条命令至可换页 15848～16132 微秒。
  对比优化 HUD 前的 512 档 30.009 FPS，当前软件已使本轮采样赶上每次显示换页。
- 日志为 `reports/simulation_perf_soc.log` 和 `reports/soc_perf_20261002.log`（原进度日志已归档）。
  四档实际扫描预览为 `reports/basic_perf_8.png`、`basic_perf_15.png`、
  `basic_perf_22.png`、`basic_perf_30.png`，均已检查。
- 发布包应用与仿真执行的二进制一致，上传包 CRC/RLE 校验通过；
  上传器沿用此前通过 9 项重连/错误恢复检查的版本。

上述帧率属于当前 SoC 仿真的短时采样，每档一组随机布局，DDR 使用周期性背压模型。
512 档的软件和搬运余量较小，不能据此保证实板所有随机布局长期稳定 60 FPS。
本轮未重跑完整 77 帧动画或等待 4 秒自动切换；这些沿用现有流程，实板仍需验收。

### 取消 1024 档的背景

60 FPS 要求一帧在约 16.7 ms 内完成。此前五档软件优化的完整系统仿真中，
1024 档仅硬件引擎 BUSY 的累计时间就为 25.28～25.54 ms，已经超过一帧预算；
减少 HUD、运动和寄存器开销无法消除这段真实搬运时间。

用户随后选择取消该档。当前程序和测试以 512 为最高档；历史五档包保留供回退。
本轮帧率来自实际换页确认间隔，方块尺寸和被遮挡操作的执行保持原有要求。

### 该性能包的实板复测

用户随后反馈 512 档为 HW FPS=30、HW US=18323。上传日志显示
`menu_perf_20261002`、406341 字节、ASSET READY → ASSET OK，确认新应用已成功装载。
18.323 ms 场景耗时已经超过 60 FPS 的约 16.667 ms 预算，且还未包括运动、HUD 和换页等待。
错过一次显示帧边界后等待下一次，符合约 33.3 ms 更新一帧、约 30 FPS 的结果。
此前短时仿真使用简化 DDR 响应模型，不能作为 512 档实板达到 60 FPS 的证明。

## KEY1 数量循环 / KEY0 模式切换（2026-10-02）

最新上板包为 `releases/menu_controls_20261002/`，运行 `python tools/package_menu.py` 生成。
本次仅更新 DDR 应用与屏幕操作提示，复用已验证的菜单 bitstream 和原有 UART 引导。

- KEY1：32 → 128 → 256 → 512 → 32 循环；换档重新生成布局、清空统计，保留当前模式。
- KEY0：CPU ↔ FPGA 手动切换；数量、位置、方向、速度、时间余数及两侧统计均保留。
- 基础展示取消每 4 秒自动轮换。UART `c`/`h` 仍可切换模式；同帧遇到 KEY0 时以按键切换为准。
- KEY0/KEY1 同时按下时各执行一次。KEY3 返回菜单的优先级保持最高。
- 菜单继续 KEY0 左、KEY1 右、KEY2 确认、KEY3 回退；高级展示继续 KEY1 控制颜色键控。
- 新启动标识为 `Ti60 MENU CONTROLS 20261002`，屏幕提示为 `KEY0 CPU/HW KEY1 NEXT KEY3 BACK`。

四档数量、32×32 尺寸、全部 Fill/Copy 执行、共享活动区域、随机运动和碰边反弹保留。
本次验证聚焦按键行为；512 档实板 60 FPS 的性能目标仍需后续优化，不能用此前仿真结果替代。

本轮验证：

- 固件以 `-Wall -Wextra -Werror` 编译通过，应用二进制为 12000 字节，BSS 为 12520 字节。
  片内引导二进制 SHA256 保持 `ca7cdf126179badc79754e1339d673b18f72c010139bfea0fb13ca2b0ebff674`。
- 主机检查通过 8000 组随机运动布局，四档循环、512→32、KEY0 两向切换、
  KEY0 不改变数量、KEY1 不改变模式、同时按键及既有运动/边界/统计检查通过。
- `sim-controls-soc` 使用实际 Sapphire 核、真实应用二进制及渲染 RTL，
  通过 10 个基础帧和 14 次换页请求。KEY1 从 32 FPGA 逐档升到 512 FPGA，再回 32 FPGA；
  KEY0 两向切换保留轨迹和统计，同时按键进入 128 FPGA；UART c/h、菜单返回、右选和高级首帧通过。
  硬件共执行 615 次 Fill（含 7 次清屏）和 608 次 Copy，像素、运动、HUD 统计和扫描检查均通过。
  ModelSim 0 错误、0 警告，耗时 15 分 41 秒。
- 日志为 `reports/simulation_controls_soc.log`，实际扫描截图为
  `reports/basic_controls_2.png`（32 FPGA）和 `reports/basic_controls_5.png`（512 FPGA）。
- 本专项使用一帧真实素材共享 77 个描述符加快启动，发布包仍包含完整 77 帧。
  没有重跑完整动画序列或等待高级模式的完整 4 秒自动轮换，实板新按键操作待确认。
