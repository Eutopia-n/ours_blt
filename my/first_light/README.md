# Ti60 2D 引擎：连续动画与 CPU/HW 渲染对比

适用对象：基于 Ti60F225I3 的 Ti60F225 开发板。工程使用仓库提供的 DDR3、Sapphire RISC-V 和 HDMI 示例作为板级基础。

当前链路：RISC-V 运行 C 程序 → CPU 逐像素渲染或 FPGA 经 AXI Burst 渲染 → 双缓冲 DDR → HDMI TX。纯色填充与 Block Copy 已由用户确认上板显示正常；当前版本增加 32 个运动方块与 CPU/HW 计时对比。用户于 2026-09-21 反馈实板读数：CPU 20 FPS、36202 μs，HW 60 FPS、4778 μs；这是单组观测，长时间稳定性尚待确认。最新说明见 `MOTION_DEMO.md`；前三阶段历史记录见 `DOUBLE_BUFFER.md`、`BLOCK_COPY.md`、`VALIDATION.md`。

## 1. 本阶段交付内容

- 独立 Efinity 工程 `first_light.xml`，顶层为 `competition_top`，器件为 Ti60F225 / I3。
- RGB565 矩形纯色填充，支持奇数 X、奇数宽度、AXI 写响应错误上报。
- RGB565 图像块拷贝，源和目标均位于当前 framebuffer，固定 1280 字节行距；支持不同半字偏移及重叠矩形。
- 每次最多 16 个 32 位 beat，遇到 4 KB 边界自动拆分，最终 B 响应返回后才置 DONE。
- 两个 DDR framebuffer：A=`0x01000000`、B=`0x01096000`，每页 640×480、RGB565、每像素 2 字节、每行 1280 字节，每页 614400 字节。
- 双缓冲换页：RISC-V 在后台页完成渲染后写入换页请求，视频端只在垂直消隐的帧边界采纳请求，避免一帧中途改变显示基址。
- 两个交替使用的片内行缓存，AXI 时钟域向像素时钟域提供像素。
- 拷贝引擎另有一个片内行缓存，先读完一行再写目标；显示与拷贝按完整 AXI 读 burst 仲裁。
- 加速器写通道包含 16×37 位同步 FIFO，缓存 `{WLAST,WSTRB,WDATA}`；拷贝时连续预取行 RAM，在 `WREADY` 连续有效时每周期发送一个 beat。
- 640×480 HDMI 视频输出；实际像素时钟约 25.208333 MHz，800×525 总时序，对应约 60.01984 Hz。此数值是设计刷新率，不是实测渲染性能。
- C 固件及驱动、渲染模块仿真、实际 Sapphire 核执行固件的联合仿真入口。
- 同一场景的 CPU 逐像素基线与硬件 Fill/Copy 两条路径，默认每 4 秒切换，UART 小写 c/h 可提前切换。
- 两列显示最近测得的 CPU/HW FPS 与每帧渲染微秒数，当前模式为白字，另一列为灰字；每 4 帧更新一次。
- 根据送入 HDMI 编码器的实际 DE/HS/VS，每帧测量有效宽高；RISC-V 经只读 APB 寄存器读取并显示 `RES 宽X高`，检测完成前显示 `RES WAIT`。

本阶段采用两个固定 framebuffer 连续换页。独立图像资源区、跨页资源拷贝、可变源行距、Alpha、Color Key 和互动游戏尚未实现；32 个方块也不是已测出的性能极限。已有基础演示闭环不等于整道赛题验收完成。

## 2. 为什么这样连接

CPU 通过现有的 APB 外设窗口发送少量配置；像素数据走独立的 AXI 主接口。这样 CPU 不需要逐像素写 DDR。

渲染器和扫描接口一起接入 Sapphire 的 `io_ddrMasters_0_*`。纯色填充只写 DDR，拷贝先读后写，显示扫描只读；新增仲裁器锁定当前读请求直到其全部数据返回，再选择下一笔事务，显示优先。Sapphire 内部继续负责与 CPU 的访存仲裁，并将 32 位数据转换成 DDR 控制器使用的 128 位数据。

