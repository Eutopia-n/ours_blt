# 第二阶段：硬件 Block Copy

> 历史记录：本文件对应 2026-09-21 11:41 的单页 Block Copy 版，用户已确认上板显示正常。对应文件保留在 `releases/block_copy_20260921/`。当前双缓冲版本见 `DOUBLE_BUFFER.md`；当前 `outflow/` 和 `reports/` 会被新版构建更新，本文历史数字不代表当前产物。

## 结论与范围

在已经上板显示正常的第一版工程上，增加了 RISC-V 驱动的 RGB565 图像块拷贝。源和目标都在当前 DDR framebuffer 内，行距固定为 1280 字节。保留纯色填充和原 HDMI 引脚、时钟、DDR 控制器配置。

本历史版本完成的是拷贝增量，不包含双缓冲、独立图像资源区、不同源/目标行距、动态 Demo 和 CPU/HW FPS 对比，不能据此宣布全部基础要求完成。

## 改了哪里，为什么这样做

| 文件 | 改动与作用 |
|---|---|
| `rtl/fill_engine.v` | 保留模块名和原填充流程；新增读一行、缓存、按目标对齐写一行的拷贝状态机 |
| `rtl/render_regs.v` | 新增 OPERATION 和 SRC，原寄存器偏移保持兼容 |
| `rtl/render_subsystem.v` | 新增显示扫描/图像拷贝的 AXI 读通道仲裁 |
| `software/render.h` | 新寄存器定义与 `copy_rect()` API |
| `software/main.c` | 新增 `copy_rect()`、彩条源图与复制图案、CPU 全帧校验 |
| `sim/tb_render.sv` | 非均匀图像、奇偶对齐、重叠、错误恢复和显示并发验证 |
| `sim/tb_soc.sv` | 验证真实 CPU 下发填充与拷贝，并独立统计 CPU 校验读取 |

拷贝使用两组 512×16 位同步 RAM 保存原始源数据，总容量 2048 字节，可容纳一行最多 640 个 RGB565 像素及首尾对齐数据。先读完一行再写入目标，避免同一行重叠时把尚未读取的源像素覆盖。目标地址大于源地址时从最后一行往上复制，反之从第一行往下复制，处理跨行重叠。

AXI 每个读写 burst 最多 16 个 32 位 beat；读和写分别在 4 KB 边界拆分。目标首尾像素未填满一个 32 位字时，用 WSTRB 保护相邻像素。不同奇偶 X 由同步 RAM 读地址和半字排列处理，不要求源/目标地址都按 4 字节对齐。

显示扫描和拷贝会同时请求 DDR 读取，因此不能简单根据“当前是拷贝状态”切换数据线。仲裁器在发出 ARVALID 前锁定请求者，并保持到该 burst 的全部数据被接收；只有在事务之间才切换，显示请求优先。这样可避免显示数据进入拷贝缓存，也保证等待期间 AXI 地址稳定。

遇到拷贝 RRESP 错误时，硬件接收完当前已承诺的 burst，再终止命令，不写入出错行。已经完成的较早行不会自动回滚；B 错误也不会回滚已发送的数据。若从设备永久不返回数据，软件超时只能报告故障，不能撤销 AXI 事务，需定位总线/复位问题。

## 软件接口

```c
int copy_rect(uint32_t src_x, uint32_t src_y,
              uint32_t dst_x, uint32_t dst_y,
              uint32_t width, uint32_t height);

/* 将左下方 129×97 的彩条复制到右侧。 */
if (copy_rect(31, 301, 211, 321, 129, 97) != 0) {
    /* 根据工程习惯报告错误；本 Demo 输出 FAIL block copy。 */
}
```

坐标是 640×480 framebuffer 的像素坐标；宽高必须非零、源和目标矩形都不越界。函数返回 0 表示最终 AXI 写响应已完成；-1 为参数错误，-2 为忙碌，-3 为硬件错误，-4 为 1 秒超时。不要把负值当作“已经完成拷贝”。

CPU 只配置寄存器；像素读取和写入由 FPGA 完成。Demo 使用硬件填充创建源图像，因此没有 CPU 缓存中的脏像素。以后若用 CPU 向 DDR 写图像，必须在启动硬件前 clean 相应数据缓存；仅加 `volatile` 或 `fence` 不等同于把脏 cache line 写回 DDR。

新增寄存器（APB 基址仍是 `0xF8100000`）：

| 偏移 | 名称 | 含义 |
|---|---|---|
| 0x30 | OPERATION | 0=Solid Fill，1=Block Copy；其他值产生 APB 错误 |
| 0x34 | SRC | 源像素的 DDR 字节地址，要求 2 字节对齐 |

COMMAND 仍是偏移 0x08 写 1 启动。DST/WIDTH/HEIGHT/STRIDE 复用原寄存器，COLOR 在拷贝时不使用。STATUS bit2 现在包含拷贝错误；bit4/bit5 仍专用于显示扫描。每次 `fill_rect()`/`copy_rect()` 都设置自己的 OPERATION，可以交替使用。

## 上板后应看到什么

