# 游戏开源参考与素材来源

## 游戏逻辑参考

- 项目：[migalvalm/vampire-survivors-clone](https://github.com/migalvalm/vampire-survivors-clone)。
- 固定提交：`1c90e4f49363bd392d6da6cac01a9880ae2cdf21`。
- 许可证：MIT，原文保存在 [third_party/survivors_reference/LICENSE](third_party/survivors_reference/LICENSE)。
- 参考源码：敌人生成管理、经验阈值、升级选择暂停、最近目标选择、速度追踪；五个 GDScript 原始快照保存在 `third_party/survivors_reference`。
- 使用方式：结构和规则参考，改写到 `software/survivor_game.c` 的定点 C 实现。Godot 场景、引擎、音频和该仓库图像没有加入 FPGA 构建。升级数值、360 秒关卡、对象池与板上操作由本工程定义。

## 敌人图像

- 原作者和素材包：[Kenney / Tiny Dungeon](https://kenney.nl/assets/tiny-dungeon)，16×16 像素，CC0。
- GitHub 分发来源：[series-ai/jam-ready-assets](https://github.com/series-ai/jam-ready-assets)，固定提交 `cfb6cb12b3d54a6c8158b74dc57d7caf0f01000a`。
- 原文件：`kenney-tiny-dungeon/2D/dungeon/Tilemap/tilemap_packed.png`。
- 本地原图：[assets/game/source/kenney_tiny_dungeon.png](assets/game/source/kenney_tiny_dungeon.png)，SHA-256：`d24e60a41e4ac7a745c0304dfde121143688557f40215f23221c29cfe683825f`。
- 素材包原始说明和授权：[assets/game/source/KENNEY_LICENSE.txt](assets/game/source/KENNEY_LICENSE.txt)。依据素材本身的 CC0 标识使用，未将分发仓库的通用许可替代素材许可。
- 采用三格：从左上角起、零基列/行的史莱姆 `(0,9)`、骷髅 `(1,10)`、蝙蝠 `(0,10)`，最近邻放大到 32×32 并转为 RGB565 Color Key 格式。
- 新增蓝色精英守卫由上述骷髅 RGB565 帧改色，使用同一 CC0 来源，没有加入其他不明许可素材。

## 用户人物及本地生成内容

人物原图由用户提供，保存在 `assets/player/source.png`；本工程不声称拥有该图版权，也不为它附加 CC0/MIT 许可。四方向动画的裁切、缩放和透明键处理见 [人物资源说明](assets/player/README.md)。

治疗爱心图集 `assets/game/source/user_hearts.png` 来自用户在本次需求中提供的图片附件，选用粉色爱心格并最近邻放大；其版权/许可未由用户说明，本工程不为该素材附加许可声明。

石砖竞技场、宝石、魔法弹、环绕法球、深蓝/青色治疗符文、守护者重着色帧与备用闪光帧由本工程代码生成，与人物和菜单配色协调。备用闪光帧已打包，当前战斗受击效果使用怪物 Alpha 变化及玩家闪烁。

## 中文字体

- 中文字形使用 [TakWolf/fusion-pixel-font](https://github.com/TakWolf/fusion-pixel-font) 的 Fusion Pixel 12px zh_Hans 点阵字形；当前实际使用的字符子集保存在 [software/font_cn.h](software/font_cn.h)，按 12×12 点阵绘制并置于现有 14×14 字符单元中央。
- 上游字体版本为 `2026.10.25`，字体授权为 SIL Open Font License 1.1；许可证副本保存在 [third_party/fusion-pixel-font/OFL.txt](third_party/fusion-pixel-font/OFL.txt)。本项目仅保留界面需要的字形，不包含完整上游字库。
- 字库作为 C 头文件编译进片内固件，不依赖字体运行时，也不会读取外部字体文件。需要更新字形时，可按 [third_party/fusion-pixel-font/README.md](third_party/fusion-pixel-font/README.md) 的步骤重新生成。
