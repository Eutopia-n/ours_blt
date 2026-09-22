# 分辨率显示与 FIFO：本地同步记录

历史记录：本页对应队友 FIFO/分辨率更新同步时的状态。之后已增加独立 DDR 资源区，当前工程说明和新版下载文件见 `DDR_ASSETS.md`；本页旧版本的验证数据保持原样。

日期：2026-09-22。

## 同步来源与范围

来源：`https://github.com/Eutopia-n/ours_blt`，分支 `Real-time-resolution-reading-and-FIFO`，提交 `f6beb7ebe41c57e5eb324a293dea2dda63559f33`。

本次将队友更新同步到 `S:\Ti60F225_DemoBoard_v4\my\first_light`。同步前已比对本地 RTL、固件与测试，确认其与此前上传的 `f3e71bc` 版本相同。同步了功能源码、测试和构建脚本；补齐仓库内的官方 Sapphire ModelSim 模型。Efinity 工程只增加两个新 RTL 文件，保留本地已有编译配置、引脚与时钟约束。

未修改根目录已有 Git 暂存内容，未推送或合并 GitHub 分支；未执行队友分支中对根目录早期独立示例的删除操作。旧源码、固件、日志和 bitstream 已备份到 `releases/pre_fifo_resolution_20260922/`，之前的 `releases/motion_20260921/` 也保留。

## 改动与作用

| 位置 | 改动 | 为什么这样做 |
|---|---|---|
| `rtl/sync_fifo.v`、`rtl/fill_engine.v` | 新增并接入 16×37 位写 FIFO，每项保存 WDATA、WSTRB、WLAST | AXI 暂停接收时保存待写数据；连续预取行 RAM，减少拷贝 burst 内空拍 |
| `rtl/video_mode_measure.v` | 根据输出 DE、HS、VS 统计有效宽高 | 显示实际产生的画面尺寸，而不是在文字中写死数值 |
| `rtl/render_subsystem.v`、`rtl/render_regs.v` | 同步测量结果，新增 0x44/0x48 两个只读寄存器 | 让 RISC-V 安全读取像素时钟域的结果 |
| `software/render.h`、`software/main.c` | 新增寄存器定义与 `resolution_hud()` | 该函数读取分辨率并绘制 RES 文字；检测未完成时显示 RES WAIT |
| `sim/`、`tools/`、`first_light.xml` | 增加独立测试、整机检查和新源文件列表 | 保证命令行构建、仿真和 Efinity 使用同一套源码 |

现有 Fill、Copy、RGB565 半字处理、双缓冲和 CPU/HW 对比保持。分辨率测量针对 FPGA 输出，当前为 640×480；不读取显示器 EDID、不自动切换输出分辨率，也不是 HDMI 插拔检测。

寄存器基址 `0xF8100000`：偏移 `0x44` 的高 16 位是高度、低 16 位是宽度，640×480 对应 `0x01E00280`；偏移 `0x48` 的 bit0 表示最近完成的测量是否非空，空帧后会清零。

## 本机验证

- 固件编译通过：text 3500、data 4、bss 24，共 3528 字节；4 KiB RAM 剩余 568 字节，链接器的至少 512 字节栈约束通过。四个 RAM 初始化文件与队友提交逐一比对一致。
- FIFO 独立测试通过：顺序、满空边界、溢出拒绝、同时读写和清空。
- 分辨率独立测试通过：640×480、1×1、空帧。
- 渲染回归通过：33 组图案拷贝，奇偶对齐、重叠、4 KiB 边界、读写错误恢复、AXI 反压稳定性；10 个完整视频帧、5 次换页确认，无混帧和前台页写入；分辨率寄存器及只读保护通过。
- 总线持续就绪时，640×2 Copy 为 1720 个核心周期，burst 内 W 通道无空拍。这是仿真场景，不是板上测量。

