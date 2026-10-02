# 随机基础功能 / 高级功能菜单上板包

基础展示左侧为 16 个随机位置、随机颜色的 32×32 实心块（Fill），
右侧为 16 个随机位置的白边棋盘格图像块（Copy）。
同一布局先由 CPU 绘制约 4 秒，再由硬件绘制约 4 秒，然后生成下一组；
重新进入 BASIC 也会重新生成布局。布局互不遮挡，避开顶部指标和底部提示。
高级展示仍为 77 帧不规则精灵动画和颜色键控。

本次更新 DDR 应用，FPGA bitstream 复用已验证的菜单版。
旧 releases/menu_20260929 发布包保留。请使用本目录的上传脚本，
它会读取同目录配套的 software/build/animation.bin 和 assets 素材。

## 上板步骤（PowerShell）

1. 开发板断电重启，连接 Type-C USB 和 HDMI。
2. Efinity Programmer 选择 JTAG，下载本目录的 first_light.bit。
   下载后不要按 CRESET_N 或断电，否则会重新从 Flash 加载配置。
3. 关闭占用串口的串口助手，在本目录打开 PowerShell，执行：

```powershell
python -m pip install pyserial
python .\tools\upload_sprite77.py --list-ports
python .\tools\upload_sprite77.py --port COM15
```

COM15 必须替换为实际开发板串口。PowerShell 使用带引号的 Python 完整路径时，
在前面加 &。正常日志是 ASSET READY → 发送进度 → ASSET OK，之后显示菜单。
脚本末尾的 Animation is running 是沿用的提示；实际首先进入菜单。
当前冷启动仍需要串口上传，不具备 Flash 自动加载应用和素材的功能。
若 ASSET CACHED 后仍显示旧程序，应完整断电、重新 JTAG 下载，再上传。

## 按键

- 菜单：KEY0 左选 BASIC，KEY1 右选 ADVANCED，KEY2 确认。
- 任一展示：KEY3 返回菜单。
- 高级展示：KEY1 切换颜色键控。
- UART c/h 可手动切换 CPU/HW；手动切换保留当前随机布局。

验证结果和限制见 MENU.md；仿真画面不代表实板验收。
