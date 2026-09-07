# 自研 BitBlt 加速器

这里只放本队自己写的 RTL、仿真文件、寄存器定义和软件驱动；不要把官方工程直接覆盖进来。

建议后续结构：

- `rtl/`：`blt_regs`、`blt_core`、FIFO/AXI 适配模块。
- `sim/`：Solid Fill、Block Copy 的测试平台。
- `sw/`：RISC-V C 驱动和演示程序。
- `docs/`：寄存器表、状态机图、性能数据。

开发顺序：Solid Fill → Block Copy → 总线寄存器 → DDR/帧缓存 → 双缓冲。
