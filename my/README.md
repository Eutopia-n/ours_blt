# Ti60F225 赛题二：2D 填充、Block Copy 与双缓冲

目标：RISC-V 通过 APB 寄存器下发填充/图像拷贝，硬件通过 AXI4 Burst 读写 DDR3，显示模块读取 DDR3 并输出 HDMI。

独立工程位于 [first_light](first_light/README.md)，Efinity 入口为 `first_light/first_light.xml`。

当前菜单、基础/高阶可视化、按键与 CPU/HW 屏幕对比见 [MENU_DEMO.md](first_light/MENU_DEMO.md)。双缓冲历史说明见 [DOUBLE_BUFFER.md](first_light/DOUBLE_BUFFER.md)，Block Copy 历史记录见 [BLOCK_COPY.md](first_light/BLOCK_COPY.md)，第一阶段历史验收见 [VALIDATION.md](first_light/VALIDATION.md)。官方 Demo 与 `fpga/new_project` 保留。

2026-10-08 新增 FROSTBOUND SURVIVOR 生存游戏：完整人物动画、按住移动、敌人追踪、自动攻击、经验升级、暂停、死亡重开和 180 秒胜利，见 [GAME_DEMO.md](first_light/GAME_DEMO.md)。开源参考和素材授权见 [THIRD_PARTY.md](first_light/THIRD_PARTY.md)。
