# 77 帧横移动画：制作、上传和验收

本版使用用户提供的 1078×1432 白底原图提供人物颜色，按每行从左到右、逐行向下的顺序播放 7×11 帧。第 6 行的四个独立球棒画面保留为第 36～39 帧（从 1 开始计数）。较小的透明图只辅助确定轮廓；DDR 内保存原图颜色量化后的 RGB565 像素，轮廓外统一是精确的 `0xF81F`。品红色本身**不透明**；只有启用 BitBlt 键控时，写字节选通才使背景留在画面中。

## 重新生成素材

在本目录运行：

```powershell
python tools/make_sprite77.py
```

需要 Pillow、NumPy、SciPy。脚本读取 `assets/sprite77_original.png` 与 `assets/sprite77_alpha_reference.png`，自动按已测量的 7×11 单元定位人物、缩放约 80%、修补白色手套与衣物、裁去轮廓外像素，然后生成：

- `assets/sprite77.raw`：1 MiB DDR 资源区内的解压后图像，含 16 字节头、77 个 8 字节的帧表和 RGB565 像素；每帧保存源偏移、实际宽高和绘制锚点。
- `assets/sprite77.upload`：串口上传包，透明像素游程压缩，附长度与 CRC32。
- `assets/sprite77_key_on.png` 和 `assets/sprite77_key_off.png`：77 帧的深色背景预览，分别模拟 KEY1 开与关。可以放大检查每个编号，尤其是白色手套、衣物与第 9 行拖尾。后者出现品红矩形是预期效果。

脚本先尝试统一 80% 缩放，超出 1 MiB 才整体改为 75%。当前生成物为 **964632 字节 DDR 素材**、**394401 字节串口素材**，CRC32 为 `0x4E2279B2`。每帧轮廓和颜色都在同一 RGB565 数据中；KEY1 开关只改变绘制规则，不需换一份图。

## 固件和内存布局

片内 RAM 仅 4 KiB，故引导程序放在片内 RAM，动画程序和素材从 UART 装入 DDR。这是固件大小约束下的两级启动方案，同一份 bitstream 足以演示两种 KEY 状态和 CPU/HW 两种绘制方式。

| DDR 地址 | 用途 |
|---|---|
| `0x01000000` | Framebuffer A，614400 字节 |
| `0x01096000` | Framebuffer B，614400 字节 |
| `0x01200000` | 1 MiB Sprite 素材资源区 |
| `0x013FFFF0` | 动画程序有效性、大小、校验值标记 |
| `0x01400000` | 动画程序，最多 64 KiB |

引导程序的镜像大小为 1823 字节，片内代码加数据占用 2847 字节，低于保留栈后的 3584 字节上限。动画程序通过 `software/link_ddr.ld` 链接，在 DDR 执行；`software/main.c` 仍使用原有 APB BitBlt 寄存器与 AXI/HDMI 链路。冷启动时 UART 输出 `ASSET READY`，收到完整 `S77B` 包后先写 DDR，再校验上传数据与 DDR 回读的 CRC32，最后设置有效性标记并输出 `ASSET OK`。校验或传输失败会输出 `ASSET ERR`，下一次 `ASSET READY` 可重试。若复位后 DDR 保留且 CRC 验证通过，会输出 `ASSET CACHED` 并直接启动。

## 运行

先生成素材，然后编译固件和 FPGA：

```powershell
python tools/make_sprite77.py
python tools/build.py firmware --efinity C:/Efinity/efinity-riscv-ide-2026.1
python tools/build.py sim --modelsim D:/modelsim/win64
python tools/build.py sim-key --modelsim D:/modelsim/win64
python tools/build.py sim-soc --modelsim D:/modelsim/win64
python tools/build.py sim-boot-uart --modelsim D:/modelsim/win64
python tools/build.py compile --efinity C:/Efinity/2026.1
```

用 Efinity Programmer 下载 `outflow/first_light.bit`。每次冷启动后，选实际串口 COM 号运行：

```powershell
python -m pip install pyserial
python tools/upload_sprite77.py --port COM15
```

