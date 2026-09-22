# 独立 DDR 图片资源区拷贝

日期：2026-09-22。基于已验证的分辨率显示 + 写 FIFO 版本，增加独立图片资源区、源行距、C 驱动与对应测试。不修改板级引脚、PLL、DDR 参数或像素时序。

## 地址布局与依据

| 区域 | 起始地址 | 最后一个字节 | 大小与用途 |
|---|---|---|---|
| Framebuffer A | 0x01000000 | 0x01095FFF | 614400 字节，640×480 RGB565 |
| Framebuffer B | 0x01096000 | 0x0112BFFF | 614400 字节，640×480 RGB565 |
| 图片资源区 | 0x01200000 | 0x012FFFFF | 1 MiB，存放独立 RGB565 图片 |
| Demo 图片 | 0x01200000 | 0x012007FF | 2048 字节，32×32，每行 64 字节 |

地址选择依据本机原厂依赖 `vendor/ddr3_controller/ddr3_parameter.vh`：ROW_WIDTH=14、COL_WIDTH=10、BANK_WIDTH=3、DQ_WIDTH=16、RANKS=1，对应 2^(14+10+3)×2=256 MiB；控制器 AXI_ADDR_WIDTH=28。`rtl/competition_top.v` 将 CPU DDR 地址低 28 位连到控制器，不能把高地址别名当作更多物理内存。`software/soc.h` 的 SYSTEM_DDR_BMB 译码窗口覆盖本次所选地址，但该译码窗口大小不等于物理 DDR 容量。

当前正式固件及栈位于 0xF9000000 的 4 KiB 片内 RAM，无 DDR 堆或其他图片分配器；资源区与两页显存互不重叠。以后接入系统堆、操作系统或 DDR 程序时，必须在内存布局中继续保留这三个区域。

## 为什么需要源行距

显存每行有 640 个像素，所以行距为 1280 字节；32×32 图片只需每行 64 字节。若读取图片时仍固定跳过 1280 字节，第二行起就会读错位置。因此目标行距保持 1280，源行距独立设置。

APB 基址仍为 `0xF8100000`。新增 `SRC_STRIDE`，偏移 `0x4C`、32 位读写，复位值 1280，单位字节。渲染忙时禁止写入。旧固件不写新寄存器也保持原先 1280 字节行为；新的 `copy_rect()` 每次明确恢复 1280，避免前一条资源拷贝留下 64。

源支持两类范围：所选绘制页内（行距必须 1280），或上述资源区（行距为 WIDTH×2～65534 的偶数）。目标只允许在所选绘制页内，源地址及目标地址必须两字节对齐，宽 1～640、高 1～480。非法参数置 DONE+ERROR，且不发起 AXI 读写。

资源区对 BitBlt 引擎只读，CPU 可以在启动时上传。源终点计算使用 33 位加法并检查完整行距值，防止地址回绕或高位截断绕过范围检查。源和目标不同的资源拷贝按行向下推进；旧同页拷贝继续按地址选择方向并缓存整行，保持重叠语义。源行距为 2 mod 4 时，每行重新计算半字位置与读取字数，支持紧密存放的奇数宽度图片。

16×37 位写 FIFO、最大 16-beat Burst、4 KiB 边界拆分、错误响应处理和显示读仲裁均保留。命令完成仍等待最后一笔 AXI B 响应。前台/后台页的所有权继续由双缓冲驱动管理：硬件限制目标地址属于 DRAW_PAGE，驱动只复用已经退役的前台页。

## 软件与 Demo

- `init_assets()`：启动时生成并上传一张 32×32 RGB565 三色图片，然后调用原有 `publish_pixels()` 排空 CPU 写操作。不会每帧重新上传。
- `copy_image(source, source_stride, dst_x, dst_y, width, height)`：检查参数，配置源地址、源行距和目标矩形，等待硬件完成。返回 -1 为参数无效、-2 为忙、-3 为硬件错误、-4 为超时，0 为成功。
- `copy_rect()`：保留原坐标接口与重叠拷贝行为，内部调用 `copy_image()`。
- `cpu_copy()`：软件基线逐像素读取同一张 DDR 图片。CPU 与硬件的坐标、清屏、绘制顺序、双缓冲、HUD 均相同。

例如，启动资源初始化完成后，可在当前绘制页绘制一张图片：

```c
int result = copy_image(ASSET_BASE, SPRITE_STRIDE, 100, 120, 32, 32);
if (result) fail("FAIL copy");
```

每帧为整页清屏 + 32 个 Sprite，硬件路径发出 1 个 Fill 和 32 个 Copy。原先 (0,64) 的固定源块不再绘制，因此它消失是正确现象。分辨率文字、FPS/US 显示、每 4 秒切换模式和串口小写 h/c 保留。新串口启动标识为 `Ti60 DDR ASSET 32 CPU/HW`。

资源上传不计入每帧渲染耗时，FPS 计时在初始化完成后开始。US 仍不包含 HUD 和换帧等待，FPS 包含这些开销。与旧版相比少了每帧源块生成，且源数据布局改变；只能在本版同一场景中比较 CPU/HW，不能把新旧 US 差异全部归因于某个单一硬件优化。图片为启动时生成的 RGB565 测试资源，当前不涉及图片文件解码。

## 验证与复现

