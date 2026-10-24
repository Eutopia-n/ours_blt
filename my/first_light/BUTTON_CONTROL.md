# J28 外接五键输入（2026-10-19）

按键从板上原有按键改为 J7 外接子卡 J28 的五个独立输入，复位键保持原连接。J28 按键的另一端统一接 GND，输入为低电平有效。当前功能页以 [MENU_DEMO.md](MENU_DEMO.md) 为准，游戏以 [GAME_DEMO.md](GAME_DEMO.md) 为准。

当前 `main.c` 使用 J28 外接按键控制。界面统一把五个按键命名为 `W/S/A/D/Enter`；UART 仅保留启动、异常和性能日志。RISC-V 仍计算玩家位置、其他 Sprite 坐标和 AABB 碰撞；FPGA 仍完成 Alpha/Color Key 合成。

## 1. 按键与引脚

| J28 接口 | FPGA Pin Name | 逻辑位 | 功能 |
|---|---|---|---|
| J28-34 | GPIOL_09 | bit0 / W | 菜单上一项；游戏上移；Alpha 加一；压力页数量加 1 |
| J28-37 | GPIOL_04 | bit1 / S | 菜单下一项；游戏下移；普通页切换 CPU/FPGA；压力页数量减 1 |
| J28-38 | GPIOL_10 | bit2 / A | 游戏左移；Alpha 减一；压力页上一尺寸 |
| J28-39 | GPIOL_06 | bit3 / D | 普通页返回；游戏右移；压力页下一尺寸 |
| J28-40 | GPIOR_13 | bit4 / Enter | 打开、开始、确认、暂停；压力页返回 |

上述 5 个按键均为 3.3 V LVCMOS；引脚启用 FPGA 弱上拉，释放为 1，按下接地为 0。它们是用户按键，不是单独的 `RESET_N` 配置复位按键。J7 表中这五路均标注为 3.3 V。

依据：用户提供的 J28 原理图和 J7 引脚分配表。现有顶层改为纯输入 `key_i[4:0]`，不会用输出驱动按键；SoC 原生 GPIO 仍为 4 位，第五键消抖事件通过渲染器寄存器 0x68 锁存，实时状态则通过 0x64 读取。复位键未接入 `key_i`，DDR/SoC 的 PLL 锁定及校准复位流程保持原样。

## 2. 为什么加硬件消抖与暂存

机械按键一次按下可能产生多个电平跳变。`rtl/button_input.v` 先用两级寄存器同步输入，再要求整个按键组合连续稳定 20 ms，才产生事件，避免一次按下被当成多次。

CPU 参考渲染一帧可能超过一次短按时间，因此只在帧边界读原始电平会漏掉按键。本版把一个消抖后的事件保留到 RISC-V 确认；释放按键不会抹掉该事件。菜单禁用自动重复，Alpha 与压力页 W/S 的长按重复由软件计时器处理；游戏移动直接读取 5 位持续状态。

这是最小的单事件暂存，不是无限队列：事件未被 CPU 读取时，额外的新按下不会覆盖它。操作后等待画面/日志响应，再发下一条命令。组合键不再承担游戏暂停或性能切换，避免方向键与功能键互相抢占。

## 3. 软件接口与改动

`handle_buttons()` 在每帧绘制开始前处理一个事件：

- 从官方 `SYSTEM_GPIO_0_IO_CTRL`（`0xF8015000`）的 INPUT（`+0x00`）读取低 4 位事件掩码；第五键读取图形控制器 `GFX_BUTTON_ENTER_EVENT`（寄存器 `0x68`）。
- 读取 OUTPUT（`+0x04`），翻转 bit0 写回作为确认；该输出只连接内部事件模块，不连接板上按键管脚。
- 启动时将 OUTPUT_ENABLE（`+0x08`）清零。其偏移来自官方 BSP 的 `driver/gpio.h`。
- bit0～3 直接作为游戏上下左右持续状态；bit4 作为菜单/游戏操作键。玩家仍限制在可扩展世界边界内。

`rtl/button_input.v` 对五键统一消抖，GPIO 确认翻转同时清除第五键事件；渲染器寄存器 0x68 暴露第五键锁存事件，0x64 保留实时按键状态。这样 Enter 短按在画面换页期间也不会丢失。没有改动 DDR 地址布局或性能指标口径。

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
2. 串口开 115200、8N1、无流控；启动后使用 W/S 选择，Enter 进入，D 返回。
3. 游戏中 W/S/A/D 分别控制上/下/左/右，Enter 开始、暂停、确认。
4. Alpha 页 W/A 以步进 1 调整透明度，长按持续变化；D 离开功能页。
5. Sprite 压力页：W 加 1、S 减 1；持续按住约 300 ms 后，每约 60 ms 连续加/减 1，松开停止；A/D 双向循环 4×4、16×16、24×24、32×32，长按不重复切换；Enter 返回。每种尺寸独立记录 `MAX60`。调整负载时重开采样，松开保持约半秒观察一次 30 帧结果。
6. 保存每档的完整 UART 指标行。`RENDER_US` 为普通页 4 帧、压力页 30 帧的平均绘制时间；`DDR_AR/AW` 为同一采样窗口的 FPGA 渲染 burst 总数，CPU 模式为 0，均不包括视频扫描。实板数据需实际下载后采集。

若没有响应：先检查 `first_light.peri.xml` 的五个 `key_i` 引脚是否为 GPIOL_09、GPIOL_04、GPIOL_10、GPIOL_06、GPIOR_13，电平为 3.3 V、模式为 input。用片内逻辑分析工具观察 `key_i`，释放应为 `11111`，按下某键对应位变为 0；再观察 `button_pending` 低四位和 `button_ack[0]` 是否翻转。第五键可观察 `GFX_BUTTON_HELD[4]`。

## 5. 当前验证记录

- 固件构建通过：text 55812 B、data 8 B、bss 5484 B，共 61304 B，低于 64 KiB 片内 RAM；四路初始化文件已重新生成。
- `python my/first_light/tools/build.py sim-buttons` 通过：五键消抖、短按暂存、确认清除及独立按键动作回归通过。
- `python my/first_light/tools/build.py sim` 通过：FIFO、拷贝、Alpha/Color Key、填充、HDMI、双缓冲、AXI 背压及错误恢复均通过；图形寄存器 0x68 的 Enter 事件读回也通过。
- `python my/first_light/tools/build.py sim-soc --ui-smoke` 通过：真实 Sapphire CPU 固件验证 23 个页面、27 次 HDMI 完整扫描及菜单/功能页按键操作。
- `python my/first_light/tools/build.py sim-game` 通过：52 次换页、48 帧游戏、73 次 HDMI 扫描、634 条渲染命令，覆盖五键、四方向动画、怪物/法球 Alpha+Key、暂停/继续/返回和无前台页写入。
- 以上为固件、RTL 和 ModelSim 仿真结果；实际 J28 接线、电气情况以及板上最高负载 FPS 仍以下载后观察为准。本次没有写入板卡或上传 GitHub。
