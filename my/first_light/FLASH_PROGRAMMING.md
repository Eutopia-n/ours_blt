# SPI Flash 掉电启动

工程将 RISC-V 固件和图片初始化数据嵌入 FPGA bitstream。`compile` 只在电脑生成 bitstream，断电后会消失；要让板卡独立上电启动，需把配置写入 Ti60 板载 SPI Flash 一次。

## 编程步骤

1. 用最新工程编译：

   ```powershell
   python tools/build.py firmware
   python tools/build.py compile
   ```

2. 接好 Ti60 板卡电源与 JTAG 下载器，打开 PowerShell 并切换到 `my/first_light` 工程目录。
3. 执行下面命令写 SPI Flash：

   ```powershell
   python tools/build.py flash
   ```

   此命令使用 Efinity 的 `--flow program --pgm_opts mode=jtag_bridge`，通过 JTAG bridge 将 Active 配置写入 SPI Flash。它会更改板卡的 Flash 内容，运行时保持供电并等待 Programmer 报告成功。日志保存在 `reports/flash_program.log`。

4. Programmer 显示成功后，板卡配置已写入 SPI Flash。以后正常使用时给板卡上电即可，不用每次重新下载；若需要确认启动模式，可另行断电重上电观察首页。

## 使用 Efinity 图形界面

也可以在 Efinity Programmer 中手动编程：先运行 `python tools/build.py compile`，再打开 Efinity Programmer，选择 Ti60 下载器和本工程的 `outflow/first_light.hex`，将配置模式设为 Active/JTAG bridge（SPI Flash），启动 Program 并等待成功提示。不要选仅把 `.bit` 临时装入 FPGA 的 volatile/JTAG 配置模式，那种方式断电会丢失。

## 区分临时下载与掉电配置

- `python tools/build.py compile`：综合并生成 `outflow/first_light.bit`，不连接板卡、不写 Flash。
- Efinity Programmer 的临时 JTAG 配置：当前上电期间可运行，断电后配置丢失。
- `python tools/build.py flash`：连接板卡并写 SPI Flash，成功后才具备掉电保留条件。

若 Programmer 找不到下载器，先检查 USB/JTAG 线、板卡供电和设备管理器里的易灵思下载器驱动，再重试 `python tools/build.py flash`。若只想临时运行，直接在 Efinity Programmer 选 FPGA 的 JTAG 配置方式并载入 `outflow/first_light.bit`；该方式断电后需要重新配置。
