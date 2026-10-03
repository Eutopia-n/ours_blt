# SPI Flash Auto Boot 5x7 Font Engine

本工程名称：**SPI Flash Auto Boot 5x7 Font Engine**。它在 Ti60F225 上实现 2D 图形渲染、SPI Flash 自动启动和 5×7 HUD 字体显示；工程文件仍保留 `first_light` 路径名，以兼容现有 Efinity 构建脚本。

当前新增 KEY2 透明度：高级展示短按 +2，长按 500 ms 后每 100 ms 连加，0～100 循环；CPU/FPGA Alpha 混合与验证见 [说明](ALPHA_KEY2.md)。上板必须使用配套新 bitstream 和应用。

当前整合版的菜单、按键分配、构建和上板步骤见 [MENU.md](MENU.md)。
基础展示保留 32 / 128 / 256 三档，方块随机初始化位置、方向、速度并碰边反弹，纯色填充与棋盘格拷贝共用活动区域。
KEY1 按 32 → 128 → 256 → 32 循环数量，KEY0 手动切换 CPU/FPGA；保留操作吞吐量、CPU/HW 耗时比和连续运动。
最新上板包入口为 [KEY2 透明度包](releases/alpha_key2_20261002/README.md)。当前输出仍为 640×480。
下文保留 77 帧高级功能的原有设计与历史验收记录；其中的旧发布包不含菜单。

高级展示使用用户提供的原图生成 77 帧 RGB565 动画。当前本地版本优先从 SPI Flash 自动加载动画程序和素材，UART 仅作为 Flash 用户镜像未写入或校验失败时的调试回退方式。[旧 77 帧上板包](releases/sprite77_20260927/README.md) 仍以 UART 装载到 DDR，仅供复现历史版本；体验当前菜单请使用上方最新包。历史构建与板级验收步骤见 [SPRITE77.md](SPRITE77.md)。颜色键控设计见 [COLOR_KEY.md](COLOR_KEY.md)；此前资源区版本见 [DDR_ASSETS.md](DDR_ASSETS.md)，FIFO 原理见 [FIFO_CACHE.md](FIFO_CACHE.md)。

此前非键控版本的用户实板数据为 CPU 30 FPS / 26220 μs、HW 60 FPS / 4778 μs，见 [历史观测记录](releases/ddr_assets_20260922/BOARD_OBSERVATION.md)。本版在实板上报告 CPU 20 FPS、HW 60 FPS；用户确认 HDMI 动画和 KEY1 去背切换，详见 [本版验收记录](SPRITE77.md)。使用当前 SPI Flash 用户镜像时，冷启动不再需要运行 `tools/upload_sprite77.py`；只有采用旧 UART 调试流程时才需要上传。

适用对象：基于 Ti60F225I3 的 Ti60F225 开发板。工程使用仓库提供的 DDR3、Sapphire RISC-V 和 HDMI 示例作为板级基础。

当前链路：RISC-V 片内引导程序经 UART 将动画程序和压缩素材装入 DDR → DDR 程序选择 CPU 逐像素或 FPGA 经 AXI 搬运当前帧到后台页，KEY1 选择是否跳过品红键色 → 双缓冲换页 → HDMI TX。旧版实板结果保存在 `DDR_ASSETS.md`、`MOTION_DEMO.md` 等历史记录，不代表本版实测性能。

## 1. 本阶段交付内容

