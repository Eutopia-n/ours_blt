# FROSTBOUND SURVIVOR 游戏 Demo

游戏入口在首页第三张卡片。目标是躲避追踪的怪物，利用自动魔法攻击消灭敌人、拾取经验、选择升级，存活 180 秒。失败后可以重开，也可以返回原来的 8 个独立功能演示页。

## 操作

| 画面 | KEY0 | KEY1 | KEY2 | KEY3 |
|---|---|---|---|---|
| 首页、功能菜单 | 上一项 | 下一项 | 进入 | 返回 |
| 游戏准备页 | — | — | 开始 | 返回首页 |
| 游戏进行中，按住移动 | 上 | 下 | 左 | 右 |
| 三选一升级 | 上一项 | 下一项 | 确认 | 暂停 |
| 暂停 | — | — | 继续 | 返回首页 |
| 死亡、胜利结算 | — | — | 重开 | 返回首页 |

游戏中同时按 KEY0+KEY1 或 KEY2+KEY3 暂停；两个相邻方向可以斜向移动。斜向速度归一化，避免斜走明显快于直走。暂停和升级选择期间，游戏时间、敌人、攻击和生命值停止推进。实际板级消抖仍为 20 ms，菜单单次按下只触发一次；游戏通过只读寄存器读取持续按住状态。UART 仅用于诊断和性能日志。

## 当前内容

- 用户提供的蓝色兜帽人物：四个方向，每个方向四帧走路动画，32×32 像素。
- 深蓝石砖竞技场、青色魔法和经验宝石，白色清晰字库、生命/经验进度条，与菜单配色统一。
- 怪物会在玩家周围随机出现并追踪；波次每 15 秒加强，精英守卫与第 120 秒后低概率出现的高血量守护者能承受更多攻击、造成更高碰撞伤害并掉落更多经验。
- 自动寻找最近敌人的魔法弹，以及围绕玩家旋转并周期伤害敌人的冰霜法球。
- 接触受伤、短暂无敌及人物闪烁；敌人死亡掉落经验，附近宝石自动吸附。
- 玩家血条会按生命值变为绿、黄、红；距离玩家最近的最多 8 个敌怪显示实时血条，守护者使用黄色长血条。精英和守护者有概率掉落蓝青色治疗符文，拾取恢复 25 点生命并保留经验奖励。
- 地图为 2048×1408 世界坐标，约为当前 624×360 可视区域的 10 倍；相机随人物移动并尽量让人物留在画面中心，地图边缘会限制相机和人物移动。
- 每次升级暂停并显示三个带图标的选项及当前等级/上限；六类升级各有等级上限和质变：伤害升级获得穿透弹，施法速度升满后双发，法球升满后强化冰霜伤害，移动速度升满后周期冲刺，拾取范围升满后全图吸附，治疗升满后增加持续回血。
- 暂停、继续、死亡结算、重开、180 秒胜利，以及返回首页。
- 固定对象池：最多 256 敌人、48 魔法弹、96 宝石、4 法球。画面上的 SPRITES 为当前逻辑对象总数，不是固定 64/128/256 负载，也不是实际提交的合成命令数；边界裁切和无敌闪烁可能减少实际绘制数量。固定负载仍从高阶 SPRITE BENCH 单独演示。

## 为什么这样实现

RISC-V 负责按键解释、定点坐标、追踪、最近目标选择、碰撞、经验、升级及状态转换。`survivor_game.c` 不访问 FPGA 寄存器，方便在主机直接验证完整规则。逻辑以 60 次/秒推进，由原工程 100 MHz CLINT 计时器累计实际间隔；渲染帧率下降时进行有限补算，暂停不累计游戏时间。游戏渲染按 60 Hz 双缓冲节奏提交。

