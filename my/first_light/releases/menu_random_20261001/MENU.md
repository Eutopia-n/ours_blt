# 初级 / 高级功能菜单

本工程把 32×32 RGB565 随机位置 Fill/Copy 演示和
`Basic-functions-and-irregular-sprite-sheets` 分支的 77 帧不规则 Sprite、
颜色键控演示放入同一个 DDR 应用、同一个 FPGA 配置文件。上电配置 FPGA 后，
仍需通过 UART 上传 `software/build/animation.bin` 和 `assets/sprite77.upload`；
上传完成才显示一级菜单。旧的 `releases/sprite77_20260927/` 是历史发布包，
其中的 bitstream 和应用程序不含本菜单。

## 操作

- KEY0（C4 / GPIOL_07）：在一级菜单选左侧“BASIC”。
- KEY1（P14 / GPIOR_22）：在一级菜单选右侧“ADVANCED”。进入高级演示后，继续用于切换颜色键控。
- KEY2（N14 / GPIOR_21）：确认当前方形按钮，进入相应展示。
- KEY3（A3 / GPIOL_03）：从任一展示返回一级菜单；在一级菜单按下无操作。

初级展示左侧为 16 个随机位置、随机颜色的 32×32 实心方块，右侧为 16 个随机位置的
32×32 白边棋盘格图像块。CPU 基线逐像素填充/拷贝；硬件模式每帧提交
17 次 Fill（全屏背景 + 16 个实心块）和 16 次普通 Copy（读取独立 DDR 图像资源）。
棋盘格中的品红色在基础展示中保留，不使用颜色键控。
每半屏采用 4×4 隐形分区，在各分区内随机偏移，保证方块完整可见、互不重叠，
避开 HUD 和操作提示。随机数由进入 BASIC 时的计时器值作为种子生成，属于伪随机。
同一份布局先显示 CPU 约 4 秒，再显示 HW 约 4 秒，随后刷新下一组，约 8 秒一组。
手动 UART `c`/`h` 切换时不刷新布局；从菜单重新进入 BASIC 会重新生成。
高级展示沿用 77 帧不规则 Sprite 与颜色键控的 CPU/HW 对比。
两种展示均每 4 秒自动交替 CPU/HW 路径，UART `c`/`h` 可提前切换。
菜单文字使用现有像素字体，初版采用英文 `BASIC` / `ADVANCED` 标签。

四路按键均为低电平有效，先在 100 MHz `user_clk` 域双触发器同步、
15 ms 消抖，再以翻转位送入 Sapphire GPIO 输入位 `[3:0]`。
CPU 对上次 GPIO 值做异或，只把变化解释为一次按下事件。
图像写入后台 framebuffer，视频在帧边界换页；未改变 DDR IP、PLL、HDMI 编码器或 SDC。

板卡 PDF 的“八、用户 IO”给出四个 KEY 引脚。原厂
`08_ti60f225_soc_demo/09_Ti60F225_co_debug_demo/rtl/ddr3_example_top.v`
顶层为 `ddr3_example_top`，输入包含 100 MHz `core_clk`、DDR 时钟、
PLL 锁定信号，输出为 DDR 总线，`sys_rst` 由两个 PLL 锁定信号组成。
原厂 `03_hdmi_tx_demo/hdmi_tx_demo_v2/rtl/hdmi_src/dvi_tx/dvi_encoder.v`
以 `pixelclk`、`rstin`、RGB、HS/VS/DE 为输入，输出 TMDS 数据。
当前组合顶层 `competition_top` 把 KEY 输入接入 `user_clk` 域；
CPU 与渲染器共用 DDR，原有 AXI 握手和写 FIFO 反压路径保持不变。

77 帧素材占用 `0x01200000` 开始的资源区。初级展示在该资源区尾部
`0x012F0000` 初始化自己的 2048 字节 Sprite，并在启动时校验两个资源不重叠。
DDR 应用从 `0x01400000` 运行，片内 4 KiB 引导程序不变。

## 构建与验证

在 `my/first_light` 目录运行：

```powershell
python tools/build.py firmware --efinity C:/Efinity/efinity-riscv-ide-2026.1
python tools/build.py sim-menu-keys --modelsim D:/modelsim/win64
python tools/build.py sim-menu-soc --modelsim D:/modelsim/win64
python tools/build.py sim-basic-soc --modelsim D:/modelsim/win64
python tools/build.py sim-soc --modelsim D:/modelsim/win64
python tools/build.py compile --efinity C:/Efinity/2026.1
python tools/test_sprite77_upload.py
```