- 独立 Efinity 工程 `first_light.xml`，顶层为 `competition_top`，器件为 Ti60F225 / I3。
- RGB565 矩形纯色填充，支持奇数 X、奇数宽度、AXI 写响应错误上报。
- RGB565 图像块拷贝：支持同页显存内重叠拷贝，以及独立 DDR 资源区到所选绘制页的拷贝；源行距可单独配置，目标行距固定 1280 字节。键控模式按可配置的 RGB565 透明色逐像素保留背景。
- 图片资源区为 `0x01200000～0x012FFFFF`（1 MiB）。冷启动时 bootloader 从 SPI Flash 用户区校验并搬运 77 帧 RGB565 Sprite；Flash 不可用时可通过 UART 回退上传。品红 `0xF81F` 为键色，CPU/HW 都从该区域读取。
- 每次最多 16 个 32 位 beat，遇到 4 KB 边界自动拆分，最终 B 响应返回后才置 DONE。
- 两个 DDR framebuffer：A=`0x01000000`、B=`0x01096000`，每页 640×480、RGB565、每像素 2 字节、每行 1280 字节，每页 614400 字节。
- 双缓冲换页：RISC-V 在后台页完成渲染后写入换页请求，视频端只在垂直消隐的帧边界采纳请求，避免一帧中途改变显示基址。
- 两个交替使用的片内行缓存，AXI 时钟域向像素时钟域提供像素。
- 拷贝引擎另有一个片内行缓存，先读完一行再写目标；显示与拷贝按完整 AXI 读 burst 仲裁。
- 加速器写通道包含 16×37 位同步 FIFO，缓存 `{WLAST,WSTRB,WDATA}`；拷贝时连续预取行 RAM，在 `WREADY` 连续有效时每周期发送一个 beat。
- 640×480 HDMI 视频输出；实际像素时钟约 25.208333 MHz，800×525 总时序，对应约 60.01984 Hz。此数值是设计刷新率，不是实测渲染性能。
- C 固件及驱动、渲染模块仿真、实际 Sapphire 核执行固件的联合仿真入口。
- 初级与高级两种场景都有 CPU 逐像素基线与硬件 Fill/Copy 路径，默认每 4 秒切换，UART 小写 `c`/`h` 可提前切换。高级展示中按 KEY1 翻转去背状态；屏幕左侧显示 `KEY ON`/`KEY OFF`。
- 两列显示最近测得的 CPU/HW FPS 与每帧渲染微秒数，当前模式为白字，另一列为灰字；每 4 帧更新一次。
- 根据送入 HDMI 编码器的实际 DE/HS/VS，每帧测量有效宽高；RISC-V 经只读 APB 寄存器读取并显示 `RES 宽X高`，检测完成前显示 `RES WAIT`。

本阶段采用两个固定 framebuffer 连续换页，明确的写 FIFO、独立资源区拷贝和 Color Key 均已实现。资源可拷贝到 A/B 两页，但不开放任意地址或 A→B 显存跨页拷贝。Alpha 混合已新增，详见 ALPHA_KEY2.md；互动游戏尚未实现。77 帧动画、KEY1 两态及 CPU/HW 帧率已完成初步板级验收；视频留存和错误位单独读取见 `SPRITE77.md`。

## 2. 为什么这样连接

CPU 通过现有的 APB 外设窗口发送少量配置；像素数据走独立的 AXI 主接口。这样 CPU 不需要逐像素写 DDR。

渲染器和扫描接口一起接入 Sapphire 的 `io_ddrMasters_0_*`。纯色填充只写 DDR，拷贝先读后写，显示扫描只读；新增仲裁器锁定当前读请求直到其全部数据返回，再选择下一笔事务，显示优先。Sapphire 内部继续负责与 CPU 的访存仲裁，并将 32 位数据转换成 DDR 控制器使用的 128 位数据。

拷贝行缓存和写 FIFO 解决的是两个不同问题：行缓存允许按索引重新组合奇偶半字，并在源、目标重叠时保护尚未写出的源像素；FIFO 则把行 RAM 的同步读取与 AXI `WREADY` 反压解耦。每个 FIFO 项同时保存数据、字节选通和 burst 末尾标志，地址握手后可边预取边发送，避免旧实现逐 beat 插入 `C_WLOAD` 空周期。

DDR 与像素时钟不同，所以显示端不能直接跨时钟读取一组普通寄存器。本工程使用双时钟 RAM 作为行缓存，请求与完成信号采用翻转位及两级同步。每条有效显示行开始前检查缓存行号；取数失败时输出黑色并记录错误，避免把错误行当作正常画面。

Sapphire 的 4 KiB 片内 RAM 装入引导程序；它优先从 SPI Flash 用户区校验动画程序与 77 帧素材并搬运到 DDR，校验失败时再等待 UART 上传。不依赖外部文件系统。片内程序保留 512 字节栈空间并由链接脚本检查越界；实际大小以 `reports/firmware_size.log` 为准。

