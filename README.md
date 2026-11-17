# Ti60 RISC-V + FPGA 2D 图形加速引擎

当前构建：**reference_ui_fix_20261116**（Enter 封面卡死修复、六项全屏演示按本地预设排版、魔法书动画及完整全屏游戏界面；已编译，尚未上板）。工程入口：[my/first_light/first_light.xml](my/first_light/first_light.xml)。

## 下载与演示

- [下载 HEX（写入 SPI Flash）](my/first_light/releases/reference_ui_fix_20261116/first_light.hex)
- [下载 BIT（JTAG 临时配置）](my/first_light/releases/reference_ui_fix_20261116/first_light.bit)
- [本版变化、验证和上板说明](my/first_light/releases/reference_ui_fix_20261116/README.md)
- [旧版下载与录制资料](my/first_light/releases/demo_buffer_slow_20261101/README.md)

基础演示有矩形填充、图像复制、双缓冲三项：

- 填充/复制默认 CPU，S 手动切换 FPGA，显示两路最近采样的 FPS、任务耗时及耗时比。复制使用两张独立 DDR 测试图；Enter 进入总线详情。详情隐藏 DST，驱动仍完整提交目的地址。
- 双缓冲页默认单缓冲撕裂，S 手动切换双缓冲防撕裂；每次进入默认低速 STEP=8。W 按 8→16→32→8 切换速度，D 参考线，Enter 暂停，A 返回。已移除 A/B 页状态块。
- 高阶颜色键/Alpha 页固定 FPGA，提供开关、透明色或透明度调节和左右参考。透明度初始 255/255，W 加 5、D 减 5，Enter 切预设。
- 压力测试初始 32×32、1 个 Sprite，W/S 加减 5，D 按 32→24→16→4→32 降档；按完整 30 帧窗口判定 PASS/MAX60。
- 冰霜幸存者保留 256 敌人池、256 我方子弹池、20 宝石显示。当前工作区已取消祭坛、围墙和背景纹理，改用纯色填充，少加载 472 KiB DDR 数据。池上限不代表实拍同屏数量。

详细按键与指标：[基础演示](my/first_light/BASIC_DEMO.md)、[高阶效果](my/first_light/EFFECTS_DEMO.md)、[菜单说明](my/first_light/MENU_DEMO.md)。

## 工程与验证状态

平台 Ti60F225 I3，CPU/BitBlt 150MHz，DDR fabric 100MHz，DDR PHY 400MHz，640×480 HDMI，程序 RAM 128KiB。RISC-V 通过 APB 配置图形寄存器，加速器通过 AXI 直接访问 DDR，支持 16 拍突发和内部写 FIFO。

Enter 停在封面的问题已通过保持 FPGA 绘制完成状态修复；旧逻辑已复现漏读，修复后真实 APB 延迟读取通过。六项演示的 16 种布局状态按本地预设核对，实际画面见 [演示总览](my/first_light/reports/reference_demo_gallery.png)。

菜单按照本地 `魔法书交互预览.html` 还原：封面、九个选择状态和游戏准备页已在 RGB565 下逐像素一致。游戏运行 HUD、暂停、强化和结算均接入正式 C 绘制。所有演示和游戏继续全屏，场景使用纯色背景。

新增菜单专用 FPGA 扫描线合成模块，支持纹理缩放、明暗与透明混合；CPU 只提交书页姿态，原图形引擎及压力负载口径保留。开书按预设 2.4 秒、章节按 0.64 秒推进，过期姿态会跳过。无整屏动画帧序列，原 1 MiB DDR 素材池和 128 KiB CPU RAM 保留。

已验证实际 C 页面、六组真实动画/暂停指令的 FPGA 像素结果、连续 HDMI 扫描和压力页切换。最终编译、时序、资源用量及校验文件见[本版说明](my/first_light/releases/reference_ui_fix_20261116/README.md)。本轮未运行完整 Sapphire CPU 长仿真，尚未上实体板卡。预览数值为排版填充值，不能作为板卡帧率；实际动画耗时可从串口 `BOOK FRAMES ... MS ...` 读取。

## 构建

需要 Efinity 2026.1、Efinity RISC-V IDE 2026.1、Python 3 与 Pillow。以下安装路径按本机调整：

```powershell
cd my/first_light
python tools/build.py firmware --efinity C:/Efinity/efinity-riscv-ide-2026.1
& C:/Efinity/2026.1/bin/efx_run.bat first_light.xml --flow compile
```

生成文件位于 `outflow/`。已保留 `vendor/`、IP 参数、ROM 初始化文件和素材，正常构建不依赖官方例程目录，也不需要执行重新导入底层工程的 `tools/prepare.py`。

常用回归：

```powershell
python tools/check_basic_demo.py --cc C:/mingw64/bin/gcc.exe
python tools/check_tearing_demo.py --modelsim D:/modelsim/win64
python tools/check_demo_controls.py
python tools/check_ui.py --cc C:/mingw64/bin/gcc.exe
python tools/check_soc_ram_boot.py --modelsim D:/modelsim/win64
```

AXI/FIFO 独立检查为 `tools/check_basic_bus.py`，生成波形需额外安装 matplotlib。其他测试工具中的宿主编译器路径可按本机环境调整。完整编译不烧写板卡，下载设置见 [FLASH_PROGRAMMING.md](my/first_light/FLASH_PROGRAMMING.md)。

## 仓库内容

- `my/first_light/`：当前源码、素材、底层依赖、测试和最新发布包。
- `docs/board/`：三份板卡说明/装配图/原理图。
- [docs/UPLOAD_NEW_20261101.md](docs/UPLOAD_NEW_20261101.md)：本次导入、清理和验证范围。

本分支当前文件树已移除 13 个独立编号官方例程、旧 `my/fpga`、旧发布包、安装包和构建缓存。板卡原始资料的本地副本继续保留；Git 历史及其他分支保持原样。

素材和依赖的原始许可证见 [THIRD_PARTY.md](my/first_light/THIRD_PARTY.md)、`vendor/` 和 `third_party/`。历史功能文档用于追溯，当前行为以本页、BASIC_DEMO.md、EFFECTS_DEMO.md 和最新 release 为准。
