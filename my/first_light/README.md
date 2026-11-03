# Ti60 RISC-V + FPGA 2D 图形加速引擎

打开 [first_light.xml](first_light.xml)，当前发布为 [demo_buffer_slow_20261101](releases/demo_buffer_slow_20261101)。

- [HEX 下载](releases/demo_buffer_slow_20261101/first_light.hex) / [BIT 下载](releases/demo_buffer_slow_20261101/first_light.bit)
- [基础演示操作与指标](BASIC_DEMO.md)
- [高阶效果操作](EFFECTS_DEMO.md)
- [本版验证和限制](releases/demo_buffer_slow_20261101/VALIDATION.md)
- [录制脚本](releases/demo_buffer_slow_20261101/录制脚本.md)

双缓冲演示每次进入默认单缓冲撕裂、低速 8 像素/帧；W 切 8/16/32，S 手动切防撕裂。填充/复制默认 CPU；Alpha 初始透明度 255/255；压力初始 32×32，数量加减步长 5。

完整构建与目录说明见[仓库首页](../../README.md)。vendor、ROM 初始化文件、素材和许可证属于当前工程依赖，应保留。正常构建无需官方例程目录，不运行 tools/prepare.py。该脚本仅在另有完整官方包时用于重新导入底层模板。

配置为 CPU/BitBlt 150MHz、程序 RAM 128KiB、640×480 HDMI；游戏为 256 敌人池/256 子弹池、20 宝石显示、128px 祭坛和 W1 围墙。新版已通过主机/RTL/CPU 启动及编译检查，尚未上板验证性能。较早文档中的旧参数以当前源码和最新 release 为准。
