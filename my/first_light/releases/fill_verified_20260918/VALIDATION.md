# 第一个交付目标：离线验收记录

日期：2026-09-18。工作区：`S:\Ti60F225_DemoBoard_v4\my\first_light`。

**结论：工程、C 固件、两类功能仿真及 FPGA 完整编译已通过。开发板未连接，未进行下载、DDR 物理校准或显示器实测。**

## 1. 验证环境与产物

| 项目 | 实际使用 |
|---|---|
| FPGA 目标 | Titanium Ti60F225，I3 时序模型 |
| Efinity | 2026.1.132 |
| C 工具链 | Efinity 自带 riscv-none-elf-gcc 13.4.0 |
| 仿真器 | ModelSim SE-64 10.6e |
| 固件 | `software/build/first_light.elf`、`first_light.bin` |
| FPGA 配置文件 | `outflow/first_light.bit`、`first_light.hex` |
| 工程入口 | `first_light.xml` |
| 复现与排错说明 | `README.md` |

最终固件 `size` 结果：text=1839、data=0、bss=1 字节，总计 1840 字节；片内 RAM 4 KiB，链接脚本保留至少 512 字节栈。相关日志：`reports/firmware.log`、`reports/firmware_size.log`。

## 2. 渲染模块仿真：通过

入口：`python my\first_light\tools\build.py sim`。日志：`reports/vlog.log`、`reports/simulation.log`。

- 非法零宽度和显存越界命令不产生 AXI 写请求。
- 奇数 X 的单像素填充只修改目标半字，不覆盖相邻像素。
- 注入 AXI B 错误能上报，并可通过下一条合法命令恢复。
- 硬件绘制深灰背景与红、绿、蓝矩形，逐一检查全部 307200 个 DDR 像素。
- 连续两个完整有效帧逐像素匹配；每行 640 个有效像素，共 480 行。
- 显式断言行周期 800 个像素时钟、帧周期 420000 个像素时钟、HS 低电平 96 个时钟、VS 低电平 1600 个时钟。
- 随机 AXI 等待，检查写入 WLAST、最大 16 beat 和不跨越 4 KB 边界；写测试共执行 11016 个 burst，覆盖边界拆分。
- 注入 AXI 读错误后状态寄存器报告读错误。

最终输出：`ALL TESTS PASSED`，Errors: 0，Warnings: 0。仿真时长约 51.978 ms，墙钟耗时约 4 秒。

`reports/sim_frame.png` 来自该仿真的实际像素输出，已核对为深灰背景上的三个矩形。它不是板上截图，也不是软件重新绘制的参考图。

## 3. 真实 CPU 与固件联合仿真：通过

入口：`python my\first_light\tools\build.py sim-soc`。日志：`reports/vlog_soc.log`、`reports/simulation_soc.log`、`reports/soc_progress.log`。

采用官方 Sapphire 的 ModelSim 专用模型；CPU、指令/数据缓存、APB 桥、DDR 仲裁器和 32→128 位转换器均参与仿真。仅在 DDR 控制器的 128 位 AXI 接口处使用行为内存，未模拟 DDR PHY 的电气行为或训练过程。

实际结果：

```text
PASS: real RISC-V executed embedded firmware, 4 fills, CPU DDR verification (9600 read bursts)
PASS 307200 DDR pixels verified; enabling 640x480 HDMI
SOC TEST PASSED
Errors: 0, Warnings: 0
```

CPU 发出了 4 条填充命令，CPU 读回累计 614400 字节、9600 个读 burst；固件自身逐像素比较全部通过，然后打开显示。仿真还等待实际出现有效显示像素，并检查无扫描错误。总仿真时间约 134.762 ms，墙钟耗时约 2 分 29 秒。

联合仿真用于证明软件、总线和扫描链路连接有效；连续两帧的逐像素与同步检查由上一节专门完成。DDR 行为模型的读写速度不是实板 DDR 性能，不能据此计算比赛加速比或宣称 60 FPS 游戏性能。

联合仿真发现并修复了一个关键问题：原计时代码读 `mcycle` 时触发 cause=2 的非法指令异常。最终固件改用官方 CLINT 的 MTIME 低字，地址来自 `soc.h` 与官方 `clint.h`。上述通过结果使用的是修正后的固件。

