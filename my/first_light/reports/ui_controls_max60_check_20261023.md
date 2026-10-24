# 文字布局、压力长按和游戏 MAX60 检查

日期：2026-10-23。用户确认游戏 MAX 统计实际绘制的全部同屏 Sprite，包括人物、敌怪、弹幕和掉落物；不是只统计魔法弹。

## 修改与预期

1. `software/main.c`：增加 `text_at_width()`，只画字段内完整字符，并保护 640×480 边界；`decimal_field()`/`number_field_at()` 限制数字栏位，超过容量显示 `9999+` 一类标记，UART 数值不截断。原字模保留。修复普通页 RISC-V FPS 标签与数值重叠、DDR_WR 标签与数值重叠，将 DDR_RD/DDR_WR 分行；拉开 Alpha 数值与 `/255`、压力页尺寸与乘号之间的间距。
2. `software/demo_controls.h`：新增 `demo_bench_update()`。W/S 短按立即加/减 1，长按延迟 300 ms 后，每 60 ms 加/减 1；以实际渲染帧边界为准，单帧最多重复一次，不补发慢帧期间积压的操作。松开停止，W+S 抵消，最低 1，uint32 上界饱和。菜单、A/D、Enter 不启用长按重复。压力页保持运动帧号，连续增减时不会因每次清零帧号而反复跳回原位。负载改变后重开采样，调整过程中 WAIT；松开保持约半秒后看 30 帧结果。
3. `software/game_view.h`：游戏 `SPRITES` 改为累计实际成功提交并位于视窗内的图片，以及 CPU 实际绘制的小魔法弹。部分裁剪的图片计 1，屏外、预算跳过和闪烁隐藏的对象不计；地图符文和法球计入，地图背景、文字、血条及技能菜单图标不计。HUD 的 SPRITES、MAX60 和 FPS 使用独立栏位，技能文字限制在卡片内。暂停/结算面板也显示 MAX60。
4. `software/frame_metrics.h`：新增 `FrameMax60` 与窗口函数，游戏每个连续 30 帧窗口中，每帧从输入/逻辑处理到 HUD 绘制的耗时必须不超过 1,666,667 个 100 MHz 周期，而且相邻呈现的实际显示刷新计数增量必须等于 1。完整窗口通过后才记录其中最高实际同屏数量。一个超时或漏刷新就不更新该窗口纪录，后续正常窗口仍可恢复。暂停/升级等状态不参加，状态改变时重开采样，暂停保留纪录，重新开始游戏清零。UART 改为输出实际 `SPRITES` 与 `MAX60`。

游戏当前数量变化较快，因此 MAX60 表示通过 30 帧窗口中的峰值，不表示该峰值数量连续保持了 30 帧。固定负载极限仍应使用独立压力页逐个加压测量。没有将 FPS 写死为 60，也没有扩大游戏对象池或改变硬件合成算法。

## 检查结果

- RISC-V GCC 使用 `-Wall -Wextra -Werror` 编译通过；text=53112 B，data=12 B，bss=5532 B，总计 58656 B。
- `__bss_end=0xF900E520`、栈顶 `0xF9010000`，剩余栈空间 6880 B，满足 4096 B 链接断言。
- 8 份 RAM lane 文件与 ELF 导出固件完全一致；19 个数字栏位的地址对齐、字符宽度和帧缓冲边界通过；10 个 framebuffer/图片/背景/地图资源区互不重叠。
- 原 `sim/test_survivor_game.c` 是本机原生 C 回归，本次新增压力长按和 MAX60 用例。长按延迟、连续加减、释放、双键抵消、上下界、慢帧不积压、计时器回绕、短按事件暂存均通过；不足 30 帧不更新、一个渲染超时不更新、漏刷新/重复刷新不更新、暂停清窗口与后续恢复通过。原有移动、碰撞、生命、升级与满级质变、对象池、重开与胜利、30000 tick 确定性回归通过，日志 `reports/game_logic.log`。
- 新 `tools/check_ui.py` 提取固件实际的字形、HUD、菜单、游戏卡片及裁剪函数，替换硬件访问后执行主机检查。19 次页面预览检查通过：分类/基础/高阶菜单、6 个普通演示、压力页、游戏 HUD、全部 6 类升级/满级、准备/暂停/失败/胜利。文本与数字栏位无重叠或越界；192 字中文/符号字库覆盖全部中文字符串；数字变短后旧字清除、两页独立缓存、超宽标记及屏幕边缘保护通过。
- 主机检查调用实际游戏裁剪与绘制选择函数，核对屏外不计数、32/64 敌怪预算与实际计数对应，以及魔法弹计数。日志 `reports/ui_check.log`。
- `reports/ui_check_*.png` 为实际字模生成的布局预览，游戏图像和背景使用简化占位，不是 RTL 仿真或实板照片。其中 `ui_check_game.png`、`ui_check_pressure.png` 使用极端大数验证字段容量，不是实测成绩。
- 本次修改文件的 Git 空白检查通过。
- Efinity map、interface、pnr、pgm 全部 PASS；最终时序汇总 16 项 setup/hold 关系均为正余量，core_clk 100 MHz 的 setup 余量 2.064 ns、hold 余量 0.026 ns。

## 下载文件

- 临时 JTAG 配置：`S:\Ti60F225_DemoBoard_v4\my\first_light\outflow\first_light.bit`。
- 掉电保留：`S:\Ti60F225_DemoBoard_v4\my\first_light\outflow\first_light.hex`，沿用 Active/JTAG bridge（SPI Flash）方式，详见 `FLASH_PROGRAMMING.md`。
- 生成时间：2026-10-23 18:02:21。
- bit 大小：2375394 字节。
- bit SHA-256：`B58DE120A87050F352BAB4C5814C970CB9ADF9E695B00E6F4F90488D9982CECA`。

下载后先观察压力页短按加 1、长按连续变化、松开停止，停止调整后等待完整窗口；游戏 HUD 的 SPRITES 随当前实际绘制数量变化，MAX60 初始为 0，只有通过连续 30 帧条件后增长，暂停保留，新开一局清零。若文字仍异常，下一步对照 `ui_check_*.png` 的静态排版与实际分辨率/HDMI 缩放；若 MAX60 一直为 0，查看 FPS、RENDER_US 及相邻显示刷新计数，不能将平均显示 60 直接视为逐帧全部通过。

## 复查命令

在工程目录执行：

```powershell
$env:PATH='S:\Tools\xilinx\Vivado\2018.3\msys64\mingw64\bin;S:\Tools\xilinx\Vivado\2018.3\msys64\usr\bin;'+$env:PATH
& 'S:/Tools/xilinx/Vivado/2018.3/msys64/mingw64/bin/gcc.exe' -std=c99 -O2 -Wall -Wextra -Werror sim/test_survivor_game.c software/survivor_game.c -o software/build/test_survivor_game.exe
& software/build/test_survivor_game.exe
python tools/check_ui.py --cc 'S:/Tools/xilinx/Vivado/2018.3/msys64/mingw64/bin/gcc.exe'
python tools/build.py firmware
python tools/build.py compile
```

本次不运行 ModelSim/RTL 仿真，不上板下载，不上传 GitHub。编译和主机检查无法证明实板达到的最大 60 FPS 负载，最终数量仍需下载后读取 HUD/UART。
