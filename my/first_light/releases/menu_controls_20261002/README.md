# KEY1 数量循环 / KEY0 CPU-FPGA 模式切换上板包

基础展示支持 32 / 128 / 256 / 512 个 32×32 方块，最大档为 512。
一半为随机颜色实心块（Fill），一半为白边棋盘格图像块（Copy），两类共用活动区域。
每个对象随机初始化位置、方向及各轴 24..96 像素/秒的速度，每帧按实际用时移动，碰边反弹。
不同渲染帧率不会改变设定速度；两类方块均可跨越左右半屏，避开 HUD 和底部提示。
每帧更新位置、清屏，再交替执行 Fill/Copy；所有档位允许重叠，被覆盖的操作仍执行并计数。
基础展示由 KEY0 手动切换 CPU/FPGA，保留数量、连续运动和两侧统计。
KEY1 按 32 → 128 → 256 → 512 → 32 循环数量。
切换档位在当前帧完成后生效，生成新布局、清空统计，并保留当前 CPU/FPGA 模式。
两个键同时按下时分别执行一次。基础展示已取消每 4 秒自动轮换。
重新进入 BASIC 从 32 档、CPU 模式开始。KEY3 返回菜单。
高级展示为 77 帧不规则精灵动画和颜色键控，继续约 4 秒自动切换 CPU/FPGA。

## 屏幕统计

- BLOCKS / FILL / COPY：每帧实际方块数和两类操作数；全屏清屏另计。
- FPS：已完成并提交显示的帧率，保留一位小数。
- US：平均渲染耗时，包含背景清屏和全部方块，排除运动计算、HUD 和等待垂直消隐。
- OPS/S：已完成的方块操作数 / 实际用时，包含运动计算、HUD 和显示等待，排除背景清屏及文字操作计数。
- CPU/HW：CPU 渲染微秒数 / 硬件渲染微秒数，保留一位小数。
- 未采到当前负载的数据时显示 -；两边均有样本后显示耗时比。

统计每个完成帧更新，按最多 4 帧或约 1 秒分组；低帧率不必凑满 4 帧。
切换负载或重新进入 BASIC 会清空两边旧统计。CPU/HW 对比保持对象数量、尺寸、
图像资源及绘制顺序相同；各窗口坐标随时间变化，不是逐帧冻结场景的对比。

本次更新 DDR 应用，FPGA bitstream 复用已验证的菜单版。
此前菜单发布包均保留，包括 menu_perf_20261002。请使用本目录的上传脚本，
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
新应用串口启动标识为 Ti60 MENU CONTROLS 20261002。
当前冷启动仍需要串口上传，不具备 Flash 自动加载应用和素材的功能。
若 ASSET CACHED 后仍显示旧程序，应完整断电、重新 JTAG 下载，再上传。

## 本次验证与性能范围

本版保留 32 / 128 / 256 / 512 四档及每块 32×32 的尺寸，验证重点为按键控制。
实际 RISC-V 应用的系统仿真覆盖 CPU/FPGA 切换、四档循环、512→32、同时按键、
UART c/h、返回菜单与高级入口，以及逐像素绘制、运动和显示页检查。
此前性能包实板 512 档为 HW FPS=30 / HW US=18323，已超过 60 FPS 的单帧时间预算。
本次按键调整不构成新的实板性能验证；完整范围、日志与后续性能目标见 MENU.md。

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
- 基础展示：KEY0 切换 CPU/FPGA，KEY1 循环增加数量，KEY2 无操作。
- 高级展示：KEY1 切换颜色键控。
- UART c/h 可手动切换 CPU/HW；切换保留所有对象的运动状态。

验证结果和限制见 MENU.md。preview_32.png、preview_512.png 是本版仿真扫描截图，
其中性能数值不代表实板结果；本版尚待上板验收。
