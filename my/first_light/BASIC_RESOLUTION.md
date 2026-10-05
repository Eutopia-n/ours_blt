# 历史：BASIC 的 KEY2 分辨率切换

当前已取消切换，所有场景固定 800×600，见 [FIXED800.md](FIXED800.md)。

2026-10-05 启动修复：应用已随 `.bit` 更新，现有 Flash 素材继续使用，见 [EMBEDDED_APP.md](EMBEDDED_APP.md)。

工程为当前 `try/my/first_light` 学习副本，顶层 `competition_top`。

进入 BASIC 时为 640×480。KEY2 每次有效按下按 640×480 → 800×600 → 640×480 循环；
15 ms 消抖，长按只切换一次。KEY3 返回菜单时先恢复 640×480。
菜单里的 KEY2 仍确认进入，ADVANCED 里的 KEY2 仍执行原有透明度控制。

两个模式都属于约 60 Hz 档：640×480 使用 25 MHz 像素时钟、800×525 总时序、
负 HS/VS，刷新率约 59.524 Hz；800×600 使用 40 MHz 像素时钟、1056×628 总时序、
正 HS/VS，刷新率约 60.317 Hz。这是设计值，未做本次实板观测。

## 切换与内存

- 软件在上一帧 PRESENT 完成后关闭显示，写模式请求，等待像素域采纳及 PLL 重锁，
  然后按新宽高清屏、绘制后台页并 PRESENT。渲染期间不修改行距。
- 像素域只在垂直消隐、旧行 AXI 读事务完成时采纳模式。请求与完成翻转位保持，
  清空旧缓存行标签，重新预取首行；PLL 重锁不复位 SoC、DDR 或 APB 配置。
- `user_clk/core_clk` 为 100 MHz，负责软件、APB、渲染和 AXI。视频像素时钟为 25/40 MHz。
  AXI ARVALID/ARREADY、RVALID/RREADY、RLAST 保持既有握手和 burst 级仲裁。
- A=`0x01000000`，B=`0x010EA600`，各页固定保留 960000 字节；行距均为 1600 字节。
  两页结束于 `0x011D4C00`，低于 `0x01200000` 素材区。640 模式仅扫描每行前 640 像素。
- 新 HDMI 参考 PLL 使用空闲的 PLL_BL0：100 MHz × 32 = 3200 MHz，输出 50/80 MHz。
  RTL 两个翻转触发器除以二，得到 25/40 MHz 参考；选择器只在 HDMI PLL 复位期间改变。
  HDMI PLL 保持慢/快时钟 1:5、偶数分频，最坏 40 MHz 像素时钟用于约束与接口检查。
  DDR PLL、DDR IP、DVI/TMDS 编码器及板级引脚不变。

APB 基址 `0xF8100000`：`0x5C` 为模式请求（0=640×480，1=800×600），仅允许在显示关闭、
渲染空闲且无待确认换页时写入。`0x60` 为状态：bit0 当前模式，bit1 待采纳，bit2 PLL 就绪。
原 `0x44/0x48` 继续报告从实际 HS/VS/DE 测得的宽高与有效位。

## 代码与复现

主要改动为 `rtl/framebuffer_video.v`、`rtl/video_clock_control.v`、`rtl/render_subsystem.v`、
`rtl/render_regs.v`、`rtl/fill_engine.v`、`rtl/competition_top.v`、`software/main.c`、
`software/render.h`、`first_light.peri.xml`、`first_light.sdc`。
`tools/prepare.py` 和 `tools/config_video_modes.py` 记录可重建的顶层及视频 PLL 配置。
`video_clock_control.v` 由顶层 include，和现有按键模块的接入方式一致。

在本工程目录运行：

```powershell
python tools/build.py firmware
python tools/build.py sim-resolution --modelsim D:/modelsim/win64
python tools/build.py sim-resolution-soc --modelsim D:/modelsim/win64
python tools/build.py compile
```

变更前的源码和应用/Flash 用户镜像位于 `releases/pre_basic_resolution_20261005/`。
当前上板使用 `basic_resolution_single_bit_20261005` 中的 FPGA 配置即可。
旧 Flash 镜像中的应用会被忽略，素材继续使用；只在首次准备或更换素材时写入 `0x380000` 用户区。
没有执行板卡下载或 Flash 写入。

下一步上板验收：进入 BASIC，连续切换两次，
确认显示器重新锁定、RES 显示变化；再从 800 模式返回菜单并检查 ADVANCED 的 KEY2 透明度。

后续扩大模式时，需要一起调整时序、像素时钟、缓存地址宽度和 framebuffer 保留区，
并重新检查素材区边界；目前仅开放这两个模式。

## 分辨率版验证记录（启动修复前）

本节数值对应先前双文件版本，日志归档在 `releases/basic_resolution_20261005/validation/`。
最新启动修复的检查范围和下载文件见 `EMBEDDED_APP.md`。

- RISC-V 应用与片内启动程序编译成功。应用 13368 字节；Flash 用户镜像 981016 字节。
  已检查镜像内应用、素材 CRC32，以及二进制与逐字节 hex 的一致性。
- Efinity 2026.1 的 map、interface、pnr、pgm 均 PASS，并生成新 `.bit` / `.hex`。
  最终报告中 100 MHz 核心 setup/hold slack 为 1.388 / 0.026 ns，40 MHz 像素域为
  20.803 / 0.097 ns，报告列出的各时钟 setup、hold 均为正值。
  见 `reports/compile.log`、`outflow/spi_flash_autoboot_5x7_font.timing.rpt`。
- `sim-resolution` PASS：两种分辨率的逐像素完整帧、同步极性与脉宽、800/600 行列边界、
  第 512 行之后的标签、停滞 AXI 读完成后才切换、PLL 失锁恢复、800×600 全屏填充、
  非法宽高及空操作。见 `reports/simulation_resolution.log`，0 errors / 0 warnings。
- 原渲染回归 `sim` PASS：Fill、普通/键控/Alpha Copy、重叠、奇偶对齐、4 KiB 拆分、
  AXI 反压和错误、双缓冲及实际扫描输出。见 `reports/simulation.log`，0 errors / 0 warnings。
- 四路按键消抖测试 PASS，包含短脉冲、抖动、长按与复位。
  见 `reports/simulation_menu_keys.log`；8 条警告为该测试未接入模块的 `down` 输出。
- `sim-resolution-soc` PASS：真实固件的菜单确认、BASIC CPU 路径 640→800→640 的完整帧扫描、
  FPGA 路径下 800×600 全屏填充与切换、KEY3 退出恢复、ADVANCED KEY2 透明度 0→2。
  BASIC 流程共 4 次模式请求；菜单和高级展示不产生模式请求，没有前台页写入、显示欠载或读错误。
  见 `reports/simulation_resolution_soc.log`，0 errors / 0 warnings。
  本机运行约 18 分钟；进行中可查看 `reports/resolution_soc_progress.log`。

SoC 联合仿真使用真实 Sapphire 核、当前 `animation.bin` 和 DDR 模型；素材为保留真实首帧的
紧凑测试素材，应用和素材预装到 DDR。该测试覆盖菜单/BASIC/ADVANCED 的按键流程，
不代表 SPI Flash 实物加载、LVDS 电气信号或显示器兼容性验证。

Efinity 启动时现有 Anaconda 环境提示 `ModuleNotFoundError: conda`，未阻断其后四个编译阶段。
固件链接器保留现有 RWX segment 警告；本次 C 编译开启 `-Wall -Wextra -Werror`。
上板文件位于 `releases/basic_resolution_20261005/`；实板显示和按键验收尚未执行。
