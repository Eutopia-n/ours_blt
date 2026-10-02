# 可调负载基础功能 / 高级功能菜单上板包

基础展示支持 32 / 128 / 256 / 512 / 1024 个 32×32 方块。
左侧一半为随机颜色实心块（Fill），右侧一半为白边棋盘格图像块（Copy）。
每帧先清屏，再执行所有操作；高档允许重叠，覆盖掉的操作仍实际执行并计数。
32 档每半屏 16 块互不重叠；所有档位避开 HUD 和底部按键提示。
同一布局先由 CPU 绘制约 4 秒，再由硬件绘制约 4 秒，然后生成下一组；
KEY0 降档，KEY1 升档，到端点后不循环，两个键同时按下抵消。
切换档位在当前帧完成后生效，生成新布局、清空统计并从 CPU 开始。
重新进入 BASIC 从 32 档开始。KEY3 返回菜单。
高级展示仍为 77 帧不规则精灵动画和颜色键控。

## 屏幕统计

- BLOCKS / FILL / COPY：每帧实际方块数和两类操作数；全屏清屏另计。
- FPS：已完成并提交显示的帧率，保留一位小数。
- US：平均渲染耗时，包含背景清屏和全部方块，排除 HUD 和等待垂直消隐。
- OPS/S：已完成的方块操作数 / 实际用时，包含 HUD 和显示等待，排除背景清屏及文字操作计数。
- CPU/HW：CPU 渲染微秒数 / 硬件渲染微秒数，保留一位小数。
- 未采到当前布局的数据时显示 -；两边均有样本后显示耗时比。

统计每个完成帧更新，按最多 4 帧或约 1 秒分组；低帧率不必凑满 4 帧。
切换负载或生成下一组布局会同时清空两边旧统计，避免不同负载/布局混算。

本次更新 DDR 应用，FPGA bitstream 复用已验证的菜单版。
旧 releases/menu_20260929 和 menu_random_20261001 发布包保留。请使用本目录的上传脚本，
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
成功后脚本提示 Upload verified; the DDR application is running，屏幕首先进入菜单。
当前冷启动仍需要串口上传，不具备 Flash 自动加载应用和素材的功能。
若 ASSET CACHED 后仍显示旧程序，应完整断电、重新 JTAG 下载，再上传。

## 上传中断的处理

脚本对串口打开、读取、写入和验证阶段的 I/O 错误最多尝试 3 次。
发生中断时取消待发送数据、关闭旧串口，等待 3 秒后重新打开，
收到新的 ASSET READY 后从第 0 字节重传；不会从中断偏移继续。
Write timeout 后的 ClearCommError / 拒绝访问表示 Windows 串口操作失败，
仅凭日志不能确定是 USB 连接、驱动还是端口占用问题。

1. 停止其他上传进程，关闭串口助手、VS Code 串口监视器及 Efinity Programmer。
2. 再次执行本目录的上传脚本；若仍失败，检查 Type-C 线和 USB 连接，优先直连电脑。
3. 若拔插 USB 导致板子断电，重新 JTAG 下载 first_light.bit 后再上传；
   不要在 JTAG 下载后按 CRESET_N。端口号改变时重新 --list-ports。

自动重试不能恢复已经丢失的 FPGA 配置。如果应用已启动但 ASSET OK 丢失，
它也不会重新发送 READY，此时需要完整断电、重新 JTAG 下载并上传。

## 按键

- 菜单：KEY0 左选 BASIC，KEY1 右选 ADVANCED，KEY2 确认。
- 任一展示：KEY3 返回菜单。
- 基础展示：KEY0 降低数量，KEY1 增加数量，KEY2 无操作。
- 高级展示：KEY1 切换颜色键控。
- UART c/h 可手动切换 CPU/HW；手动切换保留当前随机布局。

验证结果和限制见 MENU.md。preview_1024.png 是本版 1024 档仿真扫描截图，
其中性能数值不代表实板结果；本版尚待上板验收。
