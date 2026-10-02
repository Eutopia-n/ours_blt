# KEY2 透明度循环上板包

在 ADVANCED 中短按 KEY2：0 → 2 → 4 → … → 100 → 0。
按住 0.5 秒后，每 0.1 秒增加 2；松开停止。数值越大越透明。
菜单中 KEY2 仍是确认，进入高级展示时不会把确认长按当作透明度调节；松开再按生效。
每次重新进入高级展示从 0 开始。KEY1 去背开关、KEY3 返回菜单。
基础展示仍为 KEY0 CPU/FPGA 切换，KEY1 循环 32/128/256 个方块。

## 使用

1. Type-C 和 HDMI 连接开发板，冷启动。
2. Efinity Programmer 通过 JTAG 下载本目录的 first_light.bit。
3. 在本目录运行以下命令，COMx 使用查询得到的实际串口号：

```powershell
python tools/upload_sprite77.py --list-ports
python tools/upload_sprite77.py --port COMx
```

上传需要 pyserial。正常提示 ASSET READY → ASSET OK；应用启动标识
为 Ti60 ALPHA KEY2 20261002。JTAG 下载后不要按配置复位或断电，否则需重新下载。
新功能同时依赖本包的新 bitstream 和 animation.bin，请配套使用。

## 验证范围

控制逻辑、混合模块、完整渲染回归、真实 Sapphire 固件联合仿真和 Efinity 全流程编译通过。
长按计时和完整 51 档循环由实际软件控制函数的主机测试覆盖；联合仿真覆盖菜单确认
隔离、KEY2 0/2/4、CPU/HW、键控开关、返回重入、逐像素与实际扫描输出。
混合运算在综合报告中映射到 12 个 DSP48。时序、寄存器和复现方法见 ALPHA_KEY2.md。

reports/alpha_4.png 和 alpha_6.png 是仿真扫描画面，分别对应 2% CPU 与 4% FPGA。
这些不是实板照片；本版还需上板确认手感、长按回绕和持续运行。
source_snapshot 为本轮相关源文件快照；完整可编译工程仍在上级 my/first_light。
SHA256SUMS.txt 可核验包内文件。
