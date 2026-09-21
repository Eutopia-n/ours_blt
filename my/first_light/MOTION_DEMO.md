# 第四阶段：连续动画与 CPU/HW 对比

日期：2026-09-21。保留前一版双缓冲 RTL、DDR/PLL/引脚，仅扩展 C 程序、测试与构建入口。不自动下载 FPGA，不写 SPI Flash。

## 现在能看到什么

- 640×480 RGB565 画面内有 32 个 32×32 彩条方块，持续往返移动。
- 左上角为 CPU FPS / US，右上角为 HW FPS / US；白字表示当前模式，灰字保留另一模式最近的统计。尚未采样时显示 -，不是 0 FPS。
- 默认先 CPU，每 4 秒自动切换 CPU/HW；每次切换重置场景帧号。串口发送小写 c 或 h 可提前切换，不会关闭自动轮换。
- 每 4 个已确认提交帧更新一次统计并输出一行串口数据。两个模式不是同时绘制，灰色值也不是当前模式的即时值。

本阶段已具备基础演示闭环：RISC-V C 程序、硬件 Fill/Copy、AXI DDR、连续双缓冲、HDMI、CPU/HW 屏幕对比。仍须实板验收；没有实现 Alpha、Color Key、互动游戏、独立资源区/跨页图像搬运，也没有测出最大 Sprite 数量。

## 比较为什么可信

两种模式每帧做相同工作：整页清屏，画同一个三色源块，再从源块拷贝 32 个 Sprite。坐标、大小、颜色、图层顺序、双缓冲和文字叠加相同。

CPU 路径使用 volatile RGB565 逐像素读写，是符合赛题背景的朴素 C 基线，不声称代表高度优化的 memcpy/CPU 极限；它不调用硬件 Fill/Copy。硬件路径每帧发 4 个 Fill 和 32 个 Copy 命令，逐条等待完成。两者的统计文字均由 CPU 绘制。源块位于后台页 (0,64)，这是当前引擎同页地址限制下的最小 Demo，不是通用纹理资源系统。

计时使用官方 SoC CLINT 的 mtime 低 32 位，100 MHz。该核读取 mcycle 会异常，所以不使用它。无符号差值支持计数器回绕；单个计时区间远小于约 42.95 秒的回绕周期。

~~~text
US = 最近 4 帧场景渲染总 tick / 400
FPS = 400000000 / 最近 4 次完成换帧的总 tick
~~~

US 包含清屏、源块生成、32 次拷贝、命令提交/等待及最终内存同步；不含文字绘制和等待垂直消隐。FPS 包含文字、换帧等待和循环开销，使用整数截断；第一组还受启动阶段影响，实板记录建议等两轮切换后再取值。约 60.01984 Hz 仅是 HDMI 时序刷新率，不是写死的 FPS。两个模式都达到显示刷新上限时，比较 US 仍能体现渲染速度差异。仿真 DDR 时延不是真实 DDR 性能，仿真数值不能用于比赛报告的实测加速比。

## 缓存与内存同步

实际生成的 Sapphire DataCache 是 write-through。硬件写像素不更新 CPU 缓存，所以 CPU 绘制前执行官方支持的 .word 0x500f 失效操作。

官方通用 BSP 另有 CSR 0x810 刷新接口，但当前 reduced CSR 核没有实现，联合仿真证实会触发 cause=2，不能使用。publish_pixels() 用 fence、缓存失效和一次强制 DDR 读回替代：当前 BmbToAxi4SharedBridge 对同一来源的读写方向切换设置 hazard，在先前写响应全部返回前不发出后续读。读回完成后再提交显示页。因此不是仅靠 fence 或固定延时猜测写入完成。若以后更换 CPU/缓存/总线配置，必须重新核对这一保证。

wait_render() 合并两个驱动的完成/超时轮询；cpu_fill()/cpu_copy() 是软件基线；scene() 统一场景；text_at()/decimal()/hud() 生成屏幕统计；publish_pixels() 确保像素对显示端可见。未修改硬件接口。固件通过 LTO 消除多余代码，链接器继续保留至少 512 字节栈空间。

## 编译与仿真

在仓库根目录逐步执行，任一步失败时停止并查看 reports 日志：

~~~powershell
python my\first_light\tools\build.py firmware
python my\first_light\tools\build.py sim
python my\first_light\tools\build.py sim-soc
python my\first_light\tools\build.py compile
~~~

sim 保留 Fill/Copy/双缓冲回归；sim-soc 使用真实 Sapphire 核执行正式固件，模拟串口 h/c 实现 CPU→HW→CPU，独立逐像素校验场景、整帧扫描、页面归属与换帧边界，并验证两类计时输出。DDR 端包含确定性反压。测试不会修改 CPU 时间或用测试专用固件伪造性能。4 秒自动轮换需在实板长时间观察；短联合仿真通过串口提前切换，不声称验证过完整自动轮换周期。

reports/motion_1.png、motion_5.png、motion_9.png 来自仿真的实际扫描像素，不是屏幕照片。最终验证结果与文件哈希在本页后续验收记录中列出。

## 下载与验收

1. 沿用已成功的 Efinity Programmer JTAG 临时配置流程，加载本版 first_light.bit；C 固件已嵌入，无需另烧程序。
2. HDMI 仍接原 TX。USB 串口沿用已确认端口，115200、8N1，发送模式选择 ASCII/文本，不要发送字面十六进制字符串。无需猜测或修改任何引脚。
3. 等约 10 秒，确认两列均出现数字、白字列约每 4 秒交替、方块连续移动，模式切换时位置重置属于设计行为。
4. 可分别发送小写 h、c，确认对应列变白。至少观察 1 分钟有无黑线、错色、撕裂、停止或 FAIL/TRAP。
5. 记录两轮之后的 CPU/HW FPS 与 US 和板上环境；尚未上板测得的性能不要填入报告。

