# Solid Fill 验证记录（2026-09-07）

## 被测对象

- RTL：`rtl/blt_solid_fill.v`
- Testbench：`sim/blt_solid_fill_tb.v`
- Efinity 工程：`efinity/blt_solid_fill.xml`

## RTL 仿真

- 工具：Icarus Verilog
- 语言选项：Verilog 2005，启用全部常规警告
- 覆盖：3x2 正常填充、1x1 边界、零宽空操作、下游背压
- 结果：`ALL TESTS PASSED`

## Efinity 综合

- 工具版本：Efinity 2026.1.132
- 器件：Ti60F225
- Timing Model：I3
- 阶段：Map / Synthesis（未执行布局布线与 bitstream）
- 结果：`map : PASS`
- 错误：0
- 资源估算：
  - EFX_ADD：91
  - EFX_LUT4：207
  - EFX_FF：193

## Efinity 图形界面全流程复核

- 结果：布局布线及 bit/hex 生成完成，Error 日志为空。
- 产物：`blt_solid_fill.bit`、`blt_solid_fill.hex`。
- 工具提示：工程没有 SDC，工具自动采用 1 ns 默认约束。
- 最大分析频率：433.651 MHz（对应数据路径 2.306 ns）。
- Setup Slack：-1.306 ns（相对于工具自动采用的 1 GHz 默认约束）。
- Hold Slack：0.038 ns。

因此当前结果只能证明独立 RTL 能完成 Efinity 全流程，不能证明目标系统时序
已经收敛。该工程没有真实板级引脚和系统时钟约束，生成的 bit/hex 不用于上板。

当前 Windows 命令行环境中必须通过 `C:\Efinity\2026.1\bin\efx_run.bat`
启动流程。直接运行 `efx_map.exe` 曾在尚未分析 RTL 前触发工具进程访问异常；
改用官方启动器后综合通过，因此该异常归类为工具启动环境问题，不是 RTL 错误。

## 尚未覆盖

- 未接 AXI、DDR 或官方跨时钟 FIFO。
- 未确认最终帧缓冲像素格式。
- 已执行无真实板级约束的布局布线和 bitstream 生成，但未完成目标系统时序
  收敛，也未进行上板验证。