拷贝行缓存和写 FIFO 解决的是两个不同问题：行缓存允许按索引重新组合奇偶半字，并在源、目标重叠时保护尚未写出的源像素；FIFO 则把行 RAM 的同步读取与 AXI `WREADY` 反压解耦。每个 FIFO 项同时保存数据、字节选通和 burst 末尾标志，地址握手后可边预取边发送，避免旧实现逐 beat 插入 `C_WLOAD` 空周期。

DDR 与像素时钟不同，所以显示端不能直接跨时钟读取一组普通寄存器。本工程使用双时钟 RAM 作为行缓存，请求与完成信号采用翻转位及两级同步。每条有效显示行开始前检查缓存行号；取数失败时输出黑色并记录错误，避免把错误行当作正常画面。

固件放在 Sapphire 的 4 KiB 片内 RAM。固件与 FPGA 配置一起编译进 bitstream，不需要先在 DDR 装载程序，也不依赖 SPI Flash 中已有的软件。保留 512 字节栈空间并由链接脚本检查越界；实际大小以 `reports/firmware_size.log` 为准。

## 3. 文件入口

| 文件 | 作用 |
|---|---|
| `first_light.xml` | Efinity 工程入口 |
| `first_light.peri.xml` | 官方板级 DDR 引脚与 HDMI TX 外设约束的组合 |
| `first_light.sdc` | 时钟与跨时钟约束 |
| `rtl/competition_top.v` | CPU、DDR、渲染器与 HDMI 编码器连接；由准备脚本生成 |
| `rtl/fill_engine.v` | 保留模块名，新增 Block Copy 读写状态机及同步行 RAM |
| `rtl/sync_fifo.v` | 16 项单时钟写数据 FIFO，缓存一个最大 AXI burst |
| `rtl/render_regs.v` | APB 寄存器与状态接口 |
| `rtl/framebuffer_video.v` | DDR 扫描读取、行缓存、行场同步 |
| `rtl/video_mode_measure.v` | 从实际 DE/HS/VS 测量每帧有效宽高 |
| `rtl/render_subsystem.v` | 模块连接、显示/拷贝读通道仲裁 |
| `software/main.c` | C 驱动、连续动画、CPU/HW 基线与计时、像素字体 |
| `software/double_buffer_demo.c` | 保留上一阶段的静态两页校验程序 |
| `software/start.S`、`software/link.ld` | 片内 RAM 启动、异常处理入口与内存布局 |
| `sim/tb_render.sv` | 像素、总线反压、错误处理、行场时序检查 |
| `sim/tb_sync_fifo.sv` | FIFO 顺序、满空边界、同时读写及清空测试 |
| `sim/tb_video_mode_measure.sv` | 分辨率测量的正常、边界和空帧独立测试 |
| `sim/tb_soc.sv` | 官方 Sapphire 仿真模型运行真实固件 |
| `tools/build.py` | 编译与仿真入口，不执行硬件下载 |
| `reports/sim_frame.png` | 从仿真实际像素输出保存的画面，不是显示器照片 |
| `reports/motion_1.png`、`motion_5.png`、`motion_9.png` | CPU/HW/CPU 的仿真扫描输出，不代表实板 FPS |
| `outflow/first_light.bit` | FPGA 编译产物，含片内启动固件 |

`vendor/` 为必要官方依赖副本，来源见该目录 README。GitHub 仓库不包含完整随板 Demo 和安装包；根目录原有独立 RTL/仿真模块保留。不要直接修改生成的顶层或外设文件；需要更改板级组合时修改 `tools/prepare.py`。

## 4. 可复制的离线编译命令

在 PowerShell 中从克隆后的仓库根目录运行。本机默认工具安装位置是 `S:\Efinity` 和 `S:\ModelSim\win64`；其他电脑可通过 --efinity 和 --modelsim 指定自己的安装路径。普通构建不需要执行 prepare。

```powershell
python my\first_light\tools\build.py firmware
python my\first_light\tools\build.py sim-fifo
python my\first_light\tools\build.py sim-mode
python my\first_light\tools\build.py sim
python my\first_light\tools\build.py sim-soc
python my\first_light\tools\build.py compile
```

