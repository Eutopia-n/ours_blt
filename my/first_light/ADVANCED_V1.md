# 高阶 Demo：互动 RGB565 Sprite 合成与测量

**历史阶段记录**：下文的 Alpha=160、玩家移动及组合键操作描述的是 2026-10-01/02 版本。当前固件已升级为菜单演示、Alpha=128、独立对比样例和屏幕 HUD，见 [MENU_DEMO.md](MENU_DEMO.md)。寄存器与 RGB565 合成公式仍适用。

本阶段在既有 DDR 资源区、AXI Burst、写 FIFO 和双缓冲上接入硬件 Alpha/Color Key，并完成 64/128/256 个 Sprite 的互动负载和运行指标输出。2026-10-02 控制输入改为板载按键，UART 保留指标输出；按键版记录见 [BUTTON_CONTROL.md](BUTTON_CONTROL.md)。文末保留 2026-10-01 串口输入版的仿真数据，实板效果和性能须下载后确认。

## 1. 本次范围

- `OPERATION=0`：原有纯色填充。
- `OPERATION=1`：原有图像拷贝，包括同页显存重叠拷贝。
- `OPERATION=2`：新增 Sprite 合成；从独立 DDR 图片资源区读取前景，从所选绘制页读取背景，再写回该绘制页。
- RGB565，单条指令使用一个 8 位全局 Alpha，支持 Alpha、Color Key 分别开启或同时开启。
- 资源源行距独立，支持奇数 X/宽度、源行半字位置交替、16 beat burst、4 KB 边界拆分。

`main.c` 启动时生成并上传一张 32×32 菱形资源，黑色 RGB565 像素作为 Color Key，前景使用全局 Alpha=160。RISC-V 计算场景坐标、处理按键事件和检测玩家碰撞；硬件模式提交 OPERATION=2，让 FPGA 逐 Sprite 完成 Alpha/Color Key。CPU 模式运行逐像素参考算法，用于对比。

初始 Sprite 数为 64，KEY0+KEY1 循环选择 64、128、256；KEY0/1/2/3 分别向上/下/左/右移动玩家，每次 8 像素，KEY2+KEY3 切换 CPU/FPGA。事件在下一帧边界处理，玩家限制在画面范围内。碰撞使用玩家 16×16 区域与其他 Sprite 32×32 矩形的 AABB 重叠判断。

数量包含第 0 个玩家 Sprite，其余为自动移动 Sprite。启动为 CPU 模式，组合键切换后保持该模式，已取消自动切换。`HIT` 是从启动开始累计的重叠检测次数，同一对象连续多帧重叠会多次计数，目前用 UART 展示结果。

每连续 4 帧输出一行指标；切换模式或 Sprite 数量时会清空当前采样窗口，保证同一行统计来自同一负载：

```text
HW FPS <帧率> RENDER_US <平均每帧渲染微秒数> SPRITES <数量> DDR_AR <读 burst 数> DDR_AW <写 burst 数> HIT <累计碰撞数>
```

`DDR_AR/AW` 是该行对应的 4 帧渲染 burst 总数，只统计 FPGA 渲染引擎的 AR/AW 握手，不包含 CPU 像素访问或视频扫描；CPU 模式这两个字段为 0。`RENDER_US` 计量绘制场景的四帧平均值，不含垂直消隐换页等待；`FPS` 则按四次完成换页的总时间计算，排除指标串口输出耗时，因此不能代表包含串口输出的长期实际吞吐率。指标通过 UART 输出，以避免占用 4 KiB 片内 RAM 中的固件空间绘制文字 HUD。串口使用 115200、8N1。

## 2. 为什么这样做

普通 Copy 只读前景、写目标。Alpha 必须同时知道原背景，因此额外增加一组背景行 RAM：

1. AXI 读取一行资源，存入原有前景行缓存。
2. AXI 读取对应目标行，存入新增背景行缓存。
3. 前景按源/目标半字位置对齐；背景保持目标字的位置。
4. 分别计算 R、G、B，连同字节写使能进入 16×37 位写 FIFO。
5. 发送 AXI 写 burst，最后一个 B 响应成功后才报告 DONE。

