# FROSTBOUND SURVIVOR 验证记录（2026-10-08）

## 交付与预期现象

首页保留基础、高阶两组共 8 个独立功能演示，第三项进入 FROSTBOUND SURVIVOR。游戏使用用户人物四方向 × 四动作帧、深蓝石砖竞技场、青色法术与经验宝石、Kenney 像素敌人；按住四个板上按键移动，攻击自动进行。支持随机波次、追踪、碰撞受伤与无敌时间、经验吸附、三选一升级、暂停/继续、死亡重开、180 秒胜利及返回菜单。

规则在 `software/survivor_game.c`，显示与现有驱动适配在 `software/game_view.h`。RISC-V 负责位置/碰撞/规则，FPGA 负责背景拷贝、Alpha/Color Key 合成及 HDMI。新增只读 APB `0xF8100064` 暴露消抖后的持续按键状态；原 GPIO 暂存事件继续用于菜单短按。板级引脚沿用已核对的现有连接，没有新增引脚约定。

游戏操作见 [GAME_DEMO.md](../GAME_DEMO.md)；固定提交、MIT/CC0 许可证及使用范围见 [THIRD_PARTY.md](../THIRD_PARTY.md)。

## 编译、内存和配置产物

- 固件：`python tools/build.py firmware` 通过，C 编译启用 `-Wall -Wextra -Werror`。裸机链接保留片内 RAM 的 RWX 段提示。
- text = 42200 B，data = 8 B，bss = 3540 B，总计 45748 B，固件二进制 42208 B。
- 片内 RAM 64 KiB，剩余 19788 B，可用栈通过链接脚本至少 4096 B 检查。综合与仿真 OCR 解码窗口、地址线和 RAM 深度一致。
- 四路初始化文件每路 16384 项；已逐字节重组为完整 65536 B 映像，与当前固件二进制加零填充相同。根目录及 `vendor/soc` 两处初始化文件完全一致。
- 二进制 SHA-256：`49CD43298C3D6A9FF77172DD6302ECF9B7EA1F4979497C569D8F4C7EF8AE87D8`。
- `python tools/build.py compile`：map、interface、pnr、pgm 全部 PASS；pgm 是配置产物生成，没有执行板卡下载或外部 Flash 编程。
- bitstream：2351703 B；SHA-256：`A286D1CB6F9DBF5C7C43243F551C55FBA6DB495A642B71960F67E1D543E18BC9`。
- 资源综合报告：12003 LUT4、11342 FF、146 RAM10、6 DSP48、12 DSP24。
- 布线时序报告（15:24:33）：100 MHz core setup slack +1.987 ns、400 MHz DDR +0.362 ns、约 25.209 MHz HDMI +34.466 ns。列出的 setup/hold 关系均为正裕量。

配置产物在 `outflow/first_light.bit`，归档副本在 `releases/survivor_20261008/first_light.bit`。当前游戏没有新增 Flash 装载依赖；Flash/DDR3 容量与片内程序 RAM 不能互相替代。

## 规则测试

`sim/test_survivor_game.c` 用主机 C 编译器执行真实 `survivor_game.c`，结果见 [game_logic.log](game_logic.log)。

覆盖持续移动、停止、斜向与边界钳位、两组暂停组合键及松开后的短按、暂停计时冻结、返回、最近敌人自动攻击、魔法弹击杀、碰撞扣血和无敌保护、经验跨阈值与保留余量、六类升级、死亡优先级、死亡重开、180 秒胜利边界、256 敌人池满载、96 宝石池合并经验及 30000 次确定性更新。两份相同种子/输入的游戏状态逐次完全一致，测试中发生 68 次升级和 12 次结束/重开，动态运行峰值敌人 39 个；满载测试另行覆盖 256 个。

这证明规则和边界，不代表在板上连续玩完 180 秒，也不代表 256 敌人的实际渲染性能。

## 按键与渲染 RTL 回归

- `python tools/build.py sim-buttons`：通过，Errors = 0、Warnings = 0。检查消抖、四键持续状态、事件确认后持续状态保留、松开清零、短按暂存、组合键、斜向及复位。
- `python tools/build.py sim`：通过，Errors = 0、Warnings = 0。保留 Fill/Copy/Alpha/Color Key 像素、完整 RGB565 混合运算、AXI 反压、4 KB 边界、FIFO、双缓冲及读错误回归；新增持续按键寄存器的读值和只读错误检查。

