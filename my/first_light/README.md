# Ti60 2D 引擎：独立功能演示与生存游戏

2026-10-27 更换简体中文像素字体为 TakWolf 的 Fusion Pixel 12px zh_Hans；固件内嵌 UI 所需字形子集，保持原有字符间距和行高。主机 UI 检查扩展为检测被截断的定宽文本字段，菜单、各演示页、游戏 HUD、升级页和结算页均通过布局检查。上游字体版本和 OFL 许可记录见 [THIRD_PARTY.md](THIRD_PARTY.md)。

2026-10-27 优化生存游戏移动和小怪绘制：镜头改为逐像素跟随，消除 8 像素取整造成的跟随跳动；旧 Sprite 覆盖区改用按页 32×32 脏格位图，分离远处脏区并合并相邻格，减少空白背景重画。敌怪绘制上限提高到 128，按 30 帧窗口的实测 FPS/渲染时间在 32/48/64/96/128 间逐级调节；连续 3 个低帧窗口才回退一级；UART 增加 `ENEMY_DRAWN` 和 `ENEMY_BUDGET` 便于板上核对。游戏时长延长至 360 秒，升级选择页不再提供 A 退出键。

2026-10-23 修复压力页每帧清整屏、重复绘制全部 HUD 导致的固定 30 FPS 开销：两页静态说明分别只初始化一次，每帧只清 640×256 运动区域，数值按页缓存并以连续 32 位写入更新。压力页 `RENDER_US` 纳入 HUD，FPS 保留 UART 报告实际耗时；`MAX60` 同时核对每帧完整渲染 ≤16.6667 ms 和显示刷新计数增量为 1。UART 新增 `MAX_US`、`MISSED` 诊断字段。菜单复用游戏图集中的同像素人物代表帧，减少重复固件资源。编译结果与实测限制见 [压力页修复记录](reports/pressure_60fps_fix_20261023.md)。

2026-10-23 更新文字布局、压力页长按与游戏 MAX60：游戏 HUD 的 `SPRITES` 为本帧实际绘制到屏内的 Sprite 数，`MAX60` 为本局连续 30 帧满足 60 FPS 条件的窗口中最大实际同屏数量；屏外和未绘制对象不计入。Sprite 压力页固定开启 FPGA Alpha + Color Key，提供完整 4×4、16×16、24×24、32×32 素材；从 1 个 Sprite 开始，W 增加 1 个、S 减少 1 个，按住 300 ms 后约每 60 ms 连发一次，D 循环切换尺寸、A 返回；每个采样窗口逐帧检查完整渲染 16.6667 ms 预算和实际显示刷新计数，`MAX60` 按尺寸分别记录已通过的最高数量，不设置 4096 等人为档位上限。文本字段增加宽度与边界保护，普通功能页 DDR 指标分行，游戏指标栏独立排版；主机文字布局检查见 `tools/check_ui.py`。

2026-10-27 优化生存游戏背景和双缓冲绘制：游戏画布使用 RGB565 深蓝灰纯色（`0x1085`），删除面板纹理生成与 DDR 纹理拷贝；各 framebuffer 页保留纯色底，按页恢复旧 Sprite 覆盖区域。固定底色无需镜头滚动和补画新露出条带。所有演示功能页以及游戏准备、暂停和结算页面按 A 返回；升级选择页必须确认技能后继续，D 可暂停；Alpha 减少透明度和压力页换尺寸改用 D。回血掉落使用用户提供的红色爱心图。此前已移除地图中的蓝色十字装饰和双缓冲演示页面的“页面 A/B”文字标记。

2026-10-19 优化压力页：每个测试 Sprite 采用完整尺寸素材，提供 16×16、24×24、32×32 三档，仍由 FPGA 同时执行 Alpha 与 Color Key；游戏人物和敌怪仍使用完整 32×32 图像。

2026-10-19 使用用户提供的粉色像素爱心替换治疗掉落图标；游戏敌怪图像预算提升到最高 64 个，仅在 FPS≥59 且场景渲染低于 12 ms 时开启，其他情况回退到 32 个以优先保帧。

2026-10-18 更新游戏绘制预算：按画面内距离优先选择敌怪，避免离屏对象占满图像合成命令；敌怪血条只在受击后的短时间内显示；HUD 显示 Sprite 当前数/405 上限。五个 J28 按键在界面中统一命名为 W/S/A/D/Enter，仍对应原来的五个逻辑位。

