# Ti60F225 RISC-V + FPGA 2D 渲染引擎

本目录用于维护独立 RTL 模块、配套仿真及软件接口代码。

当前可上板的集成工程位于 `my/first_light/`，必要原厂依赖独立放在该工程的 vendor 目录并标明来源，原有独立模块保留。

## 当前可运行工程：Ti60F225 2D 渲染

- 开发板：基于 Ti60F225I3 的 Ti60F225 开发板。
- 功能：RISC-V C 驱动、AXI DDR 纯色填充/图像拷贝、16×37 位写 FIFO、独立 DDR 图片资源区、可配置源行距、双缓冲、640×480 HDMI、实际输出分辨率显示，以及 32 个运动 Sprite 的 CPU/HW 性能对比。
- 图片启动时上传一次到 `0x01200000`，两种模式每帧均从同一资源区读取。硬件每帧执行 1 个 Fill 和 32 个 Copy，目标为后台显存。
- 最新用户实板反馈：CPU 30 FPS / 26220 μs，HW 60 FPS / 4778 μs；帧率比 2 倍、场景渲染加速比约 5.49 倍。这是单组用户观测，不代表长期稳定性或最大负载。
- 基础功能已覆盖并完成代码/仿真验证；Alpha、Color Key、互动游戏及最大 Sprite 数量测量尚未完成。图片格式当前为 RGB565，目标行距固定 1280 字节。

入口：[工程说明](my/first_light/README.md)、[独立 DDR 资源区与验收记录](my/first_light/DDR_ASSETS.md)、[最新下载文件](my/first_light/releases/ddr_assets_20260922/first_light.bit)、[实板观测记录](my/first_light/releases/ddr_assets_20260922/BOARD_OBSERVATION.md)。此前 FIFO/分辨率版本和旧动画版均保留在 `my/first_light/releases/`。

### 克隆与复现

在 PowerShell 中执行，工具默认位置为 S:/Efinity 和 S:/ModelSim/win64，可通过 --efinity 和 --modelsim 指定实际安装位置：

~~~powershell
git clone https://github.com/Eutopia-n/ours_blt.git
cd ours_blt
python my/first_light/tools/build.py firmware
python my/first_light/tools/build.py sim-fifo
python my/first_light/tools/build.py sim-mode
python my/first_light/tools/build.py sim
python my/first_light/tools/build.py sim-soc
python my/first_light/tools/build.py compile
~~~

首次克隆不需要运行 prepare；仓库已包含生成后的工程配置、必要 IP 和 RAM 初始化输入。只有重新从随板资料导入时才使用 `prepare --board-root <完整随板资料目录>`，然后重新执行 firmware。工具安装包、大型随板资料和编译缓存不在仓库中。

固件、模块仿真、真实 Sapphire 核联合仿真和完整 FPGA 编译已有通过记录，见工程 reports 和 releases；仿真依赖 ModelSim 与可用许可证。编译命令不会自动下载 FPGA。

最新资源区版本通过 58 组独立图片拷贝及显示期间两页后台拷贝测试；真实 CPU 联合仿真验证一次性 2048 字节上传、9 次换页和 12 个完整扫描帧，最终 setup slack +0.361 ns、hold slack +0.026 ns。已有板级 DDR/HDMI 相邻引脚告警保留，需实板持续运行验收。

## 目录结构

- `rtl/`：模块源码与接口适配。
- `sim/`：测试平台与仿真文件。
- `sw/`：软件接口与使用示例。
- `docs/`：接口说明与验证记录。
- `efinity/`：工具工程配置。
- `my/first_light/`：Ti60F225 RISC-V、DDR、2D 渲染与 HDMI 集成工程。

## 维护约定

- 模块与配套测试保持同步，接口变更时更新相关说明。
- 外部依赖与本目录源码分开管理，避免直接覆盖已有文件。
- 具体使用方式、适用范围与验证情况以对应模块文档为准。