串口格式（尖括号内容是现场测量值，不是固定数字）：

~~~text
Ti60 MOTION 32 CPU/HW
CPU FPS <每秒完成帧数> US <平均渲染微秒数>
HW FPS <每秒完成帧数> US <平均渲染微秒数>
~~~

| 现象 | 下一步具体检查 |
|---|---|
| 仍是静态方块或旧 PASS | 核对所选 bitstream 时间/hash；不要误用 double_buffer 归档 |
| 初始某列是 - | 等待至少一次该模式的 4 帧采样；另一列未运行前保留 - 是正常现象 |
| 两列 FPS 相近 | 看 US；显示刷新上限和垂直消隐等待会限制最终 FPS |
| 只有启动行，不再更新 | 先保留完整串口日志；检查 DDR 校准、总线响应与 TRAP；回退旧归档判断板级链路 |
| FAIL fill/copy/present | 查看 GFX STATUS 的 busy/error/underflow/read error/swap pending；不要继续强制提交 |
| 黑线或持续闪烁 | 记录当前模式，检查 STATUS bit4/bit5、显示读仲裁和 DDR 响应；不要先改 HDMI 引脚 |
| 串口命令无反应 | 确认 ASCII 小写 h/c、115200 8N1、同一块板的串口；命令在下一帧边界处理 |

旧版回退文件位于 releases/double_buffer_20260921/。旧源码为 software/double_buffer_demo.c，旧联合测试为 sim/tb_soc_double_buffer.sv；重新构建时 firmware 和 sim-soc 两步都加 --demo double-buffer。恢复本版时重新执行默认 firmware 再 compile，不能只改 GUI 工程名或 compile 的参数。

## 编译验收记录

- 固件编译通过：text=3312、data=4、bss=24，共 3340 字节。片内 RAM 剩余 756 字节，链接脚本的至少 512 字节栈约束保持。保留片内 RAM 的 LOAD 段 RWX 提示。
- 模块回归通过：33 组非均匀拷贝，奇数像素/重叠/4 KB 边界/错误恢复，显示与 Copy 并发，10 个完整帧、5 次换页确认；Errors=0、Warnings=0。
- 真实 RISC-V 联合仿真通过：5 个 CPU 场景帧、4 个硬件场景帧，CPU→HW→CPU，9 次换页确认；扫描检查 8 个完整 A 页帧与 8 个完整 B 页帧。场景逐像素一致、无前台页写入、无扫描像素错配，UART 两类计时均正确输出。模拟时间 333.265 ms，SOC TEST PASSED，Errors=0、Warnings=0。日志为 reports/simulation_soc.log。
- 本次行为仿真的首组输出为 CPU FPS 19 / US 35948、HW FPS 60 / US 4370，仅证明正式计时代码和屏幕统计运行，不代表开发板实测性能；首组也包含启动/切换影响。
- Efinity 全流程 map/interface/pnr/pgm 均 PASS。pgm 仅生成 bitstream，不表示已经下载到开发板。
- 资源保持 XLR 18685/60800、Memory Blocks 82/256、DSP 4/160。最小 setup slack +0.315 ns、hold slack +0.026 ns，仅针对现有 SDC 受约束路径。
- 官方接口仍有 GPIOR_P_09 与 HDMI tmds_clk 相邻的噪声耦合告警。原厂网表及未使用端口提示保留，不宣称全工程零告警。
- outflow/first_light.err.log 为追加式历史文件，开头仍有 9 月 18 日首次构建的 include 错误；本次 9 月 21 日 13:24:14 的区段没有新增错误，当前结果以本轮 compile.log 和报告时间为准。

本次 bitstream 生成时间为 2026-09-21 13:27:18，大小 2004387 字节，SHA256 为：

~~~text
2720C8BF140B795FD6AE7EE38947468FBC1488214422F5A8A110DBFE17E466CA
~~~

2026-09-21 用户反馈了一组实板显示值：CPU FPS 20 / US 36202、HW FPS 60 / US 4778。该记录来自用户读数，未由工具独立采集；观察时长、波动范围及下载文件哈希未另行核验。长时间自动轮换和 HDMI/DDR 电气稳定性仍不能仅凭这组读数判定。

| 模式 | 屏幕 FPS | 场景渲染耗时 |
|---|---:|---:|
| CPU 逐像素基线 | 20 | 36202 μs = 36.202 ms |
| 硬件 Fill/Copy | 60 | 4778 μs = 4.778 ms |

根据本组读数，最终帧率为 CPU 模式的 3 倍，场景渲染加速比为 36202/4778≈7.58 倍，渲染耗时减少约 86.8%。结论仅适用于当前 Demo 和该组观测，不代表其他负载、优化 CPU 基线或 Sprite 数量极限。US 不含文字绘制和等待换帧，因此不能用 1000000/US 直接代替屏幕 FPS。硬件 60 FPS 与当前约 60 Hz 的显示/换帧上限一致，尚不构成长时间稳定 60 FPS 的证明。

本版下载文件、固件、源码快照、报告及三张扫描预览已归档到 releases/motion_20260921/。优先从该归档选择 first_light.bit，避免后续构建覆盖 outflow 后误用其他版本。上一版归档未覆盖。