## 4. FPGA 完整编译：通过

入口：`python my\first_light\tools\build.py compile`。日志：`reports/compile.log`。

```text
map       : PASS
interface : PASS
pnr       : PASS
pgm       : PASS
```

最后一次编译包含修正后的 CLINT 固件。`pgm` 为配置文件生成步骤，本次没有调用 Programmer 下载。

资源使用来自 `outflow/first_light.place.rpt`，包含 CPU、DDR 控制器、渲染器及 HDMI 编码器的整体用量：

| 资源 | 使用 / 总量 | 比例 |
|---|---:|---:|
| XLR | 17581 / 60800 | 28.92% |
| Memory Blocks | 80 / 256 | 31.25% |
| DSP Blocks | 4 / 160 | 2.50% |
| Global Clocks | 9 / 32 | 28.12% |

资源余量可供后续功能使用，但不能直接据此推断 Alpha 或复杂游戏能容纳的 Sprite 数量。

## 5. 时序与接口检查

最终布局布线报告：`outflow/first_light.timing.rpt`，生成时间 2026-09-18 15:06:00。

| 时钟域 | 目标频率 | Setup slack | Hold slack |
|---|---:|---:|---:|
| core_clk | 100 MHz | +4.091 ns | +0.026 ns |
| sdram_clk | 400 MHz | +0.403 ns | +0.098 ns |
| rx_cal_clk | 400 MHz | +0.470 ns | +0.028 ns |
| tx_cal_clk | 400 MHz | +0.403 ns | +0.091 ns |
| tx_cal_clk_90edge | 400 MHz | +0.384 ns | +0.072 ns |
| HDMI 像素时钟 | 约 25.208333 MHz | +35.496 ns | +0.090 ns |

这些数值对应当前 SDC 中已约束路径；跨时钟路径采用异步组约束，时序通过不替代跨时钟握手的功能验证。`outflow/first_light.cdc.rpt` 报告无同步器告警，也不等同于形式化 CDC 证明。

HDMI PLL：25 MHz 参考，局部反馈分频 121，VCO 3025 MHz；像素输出 /120、串行器半速时钟 /24，分别约 25.208333 MHz、126.041667 MHz。串行时钟相移设置 4，对应 30°、约 0.661 ns，外设检查通过。采用偶数输出分频消除了串行时钟占空比失真告警。

## 6. 已知告警与未验证内容

1. **板级引脚距离告警保留。** `outflow/design_issue.xml` 仅剩一条外设告警：DDR 时钟 `ddr_ck` 使用的 `GPIOR_P_09` 与 HDMI 的 `tmds_clk` 相邻，工具提示潜在噪声耦合。二者来自原板连接，不能擅自换脚。是否在实板上影响 HDMI/DDR 稳定性尚不确定，需在两者同时运行时观察校验、欠载与显示稳定性；必要时结合原理图及板厂建议处理。
2. 官方 DDR/SoC RTL 仍有裁剪、未使用端口和可综合性提示等警告；本记录不宣称 FPGA 编译零告警。手写渲染模块及 CPU 联合功能仿真的最终结果均为零错误、零告警。
3. 固件链接器提示 RAM 的 LOAD 段具有 RWX 权限。本阶段代码与数据共用片内 RAM，没有配置 MMU/PMP 分区；该提示已记录。
4. Efinity 的部分 `outflow/*.log` 会追加保存之前失败尝试，应按最后一次运行的时间区分历史内容；`reports/compile.log` 和两份 `reports/simulation*.log` 为最终覆盖保存的结果。
5. 未连接开发板，未验证 DDR 训练、电源/复位、物理 HDMI 链路、显示器兼容性、串口实际输出或长时间运行。TMDS 使用官方编码器，仿真主要验证编码器前的像素及同步信号，不包含 HDMI 线缆和模拟电气模型。
6. 本阶段没有双缓冲、图像拷贝或 FPS 对比，不能作为全部基础要求验收通过的证明。

下一步上板预期及逐项排错方法见 `README.md` 第 7 节。首先验收当前静态闭环，再扩展 Block Copy 和垂直消隐期的双缓冲切换。
