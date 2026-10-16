# 分辨率显示与写 FIFO：2026-09-22 归档

下载文件：本目录 `first_light.bit`。适用 Ti60F225I3，640×480 RGB565。保留 32 个运动彩条块、CPU/HW FPS 与 US 对比、双缓冲；增加实际输出分辨率文字与 16×37 位 AXI 写 FIFO。正式 RISC-V C 固件已嵌入。

源代码来自 `Real-time-resolution-reading-and-FIFO` 分支的 `f6beb7ebe41c57e5eb324a293dea2dda63559f33`，本机重新构建。硬件引脚和时钟约束保持本地原配置；没有执行远端分支对早期示例目录的删除，也没有提交或推送 GitHub。

固件、FIFO 独立仿真、分辨率独立仿真、渲染回归、真实 RISC-V 联合仿真和 FPGA 全流程均通过。联合仿真覆盖 5 个 CPU 场景帧、4 个硬件场景帧、9 次换页和 16 个完整扫描帧。最终 setup slack +0.205 ns、hold slack +0.021 ns。原有 DDR/HDMI 相邻引脚告警保留。详细结果见 `SYNC_FIFO_RESOLUTION.md` 和 `reports/`。

本次未上板，归档中的 CPU/HW 性能与 PNG 图均来自仿真。使用 Efinity Programmer 的 JTAG 临时配置方式下载后，应看到 RES 640X480；启动短暂 RES WAIT 正常。保持原 HDMI TX 连接、串口 115200 8N1，等待两轮 CPU/HW 自动切换后记录 FPS/US，并观察至少一分钟是否稳定。

本目录保存源码与交付快照，不包含大型 vendor IP，因此不是独立可编译工程。复现使用仓库 `my/first_light` 及其中的 vendor 依赖。`first_light.bit` 可直接用于下载；`first_light.elf`、`first_light.bin` 和 `.map` 用于固件核对。旧版回退文件为相邻 `motion_20260921/first_light.bit`；本次同步前备份位于 `pre_fifo_resolution_20260922/`。

| 文件 | SHA256 |
|---|---|
| first_light.bit | 686ABDD804639D5AEAA894088F581CF6A5C3ADEFA082027D7FEA4658A72D7E40 |
| first_light.bin | 1C006B5FC57D0B915B938C1E42705C89E89023CD13AF5E6C3AAF788150F633DB |
| first_light.elf | 03348765D66E8F40C5FCB210278C908DD7B9D42F4C50DE547BFDE9EBEC628756 |

生成时间：2026-09-22 14:55:15。bitstream 大小：2,029,632 字节。

本次实现了明确的写 FIFO，尚未实现独立 DDR 图片资源区拷贝、Alpha、Color Key 或互动游戏。