```powershell
Set-Location 'S:\Ti60F225_DemoBoard_v4'
python my\first_light\tools\build.py firmware
python my\first_light\tools\build.py sim
python my\first_light\tools\build.py sim-soc
python my\first_light\tools\build.py compile
```

本轮固件编译通过：text=3280、data=4、bss=24，共 3308 字节；4 KiB 片内 RAM 留有 788 字节，至少 512 字节栈约束通过。LTO 会移除 Demo 未用到的驱动分支，今后扩大软件功能后需重新检查容量。

模块仿真已通过原有 33 组拷贝、Fill、FIFO、双缓冲和分辨率测试，并增加 58 组资源拷贝（另有显示运行期间 A/B 后台页各 1 组）：宽度 1/2/31/32/33/639/640、源/目标半字偏移、紧密/带填充行距、最大 65534 行距、640×480 图片、4 KiB 边界、资源区末端、错误响应与恢复。17 条非法命令检查源/目标越界、地址回绕、行距无效、尺寸无效，确认没有任何 AXI 事务。整块模拟内存与独立期望数据比较，同时检查资源和邻接像素不被修改。

真实 Sapphire 联合仿真已通过：资源只上传一次、实际写入 2048 字节；CPU 发起 160 笔资源区读取，硬件发起 4096 笔资源区读取；每次提交时图片内容保持不变。完成 CPU→HW→CPU，共 5 个 CPU 场景帧、4 个硬件场景帧、9 次换页确认，以及 A/B 页各 6 个完整扫描帧，无像素错配、前台页写入、混帧或显示欠载。`SOC TEST PASSED`，Errors=0、Warnings=0，模拟时间约 249.958 ms，日志实际运行时间 23 分 28 秒。

本轮仿真输出为 CPU 29 FPS / 26212 μs、HW 60 FPS / 4366 μs，仅用于验证实际计时代码运行。已检查 `reports/motion_1.png`、`motion_5.png`、`motion_9.png`：原固定源块消失、32 个运动块正常、RES WAIT 更新为 RES 640X480、模式颜色及统计正确。这些是仿真扫描预览，不是实板照片。完整日志、预览、源码、固件及下载文件已归档到 `releases/ddr_assets_20260922/`。

交付后用户反馈实板屏幕读数：CPU 30 FPS / 26220 μs，HW 60 FPS / 4778 μs，帧率比为 2 倍、场景渲染加速比约 5.49 倍。该读数来自用户反馈，工具没有独立采集串口、确认烧录文件哈希或记录波动范围，不能据此证明长期稳定性。原始观测与计时口径见 `releases/ddr_assets_20260922/BOARD_OBSERVATION.md`。

Efinity 2026.1.132 的 map/interface/pnr/pgm 全部通过。最终最小 setup slack 为 +0.361 ns、hold slack 为 +0.026 ns，核心时钟 100 MHz 路径 setup slack 为 +2.299 ns，均针对现有 SDC 受约束路径。资源为 XLR 19492、Memory Blocks 84、DSP 6；相比前一版增加 373 个 XLR、2 个 DSP，RAM 数量不变。新增乘法用于源地址范围计算，不代表实现了 Alpha 混合。

本机 bitstream 生成时间 2026-09-22 15:18:26，大小 2,034,591 字节，SHA256：`4CBAFA9A80B52268FE58F60773CBBC775F64174C413E3A0BA82588FCD84B40F0`。接口检查仍有原工程 DDR `GPIOR_P_09` 与 HDMI `tmds_clk` 相邻的噪声耦合告警。已有初始化/原厂网表提示保留，不宣称全工程零告警，也不以仿真替代实板 DDR/HDMI 稳定性验证。

## 下载与验收

本轮完成后使用 `releases/ddr_assets_20260922/first_light.bit`，沿用成功的 Efinity Programmer JTAG 临时配置流程。C 固件已经嵌入，无需单独下载。HDMI 仍接 TX，串口 115200、8N1。

1. 确认串口启动标识包含 DDR ASSET；画面有 32 个移动彩条块、CPU/HW 两列与 RES 640X480。
2. 左侧原固定源块应消失，运动彩条块仍正常；等待至少两轮自动切换，然后分别记录 CPU/HW 的 FPS 与 US。
3. 发送小写 h/c 验证手动切换，并观察至少一分钟是否有黑线、错色、撕裂、停止或 FAIL/TRAP。

| 异常 | 具体检查项 |
|---|---|
| 仍有旧固定源块或旧启动文字 | 核对下载路径和归档哈希，是否误选前一版 bitstream |
| 图片第二行起错色 | 读取 SRC=0x01200000、SRC_STRIDE=64、WIDTH=32、HEIGHT=32、STRIDE=1280 |
| 第一帧图片错误 | 查看启动上传是否完整；确认 write-through 缓存下 `publish_pixels()` 的失效与 DDR 读回已执行 |
| FAIL copy | 检查 STATUS bit2、源/目标范围、源行距及 RRESP/BRESP；资源区不能作硬件写目标 |
| FAIL present 或黑线 | 检查 STATUS bit4/5/7、DDR 校准、扫描仲裁和换页确认；先保存串口日志 |

上一版可从 `releases/fifo_resolution_20260922/` 回退；本轮修改前的全部相关源码、固件和报告备份在本机 `releases/pre_ddr_assets_20260922/`（不随 GitHub 上传）。本轮尚不包含 Alpha、Color Key 或高负载互动游戏。