实际工具目录可用 `--efinity`、`--modelsim` 替换。构建输出为
`outflow/first_light.bit`、`software/build/animation.bin`、片内 RAM 初始化文件。
上板时先配置当前 `outflow/first_light.bit`，再运行
`python tools/upload_sprite77.py --list-ports` 查询端口，接着用
`python tools/upload_sprite77.py --port COMx` 上传当前应用与素材。
`COMx` 需替换为本机实际串口号。

## 本次验证（2026-09-29）

- RISC-V 固件以 `-Wall -Wextra -Werror` 编译通过；DDR 应用为 5888 字节，片内引导固件仍在 4 KiB 限额内。
- `sim-menu-keys` 通过短脉冲、长按、四键独立事件和复位检查。
- `sim-menu-soc` 在真实 Sapphire 模型中通过默认 BASIC、进入初级、KEY3 返回、右选 ADVANCED、进入高级首帧的检查。
- `sim-soc` 通过 77 帧循环、KEY1 两态、CPU/HW/CPU 切换、12 次换页和 26 帧完整扫描；ModelSim 0 错误、0 警告。
- Efinity `compile` 的 map、interface、pnr、pgm 均通过；pinout 为 C4/P14/N14/A3。最小 setup slack 为 +0.195 ns，最小 hold slack 为 +0.026 ns。

上述是编译与仿真结果；菜单整合版尚未在开发板上按键验收。

## 随机基础展示更新（2026-10-01）

源代码：`software/basic_layout.h` 生成随机布局与棋盘格资源，
`software/main.c` 调用原有 Fill/Copy 驱动并保持一组 CPU/HW 对比期间的布局。
本次为 DDR 应用更新，片内 UART 引导二进制重新编译前后 SHA256 相同：
`ca7cdf126179badc79754e1339d673b18f72c010139bfea0fb13ca2b0ebff674`。
发布包复用 `releases/menu_20260929/first_light.bit`，其 SHA256 为
`7936b9a0d9d62e0a7bb5ecb4012d486c90c3ef409e7aac4ea7c51b5772eb3ea2`。
本次没有重新综合 FPGA。当前 `outflow/` 可能包含用户另一次构建，不作为本次打包输入。

布局边界与随机性检查（本机 MinGW GCC）：

```powershell
gcc -std=c11 -O2 -Wall -Wextra -Werror tools/test_basic_layout.c -o software/build/test_basic_layout.exe
.\software\build\test_basic_layout.exe
```

`sim-basic-soc` 运行实际 Sapphire 核和真实应用二进制，通过 UART `h` 加速切换到硬件，
检查两组随机布局的完整绘制区域、每组 CPU/HW 逐像素一致、硬件命令类型/数量/源地址、
双缓冲扫描、返回菜单、重新进入 BASIC 以及进入高级首帧。自动 4 秒切换沿用应用计时逻辑，
该快速仿真不等待完整 8 秒实时时段。

本次验证结果：

- 新 DDR 应用编译通过（`-Wall -Wextra -Werror`），二进制 6500 字节，BSS 412 字节。
- `test_basic_layout` 通过 10000 个种子的复现性、新布局、边界、不重叠、奇偶 X 和边缘偏移检查。
- `sim-basic-soc` 通过：两组 CPU/HW 图像逐像素一致，两组之间变化 55072 个像素；
  两帧硬件合计 34 次 Fill / 32 次普通 Copy，复制源为专用 32×32 DDR 资源。
  菜单返回、重新进入 BASIC、进入高级首帧、扫描像素及前后台页写入检查均通过。
  ModelSim 日志 `reports/simulation_basic_soc.log`：0 错误、0 警告。
- `tools/test_sprite77_upload.py` 的 4 项测试通过。
- 仿真扫描预览 `reports/basic_random_1.png`～`basic_random_4.png` 已输出，第二张已做视觉检查。
- 本次为软件更新，实板效果、4 秒自动切换及帧率仍需上板确认。

最新上板包为 `releases/menu_random_20261001/`，运行 `python tools/package_menu.py` 生成。
使用包内 `.bit` 与上传脚本，按该包 README 操作；旧包保留供回退。

顶层按键与 SoC GPIO 连线由 `tools/prepare.py` 重建；直接修改
`rtl/competition_top.v` 或 `first_light.peri.xml` 后再次运行 prepare 会被覆盖。
