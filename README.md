# Ti60 冰霜幸存者（270 分支）

当前工程：[my/first_light](my/first_light)。Efinity工程入口：[first_light.xml](my/first_light/first_light.xml)。

- 怪物逻辑/绘制上限270，我方子弹256；150MHz CPU与绘图，128KiB程序RAM。
- 针对640×480铺满16:9屏幕，玩家与怪物纵向移动补偿4/3；改回4:3保比例显示前请将GAME_MOTION_Y_NUM/DEN改为1/1并重新编译。
- 史莱姆同类、蝙蝠同类相互避让，跨组穿行；B/D/E保持相互避让。仅保留中心祭坛，视频演示页已删除。
- 存活怪物与子弹合计达到512时出怪间隔×2，回落到448及以下恢复。

## 直接下载

[first_light.bit](my/first_light/releases/enemy270_20261030/first_light.bit) · [first_light.hex](my/first_light/releases/enemy270_20261030/first_light.hex) · [验证与校验](my/first_light/releases/enemy270_20261030)

当前版本通过软件回归、CPU启动仿真和Efinity编译/时序检查，尚未上板确认本版FPS。没有自动烧录板卡。

## 构建

依赖Efinity 2026.1、Efinity RISC-V IDE 2026.1、Python与Pillow。先切换到my/first_light：

```powershell
cd my/first_light
python tools/build.py firmware --efinity C:/Efinity/efinity-riscv-ide-2026.1
& C:/Efinity/2026.1/bin/efx_run.bat first_light.xml --flow compile
```

根据本机安装位置调整路径。生成配置在outflow/；上述命令只生成文件，不烧录。JTAG/SPI Flash操作另见[FLASH_PROGRAMMING.md](my/first_light/FLASH_PROGRAMMING.md)。已内置vendor/和ROM初始化文件，正常构建不依赖被清理的官方例程，也不需要运行tools/prepare.py。

## 验证

```powershell
python tools/check_bullet_grid.py
python tools/check_altar_pass_policy.py
python tools/check_move169.py
python tools/check_ui.py --cc D:/Xilinx/Vivado/2018.3/msys64/mingw64/bin/gcc.exe
python tools/check_soc_ram_boot.py --modelsim D:/modelsim/win64
```

宿主C编译器/ModelSim路径按本机调整；前三个脚本默认沿用工程内已记录的本机工具链位置。本版依据与限制见[验证记录](my/first_light/reports/enemy270_validation.md)。旧sim/tb_soc.sv是较早菜单/按键测试，不作为当前版验收依据。

## 目录与清理

- my/first_light/：当前源码、素材、vendor依赖、验证脚本及单一最新release。
- docs/board/：保留的三份板卡手册/装配图/原理图。
- docs/GIT_TEAM_GUIDE.md：原团队协作指南。
- [docs/UPLOAD_270.md](docs/UPLOAD_270.md)：本次导入与清理范围。

官方编号例程、安装包/旧子卡资料、my/fpga旧工程、旧release和构建缓存已从本分支当前文件树清理。其他分支与历史提交未改写；因此这次清理不会自动压缩既有Git历史。

素材及第三方许可见[THIRD_PARTY.md](my/first_light/THIRD_PARTY.md)和vendor/、third_party/内原始许可证。未将整个工程统一改成MIT或CC0许可。