FPGA 负责背景 Block Copy、RGB565 Alpha/Color Key 合成、DDR burst 和双缓冲扫描。两块帧缓冲只在游戏开始时各初始化一次；之后每帧只拷贝滚动的可玩地图区域，避免重复搬运完整 640×480 背景。HUD 静态字样每个页面只写一次，变化数字和血条只更新对应小区域。逻辑对象池仍支持 256 个敌人、96 个宝石和 48 个法术弹；渲染器对当前视野内的敌人/宝石/法术弹设置 32/32/24 个合成预算，并轮换起始槽位，让高波次保持 60 FPS。所有游戏 Sprite 使用 Color Key = 0，法球、魔法弹、宝石及受伤效果再叠加全图 Alpha。人物和怪物的透明轮廓由 Color Key 实现；当前没有逐像素 Alpha 通道。

参考 GitHub 的 [migalvalm/vampire-survivors-clone](https://github.com/migalvalm/vampire-survivors-clone) 中的刷怪、经验、升级暂停、最近目标与追踪结构，针对裸机 RISC-V 改写为无堆内存、无浮点的 C；参考源码与 MIT 许可证保存在 `third_party/survivors_reference`。敌人采用 [Kenney Tiny Dungeon](https://kenney.nl/assets/tiny-dungeon) 的 CC0 像素素材，从 GitHub 素材仓库固定提交取得。来源、裁切和使用范围见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 屏幕和 UART 指标

游戏每 30 个提交帧更新一次指标。进入准备、运行、升级、暂停或结算状态时清空采样，避免把不同负载混在一起。状态刚切换的零值表示尚未取得完整采样窗口。

| 指标 | 口径 |
|---|---|
| FPS | 30 帧 / 实际计时器间隔，包含逻辑、场景、HUD、换页等待和 UART 开销；整数截断 |
| US / RENDER_US | 每帧逻辑计算、游戏绘制和 HUD 的平均微秒数；排除换页等待与 UART |
| SPRITES | 玩家 + 活跃敌人 + 魔法弹 + 宝石 + 法球 |
| ENEMIES | 活跃敌人数 |
| 屏幕 DDR RD / DDR WR | 渲染引擎每帧平均读/写 burst，整数截断 |
| UART DDR_AR / DDR_AW | 同一 30 帧内渲染引擎读/写 burst 总数 |

渲染引擎计数包含游戏地图拷贝及 Sprite 合成；小型动态 HUD 血条改用 CPU 打包写入，CPU 像素写入、CPU DDR 读写和 HDMI 扫描不计入 DDR burst 统计，因此它不是 DDR 控制器全局流量。原独立功能页仍采用各自的 4 帧 CPU/HW 对比口径。FPS 由 30 帧墙钟时间窗口计算；地图每帧拷贝到后缓冲，HUD 静态字样每个页面仅写一次，数值和血条只有发生变化时才更新。SoC 游戏仿真曾报告 60 FPS、平均 RENDER_US 6435；最高 Sprite 负载建议在板上观察。

## 存储

为容纳完整游戏及 16 帧人物，Sapphire 片内 RAM 从上一版 16 KiB 扩为 64 KiB；综合模型、仿真模型、解码范围、链接脚本和四路初始化文件一起更新。链接脚本检查至少 4096 字节栈空间。程序和压缩图片随 bitstream 初始化。要让板卡掉电后自动启动，还需使用 Efinity Programmer 的 SPI Active/JTAG bridge 模式写入板载 8 MB Flash；步骤见 `FLASH_PROGRAMMING.md`。

| 区域 | 地址 | 字节数 |
|---|---|---:|
| framebuffer A | `0x01000000` | 614400 |
| framebuffer B | `0x01096000` | 614400 |
| 原性能测试 Sprite | `0x01200000` | 2048 |
| 原菜单四方向代表帧 | `0x01200800` | 8192 |
| 游戏图集，25 帧 | `0x01204000` | 51200 |
| 游戏背景，首次进入时生成并复用 | `0x01220000` | 614400 |
| 地图地砖循环纹理，首次进入时生成并复用 | `0x012B6000` | 131072 |
| 片内程序和变量 | `0xF9000000～0xF900FFFF` | 65536 容量 |

启动上传的 Sprite 共 61440 字节；首次进入游戏时生成 614400 字节场景背景和 131072 字节地图纹理。两个 framebuffer、资源、背景和地图纹理的有效数据总量为 2035712 字节，小于板卡 256 MB DDR3。片内 RAM 与板卡的 8 MB Flash、256 MB DDR3 是不同存储。

## 文件与函数

| 文件 | 作用 |
|---|---|
| `software/survivor_game.h/.c` | 游戏数据、`game_reset()` 初始化、`game_input()` 状态/按键、`game_tick()` 一次逻辑更新、`game_orbit_position()` 法球坐标、`game_sprite_count()` 对象统计 |
| `software/game_view.h` | 接入现有驱动与字库；`init_game_assets()` 上传图集、`game_background()` 生成场景及循环地砖、`game_draw_world_floor()` 按相机位置滚动地面、`game_sprite()` 裁切与合成、`game_loop()` 计时/输入/呈现 |
| `software/game_assets.h` | 共享调色板与 RLE 图集，生成文件 |
| `tools/prepare_game_assets.py` | 裁切开源敌人、生成魔法和宝石、打包 RGB565 资源 |
| `sim/test_survivor_game.c` | 不依赖 FPGA 的规则测试，包括对象池满载和 30000 次确定性逻辑更新 |
| `sim/tb_soc_game.sv` | 真实 Sapphire CPU 执行固件，核对持续按键、四方向/四动作帧、独立合成参考、DDR 整帧、HDMI、暂停/返回 |

在仓库根目录运行：

```powershell
python my/first_light/tools/build.py firmware
python my/first_light/tools/build.py sim-buttons
python my/first_light/tools/build.py sim
python my/first_light/tools/build.py sim-game
python my/first_light/tools/build.py sim-soc --ui-smoke
python my/first_light/tools/build.py compile
```

资源已随工程保存，普通构建不用联网或 Pillow。`prepare_game_assets.py` 从已核对的前 23 帧 RGB565 资源生成新增帧、RLE 和参考文件，只使用 Python 标准库；重新裁切原人物才需要 Pillow。`sim-game` 使用隔离的 ModelSim 库，输出 `reports/simulation_soc_game.log` 和 `reports/game_*.png`；有效预览以当前 `preview_soc_game.log` 为准。

主机规则测试可以使用任意支持 C99 的 C 编译器，例如 Tiny C Compiler：`tcc -Wall -Werror -o game_test.exe sim/test_survivor_game.c software/survivor_game.c`，再运行 `game_test.exe`。主机编译器不是 FPGA 固件构建依赖。

## 上板预期和排查

下载最新 `outflow/first_light.bit` 后，首页应有基础、高阶、游戏三项；进入游戏后先显示准备说明，KEY2 开始，按住方向键移动，魔法自动攻击，组合键暂停。新游戏胜负流程不依赖串口输入。

若仍为旧菜单，核对运行的 bitstream 路径和 SHA-256。若断电后不能自动启动，确认执行的是 `flash` 而不只是 `compile`，并检查 Programmer 配置模式与 SPI Flash 写入结果。若按住只能走一步，读 `0xF8100064` 的低四位，检查 `button_input.held`、顶层 `button_held` 和 `render_regs` 连线；事件位 `pending` 用于短按菜单，不能代替持续状态。若启动异常，检查 OCR 解码掩码 `0x0000FFFF`、`SYSTEM_RAM_A_SIZE=65536`，以及四个初始化 lane 每个 16384 行。若资源异常，核对 `0x01204000` 图集、每帧 2048 字节和行距 64；背景应在 `0x01220000`。若 HDMI 无画面，检查 DDR `cal_done`、HDMI PLL `hdmi_tx_locked`、UART 的 FAIL/TRAP 和渲染 STATUS。

编译与仿真通过后仍需实板确认按键手感、难度、最高负载 FPS 和显示器观感。当前是单场竞技生存 Demo，音效、持久存档和多角色选择不在本次实现中。
