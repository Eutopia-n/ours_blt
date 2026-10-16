# 生存游戏 Demo 帧率优化与下载记录（2026-10-12）

## 本次帧率优化

游戏原来每帧先把完整 640×480 背景拷贝到后缓冲，再拷贝一遍滚动地图视口。现在只在游戏启动时初始化两块双缓冲；每帧只拷贝 624×360 地图视口。每个页面的 HUD 静态字样只写一次，变化数字和血条使用局部 CPU 更新；不再每帧恢复整条 HUD 背景。

按像素数估算，背景/地图复制从约 521856 像素降到约 224640 像素，减少约 56.9%。该估算只针对背景/地图复制，不包含 Sprite Alpha 合成、动态血条、CPU HUD 和 HDMI 扫描。

60 Hz 双缓冲仍由帧边界换页；游戏逻辑按 60 次/秒推进，FPS 按实际 CLINT 时间计算。目标是渲染在每个约 16.67 ms 的刷新周期内完成。总 Sprite 数和 DDR 仲裁会影响结果，Efinity 编译及 RTL 仿真不能替代目标板运行时 FPS 测量；本次按用户要求不做板上验证。

## 自动验证结果

- C 主机规则测试通过：包括地图/相机、Alpha ±1、长按重复、碰撞/血量、六类升级上限与质变、对象池以及 30000 次确定性更新。
- 按键、FIFO、视频模式 RTL 仿真通过。
- 菜单/基础功能 SoC 仿真通过：19 个菜单帧、24 个页面、27 个 HDMI 完整扫描帧。
- 更新后的 game SoC testbench 已通过 ModelSim 编译（0 errors / 0 warnings）。渲染预算加入前的完整游戏 SoC 仿真通过：52 次页面呈现、48 个游戏帧、70 次 HDMI 完整扫描；UART 记录 `GAME FPS 60 RENDER_US 6435`。随后加入 32/32/24 合成预算并重新完成固件与 Efinity 工程编译；最高负载仍按用户要求留给板上观察。
- Efinity map/interface/pnr/pgm 全部通过。

固件：text 47128、data 8、bss 5484、总计 52620 字节，片内 RAM 容量 65536 字节。下载文件：

- `outflow/first_light.bit`：2363295 字节，SHA-256 `A65F35CC46C763FD8FBD7F56F791EB7B443BA943BF9EC376509DA7EF3676724E`
- `outflow/first_light.hex`：2363355 字节，SHA-256 `00D5196AD2FC69FD72C36FB8A4C38DA8E327876A2CF9B7D971789DD0F2B0A07E`

## 下载到板卡

一次性写入 SPI Flash，之后每次上电自动启动、不用重复下载：

```powershell
cd S:\Ti60F225_DemoBoard_v4\my\first_light
python tools/build.py flash
```

执行前接好并上电 Ti60 与 USB/JTAG 下载器。Efinity Programmer 报告成功即完成 Flash 编程。也可以用 Efinity Programmer 选择 `outflow/first_light.hex`，使用 Active/JTAG bridge（SPI Flash）模式编程。

如果只是临时运行，Efinity Programmer 选择 FPGA 的 JTAG/volatile 配置并载入 `outflow/first_light.bit`；断电后需重新配置。SPI Flash 和临时 JTAG 两种方式不要混淆。更完整说明见 `FLASH_PROGRAMMING.md`。
