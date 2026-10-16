# 板载按键输入（2026-10-02 历史版本）

以下保留旧版引脚依据和验收记录。2026-10-06 的功能页改为菜单与单键操作；2026-10-08 游戏版通过新增持续状态寄存器接入按住移动，游戏组合键用于暂停。当前功能页以 [MENU_DEMO.md](MENU_DEMO.md) 为准，游戏以 [GAME_DEMO.md](GAME_DEMO.md) 为准。下文的移动步长、组合键用途、bitstream 哈希、固件大小、图片和性能数据仅对应旧版本，不能代表当前 `outflow` / `reports`。

当前 `main.c` 使用板载按键控制。UART 仅保留启动、异常和性能日志，不再处理 `w/a/s/d`、`1/2/4`、`h/c`。RISC-V 仍计算玩家位置、其他 Sprite 坐标和 AABB 碰撞；FPGA 仍完成 Alpha/Color Key 合成。

## 1. 按键与引脚

| 板载按键 | FPGA Pin Name | 封装管脚 | 功能 |
|---|---|---|---|
| KEY0 / SW0 | GPIOL_07 | C4 | 上移 8 像素 |
| KEY1 / SW1 | GPIOR_22 | P14 | 下移 8 像素 |
| KEY2 / SW2 | GPIOR_21 | N14 | 左移 8 像素 |
| KEY3 / SW3 | GPIOL_03 | A3 | 右移 8 像素 |
| KEY0+KEY1 | 同时按下并松开 | — | 64 → 128 → 256 → 64 |
| KEY2+KEY3 | 同时按下并松开 | — | CPU ↔ FPGA，保持所选模式 |

上述 4 个按键均为 3.3 V LVCMOS，板上有 10 kΩ 上拉电阻：释放为 1，按下接地为 0。它们是用户按键，不是单独的 `RESET_N` 配置复位按键。

依据：仓库根目录 `Ti60F225A_V4_SCH.pdf` 第 6/8 页、`TI60F225I3-V4 DEMO板软硬件设计说明-260813-1.pdf` 第 34 页（页码 33），以及 `01_Ti60F225_Key_led_osc_demo/01_Ti60F225_key_demo/LED_8bit_Test.peri.xml`。现有 SoC GPIO 原来分配到 LED，本次改为纯输入 `key_i[3:0]`，不会用输出驱动按键。官方外设文件中的 `i_arstn` 已不被当前顶层使用，本次移除这条重复占用 GPIOL_07 的约束；DDR/SoC 的 PLL 锁定及校准复位流程保持原样。

## 2. 为什么加硬件消抖与暂存

机械按键一次按下可能产生多个电平跳变。`rtl/button_input.v` 先用两级寄存器同步输入，再要求整个按键组合连续稳定 20 ms，才产生事件，避免一次按下被当成多次。

CPU 参考渲染一帧可能超过一次短按时间，因此只在帧边界读原始电平会漏掉按键。本版把一个消抖后的事件保留到 RISC-V 确认；释放按键不会抹掉该事件。单个方向键长按每 120 ms 尝试产生一次重复事件；组合键保持时不重复，组合键部分松开也不会转成方向命令，需全部松开后再按。

这是最小的单事件暂存，不是无限队列：事件未被 CPU 读取时，额外的新按下不会覆盖它。操作后等待画面/日志响应，再发下一条命令；CPU 模式下长按速度还受帧率限制。组合键尽量同时按下并保持至少 30 ms，松开至少 30 ms 后再按；不同步按下超过消抖时间可能先产生一个方向事件。其他多键组合暂不定义操作。

## 3. 软件接口与改动

`handle_buttons()` 在每帧绘制开始前处理一个事件：

- 从官方 `SYSTEM_GPIO_0_IO_CTRL`（`0xF8015000`）的 INPUT（`+0x00`）读取低 4 位事件掩码；0 表示没有事件，1/2/4/8 为方向，3/12 为组合键。
- 读取 OUTPUT（`+0x04`），翻转 bit0 写回作为确认；该输出只连接内部事件模块，不连接板上按键管脚。
- 启动时将 OUTPUT_ENABLE（`+0x08`）清零。其偏移来自官方 BSP 的 `driver/gpio.h`。
- 单方向更新位置；组合键更新数量或 CPU/HW 模式。玩家仍限制在 X=0～608、Y=0～448。

修改了 `rtl/competition_top.v`、`first_light.peri.xml`、`first_light.xml`、`tools/prepare.py` 和软件入口；新增 `rtl/button_input.v` 及专项仿真。更新模拟 GPIO 连接，使 SoC 仿真使用与实板相同的输入模块和消抖周期。没有改动合成引擎、DDR 地址布局或性能指标口径。

