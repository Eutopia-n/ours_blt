# 独立 DDR 资源图片：2026-09-22 归档

下载文件：本目录 `first_light.bit`。适用 Ti60F225I3，正式 RISC-V 固件已嵌入。保留 640×480 RGB565、32 个运动 Sprite、双缓冲、CPU/HW FPS/US、分辨率显示和 16×37 位写 FIFO。

新增 0x01200000～0x012FFFFF 的独立 DDR 资源区，以及偏移 0x4C 的源行距寄存器。Demo 启动时上传一次 32×32 图片，此后两种模式均读取该图片；硬件每帧 1 个 Fill + 32 个 Copy。目标只允许写所选绘制页，保留同页显存内的重叠拷贝。

验证完成：固件编译、渲染回归和官方 Sapphire 真实 CPU 联合仿真通过；资源仅写入 2048 字节，CPU/HW 资源读取均被观察到；9 次换页、12 个完整扫描帧无像素错配。Efinity map/interface/pnr/pgm 均通过，最终 setup slack +0.361 ns、hold slack +0.026 ns。原有 DDR/HDMI 相邻引脚告警保留。本次没有下载开发板，仿真 FPS/US 不能用作实板性能。详细信息见 `DDR_ASSETS.md` 和 `reports/`。

上板仍用 Efinity Programmer JTAG 临时配置。预期串口启动文字为 `Ti60 DDR ASSET 32 CPU/HW`；原左侧 (0,64) 固定源块消失，32 个运动彩条块和 RES 640X480 保留。等待两轮自动模式切换，再记录 CPU/HW 的 FPS 与 US，至少观察一分钟是否稳定。

交付后用户反馈 CPU 30 FPS / 26220 μs、HW 60 FPS / 4778 μs；单组读数及适用限制见 `BOARD_OBSERVATION.md`。上段“本次没有下载开发板”指工具交付阶段没有自动执行烧录，用户后续已提供实板运行反馈。

本目录是下载文件、源码和报告快照，不含大型 vendor IP，不能作为独立工程编译。复现使用仓库 `my/first_light` 和其中的 vendor 依赖。旧版回退文件在相邻 `fifo_resolution_20260922/first_light.bit`；`pre_ddr_assets_20260922/` 是本机修改前备份，不随 GitHub 上传。

| 文件 | SHA256 |
|---|---|
| first_light.bit | 4CBAFA9A80B52268FE58F60773CBBC775F64174C413E3A0BA82588FCD84B40F0 |
| first_light.bin | A71ADC6623FDEBBAE7700461D6F17B32BA577B496040B8A451E2870487CF7913 |
| first_light.elf | 8AE2B47A209390075B81F349AE8275DF1019E56E6CDE006B2DD1CDD7C578B036 |

生成时间：2026-09-22 15:18:26。bitstream 大小：2,034,591 字节。

当前已补齐明确的写 FIFO 和独立 DDR 图片资源区拷贝。Alpha、Color Key、互动游戏及最大 Sprite 数量测量仍未实现。本轮没有修改引脚、DDR 时序、Git 暂存内容或远端 GitHub 分支。