每一步退出码必须为 0，失败时先读 `my\first_light\reports` 中对应日志，再继续。只改 C 代码时执行 `firmware`、`sim-soc`、`compile`；只改渲染 RTL 时执行 `sim`、`sim-soc`、`compile`。

仅在重新导入完整随板资料时，运行 `python my/first_light/tools/build.py prepare --board-root S:/Ti60F225_DemoBoard_v4`，其中路径应替换为实际资料根目录。prepare 会覆盖 vendor 初始化文件，因此随后必须执行 firmware。本仓库已附 SoC 专用 ModelSim 模型，正常联合仿真无需访问仓库外的随板目录。

默认使用 motion 固件。复现静态双缓冲时，firmware 和 sim-soc 都加参数 `--demo double-buffer`，随后执行 compile。compile 使用最近嵌入的初始化文件，不会自动重新编译 C；只给 compile 传 --demo 参数不会切换固件。公共 outflow 会被覆盖，已验证版本请使用 releases 归档。

`compile` 包括综合、接口检查、布局布线与 bitstream 生成；其中工具输出的 `pgm : PASS` 表示生成配置文件，**不是已经烧录开发板**。

如需在 GUI 查看波形，先在 ModelSim 中将当前目录设为 `my/first_light`，再执行 `do sim/run.do`。批处理验收使用上面的 Python 命令，它还会检查仿真成功标志，避免 `$fatal` 退出码被误认为通过。

## 5. 寄存器接口

基址来自官方 `software/soc.h` 的 `IO_APB_SLAVE_0_INPUT`，当前为 `0xF8100000`。寄存器为 32 位、4 字节对齐；宽、高和颜色只使用低 16 位。

| 偏移 | 名称 | 属性 | 含义 |
|---|---|---|---|
| 0x00 | ID | 只读 | 固定 `0x32444631` |
| 0x04 | STATUS | 只读 | 见下方状态位 |
| 0x08 | COMMAND | 写 | 写 1 启动 OPERATION 选择的填充/拷贝 |
| 0x0C | DST | 读写 | 首个目标像素的 DDR 字节地址，必须 2 字节对齐 |
| 0x10 | WIDTH | 读写 | 矩形宽度，1～640 像素 |
| 0x14 | HEIGHT | 读写 | 矩形高度，1～480 行 |
| 0x18 | STRIDE | 读写 | 本阶段只支持 1280 字节 |
| 0x1C | COLOR | 读写 | RGB565 纯色值 |
| 0x20 | DISPLAY | 读写 | 0 关闭有效画面，1 允许扫描；切换在帧边界生效 |
| 0x24 | CYCLES | 只读 | 当前/最近一次填充或拷贝忙碌的核心时钟周期数 |
| 0x28 | FB_BASE | 只读 | 固定 `0x01000000` |
| 0x2C | PITCH | 只读 | 固定 1280 |
| 0x30 | OPERATION | 读写 | 0=纯色填充（复位默认），1=图像块拷贝 |
| 0x34 | SRC | 读写 | 拷贝源像素的 DDR 字节地址，必须 2 字节对齐 |
| 0x38 | DRAW_PAGE | 读写 | 填充/拷贝页：0=A，1=B；忙碌时不可修改 |
| 0x3C | SWAP_PAGE | 读写 | 请求视频显示页：0=A，1=B |
| 0x40 | SWAP | 写 | 写 1 产生换页请求，在下一帧边界生效 |
| 0x44 | VIDEO_SIZE | 只读 | 高 16 位为实测有效高度，低 16 位为实测有效宽度 |
| 0x48 | VIDEO_STATUS | 只读 | bit0=1 表示至少完成一次非空有效画面测量 |

STATUS：bit0 BUSY，bit1 DONE，bit2 渲染命令错误（填充或拷贝），bit3 DDR_READY，bit4 显示欠载，bit5 显示读响应/长度错误，bit6 当前显示页（0=A，1=B），bit7 SWAP_PENDING（换页等待确认）。DONE 和命令错误在下一条命令启动时清除；显示错误保持到复位。拷贝读错误报告在 bit2，不混入显示错误。