## 3. 文件入口

| 文件 | 作用 |
|---|---|
| `first_light.xml` | Efinity 工程入口 |
| `first_light.peri.xml` | 官方板级 DDR 引脚与 HDMI TX 外设约束的组合 |
| `first_light.sdc` | 时钟与跨时钟约束 |
| `rtl/competition_top.v` | CPU、DDR、渲染器与 HDMI 编码器连接；由准备脚本生成 |
| `rtl/fill_engine.v` | Fill、普通/键控 Copy 读写状态机、同步行 RAM 和逐像素写选通 |
| `rtl/sync_fifo.v` | 16 项单时钟写数据 FIFO，缓存一个最大 AXI burst |
| `rtl/render_regs.v` | APB 寄存器与状态接口 |
| `rtl/framebuffer_video.v` | DDR 扫描读取、行缓存、行场同步 |
| `rtl/video_mode_measure.v` | 从实际 DE/HS/VS 测量每帧有效宽高 |
| `rtl/key_toggle.v` | KEY0～KEY3 同步、15 ms 消抖和按下事件保持 |
| `rtl/render_subsystem.v` | 模块连接、显示/拷贝读通道仲裁 |
| `software/main.c` | DDR 动画程序、C 驱动、CPU/HW 基线与计时、像素字体 |
| `software/boot.c`、`software/link_ddr.ld` | 片内 UART 引导和 DDR 动画程序链接布局 |
| `tools/make_sprite77.py`、`tools/upload_sprite77.py` | 77 帧素材生成与串口上传 |
| `sim/tb_soc_sprite77.sv` | 真实 Sapphire 核执行 77 帧动画的联合仿真 |
| `software/double_buffer_demo.c` | 保留上一阶段的静态两页校验程序 |
| `software/start.S`、`software/link.ld` | 片内 RAM 启动、异常处理入口与内存布局 |
| `sim/tb_render.sv` | 像素、总线反压、错误处理、行场时序检查 |
| `sim/tb_sync_fifo.sv` | FIFO 顺序、满空边界、同时读写及清空测试 |
| `sim/tb_key_toggle.sv` | KEY1 短脉冲、抖动、长按、释放和复位测试 |
| `sim/tb_menu_keys.sv` | 四路菜单按键独立消抖、短脉冲和复位测试 |
| `sim/tb_video_mode_measure.sv` | 分辨率测量的正常、边界和空帧独立测试 |
| `sim/tb_soc.sv` | 官方 Sapphire 仿真模型运行真实固件 |
| `tools/build.py` | 编译与仿真入口，不执行硬件下载 |
| `reports/sim_frame.png` | 从仿真实际像素输出保存的画面，不是显示器照片 |
| `reports/motion_1.png`、`motion_2.png`、`motion_5.png`、`motion_6.png`、`motion_9.png` | CPU/HW 的去背开/关仿真扫描输出，不代表实板 FPS |
| `outflow/spi_flash_autoboot_5x7_font.bit` | FPGA 编译产物，含片内启动固件 |

`vendor/` 为必要官方依赖副本，来源见该目录 README。GitHub 仓库不包含完整随板 Demo 和安装包；根目录原有独立 RTL/仿真模块保留。不要直接修改生成的顶层或外设文件；需要更改板级组合时修改 `tools/prepare.py`。

## 4. 可复制的离线编译命令

在 PowerShell 中从克隆后的仓库根目录运行。`tools/build.py` 的默认工具路径是旧环境的 `S:\Efinity` 和 `S:\ModelSim\win64`；本机实际安装位置是 `C:\Efinity\2026.1`、`C:\Efinity\efinity-riscv-ide-2026.1` 和 `D:\modelsim\win64`，因此应按 `SPRITE77.md` 中的命令显式传入 `--efinity`、`--modelsim`。普通构建不需要执行 prepare。