Alpha 为 0～255，表示不透明度。每个通道使用：

```text
result = (foreground * alpha + background * (255-alpha) + 127) / 255
```

R/B 通道 5 位、G 通道 6 位，独立运算，不能把整个 16 位像素直接乘加。`+127` 用于四舍五入；RTL 用限定范围下等价的加法/移位归一化，避免通用除法器。

Color Key 在混合前比较完整 RGB565 值。命中时，关闭该半字对应的两个 WSTRB 位，背景不被写入。全部透明的 beat 仍参与 AXI burst 握手，WSTRB=0，不改变 AWLEN/WLAST；因此“跳过透明像素写入”不等于本版已经省去所有透明区总线流量。

全局 Alpha 是一张 Sprite 共用透明度，足以实现淡入淡出、半透明弹幕等效果。每像素 Alpha 是可选后续扩展，暂不增加资源格式、DDR 带宽和固件复杂度。

## 3. 新增寄存器与接口

基址仍为 `GFX_BASE`（当前 `0xF8100000`），旧偏移保持不变。

| 偏移 | 名称 | 含义 |
|---|---|---|
| 0x30 | OPERATION | 新增 2=Sprite 合成；0/1 不变，3 非法 |
| 0x50 | BLEND_CTRL | bit0=Alpha，bit1=Color Key；其余位必须为 0；复位 0 |
| 0x54 | ALPHA | 低 8 位有效，复位 255；高位忽略 |
| 0x58 | COLOR_KEY | 低 16 位 RGB565 透明色，复位 0；高位忽略 |
| 0x5C | BURST_READ | 渲染 AR 握手累计数，复位清零；32 位循环计数 |
| 0x60 | BURST_WRITE | 渲染 AW 握手累计数，复位清零；32 位循环计数 |
| 0x70 | DDR_READ_WAIT_CYCLES | 图形引擎读地址/读数据阶段因 AXI 未就绪而等待的 100 MHz 周期累计数 |
| 0x74 | DDR_WRITE_WAIT_CYCLES | 图形引擎写地址/写数据/写响应阶段因 AXI 未就绪而等待的 100 MHz 周期累计数 |

`BLEND_CTRL`：0=不透明合成，1=仅 Alpha，2=仅 Color Key，3=两者同时开启。仅 OPERATION=2 使用这些控制；忙碌时禁止改写寄存器。

新增 C 函数：

```c
int blend_image(uint32_t source, uint32_t source_stride,
                uint32_t dst_x, uint32_t dst_y,
                uint32_t width, uint32_t height,
                uint8_t alpha, uint16_t key, uint32_t flags);
```

作用：检查资源/目标范围，配置合成指令并等待完成；CPU 不逐像素搬运或混合。返回值沿用现有驱动：0 成功，-1 参数错误，-2 忙，-3 硬件错误，-4 超时。

在资源已经上传并执行 `publish_pixels()` 后，可以在 `main.c` 的后台页绘制流程中调用：

```c
if (fill_rect(0, 0, 640, 480, 0x1082)) fail("FAIL fill");
if (blend_image(ASSET_BASE, SPRITE_STRIDE, 100, 120, 32, 32,
                128, 0xf81f, GFX_BLEND_ALPHA | GFX_BLEND_KEY))
    fail("FAIL blend");
if (present_frame()) fail("FAIL present");
```

当前默认资源使用黑色透明边缘和青/红/黄三色内部区域；CPU/HW 对比使用同一个资源、同一个 Alpha/Key 配置，避免把算法差异误计为硬件加速收益。

OPERATION=2 的源只允许落在 `0x01200000～0x012FFFFF`，不接受显存源/重叠合成。目标仍限定在所选绘制页；驱动检查坐标不跨出屏幕。失败的读 burst 会排空后终止，当前行尚未开始写；之前已完成的行不会回滚。写响应失败可能已有部分像素写入，软件应放弃该帧。

