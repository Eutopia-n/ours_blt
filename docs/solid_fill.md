# Solid Fill 最小里程碑

## 模块职责

`blt_solid_fill` 接收一次矩形填充命令，并逐像素输出字节地址和固定颜色。
本模块不直接实现 AXI，也不包含跨时钟逻辑；后续由独立适配层将写请求聚合成
AXI burst 或写入官方工程的跨时钟 FIFO。

## 接口约定

- `clk`：唯一时钟。
- `rst`：同步、高有效复位。
- `start && cmd_ready`：接收一条命令；忙时的新 `start` 不会被接收。
- `base_addr`：矩形左上角像素的字节地址。
- `line_stride_bytes`：相邻两行起始地址的字节差。
- `width_px`、`height_px`：矩形宽高，单位为像素。
- `color`：每个写请求携带的 32 位像素字。
- `wr_valid && wr_ready`：一个像素写请求被下游接收。
- `wr_last`：当前请求是本命令最后一个像素。
- `done`：正常或无效命令结束时拉高一个周期。
- `invalid_cmd`：宽或高为 0 时与 `done` 同周期拉高，不产生写请求。

当前 `PIXEL_BYTES=4`。实际 RGB 排列仍待最终帧缓冲格式确认，模块只保证
32 位颜色字原样输出，不假定 ARGB/RGBA/BGRA。

## 验证点

1. 正常值：3x2 矩形、行跨度大于有效行宽，核对 6 个地址及颜色。
2. 边界值：1x1 矩形，只输出一次并同时置 `wr_last`。
3. 空操作：宽度为 0，不输出写请求，返回 `done + invalid_cmd`。
4. 背压：下游暂停多个周期时，`wr_valid/addr/data/last` 保持稳定，恢复后无丢失。

## 本地仿真

在 `ours_blt` 目录运行：

```powershell
New-Item -ItemType Directory -Force sim\build | Out-Null
iverilog -g2005 -s blt_solid_fill_tb -o sim\build\blt_solid_fill_tb.vvp rtl\blt_solid_fill.v sim\blt_solid_fill_tb.v
vvp sim\build\blt_solid_fill_tb.vvp
```

期望最后一行是 `ALL TESTS PASSED`。

## Efinity 2026.1

在 Efinity 中打开 `efinity/blt_solid_fill.xml`，执行 Synthesis。该工程只用于
RTL 编译/综合验证，没有 Peripheral Designer 和引脚约束，因此不要执行完整
Place & Route 或生成 bitstream。期望顶层为 `blt_solid_fill`，器件为
`Ti60F225`、Timing Model 为 `I3`，综合结束无 Error。

接入官方 10 工程时，不复制此 XML；只把 `rtl/blt_solid_fill.v` 添加为 Design
File，再新增尚未实现的 FIFO/AXI 适配层。