## 4. 构建与上板

仓库根目录执行：

```powershell
python my/first_light/tools/build.py firmware
python my/first_light/tools/build.py sim-buttons
python my/first_light/tools/build.py sim-soc
python my/first_light/tools/build.py compile
```

`compile` 使用已经生成的固件初始化文件，改 C 后必须先执行 `firmware`。`pgm : PASS` 是配置文件生成成功，不表示已经下载。

1. 在 Efinity Programmer 中用 JTAG 加载 `my/first_light/outflow/first_light.bit`，HDMI 接本板 TX。
2. 串口开 115200、8N1、无流控，应看到 `Ti60 DDR BLEND BUTTONS 64/128/256 CPU/HW`。启动为 CPU、64 个 Sprite。
3. 同时按 KEY2+KEY3 并松开，确认日志为 `HW ... SPRITES 64 ...`。此后模式保持，可单按四个方向键移动玩家。
4. 同时按 KEY0+KEY1 并松开，等待 `SPRITES 128`；再次按下并松开，等待 `SPRITES 256`；第三次回到 64。
5. 保存每档的完整 UART 指标行。`RENDER_US` 为 4 帧平均绘制时间；`DDR_AR/AW` 为 4 帧 FPGA 渲染 burst 总数，CPU 模式为 0，均不包括视频扫描。实板数据需实际下载后采集。

若没有响应：先确认启动行含 `BUTTONS`，再检查 `first_light.peri.xml` 的四个 `key_i` 引脚与表中一致、电平为 3.3 V、模式为 input。用片内逻辑分析工具观察 `key_i`，应从 `1111` 变为对应位 0；若原始输入正确，再观察 `button_pending` 是否非零及 `button_ack[0]` 是否翻转。组合键不切换时，先全部松开至少 30 ms，再同时按下；CPU 模式等待下一帧才更新。

## 5. 验证记录

固件构建通过：text 3288 B、data 16 B、bss 4 B，共 3308 B，保留原有 512 B 栈预留。专项仿真 `ALL BUTTON TESTS PASSED`，无错误/警告，覆盖短抖动、四方向、短按保留、长按重复、组合键单次触发、待处理事件保护和复位。

Efinity `compile` 通过：map/interface/pnr/pgm 均为 PASS。`outflow/first_light.bit` 大小 2,048,670 B，SHA256：

```text
71AD6E9C1D40BD0F1CCD0C89212A831EF0256DE62A05DC5B43A9B930199DCDDD
```

布局资源 XLR 20203/60800、RAM 86/256、DSP 18/160；100 MHz 核心 setup 余量 +1.989 ns，全部已约束时钟的最小 setup +0.314 ns、最小 hold +0.026 ns。引脚报告确认 KEY0～KEY3 均为独立的 3.3 V 输入。保留既有 DDR 时钟与 HDMI 相邻引脚的布局告警，需实板观察信号完整性。

真实 Sapphire RISC-V 联合仿真 `SOC TEST PASSED`，退出码 0，Errors: 0、Warnings: 0。按键事件共确认 5 次：短按上移、切 FPGA、切 128、切 256、回切 CPU；全程使用实板同样的 20 ms 消抖参数。提交 3 个 CPU 帧、18 个 HW 帧，确认 21 次换页，完成 A 页 14 帧/B 页 22 帧扫描，无前台写入、扫描像素不一致、欠载或读错误。

移动前后 CPU 帧、64/128/256 HW 首帧、回切 CPU 帧均比较完整 307200 个像素。碰撞数与独立 AABB 模型精确一致，四帧渲染 burst 与实际 AR/AW 握手计数精确一致，资源只上传一次（2048 B）。完整预览为 `reports/motion_1.png`、`motion_2.png`、`motion_3.png`、`motion_9.png`、`motion_15.png`、`motion_21.png`。

下表为按键版仿真数据，**不是实板实验数据**。所有 burst 均为 4 帧渲染总数：

| Sprite 数 | FPS | 平均渲染时间 / µs | DDR_AR / 4 帧 | DDR_AW / 4 帧 | 累计 HIT |
|---:|---:|---:|---:|---:|---:|
| 64 | 60 | 6596 | 20530 | 50738 | 5 |
| 128 | 60 | 9710 | 41068 | 63084 | 13 |
| 256 | 60 | 15862 | 82132 | 87764 | 25 |

日志：`reports/simulation_buttons.log`、`simulation_soc.log`、`preview_soc.log`、`compile.log`。当前仅生成配置文件，没有执行开发板下载。
