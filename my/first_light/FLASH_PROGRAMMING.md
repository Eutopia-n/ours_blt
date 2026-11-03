# 下载与 SPI Flash 启动

当前文件：[first_light.hex](releases/demo_buffer_slow_20261101/first_light.hex)、[first_light.bit](releases/demo_buffer_slow_20261101/first_light.bit)。bitstream 已包含 RISC-V 固件与初始化素材。

## JTAG 连接下写 Flash

在 Efinity Programmer 中：

1. USB Target 选择已连接板卡，Image 选择上面的 HEX。
2. Programming Mode 选 SPI Active using JTAG Bridge（单路 SPI，本工程 width=1）。
3. 勾选 Auto configure JTAG Bridge Image，使用软件为 Ti60 自动匹配的桥接文件。
4. Starting Flash Address 为 0x00000000，Flash Length 保持默认，勾选 Erase Before Programming，校验选 Normal verify，JTAG 时钟先保持默认。
5. 点击 Program Flash / Start Program，完成写入与校验后按配置复位键或重新上电启动。

桥接文件是 Efinity 自带的 Flash loader，使用本机同版本软件自动匹配，不把它替换成项目应用 bit。通过专用 SPI 下载连接时，按板卡连接方式使用 SPI Active 模式。

## 临时运行与重新构建

临时运行选择 JTAG 模式和 BIT，当前上电期间运行；HEX 写入 Flash 后可掉电保留。compile 只在电脑生成文件，不连接或烧写板卡。

```powershell
python tools/build.py firmware --efinity C:/Efinity/efinity-riscv-ide-2026.1
& C:/Efinity/2026.1/bin/efx_run.bat first_light.xml --flow compile
```

路径按本机安装位置调整。需要命令行写 Flash 时可执行 `python tools/build.py flash --efinity C:/Efinity/2026.1`；该步骤会改写板卡 Flash，仅在准备下载且连接、供电正常时运行。

官方设置参考：[Efinity Programmer User Guide](https://www.efinixinc.com/docs/efinity-pgm-v4.3.pdf)。
