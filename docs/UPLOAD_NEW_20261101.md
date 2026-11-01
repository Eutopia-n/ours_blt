# new 分支导入与清理（2026-11-01）

起点为 new 分支 c25588424720c708897b9b0eaffc77103bdcc176，导入本地最新、已验证的 demo_buffer_slow_20261101。
在独立克隆中整理提交，保留该分支历史；原开发工程、本地完整官方包及其他远程分支保持。

## 当前文件树移除范围

- `01_Ti60F225_Key_led_osc_demo/`
- `02_Ti60F225_hdmi_demo/`
- `03_hdmi_tx_demo/`
- `04_Ti60f225_GE_demo/`
- `05_Ti60F225_lvds_loop_demo/`
- `07_Ti60F225_MIPI_C2D_Demo/`
- `08_ti60f225_soc_demo/`
- `09_Ti60F225_hdmi2dsi_Demo/`
- `10_Ti60f225_sc431hai2hdmi_demo/`
- `11_TI60F225_MIPI_CSI_loop_demo/`
- `12_mipi_dsi_loop_demo/`
- `13_carrychain_prj_demo/`
- `17_Ti60F225_uart_demo/`

- `子卡原理图/`、`驱动安装及说明/`：独立子卡资料和安装包。
- `my/fpga/` 旧工程、旧 `my/first_light/releases/` 发布包与 `outflow/`、仿真/综合/布局缓存。只发布当前 release。
- 三份根目录板卡 PDF 以原字节内容放入 `docs/board/`，保留团队协作文档。

## 保留范围

`my/first_light/` 的全部当前生产 RTL、C 软件、素材、测试与构建脚本，Efinity XML/引脚/时序约束，vendor 中的 DDR、Sapphire、HDMI 和 FIFO 源码、参数与 ROM 初始化文件，third_party 和素材许可证。

vendor 目录是构建依赖，未视作无关例程删除。当前工程顶层为 competition_top，CPU/图形 150MHz，DDR fabric 100MHz，像素约 25.208MHz，既有时钟/复位和接口连接保持。

## 交付及检查

- 最新 BIT/HEX：[当前发布目录](../my/first_light/releases/demo_buffer_slow_20261101/)，二进制保持本地交付版本，哈希见 manifest.json。
- 整理后从源重新构建固件，与交付程序二进制完全一致；工程 XML 引用的 27 个文件全部位于当前目录。
- 源文件与 release manifest 完整 SHA-256 对照通过，未改动功能代码；修改仅涉及文档、发布布局与清理。
- 当前基础/高阶 C 主机回归、五步控制、29 个 UI 预览检查通过。
- 在本整理目录重新执行 RTL 扫描/撕裂回归、真实 CPU150/memory100 启动，以及 Efinity map/interface/pnr/pgm 全流程，均通过；150MHz 配置与最终时序检查通过。证据见当前 release 的 evidence/upload_new/。
- 同目录固件重建后源码、8 份 ROM lane 和交付 BIT/HEX 的原哈希再次核对一致；发布文件保持原已验证版本。

发布包与源码均含每次进入低速 8 的双缓冲演示，W 为 8/16/32，S 手动切换撕裂/防撕裂；填充/复制默认 CPU，Alpha 初始透明度 255/255，压力初始 32×32、数量五步和降档保持。

本次上传不表示已经上板验收性能；预览与仿真画面分别标注，不作为实板 FPS 或最大负载读数。