2026-10-16 更新为 J28 五键输入：J28-34/37/38/39/40 分别连接 GPIOL_09/GPIOL_04/GPIOL_10/GPIOL_06/GPIOR_13，复位键保持不变；菜单、功能页和游戏 HUD 改为中文。弹幕显示池提升到 48 个，使用 CPU 直接写入 5×5/7×7 小矩形，避免 32×32 图像读取和逐弹幕命令等待拖慢 60 Hz。

2026-10-10 更新 Alpha 每步 1、移除 AUTO 控制；改为 2048×1408 跟随相机地图，增加升级菜单图标/等级上限/满级质变，并将治疗符文改为蓝青配色。掉电启动需一次性写入 SPI Flash，步骤见 [FLASH_PROGRAMMING.md](FLASH_PROGRAMMING.md)。

2026-10-08 新增首页第三项 **FROSTBOUND SURVIVOR**：用户人物四方向 16 帧动画、持续按键移动、随机刷怪和追踪、自动魔法弹与环绕法球、碰撞受伤、经验拾取、三选一升级、暂停/继续、死亡重开和胜利结算。当前地图可滚动、人物由相机跟随，技能满级后触发穿透、双发、冲刺等效果。菜单、石砖竞技场和魔法采用统一的深蓝/青色像素风格。操作和存储说明见 [GAME_DEMO.md](GAME_DEMO.md)，开源参考与许可证见 [THIRD_PARTY.md](THIRD_PARTY.md)。

提供 7 个独立功能页：纯色填充、块拷贝、双缓冲、HDMI/分辨率、Color Key、Alpha 混合和 FPGA Alpha+Color Key Sprite 压力测试。压力页从 1 个 Sprite 开始，W/S 单个增减，D 循环 4×4、16×16、24×24、32×32 完整素材，A 返回，显示实际 FPS、RENDER_US、DDR_RD/WR 与对应尺寸的 `MAX60`；具体可达到的负载以固定 60 FPS 帧预算下的实测记录为准。碰撞检测留在游戏逻辑中，不单独占用演示页。操作见 [MENU_DEMO.md](MENU_DEMO.md)，按键引脚依据见 [BUTTON_CONTROL.md](BUTTON_CONTROL.md)。

2026-09-22 在分辨率显示与写 FIFO 版本上增加独立 DDR 图片资源区和源行距。当前版本说明见 [DDR_ASSETS.md](DDR_ASSETS.md)；此前同步记录见 [SYNC_FIFO_RESOLUTION.md](SYNC_FIFO_RESOLUTION.md)，FIFO 原理见 [FIFO_CACHE.md](FIFO_CACHE.md)。

`releases/` 中的旧版 bitstream 和性能读数仅供历史回退，不包含本次 64/128/256 Sprite 互动固件。

适用对象：基于 Ti60F225I3 的 Ti60F225 开发板。工程使用仓库提供的 DDR3、Sapphire RISC-V 和 HDMI 示例作为板级基础。

当前链路：RISC-V 启动时上传图片到独立 DDR 资源区 → CPU 逐像素或 FPGA 经 AXI Burst 读取前景、读取背景并完成 Alpha/Color Key 合成 → 双缓冲换页 → HDMI TX。纯色填充与 Block Copy 的历史版本已由用户确认上板显示正常。旧版 CPU/HW FPS 观测不能代表当前透明 Sprite 性能。

## 1. 本阶段交付内容

