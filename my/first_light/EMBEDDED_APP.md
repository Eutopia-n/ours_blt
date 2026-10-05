# 应用随 .bit 更新

2026-10-05 启动修复版。已写入 77 帧素材的现有开发板，现在只需重新通过 JTAG 下载
`releases/fixed800_single_bit_20261005/fixed800_single_bit.bit`。
Flash 中原有的应用会被忽略，现有素材继续使用，无需重写 Flash 用户区。

当前所有场景固定 800×600；BASIC 中 KEY2 无操作，KEY3 返回菜单。详见 [FIXED800.md](FIXED800.md)。
菜单确认、高级展示透明度仍按原来的按键操作。

## 修改

- `rtl/render_regs.v`：现有 100 MHz APB 外设增加 16 KiB 只读程序 ROM，窗口为
  `0xF8108000～0xF810BFFF`。地址在 APB setup 阶段给出，下一拍 access 阶段返回数据。
  写入和未对齐访问报错。AXI、DDR、HDMI 时序与分辨率切换逻辑沿用此前版本。
- `tools/build.py`：编译 `animation.bin` 后生成 `software/build/embedded_app.memh` 和
  大小/CRC 头文件。综合将当前应用与 FPGA 逻辑装入同一个 `.bit`。
- `software/boot.c`：从既有 FTL1 Flash 镜像只加载素材；在启动应用之前，始终把 ROM 中
  的当前应用复制到 DDR `0x01400000`，校验后跳转。DDR 残留旧应用也会被覆盖。
  素材 CRC 和地址边界检查保留。现有 UART 回退协议仍接收完整包，运行的应用以 ROM 为准。

## 构建与本次检查

在本工程目录执行：

```powershell
python tools/build.py firmware
python tools/build.py compile
python tools/build.py sim-embedded-boot --modelsim D:/modelsim/win64
```

先编译固件，再编译 FPGA，避免 ROM 与启动程序的 CRC 不一致。
应用上限为 16 KiB；当前为 12940 字节，超出时构建会明确报错。

本次仅检查修改涉及的部分：固件编译、APB ROM 全地址/只读/未对齐/边界测试、
真实 CPU 覆盖旧 DDR 应用并启动新应用的短仿真，以及 FPGA 编译和最终时序报告。
这些检查均已通过；短启动仿真约 21 秒，未重跑此前耗时较长的整套按键动画回归。
短仿真预装了紧凑素材，用于检查程序 ROM 启动路径；Flash 实物读取和显示效果仍待上板确认。

启动修复前的源码备份在 `releases/pre_embedded_app_20261005/`。
JTAG 下载断电后会丢失；如果需要冷启动也使用本版，再把本版 FPGA 配置写入 Flash 配置区。
