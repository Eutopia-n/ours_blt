# BitBlt 内部 FIFO 缓存

## 作用与边界

本工程同时保留“整行缓存”和“写数据 FIFO”。整行缓存负责重叠 Block Copy 与 RGB565 半字对齐；FIFO 负责吸收行 RAM 读取和 AXI 写通道反压，二者不能互相替代。

FIFO 位于 `fill_engine` 与 AXI W 通道之间，容量为 16 项，正好容纳本工程允许的最大 16-beat burst。每项 37 位：

- bit 36：`WLAST`
- bit 35:32：`WSTRB`
- bit 31:0：`WDATA`

FIFO、BitBlt 状态机和 AXI 主接口都使用 100 MHz `user_clk`，复位使用现有同步 `renderer_reset`，没有新增跨时钟通路。APB 寄存器、C 驱动和 HDMI 像素时钟域均未改变。

## 握手与反压

- Solid Fill 直接产生颜色、首尾字节选通和 `WLAST` 后入队。
- Block Copy 从整行 RAM 连续预取并完成半字重排后入队。
- `WVALID` 仅在 FIFO 非空时有效；只有 `WVALID && WREADY` 才出队。
- AXI 反压期间读指针不变，因此 `WDATA/WSTRB/WLAST` 保持稳定。
- 新命令、复位或异常返回空闲态时清空 FIFO，旧数据不会进入下一条指令。

在 FIFO 之前，Block Copy 的同步行 RAM 每个写 beat 后需要一个 `C_WLOAD` 周期。现在预取和发送可以重叠；仿真总线始终就绪时，一个 burst 内的 W beat 连续发送。

## 验证

```powershell
python my\first_light\tools\build.py sim-fifo --modelsim D:\ModelSim\win64
python my\first_light\tools\build.py sim --modelsim D:\ModelSim\win64
python my\first_light\tools\build.py sim-soc --modelsim D:\ModelSim\win64
python my\first_light\tools\build.py compile --efinity D:\Efinity
```

`tb_sync_fifo.sv` 覆盖空、满、上溢拒绝、下溢拒绝、顺序、同时入队/出队和清空。`tb_render.sv` 继续覆盖所有复制对齐、重叠、4 KB 边界、随机 AXI 反压和错误恢复，并额外检查 FIFO 不溢出、不下溢以及 ready 条件下没有 `WVALID` 空拍。

## 2026-09-22 验证记录

- FIFO 独立仿真：`ALL FIFO TESTS PASSED`，Errors=0、Warnings=0。
- 渲染回归：33 组图案拷贝及完整 HDMI/双缓冲测试通过；总线始终就绪时 640×2 Block Copy 为 1720 个 100 MHz 核心周期，burst 内没有 `WVALID` 空拍。
- 真实 Sapphire 联合仿真：CPU 19 FPS / 35948 μs，HW 60 FPS / 4383 μs；9 次换页及 A/B 页逐像素检查通过，`SOC TEST PASSED`。
- Efinity 2026.1：`map/interface/pnr/pgm` 全部 PASS；XLR 19119/60800（31.45%），Memory Blocks 84/256（32.81%），DSP 4/160（2.50%）。
- 最小 setup slack +0.205 ns，最小 hold slack +0.021 ns，时序通过。
- 生成文件 `outflow/first_light.bit` 为 2,029,632 字节，SHA256 `5F1BDE5F5604858D6C695486724D71D50DDE1DB821A1B54080426754918FC76C`。

接口检查仍报告官方板级已有的一条相邻 HSIO 引脚告警：DDR `GPIOR_P_09` 与 HDMI `tmds_clk` 距离较近。本次未修改引脚或时钟约束，需要在新版 bitstream 上板时继续观察 DDR 与 HDMI 同时运行的稳定性。