```powershell
python my\first_light\tools\build.py firmware
python my\first_light\tools\build.py sim-fifo
python my\first_light\tools\build.py sim-mode
python my\first_light\tools\build.py sim-key
python my\first_light\tools\build.py sim
python my\first_light\tools\build.py sim-soc
python my\first_light\tools\build.py sim-boot-uart
python my\first_light\tools\build.py compile
```

每一步退出码必须为 0，失败时先读 `my\first_light\reports` 中对应日志，再继续。只改 C 代码时执行 `firmware`、`sim-soc`、`compile`；只改渲染 RTL 时执行 `sim`、`sim-soc`、`compile`。

仅在重新导入完整随板资料时，运行 `python my/first_light/tools/build.py prepare --board-root S:/Ti60F225_DemoBoard_v4`，其中路径应替换为实际资料根目录。prepare 会覆盖 vendor 初始化文件，因此随后必须执行 firmware。本仓库已附 SoC 专用 ModelSim 模型，正常联合仿真无需访问仓库外的随板目录。

默认使用 motion 固件。复现静态双缓冲时，firmware 和 sim-soc 都加参数 `--demo double-buffer`，随后执行 compile。compile 使用最近嵌入的初始化文件，不会自动重新编译 C；只给 compile 传 --demo 参数不会切换固件。公共 outflow 会被覆盖，已验证版本请使用 releases 归档。

`compile` 包括综合、接口检查、布局布线与 bitstream 生成；其中工具输出的 `pgm : PASS` 表示生成配置文件，**不是已经烧录开发板**。

本工程不使用 Efinity 的片上 Debugger。随板 co-debug 工程曾在项目 XML 中启用自动插入 Debugger，却没有附带 `debug_profile.wizard.json`；如果运行 Debugger 流程会在第 0 步报告该文件不存在。当前工程已将 `auto_instantiation` 设为 `off`、`profile` 设为 `NONE`，重新导入脚本也会保持此设置。生成下载文件请运行普通 `compile` 流程，再用 Programmer 加载 `.bit`。若以后确实需要片上逻辑分析器，应先在 Debug Wizard 中创建与探针配置对应的 profile。

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
| 0x1C | COLOR | 读写 | Fill 的 RGB565 填充值；键控 Copy 的 RGB565 透明色 |
| 0x20 | DISPLAY | 读写 | 0 关闭有效画面，1 允许扫描；切换在帧边界生效 |
| 0x24 | CYCLES | 只读 | 当前/最近一次填充或拷贝忙碌的核心时钟周期数 |
| 0x28 | FB_BASE | 只读 | 固定 `0x01000000` |
| 0x2C | PITCH | 只读 | 固定 1280 |
| 0x30 | OPERATION | 读写 | 0=纯色填充（复位默认），1=不透明图像块拷贝，2=键控图像块拷贝；3 拒绝 |
| 0x34 | SRC | 读写 | 拷贝源像素的 DDR 字节地址，必须 2 字节对齐 |
| 0x38 | DRAW_PAGE | 读写 | 填充/拷贝页：0=A，1=B；忙碌时不可修改 |
| 0x3C | SWAP_PAGE | 读写 | 请求视频显示页：0=A，1=B |
| 0x40 | SWAP | 写 | 写 1 产生换页请求，在下一帧边界生效 |
| 0x44 | VIDEO_SIZE | 只读 | 高 16 位为实测有效高度，低 16 位为实测有效宽度 |
| 0x48 | VIDEO_STATUS | 只读 | bit0=1 表示最近完成的画面测量非空；复位或测得空帧时为 0 |
| 0x4C | SRC_STRIDE | 读写 | 拷贝源行距，单位字节，复位 1280；资源区支持 WIDTH×2～65534 的偶数，同页显存必须为 1280 |

STATUS：bit0 BUSY，bit1 DONE，bit2 渲染命令错误（填充或拷贝），bit3 DDR_READY，bit4 显示欠载，bit5 显示读响应/长度错误，bit6 当前显示页（0=A，1=B），bit7 SWAP_PENDING（换页等待确认）。DONE 和命令错误在下一条命令启动时清除；显示错误保持到复位。拷贝读错误报告在 bit2，不混入显示错误。

