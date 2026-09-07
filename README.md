# 自研 BitBlt 加速器

这里只放本队自己写的 RTL、仿真文件、寄存器定义和软件驱动；不要把官方工程直接覆盖进来。

建议后续结构：

- `rtl/`：`blt_regs`、`blt_core`、FIFO/AXI 适配模块。
- `sim/`：Solid Fill、Block Copy 的测试平台。
- `sw/`：RISC-V C 驱动和演示程序。
- `docs/`：寄存器表、状态机图、性能数据。

开发顺序：Solid Fill → Block Copy → 总线寄存器 → DDR/帧缓存 → 双缓冲。

## 当前里程碑

- `rtl/blt_solid_fill.v`：独立 Solid Fill 写请求生成器。
- `sim/blt_solid_fill_tb.v`：正常、边界、空操作和背压测试。
- `efinity/blt_solid_fill.xml`：Ti60F225/I3 的独立 Efinity 综合工程。
- `docs/solid_fill.md`：接口约定、验证点和编译步骤。
- `docs/verification/solid_fill_2026-09-07.md`：仿真与 Efinity 综合证据。
- `rtl/blt_block_copy.v`：单未完成读请求的 Block Copy 数据通路。
- `sim/blt_block_copy_tb.v`：Block Copy 正常、边界、空操作和背压测试。
- `efinity/blt_block_copy.xml`：Block Copy 独立综合工程。
- `docs/block_copy.md`：Block Copy 接口、限制与验证说明。
- `docs/verification/block_copy_2026-09-07.md`：Block Copy 仿真与综合证据。