日志：[simulation_buttons.log](simulation_buttons.log)、[simulation.log](simulation.log)。

## 真实 CPU 游戏整机仿真

`python tools/build.py sim-game` 通过，`SOC GAME TEST PASSED`，Errors = 0、Warnings = 0。实际 Sapphire CPU 执行同一 release 固件，使用带 AXI 反压的 DDR 模型以及原 100 MHz 核心、25.208333 MHz 像素时钟；仅将按键消抖等待缩短为 32 核心周期，实板仍为 20 ms。

- 50 张提交页面，46 个游戏呈现帧，64 个完整 HDMI 扫描帧，437 条渲染命令。
- 启动图像上传恰好 57344 B，全部 23 帧游戏图像与未压缩源参考逐像素相同，菜单四方向代表帧也相同。
- 初次进入游戏生成背景恰好 614400 B。背景与图像均位于原 1 MiB DDR 资源池内；两个 framebuffer、Sprite 和背景的有效数据总计 1900544 B。
- 持续按住后的玩家位置变化、四方向与四个动作帧全部覆盖；APB 按住位与消抖状态逐次核对。
- 敌人和法球的 Alpha/Color Key 合成与独立整数参考一致；每次 FPGA 像素写入、每张后台页、每个 HDMI 像素均核对。
- 两组组合键暂停、KEY2 继续、斜向移动、KEY3 返回菜单通过。最终第 50 张页面为实际返回后的首页，已完成完整扫描。
- 无前台页写入、换页中途切换、混合页面、显示下溢或读响应错误。

首个连续运行的 30 帧窗口，UART 输出：

```text
GAME FPS 60 RENDER_US 10308 SPRITES 5 ENEMIES 1 DDR_AR 298646 DDR_AW 300828 LEVEL 1 KILLS 1
```

这是约 1 秒、少量敌人的仿真样本；不是实板数据，也不能推算 64/128/256 敌人性能。FPS 包括逻辑、HUD、换页等待和采样窗口内 UART；渲染时间包含逻辑、场景/HUD，排除换页与 UART。读写 burst 为渲染引擎 30 帧累计，排除 CPU 和 HDMI 扫描。当前采样末帧对象数不等于窗口平均对象数。

日志：[simulation_soc_game.log](simulation_soc_game.log)、[soc_game_progress.log](soc_game_progress.log)。准备、运行、暂停和返回的图像来自经过核对的实际 HDMI 扫描；升级/死亡/胜利规则在主机测试覆盖，未通过加速或注入状态伪装为整机完整通关。

预览：[首页](survivor_home.png)、[准备](survivor_ready.png)、[运行](survivor_play.png)、[暂停](survivor_pause.png)、[返回首页](survivor_return.png)。

## 原独立菜单回归

`python tools/build.py sim-soc --ui-smoke` 通过，Errors = 0、Warnings = 0。19 张菜单、24 张提交页、27 个完整扫描帧、24 次换页；前向/反向循环、进入/返回、Fill 参数切换、Alpha HW/CPU 代表性功能正常。扩展图像上传 57344 B 后菜单四方向参考仍完全一致。

日志：[simulation_soc_ui.log](simulation_soc_ui.log)。本次没有重新测量完整八功能/64、128、256 Sprite 性能，历史完整回归见 [individual_validation_20261006.md](individual_validation_20261006.md)，不要将历史结果写成当前游戏实板测量。

## 上板验收

1. 下载上述归档 bitstream，确认首页三项并核对 SHA-256。
2. 进入第三项，KEY2 开始，按住各方向并尝试斜向；验证停止、朝向和动画。
3. 组合键暂停，KEY2 继续；进入升级后 KEY0/1 选择、KEY2 确认；检查暂停/选择不推进游戏时间。
4. 留在怪物附近观察受伤和无敌闪烁，失败后 KEY2 重开；正常生存至 180 秒检查胜利结算。
5. 暂停后 KEY3 返回，分别演示原基础、高阶功能及 64/128/256 固定负载。
6. 保存 UART 游戏/性能日志，记录实际敌人数、Sprite 数、FPS、渲染时间和引擎 burst；与仿真记录分开注明。

若异常，具体寄存器、初始化范围和板级信号检查见 [GAME_DEMO.md](../GAME_DEMO.md) 末尾；本次尚未执行上板下载，实际操控与高负载难度需要实板调整。