VIDEO_SIZE 测量的是 FPGA 输出的有效画面，当前应为 `0x01E00280`（640×480）；它不读取显示器 EDID，也不自动切换分辨率。VIDEO_STATUS 按帧更新，不是 HDMI 插拔检测信号。

换页顺序：绘制完成 → SWAP_PAGE 写目标页 → SWAP 写 1 → 等待 STATUS bit7=0 且 bit6 等于目标页 → 复用旧前台页。bit7 为 1 时，新的 SWAP、SWAP_PAGE 或渲染 COMMAND 写入产生 APB 错误，避免请求互相覆盖。即使提交同一显示页，也必须等待确认，不能只检查 bit6。

配置顺序：等待空闲 → 写 OPERATION 及 DST/WIDTH/HEIGHT/STRIDE → Fill 写 COLOR，普通 Copy 写 SRC/SRC_STRIDE，键控 Copy 再写 COLOR 作为透明色 → COMMAND 写 1 → 等待 DONE=1 且 BUSY=0 → 检查错误。忙碌时写寄存器、写只读地址或访问未知地址会产生 APB 错误。`fill_rect()`、`copy_rect()`、`copy_image()` 和 `copy_image_keyed()` 各自设置 OPERATION，支持交替调用。

硬件检查目标在所选绘制页内，源在同页显存或资源区内；C 驱动检查目标 X+WIDTH 和 Y+HEIGHT。每像素为 RGB565 两字节，资源区源地址/行距必须为偶数。缓存整行并保持原有同页重叠拷贝方向；资源区则独立递增源行地址。行距为 2 mod 4 时，每行重新计算源半字位置。硬件不允许写资源区；是否将所选绘制页保持为后台页由双缓冲驱动保证。

## 6. 软件流程与函数

`fill_rect(x,y,width,height,color)` 配置硬件并等待写响应完成，返回 0 表示成功；负值表示参数、忙碌、硬件错误或超时。它不使用 CPU 写像素。

`copy_rect(src_x,src_y,dst_x,dst_y,width,height)` 配置源与目标，由硬件完成搬运，也不使用 CPU 写像素。CPU 写像素后必须确保 DDR 写响应完成；本核使用 write-through 缓存，由 `publish_pixels()` 失效缓存并强制 DDR 读回进行同步，不能调用本核未实现的 CSR 0x810。

`copy_image(source,source_stride,dst_x,dst_y,width,height)` 接受 DDR 图片地址和源行距；`copy_rect()` 通过它保留同页接口。`copy_image_keyed(...,key)` 用完全相同的地址和行距检查，并按 RGB565 精确相等跳过透明色。当前 CPU/HW 每帧都清屏，按帧表绘制 77 帧中的当前动作：`KEY ON` 时 CPU 跳过品红像素，硬件使用操作 2；`KEY OFF` 时 CPU 写入所有像素，硬件使用普通拷贝操作 1。两模式使用相同的 Sprite、位置和背景。

`cycle_now()` 读取官方 CLINT 的 MTIME 低 32 位（基址加 `0xBFF8`），用于超时和延时。该 Sapphire 配置读 `mcycle` CSR 会产生非法指令异常，因此使用已在 BSP 中定义的 CLINT 接口。时间差用无符号减法计算，以处理低 32 位翻转。

当前 `scene()` 按相同坐标分别调用 CPU 逐像素或硬件 Fill/Copy 路径；`hud()` 叠加两个模式的最近测量值和去背状态；`fatal_trap()` 输出异常原因和地址。程序持续后台绘制和提交，每 4 秒切换 CPU/HW 模式；串口小写 `c`/`h` 选择渲染路径，KEY1 单次按下翻转去背状态，详细计时口径见 `MOTION_DEMO.md`。按键消抖后状态保持到固件下一次轮询，再经帧边界换页显示。

历史静态程序保存在 `double_buffer_demo.c`，其中 `expected_pixel_page()` 用于 CPU 全帧读回核验：先绘制 A 页并开启显示，再绘制 B 页并提交，两页共校验 614400 个像素。它不再是默认固件。

`present_frame()` 等待本次提交被确认，成功后把旧前台页设为绘制页；返回 -2 表示命令或换页忙，-3 表示渲染/视频错误，-4 表示 2 秒超时。超时不撤销硬件请求，不能据此继续绘制，应停止并排查/复位。

