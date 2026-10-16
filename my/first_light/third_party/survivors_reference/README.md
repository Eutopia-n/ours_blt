# Survivor 规则参考快照

来源：<https://github.com/migalvalm/vampire-survivors-clone>，提交 `1c90e4f49363bd392d6da6cac01a9880ae2cdf21`，MIT 许可证见同目录 `LICENSE`。快照保留原始源码，用于审阅参考依据，不参与 FPGA 编译。

| 本地文件 | 原项目路径 | 用于参考 |
|---|---|---|
| `enemy_manager.gd` | `scenes/manager/enemy_manager.gd` | 波次、边缘随机出生、生成间隔 |
| `experience_manager.gd` | `scenes/manager/experience_manager.gd` | 经验累计和递增阈值 |
| `upgrade_manager.gd` | `scenes/manager/upgrade_manager.gd` | 升级候选及暂停选择 |
| `sword_ability_controller.gd` | `scenes/ability/sword_ability_controller/sword_ability_controller.gd` | 选择最近敌人、自动攻击 |
| `velocity_component.gd` | `scenes/component/velocity_component.gd` | 敌人朝玩家移动 |

裸机适配在 `../../software/survivor_game.c`：改为固定对象池、整数/定点坐标和 60 Hz 逻辑更新，并加入四按键输入、暂停/重开与 180 秒胜利。不是将 Godot 运行时搬到 FPGA。具体来源及素材使用范围见 `../../THIRD_PARTY.md`。
