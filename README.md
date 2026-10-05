# 800x600 RISC-V FPGA 2D Rendering Engine - R4B

Ti60F225 上的 RISC-V + FPGA 2D 渲染工程，固定输出 800×600 HDMI，支持硬件填充、图像块拷贝、Alpha 混合、颜色键控、双缓冲、SPI Flash 素材加载和 5×7 字体。

本分支 `resolution-800x600-r4b-scan64-fill64` 保存 2026-10-05 成功上板的 R4B。用户反馈无黑条；BASIC 32 / 128 / 256 档的 HW 稳定值均约 60.3 FPS，所提供串口记录全部 BASIC 样本 `UF=0`。高阶第三条互动游戏与 Sprite 极限测试尚未实现。

## 获取并打开工程

```powershell
git clone --single-branch --branch resolution-800x600-r4b-scan64-fill64 https://github.com/Eutopia-n/ours_blt.git C:\FPGA\ours_blt-r4b
```

在 Efinity / Elitestek 中打开 `C:\FPGA\ours_blt-r4b\my\first_light\first_light.xml`。

- [当前工程说明、赛题对应与构建方法](my/first_light/README.md)
- [已成功上板的 R4B bit 文件](my/first_light/releases/fixed800_directpll_scan64_fill64_R4B.bit)
- [版本清单与 SHA-256](my/first_light/releases/fixed800_directpll_scan64_fill64_R4B.json)
- [本次实板串口记录](my/first_light/releases/r4b_validation/board_uart_20261005.log)
- [历史项目说明](README_HISTORY.md)

已有本项目 Flash 素材的板卡，只需通过 JTAG 下载上述 R4B bit。全新板卡需先配置素材用户区；JTAG 临时下载不等于将 FPGA 配置永久写入 Flash。具体步骤见当前工程说明。

本分支继承 `spi-flash-autoboot-5x7-font` 的历史，在独立分支提交 R4B 源码与配套产物。