- Efinity 2026.1.132 的 map/interface/pnr/pgm 全部 PASS。最终时序报告最小 setup slack 为 +0.205 ns、hold slack 为 +0.021 ns；此结论针对现有 SDC 受约束路径。布局阶段曾报告的负 hold slack 已由后续布线修复，不能把中间报告当成最终结果。
- 本机综合/布局报告：XLR 19119、Memory Blocks 84、DSP 4；旧动画版本分别为 18685、82、4。新增 FIFO 与分辨率逻辑增加了 434 个 XLR 和 2 个 Memory Blocks，未增加 DSP。
- 官方板级约束仍有 DDR `GPIOR_P_09` 与 HDMI `tmds_clk` 相邻的噪声耦合告警。未修改引脚。编译和行为仿真不能替代板上 DDR/HDMI 稳定性检查。
- 本机 bitstream 生成时间 2026-09-22 14:55:15，大小 2,029,632 字节，SHA256：`686ABDD804639D5AEAA894088F581CF6A5C3ADEFA082027D7FEA4658A72D7E40`。它是本机重新生成的文件，不使用队友文档中的旧哈希。

- 真实 Sapphire RISC-V 联合仿真通过：5 个 CPU 场景帧、4 个硬件场景帧，CPU→HW→CPU，9 次换页确认；A/B 页各 8 个完整扫描帧，无场景像素错配、前台页写入、混帧或显示欠载，`SOC TEST PASSED`，Errors=0、Warnings=0。模拟时间约 333.265 ms，实际运行 14 分 07 秒。
- 联合仿真输出为 CPU 19 FPS / 35948 μs、HW 60 FPS / 4383 μs，与队友记录一致。这仅验证计时代码，不是本机开发板实测；此前用户反馈的 CPU 20 FPS / 36202 μs、HW 60 FPS / 4778 μs 属于旧版观测，不能直接用两组数值计算本次更新的性能变化。
- 已检查实际扫描导出的 `reports/motion_1.png`、`motion_5.png`、`motion_9.png`：首帧 RES WAIT，随后 RES 640X480；CPU/HW 列颜色和统计显示正常。这些是仿真预览，不是显示器照片。

验收日志保存在 `reports/`，新版下载文件、源码、固件和本轮报告归档在 `releases/fifo_resolution_20260922/`。本次没有下载到开发板。

## 构建与上板

在仓库根目录按顺序运行，每步失败时停止并查看 `my/first_light/reports/`：

```powershell
python my\first_light\tools\build.py firmware
python my\first_light\tools\build.py sim-fifo
python my\first_light\tools\build.py sim-mode
python my\first_light\tools\build.py sim
python my\first_light\tools\build.py sim-soc
python my\first_light\tools\build.py compile
```

上板沿用已成功的 Efinity Programmer JTAG 临时配置流程，选择 `releases/fifo_resolution_20260922/first_light.bit`。正式固件已经嵌入 bitstream，无需另外下载 C 程序。

预期画面仍是 32 个移动彩条块和 CPU/HW FPS、US 两列；新增 `RES 640X480`。启动短暂显示 `RES WAIT` 属于正常等待。默认约每 4 秒切换模式，串口 115200、8N1，可发送小写 `h` 或 `c` 提前切换。至少观察一分钟并记录两种模式的最新 FPS/US，仿真数值不能代替实板性能。

| 现象 | 下一步具体检查 |
|---|---|
| 画面正常但没有 RES 文字 | 核对下载文件的完整路径与 SHA256，避免使用旧 motion 归档 |
| 一直显示 RES WAIT | 读取 0xF8100048 的 bit0 和 0xF8100044；检查 `mode_measure` 的 DE/HS/VS、像素时钟及 `video_mode_toggle_sync` |
| 花屏、黑线或 FAIL copy/present | 保存串口输出；查看 STATUS bit2/4/5，以及 AXI WVALID/WREADY/WLAST/WSTRB，比较旧版归档是否正常 |
| CPU/HW 帧率与以前不同 | 等待至少两轮自动切换后同时记录 FPS 和 US，保持相同显示器与负载再比较 |

本次补齐明确的写 FIFO；独立 DDR 图片资源区拷贝仍未实现，当前 Copy 的源和目标仍限定在选中的绘制页内。Alpha、Color Key 和高负载互动游戏也不属于本次同步内容。