## 4. 修改文件与核验

| 文件 | 本次变化 |
|---|---|
| `rtl/fill_engine.v` | 背景行 RAM、背景读状态、RGB565 混合算术、Key 字节屏蔽 |
| `rtl/render_regs.v` | 新增合成控制寄存器，允许 OPERATION=2 |
| `rtl/render_subsystem.v` | 连接合成控制，复用现有 AXI 仲裁 |
| `software/render.h` | 新寄存器、控制位、驱动声明 |
| `software/main.c` | 64/128/256 场景、按键控制、RISC-V AABB 碰撞、CPU/HW 合成与指标 |
| `sim/tb_render.sv` | 独立整数除法参考模型、透明写屏蔽与错误恢复测试 |
| `sim/tb_soc.sv` | 真实 CPU 执行固件，板载按键输入、UART 输出、代表帧像素、碰撞与 burst 统计检查 |

仿真比较整个存储范围，检查源资源、邻接像素和另一页未被破坏。测试覆盖全部 64×64×256=1,048,576 组单通道数值，以及多种 Alpha/控制位/奇偶对齐、独立行距、边界和错误恢复。旧 Fill/Copy、FIFO、显示扫描和双缓冲测试同时保留。

复现命令（仓库根目录 PowerShell）：

```powershell
python my/first_light/tools/build.py firmware
python my/first_light/tools/build.py sim-buttons
python my/first_light/tools/build.py sim
python my/first_light/tools/build.py sim-soc
python my/first_light/tools/build.py compile
```

`sim-soc` 使用实际 Sapphire CPU 模型运行当前固件，覆盖按键移动/模式/数量命令、64/128/256 Sprite、逐像素场景、渲染 burst 指标和 CPU→FPGA→CPU 切换。`compile` 的 pgm PASS 仅表示生成 bitstream，并非下载开发板。

## 5. 当前功能边界与上板操作

本版负载由一张程序生成的菱形资源重复绘制，Sprite 数量可选 64、128、256；不是 256 张不同纹理。板载按键引脚已与原理图、板卡说明书和官方按键示例交叉核对，接入说明见 `BUTTON_CONTROL.md`。

板载按键如下（串口不再接收控制命令）：

| 输入 | 作用 |
|---|---|
| KEY0+KEY1 | 循环选择 64 → 128 → 256 → 64 个 Sprite |
| KEY0 / KEY1 / KEY2 / KEY3 | 上 / 下 / 左 / 右，每次 8 像素 |
| KEY2+KEY3 | 切换 CPU / FPGA 参考渲染路径 |

串口终端使用 115200、8N1，仅接收日志。每次调整数量后等待 4 帧采样；日志中的 AR/AW 是 FPGA 渲染器 burst 数，不是整个 SoC 的总 DDR 事务。FPGA 模式若达不到 60 FPS 属于负载数据，不能将 HDMI 刷新率当作场景帧率。

上板验收步骤：

1. 在 Efinity Programmer 中用 JTAG 加载本工程的 `outflow/first_light.bit`，HDMI 接板上的 TX 接口。
2. 在设备管理器确认本板的串口 COM 号，终端设为 115200、8N1、无流控，确认启动行包含 `BUTTONS`。
3. 同时按 KEY2+KEY3 并松开，等到 `HW ... SPRITES 64 ...` 后保存完整指标行；每次同时按 KEY0+KEY1 并松开，分别记录 128 和 256 的 HW 指标。
4. 按 KEY0/1/2/3，观察初始位于画面中央的玩家移动；检查 UART 中 `HIT` 的累计变化。再按 KEY2+KEY3 可记录同一数量的 CPU 参考结果。
5. 启用串口终端的日志保存功能，记录测试日期、Sprite 数、模式、FPS、RENDER_US、DDR_AR、DDR_AW 和 HIT。使用上面的四帧口径解释 burst 数。