- 独立 Efinity 工程 `first_light.xml`，顶层为 `competition_top`，器件为 Ti60F225 / I3。
- RGB565 矩形纯色填充，支持奇数 X、奇数宽度、AXI 写响应错误上报。
- RGB565 图像块拷贝：支持同页显存内重叠拷贝，以及独立 DDR 资源区到所选绘制页的拷贝；源行距可单独配置，目标行距固定 1280 字节。
- 图片资源区为 `0x01200000～0x012FFFFF`（1 MiB）。启动上传原测试/菜单资源、四档压力素材共 13984 字节及游戏图集 51200 字节，共 65184 字节。游戏使用帧缓冲直接填充深蓝灰纯色底，不再分配背景纹理。
- 每次最多 16 个 32 位 beat，遇到 4 KB 边界自动拆分，最终 B 响应返回后才置 DONE。
- 两个 DDR framebuffer：A=`0x01000000`、B=`0x01096000`，每页 640×480、RGB565、每像素 2 字节、每行 1280 字节，每页 614400 字节。
- 双缓冲换页：RISC-V 在后台页完成渲染后写入换页请求，视频端只在垂直消隐的帧边界采纳请求，避免一帧中途改变显示基址。
- 两个交替使用的片内行缓存，AXI 时钟域向像素时钟域提供像素。
- 拷贝引擎另有一个片内行缓存，先读完一行再写目标；显示与拷贝按完整 AXI 读 burst 仲裁。
- 加速器写通道包含 16×37 位同步 FIFO，缓存 `{WLAST,WSTRB,WDATA}`；拷贝时连续预取行 RAM，在 `WREADY` 连续有效时每周期发送一个 beat。
- 640×480 HDMI 视频输出；实际像素时钟约 25.208333 MHz，800×525 总时序，对应约 60.01984 Hz。此数值是设计刷新率，不是实测渲染性能。
- C 固件及驱动、渲染模块仿真、实际 Sapphire 核执行固件的联合仿真入口。
- RISC-V 在游戏中计算玩家、敌人和碰撞；Sprite 压力页从 1 个开始按键逐个增加随机运动坐标，D 循环选择 4×4、16×16、24×24、32×32 完整素材，A 返回，由 FPGA 开启 Alpha + Color Key 完成合成。
- 基础菜单含 4 项、高阶菜单含 3 项；压力页每档采样 30 帧，逐帧检查完整渲染预算及无漏刷新，并记录已通过的最高 Sprite 数量。未实测的数量不会被视作达到目标。
- 普通功能页显示 CPU/FPGA 的 FPS、平均渲染时间和 DDR burst；压力页显示 FPGA FPS、RENDER_US、DDR_RD/WR、当前 Sprite 数和 `MAX60`。UART 普通页每 4 帧、压力页每 30 帧输出指标，并输出本窗口 `PASS/FAIL` 状态，不输出碰撞累计数。
- 根据送入 HDMI 编码器的实际 DE/HS/VS，每帧测量有效宽高，HUD 读取对应 APB 寄存器显示分辨率。
- 游戏使用固定 60 Hz 逻辑更新、256 敌人/48 魔法弹/96 宝石对象池和 6 种升级，FPGA 负责背景拷贝与 Alpha/Color Key 合成。弹幕优先由 CPU 写入 5×5/7×7 RGB565 小矩形，48 个逻辑弹幕都可在一帧内更新；屏幕显示生命、经验、等级、时间、击杀和渲染指标。

菜单中 W 上一项、S 下一项、Enter 进入、子菜单按 A 返回；所有演示功能页按 A 返回。游戏中 W/S/A/D 为上/下/左/右；准备、暂停和结算页面按 A 返回首页，升级页用 W/S 选择、Enter 确认、D 暂停且无退出键。游戏时长为 360 秒。Alpha 页支持 W 加一、D 减一，按住自动重复且端点饱和。Sprite 压力页固定运行 FPGA 合成，W 加 1、S 减 1、D 换尺寸、A 返回。UART 仅输出日志。掉电启动须写入 SPI Flash，完成后断电重上电验证。

## 2. 为什么这样连接

CPU 通过现有的 APB 外设窗口发送少量配置；像素数据走独立的 AXI 主接口。这样 CPU 不需要逐像素写 DDR。

渲染器和扫描接口一起接入 Sapphire 的 `io_ddrMasters_0_*`。纯色填充只写 DDR，拷贝先读后写，显示扫描只读；新增仲裁器锁定当前读请求直到其全部数据返回，再选择下一笔事务，显示优先。Sapphire 内部继续负责与 CPU 的访存仲裁，并将 32 位数据转换成 DDR 控制器使用的 128 位数据。

拷贝行缓存和写 FIFO 解决的是两个不同问题：行缓存允许按索引重新组合奇偶半字，并在源、目标重叠时保护尚未写出的源像素；FIFO 则把行 RAM 的同步读取与 AXI `WREADY` 反压解耦。每个 FIFO 项同时保存数据、字节选通和 burst 末尾标志，地址握手后可边预取边发送，避免旧实现逐 beat 插入 `C_WLOAD` 空周期。

