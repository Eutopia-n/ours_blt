# 演示与生存游戏更新验证（2026-10-09）

## 改动与预期

1. Alpha 短按 KEY0 增加 16/255，KEY0+KEY1 减少 16/255；持续按住约 300 ms 后，每约 120 ms 调一级。端点饱和、松开停止，避免 255→0 的突变。CPU 慢帧时调节在帧边界执行，间隔会更长。
2. 功能页顶部明确显示 RISCV FPS / FPGA FPS、RENDER US、DDR R/W、BURSTS/FRAME 及测得的输出分辨率。Alpha 页对照 REFERENCE OPAQUE / FPGA ALPHA，保持 Color Key 关闭。
3. 游戏玩家血条按 HP 变绿/黄/红；最近的最多 8 个敌怪显示当前 HP / 出生时最大 HP。每条血条最多两次硬件 Fill，避免 256 个敌怪全部加绘血条；远处敌怪仍正常计算和渲染。
4. 玩家中心范围从 x=40～600、y=120～400 增到 x=24～616、y=96～424，面积约增加 24%。地图仍为单屏竞技场。
5. 60 秒后加入蓝色精英守卫；骷髅/精英死亡有 1/4 概率掉落粉色治疗符文，恢复 25 HP 并保留 XP，不超过最大 HP，不撤销同一 tick 已发生的致命碰撞。

操作与职责见 [MENU_DEMO.md](../MENU_DEMO.md)、[GAME_DEMO.md](../GAME_DEMO.md)。精英守卫是 Kenney CC0 骷髅改色，治疗符文由本工程生成，来源见 [THIRD_PARTY.md](../THIRD_PARTY.md)。

## 固件、存储及 FPGA 配置

- 固件 `-Wall -Wextra -Werror` 构建通过；text=43992 B、data=8 B、bss=3540 B，总计 47540 B。
- BIN=44000 B，SHA-256：`DB1F840F86EC1E5F650930503D45280356636F04B343710A2D5D15EFC30F0EE2`。
- 64 KiB 片内 RAM 剩余 17996 B；链接脚本的至少 4096 B 栈空间检查通过。四路初始化每路 16384 项，重组精确等于 65536 B 填充固件，两处初始化文件一致。
- 游戏图集 25 帧、51200 B，RLE/调色板/偏移共 19144 B。原前 23 帧继续复用，新增 23=治疗符文、24=精英守卫；生成工具使用 Python 标准库，重复生成保持一致。
- 启动图像上传共 61440 B；复用背景为 614400 B。两个 framebuffer、图像、背景有效数据合计 1904640 B；没有执行 Flash 编程。
- Efinity map/interface/pnr/pgm 全部 PASS，bitstream=2356620 B；SHA-256：`3586F2A696F29354BAB15949202B5F55B2974ACA3C6135C60FD7485CEB672F80`。
- 2026-10-09 17:01:09 时序：core 100 MHz setup +1.987 ns，DDR 400 MHz +0.362 ns，HDMI +34.466 ns。报告列出的 setup/hold 关系均为正。
- 综合资源：12003 LUT4、11342 FF、146 RAM10、6 DSP48、12 DSP24。

## 已完成验证

- 按键 RTL：消抖、短按保留、held、可选重复、组合键、复位通过，Errors=0/Warnings=0。
- 渲染 RTL：Fill/Copy、61 组 Alpha/Key、1048576 通道组合、AXI 反压、4 KB 边界、错误恢复、双缓冲及完整 HDMI 像素通过，Errors=0/Warnings=0。
- 主机规则：用 MSVC C11 编译执行真实 `survivor_game.c` 及 `demo_alpha_update()`，Alpha 步进、延迟/重复/释放/端点/计时器回卷、扩大地图边界、治疗/上限/致命伤、精英出生/掉落、原升级/暂停/胜负/满对象池均通过。30000 次确定性更新中，两份状态逐 tick 一致；111 次升级、4 次结束、峰值 256 敌怪。
- 开发中的独立页完整 SoC 回归通过：79 张提交页、8 个 CPU 帧、49 个 FPGA 帧、118 个 HDMI 扫描帧，所有八功能与 64/128/256 负载核对完成。随后增加 Alpha 端点饱和/减小组合键和修正底栏重叠；最终固件以另行菜单/Alpha 代表页及游戏整机回归为准，不能把此中间版本记录标为最终二进制完整八功能验证。

