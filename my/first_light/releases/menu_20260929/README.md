# 初级 / 高级菜单上板包

本目录的 `first_light.bit` 与 `software/build/animation.bin` 来自同一次菜单版构建。
`assets/sprite77.upload`、`assets/sprite77.raw` 是 77 帧高级展示素材。
配置 FPGA 后，DDR 尚无应用和素材，需通过 UART 上传后才显示菜单。

1. 将整个文件夹复制到运行 Windows 的电脑，接好开发板 Type-C USB 和 HDMI。
2. 用 Efinity Programmer 加载这里的 `first_light.bit`。
3. 在此目录的 PowerShell 中执行：

   ```powershell
   python -m pip install pyserial
   python .\tools\upload_sprite77.py --list-ports
   python .\tools\upload_sprite77.py --port COMx
   ```

   将 `COMx` 换成实际串口号。上传成功后显示一级菜单。

菜单中 KEY0 左选 BASIC，KEY1 右选 ADVANCED，KEY2 确认；
在展示中 KEY3 返回菜单。高级展示中 KEY1 继续控制颜色键控。
两种展示每 4 秒自动在 CPU/HW 路径间切换。

板卡引脚和验证流程见本目录的 `MENU.md`；源码位于工程的 `my/first_light`。
此包的 Efinity 编译、四键仿真、菜单联合仿真和完整高级回归均已通过，
详见 `MENU.md`。目前尚无本菜单版的实板照片或运行记录。