复现本历史版时，用 Efinity Programmer 的 JTAG 临时配置方式加载 `releases/block_copy_20260921/first_light.bit`。构建过程不会自动下载，也不会写 SPI Flash。

原有红、绿、蓝矩形仍在；屏幕下部新增两块相同的三色图案，从上到下为青色、品红、黄色。左侧源图左上角为 (31,301)，右侧复制图为 (211,321)，均为 129×97 像素。右侧整块图案由一次 `copy_rect()` 生成。

串口设置为 115200、8N1，预期输出：

```text
Ti60: RISC-V -> AXI FILL/COPY -> DDR -> HDMI
PASS FILL/COPY: 307200 DDR pixels; enabling HDMI
VIDEO status=0x0000000A
```

参考图 `reports/sim_frame.png` 来自实际仿真像素输出。它只证明仿真结果，不替代本次新版上板检查。

纯填充回退版在 `releases/fill_verified_20260918/first_light.bit`。若只有三个矩形、没有两块彩条，检查是否下载了纯填充版。

## 如果新版本异常，下一步检查什么

| 现象 | 具体检查 |
|---|---|
| `FAIL block copy` | STATUS bit2、SRC/DST、OPERATION=1、AR/R 与 AW/W/B 是否完整握手 |
| `FAIL DDR pixel index=...` | 把索引除以 640 得到 Y，取模得到 X；重点检查彩条边缘像素、WSTRB 和源/目标半字对齐 |
| 复制颜色正确但上下顺序错误 | 源行地址、目标行地址和逆向行遍历；对照复制前源图 |
| 开启扫描后出现黑线 | STATUS bit4/bit5，以及读通道是否等前一笔 burst 完成后再换请求者 |
| 串口 PASS 但只有旧画面 | 确认 FPGA 下载文件路径和时间；C 固件已包含在新 bitstream，不能只改源码而沿用旧 bitstream |

本历史版仍是单 framebuffer，显示时写入新画面可能产生撕裂；双缓冲后续交付见 `DOUBLE_BUFFER.md`。

## 复现命令

在仓库根目录执行，各步成功后再继续：

```powershell
Set-Location 'S:\Ti60F225_DemoBoard_v4'
python my\first_light\tools\build.py firmware
python my\first_light\tools\build.py sim
python my\first_light\tools\build.py sim-soc
python my\first_light\tools\build.py compile
```

本阶段没有新增综合源文件，不需要重新生成板级工程。若手动执行 `prepare`，随后必须执行 `firmware`，因为准备脚本会重新导入官方初始化文件。

## 本次验收记录

日期：2026-09-21。以下数字来自本次源码、固件和完整 Efinity flow 的最终日志；历史 `VALIDATION.md` 中的资源数字仍只对应 2026-09-18 纯填充版本。

### 仿真与软件

- `reports/simulation.log`：渲染器测试通过。33 组非均匀图案的对齐、尺寸、重叠和读写错误恢复测试通过；随后完成彩条 Demo 拷贝和显示并发拷贝。报告显示 31842 个 burst、7612 个仲裁竞争周期，两个完整 HDMI 光栅帧通过，Errors=0、Warnings=0。
- 历史 CPU 联合仿真：7 次填充、1 次拷贝（485 个读 burst），CPU 以 9600 个 burst 读回 614400 字节（307200 个 RGB565 像素），全部校验通过，`SOC TEST PASSED`。
- 历史固件大小：`text=2499, data=0, bss=1, dec=2500`；4 KiB 片内 RAM 未越界。

### FPGA 编译

- `reports/compile.log`：`map : PASS`、`interface : PASS`、`pnr : PASS`、`pgm : PASS`。`pgm` 只生成配置文件，没有执行下载或写 SPI Flash。
- 历史配置文件：[releases/block_copy_20260921/first_light.bit](S:/Ti60F225_DemoBoard_v4/my/first_light/releases/block_copy_20260921/first_light.bit)，大小 2,014,581 字节，生成时间 2026-09-21 11:41:22；SHA256：`E922BA090E47A5057586AF1499EF795F8344A7880C803D285DDEB290DED7375B`。
- 历史布局资源：XLR 18,695/60,800（30.75%），Memory Blocks 82/256（32.03%），DSP Blocks 4/160（2.50%），Global Clocks 9/32（28.12%）。
- 历史时序通过：最小 setup slack +0.368 ns，最小 hold slack +0.026 ns；core_clk 100 MHz、DDR 400 MHz、HDMI 像素时钟约 25.209 MHz。
- `outflow/design_issue.xml` 仍有 1 条原板级引脚距离告警：DDR `GPIOR_P_09` 与 HDMI `tmds_clk` 相邻。该告警来自官方板级连接，本次未擅自改引脚，需上板同时运行 DDR 与 HDMI 后观察。

### 当前交付边界

本历史版的模块仿真、真实 CPU 联合仿真与完整编译通过，用户随后确认画面正常显示。该确认不等于长时间稳定性或游戏性能测试。双缓冲的新代码、验证和下载说明另见 `DOUBLE_BUFFER.md`。