换页顺序：绘制完成 → SWAP_PAGE 写目标页 → SWAP 写 1 → 等待 STATUS bit7=0 且 bit6 等于目标页 → 复用旧前台页。bit7 为 1 时，新的 SWAP、SWAP_PAGE 或渲染 COMMAND 写入产生 APB 错误，避免请求互相覆盖。即使提交同一显示页，也必须等待确认，不能只检查 bit6。

配置顺序：等待空闲 → 写 OPERATION 及 DST/WIDTH/HEIGHT/STRIDE → 填充时写 COLOR，拷贝时写 SRC → COMMAND 写 1 → 等待 DONE=1 且 BUSY=0 → 检查错误。忙碌时写寄存器、写只读地址或访问未知地址会产生 APB 错误。`fill_rect()` 和 `copy_rect()` 各自设置 OPERATION，支持交替调用。

硬件检查源/目标范围是否仍在显存内；X+WIDTH 是否越过一行由 C 驱动检查。本阶段只支持 RGB565、源/目标同为 1280 字节 stride 的 framebuffer 内拷贝。缓存整行并按地址选择从上往下或从下往上遍历，从而保护重叠源数据。

## 6. 软件流程与函数

`fill_rect(x,y,width,height,color)` 配置硬件并等待写响应完成，返回 0 表示成功；负值表示参数、忙碌、硬件错误或超时。它不使用 CPU 写像素。

`copy_rect(src_x,src_y,dst_x,dst_y,width,height)` 配置源与目标，由硬件完成搬运，也不使用 CPU 写像素。CPU 写像素后必须确保 DDR 写响应完成；本核使用 write-through 缓存，由 `publish_pixels()` 失效缓存并强制 DDR 读回进行同步，不能调用本核未实现的 CSR 0x810。

`cycle_now()` 读取官方 CLINT 的 MTIME 低 32 位（基址加 `0xBFF8`），用于超时和延时。该 Sapphire 配置读 `mcycle` CSR 会产生非法指令异常，因此使用已在 BSP 中定义的 CLINT 接口。时间差用无符号减法计算，以处理低 32 位翻转。

当前 `scene()` 按相同坐标分别调用 CPU 逐像素或硬件 Fill/Copy 路径；`hud()` 叠加两个模式的最近测量值；`fatal_trap()` 输出异常原因和地址。程序持续后台绘制和提交，每 4 秒切换模式，详细计时口径见 `MOTION_DEMO.md`。

历史静态程序保存在 `double_buffer_demo.c`，其中 `expected_pixel_page()` 用于 CPU 全帧读回核验：先绘制 A 页并开启显示，再绘制 B 页并提交，两页共校验 614400 个像素。它不再是默认固件。

`present_frame()` 等待本次提交被确认，成功后把旧前台页设为绘制页；返回 -2 表示命令或换页忙，-3 表示渲染/视频错误，-4 表示 2 秒超时。超时不撤销硬件请求，不能据此继续绘制，应停止并排查/复位。

以下是历史静态程序图案参数（左上角为原点）；当前动画每帧清屏，再拷贝 32 个 32×32 彩条方块：

| 图案 | X | Y | 宽 | 高 | RGB565 |
|---|---:|---:|---:|---:|---|
| 深灰背景 | 0 | 0 | 640 | 480 | 0x1082 |
| 红色矩形 | 64 | 60 | 192 | 120 | 0xF800 |
| 绿色矩形 | 301 | 161 | 127 | 99 | 0x07E0 |
| 蓝色矩形 | 501 | 351 | 101 | 73 | 0x001F |
| 彩条源：青 | 31 | 301 | 129 | 32 | 0x07FF |
| 彩条源：品红 | 31 | 333 | 129 | 32 | 0xF81F |
| 彩条源：黄 | 31 | 365 | 129 | 33 | 0xFFE0 |
| 拷贝的彩条 | 211 | 321 | 129 | 97 | 从 (31,301) 读取 |

绿色、蓝色和彩条故意使用奇数坐标和宽度，用于覆盖一个 32 位数据字中只写一个 16 位像素的情况。相同的两块多色图用于区分图像块拷贝与纯色填充。

