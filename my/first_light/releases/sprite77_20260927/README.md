# Ti60 77 帧动画上板包

此目录保存同一次构建所需的 FPGA bitstream、片内引导程序、DDR 动画程序、77 帧素材和串口上传脚本。素材源于用户提供的白底原图，帧序为从左到右、逐行向下；第 36～39 帧只有球棒，是原图内容。

## 队友在另一台 Windows 电脑上运行

1. **复制整个 `sprite77_20260927` 文件夹**到队友电脑；不要只复制 `.py`。上传脚本会从这个文件夹读取 `software/build/animation.bin`、`assets/sprite77.upload` 和 `assets/sprite77.raw`。上传现成包无需安装 Efinity 编译器、Pillow、NumPy 或 SciPy。
2. 接好板子的 Type-C USB 和 HDMI。若板子已断电，先用 Efinity Programmer 将本文件夹的 `first_light.bit` 配置到 FPGA；当前是易失性配置，断电后需要重新配置。板子运行期间，只需这**一份** bitstream，KEY1 和 CPU/HW 切换都不需要重新下载。
3. 在 Windows 安装 Python 3（含 pip）。用资源管理器打开本文件夹，在地址栏输入 `powershell` 并回车，终端就会位于本文件夹。依次运行：

   ```powershell
   python --version
   python -m pip install pyserial
   python .\tools\upload_sprite77.py --list-ports
   ```

   `python --version` 应显示 Python 3。如果 `python` 不是命令，可把以下所有命令中的 `python` 换成 `py -3`；如果它提示 `No installed Python found!`，请先安装 Python 3 并重新打开 PowerShell。已有 Python 但命令不在 PATH 时，可使用该电脑自己的完整 `python.exe` 路径，例如 `& 'C:\路径\到\python.exe' -m pip install pyserial`，再用同一路径执行脚本。`pip` 安装和运行脚本必须使用同一个 Python。
4. 可以在插拔板上 Type-C 前后各运行一次 `--list-ports`，找新出现的非 Bluetooth COM 口；在设备管理器“端口 (COM 和 LPT)”中核对。把下面示例的 `COM7` 改成队友电脑显示的实际号码（你这台电脑之前是 COM15，不是通用号码）：

   ```powershell
   python .\tools\upload_sprite77.py --port COM7
   ```

   脚本以 115200 8N1 打开串口，先等 `ASSET READY`，然后显示上传进度。约 35 秒后出现 `ASSET OK` 和 `Animation is running` 即成功，脚本会退出，HDMI 动画继续运行。若收到 `ASSET CACHED`，表示 DDR 中已有校验通过的素材，也会直接启动。每次冷启动后需再次上传；只按 KEY1 或切换 CPU/HW 时不用上传。

### 常见问题

- `error: --port is required`：VS Code 的“运行 Python 文件”按钮不会附加参数；请在 PowerShell 运行含 `--port COM数字` 的完整命令。
- `--list-ports` 只显示 Bluetooth 虚拟端口，或没有端口：检查 Type-C 数据线和 Windows 设备管理器。从 [FTDI 官方 VCP 驱动页面](https://ftdichip.com/drivers/vcp-drivers/)安装适合该电脑 Windows 版本的驱动。板载 FT4232 的 **Interface 2 / MI_02（UART 通道 C）** 应使用 FTDI VCP 串口驱动并出现在“端口 (COM 和 LPT)”下；可在设备管理器该设备的“属性 → 详细信息 → 硬件 ID”核对 `VID_0403&PID_6011&MI_02`。若此接口仍绑定 libusbK，只为 MI_02 更新驱动到 FTDI VCP，再重新插拔并运行 `--list-ports`。下载器使用的其他接口不要随意改动。
- `Access is denied` / 端口被占用：关闭串口监视器、其他上传进程或占用该 COM 口的程序，再试。
- 一直等待 `ASSET READY` 并在 45 秒后超时：核对实际 COM 号、开发板供电、`first_light.bit` 是否已配置，以及 DDR 初始化。若动画已经在运行，无须再次上传；需要重新上传时先复位或重新配置开发板，让引导程序回到等待状态。
- `ASSET ERR` 或传输中断：保持供电和 USB 连接，等板子再次发出 `ASSET READY`；脚本会重试。多次失败时重新运行命令并检查数据线与端口。

KEY1 每按一次切换去背。`KEY ON` 时精确匹配 RGB565 `0xF81F` 并露出原有背景；`KEY OFF` 时显示品红矩形。CPU/HW 每 4 秒自动交替。屏幕显示当前动作 `FRAME 1`～`FRAME 77`、CPU/HW FPS、绘制耗时、KEY 状态和输出分辨率。人物从左向右移动，到右边后回到左边；动作计时目标为每秒 12 帧，实际帧率以屏幕和 UART 输出为准。

## 文件

- `first_light.bit`：Efinity 配置文件，包含片内 UART 引导程序。
- `first_light_boot.bin`：同一片内引导程序镜像，供检查。
- `software/build/animation.bin`：在 DDR 执行的动画程序。
- `assets/sprite77.raw`：解压后的 77 帧 RGB565，写入 1 MiB 资源区。
- `assets/sprite77.upload`：压缩串口素材。上传脚本会与 `.raw` 交叉校验。
- `assets/sprite77_key_on.png`、`sprite77_key_off.png`：素材预览。
- `reports/`：固件大小、时序、渲染与 Sapphire 联合仿真日志，以及实际仿真扫描输出。
- `reports/board_uart_20260927.log`：本次 COM15 实板 UART 输出。
- `SHA256SUMS.txt`：上述文件的 SHA-256 校验清单。

本包已在开发板上收到 `ASSET OK`，持续运行时 CPU 报告 20 FPS、HW 报告 60 FPS；用户确认 HDMI 动画与 KEY1 两种画面。还需留存视频或截图，并单独读取状态错误位。源码和更完整的构建说明位于工程根目录的 `SPRITE77.md`。
