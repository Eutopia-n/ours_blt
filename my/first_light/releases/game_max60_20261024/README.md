# 当前游戏与 MAX60 版本下载文件

归档日期：2026-10-24。对应源码提交：`0b2cab9b9aba2fc5a8d5cb221b636826cdffe18f`。

目标：Ti60F225；工程：`my/first_light`；工具：Efinity 2026.1.132。下载文件生成于 2026-10-23 18:02:21，本次上传保留现有编译结果，没有重新构建、运行仿真或下载到板卡。

## 文件用途

- `first_light.bit`：在 Efinity Programmer 中选择临时 JTAG 配置，载入此文件。
- `first_light.hex`：在 Efinity Programmer 中选择 Active/JTAG bridge（SPI Flash）方式写入，成功后可掉电启动。具体步骤见 [Flash 下载说明](../../FLASH_PROGRAMMING.md)。
- `first_light.elf`、`first_light.bin`、`first_light.map`：对应固件与链接信息，供调试和核对。FPGA 下载使用上面两种配置文件。
- `manifest.json`：对应源码提交、工具版本、文件大小与 SHA-256。

## 版本内容与记录

包括当前游戏、字体排版、压力测试 W/S 长按逐个增减、四种 Sprite 尺寸，以及按连续 30 帧条件记录实际绘制数量的游戏 MAX60。尚未加入敌怪防重叠。

[编译和主机检查记录](../../reports/ui_controls_max60_check_20261023.md) 属于此前已完成的检查，本次上传没有重跑。历史 RTL 仿真文件不代表本版本重新完成 RTL 仿真。

[用户提供的单次实测](../../reports/board_observation_20261024.md)：ENEMY=166、SPRITES=40、MAX60=57、FPS=60、RENDER_US=14470、DDR_RD=10672、DDR_WR=9447。MAX60=57 是该局历史纪录，不是硬件极限测定；平均 FPS=60 也不能证明每帧均无漏刷新。