日志：[game_logic.log](game_logic.log)、[simulation_buttons.log](simulation_buttons.log)、[simulation.log](simulation.log)、[simulation_soc.log](simulation_soc.log)。

## 最终固件整机回归

菜单/Alpha 代表页回归通过：19 张菜单页、24 张提交页、27 个完整 HDMI 核对帧、24 次换页；61440 B 图像逐像素核对，前后菜单循环、Fill 调参、Alpha 128→144、CPU/FPGA 同图与返回均通过，Errors=0/Warnings=0。日志：[simulation_soc_ui.log](simulation_soc_ui.log)。Alpha 长按节奏、递减与端点在主机 C 测试覆盖；本次整机 Alpha 场景验证短按增量，不冒称已用 SoC 连续按住测试长按功能。

游戏 SoC 仿真通过：50 张提交页、46 个游戏帧、65 个完整 HDMI 核对帧、592 条渲染命令；上传图像恰好 61440 B、背景恰好 614400 B。持续按键、四方向/四动作帧、敌怪/法球 Alpha+Key、两组暂停、继续及返回菜单通过；每条命令像素、后台页和 HDMI 扫描与参考一致，无前台页写入、错页、扫描下溢或读错误，Errors=0/Warnings=0。验证采用真实 Sapphire CPU、100 MHz CLINT、DDR 反压和逐点 HDMI 比对，实板消抖仍为 20 ms，仿真仅缩短消抖等待。日志：[simulation_soc_game.log](simulation_soc_game.log)、[soc_game_progress.log](soc_game_progress.log)。

最终图集 25 帧均核对上传像素；短整机用例覆盖早期史莱姆与血条、人物和法球。60 秒后的精英/治疗规则在主机 C 测试覆盖，本次没有伪装成整机 180 秒完整通关。预览：[Alpha](survivor_20261009_alpha.png)、[准备](survivor_20261009_ready.png)、[游戏与血条](survivor_20261009_play.png)、[暂停](survivor_20261009_pause.png)、[返回](survivor_20261009_return.png)。

游戏首个 30 帧窗口日志为 `GAME FPS 60 RENDER_US 10559 SPRITES 6 ENEMIES 2 DDR_AR 299728 DDR_AW 302034 LEVEL 1 KILLS 0`。这是约一秒、两只敌怪的仿真样本；不是实板数据，也不是 256 敌人的性能。FPS/时间含义与 burst 计数边界见 [GAME_DEMO.md](../GAME_DEMO.md)。

## 上板验收

1. 在 Efinity Programmer 用易失性 JTAG 加载本版 bitstream，确认 SHA-256 与上文一致。
2. 进入高阶 ALPHA BLEND：KEY0 每次 +16，长按连续；KEY0+KEY1 降低；达到 0/255 保持。KEY1 单键仍切 CPU/FPGA。
3. 进入游戏：观察玩家血条、近敌血条、扩大边界及 FPS/RENDER US/DDR RD/WR；15 秒后骷髅、45 秒后蝙蝠、60 秒后精英守卫；拾取粉色符文回血。
4. 固定 64/128/256 测量仍从 SPRITE BENCH 单独运行，实际板上性能需另存 UART 日志。本次仿真结果不是实板 FPS。

异常时，Alpha 检查只读 `0xF8100064` 的 held 位与 100 MHz CLINT 时间基准；若只短按有变化，确认 KEY0 持续位为 1。血条检查 `hp/max_hp`、敌怪出生 `max_hp`、DDR 帧 23/24 的像素；旧菜单或旧图集先核对下载文件。HDMI 无画面检查 DDR `cal_done`、HDMI PLL `hdmi_tx_locked`、UART FAIL/TRAP 及渲染 STATUS。
