# SPI Flash Auto Boot

本地工程的启动程序现在支持从 Ti60F225 板上的 GD25LQ64 SPI Flash 自动加载动画程序和素材。

## Flash 布局

| Flash 地址 | 内容 |
|---|---|
| `0x000000` | FPGA bitstream，由 Efinity Programmer 的正常 Active SPI 配置流程写入 |
| `0x380000` | 本工程生成的 `software/build/flash_user.bin` 或 `flash_user.hex` |

用户镜像内部包含固定 40 字节的头、`animation.bin` 和完整的 `assets/sprite77.raw`。启动时片内 bootloader 会校验头、CRC 和素材头，校验通过后把动画写到 DDR `0x01400000`，把素材写到 DDR `0x01200000`，然后跳转动画程序并输出 `FLASH BOOT`。校验失败时会退回原来的 UART 上传流程，因此不会阻断旧的调试方式。

## 生成用户镜像

在本目录执行：

```powershell
python .\tools\build.py firmware
```

`firmware` 会同时生成：

- `software/build/flash_user.bin`：从 Flash `0x380000` 开始写入的二进制用户镜像；
- `software/build/flash_user.hex`：每行一个字节的 Efinity Programmer 用户数据文件；
- `software/build/flash_user.txt`：长度和 CRC 清单。

也可以只重新打包：

```powershell
python .\tools\build.py flash-bundle
```

硬件工程的 Efinity 流程使用 `C:\Efinity\2026.1`；例如生成新的 bitstream：

```powershell
python .\tools\build.py compile --efinity C:\Efinity\2026.1
```

## 烧录顺序

1. 用 Efinity Programmer 的 **Active SPI** 模式把 `outflow\first_light.hex` 写到 `0x000000`。这一步负责 FPGA 上电配置；只用 JTAG 临时下载 `.bit` 不会保存上电启动内容。
2. 在同一个 SPI Flash 器件中，把 `software/build/flash_user.hex` 写到起始地址 `0x380000`。不要擦除 `0x000000` 的 bitstream 区域。
3. 断电再上电，FPGA 配置完成后 bootloader 会自动搬运用户镜像；不再需要运行 `upload_sprite77.py`。

如果当前只想调试 bitstream，仍可使用 JTAG `.bit` 和原 UART 上传脚本。Flash 用户镜像默认保存在本地工程的 `software/build` 中，不必提交到源代码仓库。
