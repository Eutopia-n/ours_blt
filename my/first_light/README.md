# Ti60 RISC-V + FPGA 2D 图形加速引擎

打开 [first_light.xml](first_light.xml)，当前构建为 [reference_ui_fix_20261116](releases/reference_ui_fix_20261116)（已编译，尚未上板）。

- [HEX 下载](releases/reference_ui_fix_20261116/first_light.hex) / [BIT 下载](releases/reference_ui_fix_20261116/first_light.bit)
- [基础演示操作与指标](BASIC_DEMO.md)
- [高阶效果操作](EFFECTS_DEMO.md)
- [本版验证和上板说明](releases/reference_ui_fix_20261116/README.md)
- [旧版下载与录制资料](releases/demo_buffer_slow_20261101/README.md)

双缓冲演示每次进入默认单缓冲撕裂、低速 8 像素/帧；W 切 8/16/32，S 手动切防撕裂。填充/复制默认 CPU；Alpha 初始透明度 255/255；压力初始 32×32，数量加减步长 5。

完整构建与目录说明见[仓库首页](../../README.md)。vendor、ROM 初始化文件、素材和许可证属于当前工程依赖，应保留。正常构建无需官方例程目录，不运行 tools/prepare.py。该脚本仅在另有完整官方包时用于重新导入底层模板。

本次修复 Enter 后停在封面：菜单 FPGA 的绘制完成状态现在保持到下一条指令，CPU 延迟查询不会漏读。已用真实 APB 在旧逻辑复现，并验证修复后通过。

界面以 `assets/ui/magic_book_v5/魔法书交互预览.html` 为基准。封面、九个菜单状态和游戏准备页，已在 RGB565 下与本地预设逐像素一致。游戏的运行 HUD、暂停、强化选择、失败和胜利页均已更新，具体演示及游戏继续全屏，游戏场景使用纯色背景。

六项演示的标题、徽标、数据列、详情、视窗、页脚已按本地文件重排。16 种演示状态的静态区域在 RGB565 下与预设一致；实时数值和运动测试区单独核对。[查看实际代码画面](reports/reference_demo_gallery.png)。

动画采用预设的封扣、封面、弯曲纸页和分段缓动。新增菜单专用 FPGA 扫描线绘制模块完成纹理缩放、明暗和透明混合，CPU 只生成绘制指令；按实际时间跳过过期姿态，开书目标 2.4 秒、章节翻页 0.64 秒。最终文字在原始分辨率绘制。资源仍复用原 1 MiB DDR 区，不存整屏动画序列。CPU 时钟和 HDMI 配置保留。

验证范围及最终资源、时序数据见 [发布说明](releases/reference_ui_fix_20261116/README.md)。已检查实际 C 绘制、FPGA 像素输出、连续 HDMI 扫描和压力页切换。尚未上板，预览中的 FPS 为排版填充值，GIF 时长不代表实体板卡帧率。上板后请记录串口 `BOOK FRAMES ... MS ...`；若动画仍不顺畅，优先用这两项定位实际耗时。
