# KEY2 透明度与硬件 Alpha 混合

高级展示中，KEY2 短按增加 2 个百分点，顺序为 0、2、4…98、100、0。
0% 完全显示人物，100% 完全透明。默认 0%；返回菜单后重新进入高级展示恢复 0%。
按住 500 ms 后触发第一次连加，以后每 100 ms 增加 2；松开停止。
软件按实际经过时间计算连加次数，低帧率时画面在下一帧更新到对应数值。
屏幕显示 `TRANSPARENCY n%`。透明度改变时清空原透明度下的 CPU/HW 性能统计。

菜单中的 KEY2 仍是确认；按住确认进入高级展示后，必须松开再按才能调节。
基础展示的 KEY0 CPU/FPGA、KEY1 三档数量、KEY3 返回菜单保持原有功能。
高级展示的 KEY1 仍切换颜色键控，KEY3 返回菜单，CPU/FPGA 继续自动轮换，UART c/h 可切换。

## 代码和接口

- `rtl/key_toggle.v`：输入 `key_n`，输出按下事件翻转位 `state` 和消抖后电平 `down`。
  两级输入同步与 15 ms 消抖沿用现有实现，`down` 在整个有效按住期间保持 1。
- `rtl/competition_top.v`：顶层 `competition_top` 的 KEY2 为低有效 `key2_n`，N14 / GPIOR_21。
  `key2_filter.down` 接入 `render_subsystem.key2_down`；对应生成模板在 `tools/prepare.py`。
- `rtl/render_regs.v`：APB 配置 Alpha，并提供 KEY2 按住状态。寄存器和引擎位于
  100 MHz `user_clk` 域；显示仍在 `hdmi_tx_slow_clk` 域。
- `rtl/fill_engine.v`：新增操作 3，逐行读前景、读后台页目标背景、混合、写回。
  背景读取复用现有显示优先仲裁器，一个 burst 最多 16 个 32 位 beat，不跨 4 KiB。
  读通道按 ARVALID/ARREADY 和 RVALID/RREADY 握手，错误时排空已接收 burst；
  写 FIFO 保持 WDATA/WSTRB/WLAST 直到握手，收到最后一次 B 响应才报告 DONE。
- `rtl/alpha_blend.v`：由 `fill_engine.v` include，两个 RGB565 像素并行，乘法与加法分别寄存。
  输入 `foreground/background/opacity/in_valid`，输出 `result/out_valid`，使用同步高有效复位。
  引擎等待输出并存回背景行缓存，再沿用 Copy 写 FIFO。
- `software/alpha_control.h`：短按、长按、循环及百分比转换；`main.c` 接入高级展示和 CPU 基线。

寄存器相对 GFX_BASE：`0x30 OPERATION=3` 为 Alpha Copy；`0x50 ALPHA` 为前景不透明度
0..256，复位值 256；`0x54 ALPHA_KEY` 为 0/1；`0x58 KEY2_DOWN` 是只读按住电平 bit0。
`0x1C COLOR` 在键控开启时给出透明键色，演示值为 RGB565 品红 `0xF81F`。
Alpha 大于 256、键控配置大于 1 或写入只读状态均产生 APB 错误；忙时禁止改配置。

UI 透明度 T 与前景系数 A 的关系：`A = ((100-T)*256+50)/100`，整数除法。
分别对 RGB565 的 R5、G6、B5 计算 `(F*A + B*(256-A) + 128) >> 8`。
CPU 与硬件使用相同量化、舍入规则；键色像素保留背景。
T=0 时演示使用原 Copy/Keyed Copy 快速路径，T>0 时执行硬件 Alpha Copy。
这是一张 Sprite 共用一个 Alpha 的实现，素材仍是现有 RGB565，无需重新制作。

## 验证和复现

在 `try` 根目录运行：

```powershell
python my/first_light/tools/build.py firmware --efinity C:/Efinity/efinity-riscv-ide-2026.1
python my/first_light/tools/build.py sim-alpha --modelsim D:/modelsim/win64
python my/first_light/tools/build.py sim --modelsim D:/modelsim/win64
python my/first_light/tools/build.py sim-alpha-soc --modelsim D:/modelsim/win64
python my/first_light/tools/build.py compile --efinity C:/Efinity/2026.1
```

`sim-alpha` 的软件控制测试使用 PATH 中的 GCC，硬件测试使用指定的 ModelSim。
正常、边界、空操作和复位均有覆盖，日志位于 `reports`。

已通过：控制逻辑测试覆盖两轮 51 档循环、500/100 ms 边界、松开停止、慢帧补偿、
菜单确认隔离、32 位时间回绕；混合算术测试覆盖全部 257 个硬件系数和 4112 组双像素。
渲染回归通过前景/背景读取、奇偶半字对齐、4 KiB 边界、全透明/键色、重叠拷贝、
最大矩形、空操作、前景/背景读错误、写错误恢复、AXI 反压和双缓冲显示。

Efinity 2026.1 的 map/interface/pnr/pgm 全部 PASS，混合模块确认使用 12 个 DSP48。
100 MHz 核心 setup slack +2.480 ns，时序报告最小 setup +0.294 ns、hold +0.026 ns。
启动脚本仍会打印既有 Conda 导入错误，但完整编译退出码为 0。
联合仿真使用真实 Sapphire 核及本版 animation.bin；为缩短启动校验，素材采用真实首帧，
77 个描述项共用该帧。不同宽度、对齐、重叠和最大尺寸由渲染模块回归覆盖。
仿真平台将空 UART FIFO 的无效 payload 固定为 0，保留有效接收数据，以避免厂商模型
的 X 值污染固件寄存器；这是仿真处理，不修改硬件 UART IP。
真实 Sapphire 联合仿真已通过：9 个高级场景（CPU 6 帧、FPGA 3 帧）、12 次换页请求，
覆盖 KEY2 0/2/4、确认按住隔离、CPU/HW 切换、键控开关、返回菜单及重新进入归零。
提交像素和 HDMI 扫描逐像素一致，无仿真错误/警告，日志为 reports/simulation_alpha_soc.log。
长按计时和 51 档回绕由上面的实际控制函数测试覆盖；未在 SoC 仿真中运行完整长按一圈。

配套发布包为 [alpha_key2_20261002](releases/alpha_key2_20261002/README.md)，
包含新 bitstream、DDR 应用、素材、上传脚本、源码快照、报告及 SHA256 校验值。

## 上板验收

本次同时改变 RTL 和 DDR 应用，必须使用配套新 bitstream 与 animation.bin。
JTAG 下载后，用配套 `tools/upload_sprite77.py --list-ports` 查询串口，再加 `--port COMx` 上传。
启动 UART 标识为 `Ti60 ALPHA KEY2 20261002`。

进入 ADVANCED 后检查短按 +2、长按连加、100→0、松开停止、KEY1 去背开关；
保持 KEY2 按下进入高级展示，确认数值保持 0；松开重按后开始增加。
在 50% 时检查人物与绿色/蓝色背景条叠加，在 100% 时人物完全消失，
切换 CPU/HW 确认相同透明度的画面一致。记录实板照片/视频、FPS、版本和错误状态。
当前验证属于编译与仿真，尚未对本版进行实板验收。

修改前源文件、应用及 bitstream 已备份到 `releases/pre_alpha_key2_20261002`。
