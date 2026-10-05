# 固定 800×600 单文件版

2026-10-05。当前工程的菜单、BASIC、ADVANCED 全部固定输出 800×600。
像素时钟 40 MHz，行总周期 1056、场总行数 628，HS/VS 正极性，设计刷新率约 60.317 Hz。

BASIC 中 KEY2 无操作，KEY3 返回菜单时保持 800×600。
菜单的 KEY2 仍确认进入，高级展示的 KEY2 仍调透明度。
应用随 `.bit` 更新，继续使用 Flash 中已有素材。

## 下载

最新 R1 通过 JTAG 下载 `releases/fixed800_hw_recovery_20261005/fixed800_hw_recovery.bit`。
R1 修正显示欠载标志导致应用永久停机的处理，说明和验证见 `BASIC_HW_RECOVERY.md`。
原固定分辨率版本保存在 `releases/fixed800_single_bit_20261005/`。
已有素材的板卡无需重写 `flash_user.bin`。本次没有执行实板下载。

## 修改与构建

`software/main.c` 固定画面宽高，删除分辨率切换函数和 BASIC KEY2 分支，
所有场景均清除 800×600 背景。`render_subsystem` 默认启用 `FIXED_SVGA=1`，
扫描器从 800 模式复位启动，APB `0x5C` 模式寄存器变为只读、值为 1。
`competition_top` 和 `tools/prepare.py` 将 HDMI 时钟控制器的启动模式固定为 1（40 MHz）。
通用 RTL 的历史双模式参数仅供旧测试复用，当前工程不开放切换。

显存布局继续为 1600 字节行距、每页 960000 字节。
AXI 读写仍由 100 MHz 用户时钟驱动，视频扫描为 40 MHz；握手与反压方式沿用已有实现。

```powershell
python tools/build.py firmware
python tools/build.py sim-fixed800 --modelsim D:/modelsim/win64
python tools/build.py sim-embedded-boot --modelsim D:/modelsim/win64
python tools/build.py compile
```

本次固件编译、固定模式专项仿真、内置应用启动短仿真及 FPGA 全流程编译均通过，
最终 setup/hold 时序满足约束。固定模式测试覆盖完整像素帧、HS/VS、模式写入被拒绝、
失锁恢复、800×600 全屏填充及非法尺寸；两项仿真均为 0 errors / 0 warnings。
没有重跑完整菜单动画回归，实板显示效果仍待确认。
修改前源码备份在 `releases/pre_fixed800_20261005/`。