DDR 与像素时钟不同，所以显示端不能直接跨时钟读取一组普通寄存器。本工程使用双时钟 RAM 作为行缓存，请求与完成信号采用翻转位及两级同步。每条有效显示行开始前检查缓存行号；取数失败时输出黑色并记录错误，避免把错误行当作正常画面。

固件放在 Sapphire 的 64 KiB 片内 RAM，由上一版 16 KiB 扩容以容纳完整游戏及人物动画。固件与 FPGA 配置一起编译进 bitstream，不需要先在 DDR 装载程序，也不依赖 SPI Flash 中已有的软件。链接脚本保留至少 4096 字节栈并检查越界；实际大小以 `reports/firmware_size.log` 为准。板卡的 8 MB Flash / 256 MB DDR3 与此片内 RAM 是不同存储。

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
| `software/main.c` | C 驱动、简洁菜单、按键事件、位置/碰撞、CPU/HW 基线、HUD 与计时 |
| `software/font5x7.h`、`software/font_cn.h` | ASCII 字模与 Fusion Pixel 简体中文像素字形，中文 12×12 点阵位于 14×14 字符单元 |
| `software/player_asset.h` | 从附件像素图整理的四个 32×32 RGB565 方向帧，RLE 压缩后启动解压到 DDR |
| `assets/player/`、`tools/prepare_player_assets.py` | 附件原图、完整 16 帧图集、RGB565 和方向元数据、可复现的转换工具 |
| `rtl/button_input.v` | 五路按键同步、20 ms 消抖、短按暂存，可选长按重复（当前菜单禁用） |
| `tools/expand_soc_ram.py` | 对综合/仿真 SoC 同步应用 64 KiB 片内 RAM 扩容 |
| `software/double_buffer_demo.c` | 保留上一阶段的静态两页校验程序 |
| `software/start.S`、`software/link.ld` | 片内 RAM 启动、异常处理入口与内存布局 |
| `sim/tb_render.sv` | 像素、总线反压、错误处理、行场时序检查 |
| `sim/tb_sync_fifo.sv` | FIFO 顺序、满空边界、同时读写及清空测试 |
| `sim/tb_video_mode_measure.sv` | 分辨率测量的正常、边界和空帧独立测试 |
| `sim/tb_soc.sv` | 官方 Sapphire 仿真模型运行真实固件 |
| `software/survivor_game.c`、`software/game_view.h` | 游戏规则与现有渲染驱动的显示/主循环适配 |
| `sim/tb_soc_game.sv`、`sim/test_survivor_game.c` | 游戏整机与主机规则测试 |
| `tools/build.py` | 编译与仿真入口；显式运行 `flash` 时写入硬件 SPI Flash |
| `reports/sim_frame.png` | 从仿真实际像素输出保存的画面，不是显示器照片 |
| `reports/motion_*.png` | 从联合仿真实际扫描输出转换的菜单/演示画面；有效文件以本次 `preview_soc.log` 为准，不代表实板照片 |
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
python my\first_light\tools\build.py sim-game
python my\first_light\tools\build.py compile
```

每一步退出码必须为 0，失败时先读 `my\first_light\reports` 中对应日志，再继续。只改 C 代码时执行 `firmware`、`sim-soc`、`compile`；只改渲染 RTL 时执行 `sim`、`sim-soc`、`compile`。

仅验证本次菜单/人物可执行 `python my/first_light/tools/build.py sim-soc --ui-smoke`，日志为 `reports/simulation_soc_ui.log`，覆盖菜单循环和返回、四方向资源上传、整帧/扫描像素、填充与 Alpha 的代表性功能；完整 7 页功能测试使用不带参数的 `sim-soc`。

仅在重新导入完整随板资料时，运行 `python my/first_light/tools/build.py prepare --board-root S:/Ti60F225_DemoBoard_v4`，其中路径应替换为实际资料根目录。prepare 会覆盖 vendor 初始化文件，因此随后必须执行 firmware。本仓库已附 SoC 专用 ModelSim 模型，正常联合仿真无需访问仓库外的随板目录。

默认使用 motion 固件。复现静态双缓冲时，firmware 和 sim-soc 都加参数 `--demo double-buffer`，随后执行 compile。compile 使用最近嵌入的初始化文件，不会自动重新编译 C；只给 compile 传 --demo 参数不会切换固件。公共 outflow 会被覆盖，已验证版本请使用 releases 归档。

`compile` 包括综合、接口检查、布局布线与 bitstream 生成；其中工具输出的 `pgm : PASS` 表示生成配置文件，**不是已经烧录开发板**。若要掉电保留，编译通过后接好板卡并执行 `python my/first_light/tools/build.py flash`，详情见 `my/first_light/FLASH_PROGRAMMING.md`。

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
| 0x30 | OPERATION | 读写 | 0=纯色填充（复位默认），1=图像块拷贝，2=资源 Sprite 合成 |
| 0x34 | SRC | 读写 | 拷贝源像素的 DDR 字节地址，必须 2 字节对齐 |
| 0x38 | DRAW_PAGE | 读写 | 填充/拷贝页：0=A，1=B；忙碌时不可修改 |
| 0x3C | SWAP_PAGE | 读写 | 请求视频显示页：0=A，1=B |
| 0x40 | SWAP | 写 | 写 1 产生换页请求，在下一帧边界生效 |
| 0x44 | VIDEO_SIZE | 只读 | 高 16 位为实测有效高度，低 16 位为实测有效宽度 |
| 0x48 | VIDEO_STATUS | 只读 | bit0=1 表示最近完成的画面测量非空；复位或测得空帧时为 0 |
| 0x4C | SRC_STRIDE | 读写 | 拷贝源行距，单位字节，复位 1280；资源区支持 WIDTH×2～65534 的偶数，同页显存必须为 1280 |
| 0x50 | BLEND_CTRL | 读写 | 仅 OPERATION=2 使用；bit0 Alpha，bit1 Color Key，其他位必须为 0；复位 0 |
| 0x54 | ALPHA | 读写 | 低 8 位有效，0～255；复位 255，高位忽略 |
| 0x58 | COLOR_KEY | 读写 | 低 16 位 RGB565 透明色；复位 0，高位忽略 |
| 0x5C | BURST_READ | 只读 | 渲染引擎 AR 握手累计数，复位清零，不含 CPU/视频扫描 |
| 0x60 | BURST_WRITE | 只读 | 渲染引擎 AW 握手累计数，复位清零，不含 CPU 写入 |
| 0x64 | BUTTON_HELD | 只读 | 按键消抖后的持续状态，bit0～4 对应按键1～5，1 表示按住；不随事件确认清零 |
| 0x68 | BUTTON_ENTER_EVENT | 只读 | 第五键（Enter）消抖事件，按下后保持为 1，GPIO 写入确认位后清零 |
| 0x6C | VIDEO_FRAME_COUNT | 只读 | 显示刷新累计计数，复位清零；用于检查连续换页是否漏刷新，不能当作渲染 FPS |
| 0x70 | DDR_READ_WAIT_CYCLES | 只读 | 图形引擎读地址/读数据阶段因 AXI 未就绪而等待的 100 MHz 周期累计数 |
| 0x74 | DDR_WRITE_WAIT_CYCLES | 只读 | 图形引擎写地址/写数据/写响应阶段因 AXI 未就绪而等待的 100 MHz 周期累计数 |

STATUS：bit0 BUSY，bit1 DONE，bit2 渲染命令错误（填充或拷贝），bit3 DDR_READY，bit4 显示欠载，bit5 显示读响应/长度错误，bit6 当前显示页（0=A，1=B），bit7 SWAP_PENDING（换页等待确认）。DONE 和命令错误在下一条命令启动时清除；显示错误保持到复位。拷贝读错误报告在 bit2，不混入显示错误。

VIDEO_SIZE 测量的是 FPGA 输出的有效画面，当前应为 `0x01E00280`（640×480）；它不读取显示器 EDID，也不自动切换分辨率。VIDEO_STATUS 按帧更新，不是 HDMI 插拔检测信号。

换页顺序：绘制完成 → SWAP_PAGE 写目标页 → SWAP 写 1 → 等待 STATUS bit7=0 且 bit6 等于目标页 → 复用旧前台页。bit7 为 1 时，新的 SWAP、SWAP_PAGE 或渲染 COMMAND 写入产生 APB 错误，避免请求互相覆盖。即使提交同一显示页，也必须等待确认，不能只检查 bit6。

配置顺序：等待空闲 → 写 OPERATION 及 DST/WIDTH/HEIGHT/STRIDE → 填充时写 COLOR，拷贝时写 SRC 和 SRC_STRIDE → COMMAND 写 1 → 等待 DONE=1 且 BUSY=0 → 检查错误。忙碌时写寄存器、写只读地址或访问未知地址会产生 APB 错误。`fill_rect()`、`copy_rect()`、`copy_image()` 各自设置 OPERATION，支持交替调用。

硬件检查目标在所选绘制页内，源在同页显存或资源区内；C 驱动检查目标 X+WIDTH 和 Y+HEIGHT。每像素为 RGB565 两字节，资源区源地址/行距必须为偶数。缓存整行并保持原有同页重叠拷贝方向；资源区则独立递增源行地址。行距为 2 mod 4 时，每行重新计算源半字位置。硬件不允许写资源区；是否将所选绘制页保持为后台页由双缓冲驱动保证。

## 6. 软件流程与函数

`fill_rect(x,y,width,height,color)` 配置硬件并等待写响应完成，返回 0 表示成功；负值表示参数、忙碌、硬件错误或超时。它不使用 CPU 写像素。

`copy_rect(src_x,src_y,dst_x,dst_y,width,height)` 配置源与目标，由硬件完成搬运，也不使用 CPU 写像素。CPU 写像素后必须确保 DDR 写响应完成；本核使用 write-through 缓存，由 `publish_pixels()` 失效缓存并强制 DDR 读回进行同步，不能调用本核未实现的 CSR 0x810。

`copy_image(source,source_stride,dst_x,dst_y,width,height)` 接受 DDR 图片地址和源行距；`copy_rect()` 通过它保留同页接口。`init_assets()` 启动时上传 2048 字节测试 Sprite、32/512/1152/2048 字节四档压力 Sprite 及 51200 字节游戏图集，再从解码后的游戏图集复制四个方向的首帧到原有 8192 字节菜单区，并排空 CPU 写操作；代表帧像素与原菜单资源一致。压力页从 1 个开始绘制带 Alpha/Color Key 的 Sprite，W/S 每次只增减 1 个、D 切换尺寸、A 返回；游戏使用独立怪物、宝石、红色治疗爱心和魔法图像。菜单预览使用玩家正面代表帧。

`cycle_now()` 读取官方 CLINT 的 MTIME 低 32 位（基址加 `0xBFF8`），用于超时和延时。该 Sapphire 配置读 `mcycle` CSR 会产生非法指令异常，因此使用已在 BSP 中定义的 CLINT 接口。时间差用无符号减法计算，以处理低 32 位翻转。

普通 `scene()` 按相同坐标分别调用 CPU 逐像素或硬件 Fill/Blend 路径；Sprite 压力页固定使用 FPGA Alpha + Color Key。UART 普通页每 4 帧、压力页每 30 帧报告一次测量值；`fatal_trap()` 输出异常原因和地址。按键事件在绘制下一帧前读取并确认。

历史静态程序保存在 `double_buffer_demo.c`，其中 `expected_pixel_page()` 用于 CPU 全帧读回核验：先绘制 A 页并开启显示，再绘制 B 页并提交，两页共校验 614400 个像素。它不再是默认固件。

`present_frame()` 等待本次提交被确认，成功后把旧前台页设为绘制页；返回 -2 表示命令或换页忙，-3 表示渲染/视频错误，-4 表示 2 秒超时。超时不撤销硬件请求，不能据此继续绘制，应停止并排查/复位。

以下表格是早期静态/动画版本的图案参数记录；当前互动 Sprite 版每帧清屏，再绘制所选数量和尺寸的完整菱形素材：

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

编译与上板分两步：`compile` 生成 `outflow/first_light.bit`，可用 Efinity Programmer 临时 JTAG 配置验证；要让板卡断电后自动启动，接好板卡并执行 `python tools/build.py flash` 将配置写入 SPI Flash，随后断电重上电检查。HDMI 连接板上的 TX 接口，串口参数为 115200、8N1，实际 COM 号在 Windows 设备管理器确认。旧 Block Copy 版仍在 `releases/block_copy_20260921/`，最终双缓冲版另存 `releases/double_buffer_20260921/`，不覆盖已上板验证的旧版。

当前输入、游戏指标和验收步骤见 [GAME_DEMO.md](GAME_DEMO.md)，独立功能见 [MENU_DEMO.md](MENU_DEMO.md)。历史资源/运动版本可查 [DDR_ASSETS.md](DDR_ASSETS.md)、[MOTION_DEMO.md](MOTION_DEMO.md) 和 [ADVANCED_V1.md](ADVANCED_V1.md)。

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