若玩家没有响应，先确认启动行包含 `BUTTONS`，按住方向键至少 30 ms 并等待下一帧；CPU 模式响应较慢，可切换 FPGA 模式。再按 `BUTTON_CONTROL.md` 的引脚表确认 KEY 输入平时为 1、按下为 0。若仍出现旧版静态画面或 HUD，确认下载的是当前目录里的 bitstream。若串口完全无输出，检查 COM 号、FPGA 配置状态和 DDR 校准完成信号；`FAIL present` 则读取 STATUS 的 bit4/5/7，分别定位扫描欠载、读错误和换页等待。

后续可以把程序生成资源替换为独立 Sprite 图片、加入碰撞后的游戏反馈，或根据已测出的 DDR/命令提交瓶颈增加队列。

若出现错误，先看 `reports/simulation.log` 的首个 Fatal 和对应像素/地址；若只是上板失败，看 `reports/compile.log` 以及 `outflow/first_light.timing.rpt`。合成时要确认乘法器映射情况、资源用量和目标时钟时序，不能只以 RTL 编译通过为依据。

## 6. 2026-10-01 串口输入版历史验证记录

- 固件构建通过：text 3317 B、data 16 B、bss 4 B，总计 3337 B；4 KiB 片上 RAM 仍保留栈空间。
- RTL 回归通过：ALL TESTS PASSED，覆盖 Alpha/Color Key、边界、透明写、FIFO、双缓冲和完整视频扫描。
- Efinity compile 通过：map/interface/pnr/pgm 均为 PASS；生成 bitstream outflow/first_light.bit，大小 2,056,086 B，SHA256 27A026F71DA367461D4E0770CBCC81D35C5BDD46F4877246790A9F31A2F0A946。
- 当前布局资源：XLR 19917/60800，RAM 86/256，DSP 18/160；100 MHz `core_clk` setup 余量 +2.177 ns，所有已约束时钟的最小 setup 余量 +0.314 ns，最小 hold 余量 +0.026 ns。
- 真实 Sapphire CPU 模型 SoC 回归通过：`SOC TEST PASSED`，退出码 0，无仿真错误或警告。共提交 3 个 CPU 帧、15 个 HW 帧并确认 18 次换页；扫描完成 A 页 25 帧、B 页 9 帧，全程无前台写、扫描欠载或读错误。
- 对玩家移动前/后的 CPU 帧、64/128/256 HW 首帧和回切 CPU 帧进行完整 307200 像素比较；代表帧显示扫描也逐像素比较。UART 的累计碰撞次数与独立 AABB 模型精确一致，四帧 AR/AW 指标与硬件计数差值精确一致。
- 完整仿真预览导出通过：`motion_1.png`、`motion_2.png`、`motion_3.png`、`motion_8.png`、`motion_13.png`、`motion_18.png`，分别覆盖 CPU、移动后 CPU、64/128/256 HW 和回切 CPU。日志保存在 `reports/simulation_soc.log` 和 `reports/preview_soc.log`。
- 仿真 UART 指标如下，DDR_AR/AW 均为 4 帧总数；这些数值不代表实板测量。

| Sprite 数 | FPS | 平均渲染时间 / µs | DDR_AR / 4 帧 | DDR_AW / 4 帧 | 累计 HIT |
|---:|---:|---:|---:|---:|---:|
| 64 | 60 | 6596 | 20530 | 50738 | 5 |
| 128 | 60 | 9709 | 41066 | 63082 | 13 |
| 256 | 60 | 15860 | 82128 | 87760 | 23 |

- SoC 还确认 Sprite 资源只上传一次（2048 B），FPGA Alpha/Color Key 合成读取独立 DDR 资源，CPU 玩家 UART 控制和 RISC-V AABB 碰撞计数均生效。
- Efinity 只生成并验证 bitstream，没有执行实际 JTAG 下载；上板前仍需用 Programmer 下载 outflow/first_light.bit，并按 115200 8N1 打开 UART。