以下仅是历史静态程序图案参数（左上角为原点），不用于当前 77 帧动画：

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

使用 Efinity Programmer 的易失性 JTAG 配置方式加载 `outflow/spi_flash_autoboot_5x7_font.bit`；JTAG 只更新 FPGA 当前配置，断电后需要重新配置。若已将 `flash_user.hex` 写入 SPI Flash 用户区，则重新配置或上电后 bootloader 会自动把程序和素材搬运到 DDR，无需再次串口上传。在同一次上电运行期间，KEY1 切换去背以及 CPU/HW 自动切换都不需要重新下载 bitstream。若使用旧 UART 调试流程，在发布包目录运行 `python .\tools\upload_sprite77.py --list-ports`，找到本机开发板 COM 号，再运行 `python .\tools\upload_sprite77.py --port COM7`，其中 `COM7` 只是示例，必须替换为实际号码。HDMI 连接板上的 TX 接口，串口参数为 115200、8N1。旧版保存在各 `releases/` 子目录。

默认 `KEY ON` 显示一个不规则边缘的人物或球棒帧，轮廓外露出深灰及彩色背景条。按一次 KEY1 后，屏幕变为 `KEY OFF`，品红色矩形外围盖住背景；再按一次恢复去背。人物每秒目标播放 12 个动作并向右移动，到右端后循环。两列 CPU/HW FPS 与 US、`FRAME 1`～`FRAME 77`、`RES 640X480` 均显示，白字列约每 4 秒切换。Flash 自动启动时串口显示 `FLASH BOOT`、`ASSET OK` 和 `Ti60 SPRITE 77 CPU/HW`，随后输出实测值；UART 回退时仍会先显示 `ASSET READY`。完整验收步骤见 `SPRITE77.md`。

当前若一直显示 `ASSET READY`，说明 Flash 用户镜像未被采用，应检查 SPI Flash 用户区和启动日志，必要时再运行 UART 上传脚本；`ASSET ERR` 表示传输或校验失败，脚本会从包头重试；`FAIL ASSET` 或 `FAIL copy` 应先检查素材头、帧表、状态寄存器与 DDR 读写。以下表格保留历史静态程序的故障信息；若仍看到 PASS DOUBLE BUFFER 和静态图案，说明下载的是旧版。

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

## 8. 本地 SPI Flash 自动启动

本地版本的片内 bootloader 会优先读取板上 GD25LQ64 的用户区 `0x380000`。用户区由 `python .\tools\build.py firmware` 自动生成，包含 `animation.bin`、完整 `assets/sprite77.raw` 和 CRC；校验成功后自动搬运到 DDR，串口输出 `FLASH BOOT`，接显示器即可播放。Flash 用户镜像的详细布局、烧录顺序以及 JTAG 临时下载的区别见 [SPI_FLASH_AUTO_BOOT.md](SPI_FLASH_AUTO_BOOT.md)。Flash 用户镜像由本地构建生成；源代码、打包脚本和 5×7 字体修改随本分支提交，生成的二进制可按需写入开发板 SPI Flash。

## 9. 官方源文件来源

- DDR 与 SoC：`08_ti60f225_soc_demo/09_Ti60F225_co_debug_demo`。
- HDMI 外设、P/N 取反和 TMDS 编码器：`03_hdmi_tx_demo/hdmi_tx_demo_v2`。
- CPU 联合仿真：同一 SoC IP 的 `source/hardware/netlist/source_modelsim/EfxSapphireSoc.v`，保留官方加密模型，不使用自编 CPU 替身。
- `tools/prepare.py` 只在新工程副本中将 DDR AXI ID 宽度改为 8 位，匹配 SoC 的事务 ID；补齐 APB 总线宽度及 DDR 写响应，并等待 DDR 校准后再启动 CPU。

完整源文件与许可证保存在对应官方目录和 `vendor/`。后续升级 Sapphire 或 DDR IP 时，应重新核对端口、地址映射、初始化文件名、约束和时序，并重跑两类仿真。