串口为 115200 8N1。上传总量约 399 KiB，线速传输至少约 35 秒；脚本等待板子响应与 DDR 校验。不要在上传期间断电。运行时 KEY1 每按一次切换键控；CPU/HW 每 4 秒交替，小写 `c`/`h` 可直接选；屏幕显示 FPS、耗时、分辨率、KEY 状态与 `FRAME 1`～`FRAME 77`。人物从左向右移动，至最右侧回到左侧；动作目标频率为 12 帧/秒。硬件达不到 12 帧/秒时，实际速度受渲染和换页时间限制，以屏幕 FPS 和串口输出为准。

### 上传脚本一直等待时

在 PowerShell 运行 `python tools/upload_sprite77.py --list-ports`，先找到开发板 Type-C USB 对应的 FT4232 串口。2026-09-27 本机的板载 UART 是 COM15；断开重连后端口号可能变化，不要照抄示例。使用同一个 Python 执行 `python -m pip install pyserial`。随后下载本版 bitstream、给板子上电，再用实际 COM 号运行上传脚本；脚本会显示端口列表、等待提示、传输进度或明确的超时错误。

VS Code 的“运行 Python 文件”按钮只执行脚本路径，不会附加 `--port`。如果终端显示 `the following arguments are required: --port`，脚本尚未访问开发板；改在 PowerShell 手工执行带 `--port COMx` 的命令。

片内引导程序会反复发送 `ASSET READY`，上传脚本在收到它之前不会发送素材。如果板子已经连接且选对 UART，却始终收不到该提示，检查 bitstream 是否已加载、FT4232 驱动和 DDR3 初始化；本工程的 Sapphire 核在 DDR3 `cal_done` 有效后才解除复位。板卡说明书确认板载 Type-C/FT4232 同时负责供电、下载和 UART，UART 的 FPGA 管脚是 RX=`GPIOL_02`、TX=`GPIOR_28`；工程引脚约束与其一致。

## 本次验证结果（2026-09-27）

- 素材包含 77 个有效帧表项，最宽 113 像素、最高 108 像素；表项边界、`AS77` 版本、CRC32 和上传 RLE 解码均校验通过。964632 字节素材距 1 MiB 上限仍有 83944 字节。
- `python tools/test_sprite77_upload.py` 的 4 项测试通过，覆盖错误校验、传输中断后的重试、有效 DDR 缓存跳过上传和损坏压缩数据的拒绝。`sim-boot-uart` 在真实 Sapphire 模型中验证了坏 CRC 拒绝、重新上传成功与复位后缓存启动。
- 渲染仿真与 KEY1 消抖仿真通过。`sim-soc` 让真实 RISC-V 固件执行 CPU→HW→CPU，检查第 1、39、77 帧及回绕、KEY1 开/关、两页换页、HDMI 完整扫描、资源区不被清屏覆盖，并验证 Sapphire 32→128 位桥接后的全透明及部分透明写掩码；模型报告 CPU 20 FPS、HW 60 FPS。这些数值是仿真观察，不代表开发板实测。
- 片内引导镜像 1823 字节，片内代码/数据/BSS 共 2847 字节，低于 3584 字节上限；DDR 动画程序镜像 4344 字节。Efinity 完整编译 `map/interface/pnr/pgm` 均通过，最小 setup slack 为 **+0.339 ns**。

日志和仿真扫描图在 `reports/`，固定上板包在 `releases/sprite77_20260927/`。图像是仿真输出，尚不是开发板拍摄画面。

## 板级验收记录（2026-09-27）

板载 FT4232 的 UART 通道 C（`MI_02`）改用 FTDI VCP 驱动后出现 COM15。Python 3.13/pyserial 3.5 上传 398757 字节，耗时 34.4 秒；板端依次返回 `ASSET READY`、`ASSET OK`。后续 10 秒 UART 采样记录在 `reports/board_uart_20260927.log`：CPU 27 次报告均为 20 FPS、绘制耗时中位数 34795 μs；HW 68 次报告均为 60 FPS、中位数 4168 μs；未收到 `FAIL`，自动 CPU/HW 交替持续运行。这是实板 UART 观测，不是仿真数据。

用户在 HDMI 显示器上确认了人物从左向右移动的 77 帧动画，以及 KEY1 在去背与品红矩形之间切换。尚未留存实板视频或截图，状态错误位也未单独读出；比赛提交前建议拍摄一轮完整动作和 KEY1 对比，重点确认第 9 行拖尾与白色区域。


