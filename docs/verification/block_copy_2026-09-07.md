# Block Copy 验证记录（2026-09-07）

## 被测对象

- RTL：`rtl/blt_block_copy.v`
- Testbench：`sim/blt_block_copy_tb.v`
- Efinity 工程：`efinity/blt_block_copy.xml`

## RTL 仿真

- 工具：Icarus Verilog
- 语言选项：Verilog 2005，启用常规警告
- 覆盖：3x2 正常复制、1x1 边界、零高空操作、读写请求背压
- 结果：`ALL BLOCK COPY TESTS PASSED`

仿真内存模型对每个读请求延迟两个周期返回数据，并检查模块在背压期间保持
读地址以及写地址、写数据、`wr_last` 稳定。

## Efinity 综合

- 工具版本：Efinity 2026.1.132
- 器件：Ti60F225
- Timing Model：I3
- 阶段：Map / Synthesis
- 结果：`map : PASS`
- 错误：0
- 资源估算：
  - EFX_ADD：64
  - EFX_LUT4：468
  - EFX_FF：291

## 尚未覆盖

- 未实现多未完成读、AXI Burst 或 FIFO 聚合。
- 未验证源和目标地址重叠；当前软件必须禁止重叠区域。
- 未接入官方 512 位 DDR 数据通路。
- 未加入系统 SDC、布局布线或上板验证。