## 7. 上板预期与定位方法

本次只生成新版文件，不自动下载。使用 Efinity Programmer 的易失性 JTAG 配置方式加载 `outflow/first_light.bit`；不要把“临时验证”与写 SPI Flash 混为一谈。HDMI 连接板上的 TX 接口，串口参数为 115200、8N1，实际 COM 号在 Windows 设备管理器确认。旧 Block Copy 版仍在 `releases/block_copy_20260921/`，最终双缓冲版另存 `releases/double_buffer_20260921/`，不覆盖已上板验证的旧版。

当前动画版显示 32 个运动彩条块，两列 CPU/HW FPS 与 US 数值，白字列约每 4 秒切换。串口启动行为 `Ti60 MOTION 32 CPU/HW`，随后周期输出实际测量值。至少等 10 秒让两种模式均采样，详细验收步骤见 `MOTION_DEMO.md`。

以下表格包含历史静态程序的故障信息；若仍看到 PASS DOUBLE BUFFER 和静态图案，说明下载的是旧版，不是当前动画版。

| 如果出现问题 | 下一步具体检查 |
|---|---|
| 串口完全无输出 | 确认 COM 号和 115200；检查 FPGA 配置成功、100 MHz 核心 PLL 锁定、DDR `cal_done`。CPU 被设计为等待 DDR 校准完成后才释放复位。 |
| `TRAP cause=... pc=...` | 用 RISC-V objdump 对 `software/build/first_light.elf` 反汇编，定位 PC；确认 bitstream 内固件已更新。 |
| `FAIL register ID` | 检查 APB 基址是否与 `soc.h` 一致、PADDR/PRDATA 是否完整 16/32 位连接。 |
| `FAIL ... fill` | 查看 STATUS、AW/W/B 握手、BID/BRESP 和 DDR 校准状态；DONE 必须在最终 B 响应之后。 |
| `FAIL block copy` | 看 STATUS bit2、SRC=FRAMEBUFFER+301×1280+31×2、DST=FRAMEBUFFER+321×1280+211×2、OPERATION=1；检查读仲裁、RRESP、ARLEN/RLAST 和最终 B 响应。 |
| `FAIL page A/B DDR pixels` | 检查 DRAW_PAGE 与对应 SRC/DST 地址基址是否匹配，再检查 WSTRB、stride、128 位总线转换和 DDR 本身。 |
| `FAIL page A/B present` | 读取 STATUS bit7/bit6；检查 SWAP_PAGE、跨时钟请求/确认，以及视频 v=524、h=0 时是否仍有未完成的行读取。 |
| DDR 校验通过但黑屏 | 确认 HDMI TX、显示器输入源、HDMI PLL 锁定、TMDS OE、板上 P/N 反接所需的数据取反。 |
| `FAIL video underflow...` | 看 STATUS 的 bit4/5；检查扫描读通道 RRESP/RLAST、DDR 带宽和跨时钟行完成握手。 |

HDMI 与 DDR 沿用原板连接，接口检查还保留一条相邻 HSIO 引脚可能串扰的布局告警，细节见 `VALIDATION.md`。不能随意改引脚来消除告警；实际信号完整性需要接板验证。

## 8. 官方源文件来源

- DDR 与 SoC：`08_ti60f225_soc_demo/09_Ti60F225_co_debug_demo`。
- HDMI 外设、P/N 取反和 TMDS 编码器：`03_hdmi_tx_demo/hdmi_tx_demo_v2`。
- CPU 联合仿真：同一 SoC IP 的 `source/hardware/netlist/source_modelsim/EfxSapphireSoc.v`，保留官方加密模型，不使用自编 CPU 替身。
- `tools/prepare.py` 只在新工程副本中将 DDR AXI ID 宽度改为 8 位，匹配 SoC 的事务 ID；补齐 APB 总线宽度及 DDR 写响应，并等待 DDR 校准后再启动 CPU。

完整源文件与许可证保存在对应官方目录和 `vendor/`。后续升级 Sapphire 或 DDR IP 时，应重新核对端口、地址映射、初始化文件名、约束和时序，并重跑两类仿真。
