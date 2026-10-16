# Ti60F225 DemoBoard V4 团队项目

本仓库用于汇总易灵思 Ti60F225 开发板示例工程和团队开发代码。保留原目录结构，不修改已有 HDL、引脚配置和时序约束。

## 目录说明

- `01_*` 至 `17_*`：现有开发板示例，编号并不连续。
- `my/first_light/`：当前自建 Ti60F225 RISC-V + FPGA 渲染与游戏工程。
- `子卡原理图/`、根目录 PDF：硬件参考资料。
- `驱动安装及说明/`：随开发板提供的驱动和说明。
- `docs/GIT_TEAM_GUIDE.md`：首次提交、远程连接和团队协作步骤。

当前游戏 Demo 的入口、功能和验证边界见 [`my/first_light/README.md`](my/first_light/README.md)；写入 SPI Flash 的步骤见 [`my/first_light/FLASH_PROGRAMMING.md`](my/first_light/FLASH_PROGRAMMING.md)。

## 版本管理范围

纳入源码、工程 XML、接口配置 `*.peri.xml`、时序约束 `*.sdc`、IP 文件、嵌入式软件、仿真脚本和硬件参考资料。保留 `.hex`、`.mem`、`.mif` 及源码目录内的 `.bin`，因为它们可能是 ROM/RAM 初始化或固件输入。

忽略 Efinity 的 `outflow/`、`work_syn/`、`work_pnr/`、`work_pt/`、`work_dbg/`，ModelSim 的 `work/` 和波形输出，以及 Eclipse `.metadata/`、日志、备份、根目录 `tmp/` 和 `软件安装包/`。忽略规则只影响 Git，不会删除本地文件。

以下独立资料未纳入 Git，克隆仓库时不会得到它们：

- `软件安装包/jre-8u381-windows-x64.exe`：本地安装包。
- `10_Ti60f225_sc431hai2hdmi_demo/Ti60f225_sc431hai2hdmi_v3.zip`：约 241 MB 的独立工程压缩包。它与已展开的 `Ti60f225_sc431hai2hdmi_v1/` 名称不同，不能假定内容相同；需要 V3 的成员应向资料持有人获取原包。后续可以单独解压审查后纳入源码管理。

## 工程使用

在 Efinity 中打开所需示例对应的工程 XML，按工程要求准备 IP 和开发环境后重新编译。不同示例可能使用不同工具版本，请查看相应工程 XML 中的 `sw_version` 和随板说明。

Git 初始化仅建立版本管理基线，不代表所有示例已经通过编译或上板验证。提交功能修改时，请记录 Efinity 版本、工程路径、仿真/编译结果和上板现象。

初始版本保持原文件编码和换行符；不要直接对整库执行编码转换或格式化，以免中文注释损坏或产生大量无关差异。
