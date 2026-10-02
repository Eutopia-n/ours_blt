# 初级 / 高级功能菜单

本工程把 `main` 分支的 32×32 RGB565 资源 Fill/Copy 演示和
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

初级展示沿用 32 个 32×32 RGB565 Sprite 的 CPU/HW Fill/Copy 对比；
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

顶层按键与 SoC GPIO 连线由 `tools/prepare.py` 重建；直接修改
`rtl/competition_top.v` 或 `first_light.peri.xml` 后再次运行 prepare 会被覆盖。
