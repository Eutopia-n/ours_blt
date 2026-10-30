# Ti60 冰霜幸存者：270怪物版

打开[first_light.xml](first_light.xml)。当前配置为150MHz CPU/绘图、128KiB程序RAM、640×480显示；怪物逻辑与绘制上限270、我方子弹256。

玩家和怪物按用户确认的16:9满屏显示做纵向4/3移动补偿；史莱姆之间、蝙蝠之间避让，跨组穿行，B/D/E继续互相避让。只保留中心祭坛，视频演示页已移除。怪物+子弹达到512时出怪间隔加倍，回落448及以下恢复。

预编译配置与验证：[releases/enemy270_20261030](releases/enemy270_20261030)。实际板卡FPS尚未验证。

完整构建步骤见[仓库首页](../../README.md)，素材授权见[THIRD_PARTY.md](THIRD_PARTY.md)，本地验证见[reports/enemy270_validation.md](reports/enemy270_validation.md)。
vendor/内的DDR、Sapphire SoC和HDMI源码、许可证以及根目录/SoC的ROM初始化文件均为构建依赖，应保留。正常克隆后不需要运行tools/prepare.py；它只用于从另行保留的官方包重新导入底层工程，可能覆盖本工程配置。
