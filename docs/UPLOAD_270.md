# 270分支导入与清理（2026-10-30）

基于分支原提交`c25588424720c708897b9b0eaffc77103bdcc176`，导入本地已验证enemy270_20261030版本至my/first_light。
仅270分支提交新文件树，不force push、不改写历史，不修改其他分支；本地已验证版本和各回退文件保留。

## 清理范围

- 01_Ti60F225_Key_led_osc_demo/
- 02_Ti60F225_hdmi_demo/
- 03_hdmi_tx_demo/
- 04_Ti60f225_GE_demo/
- 05_Ti60F225_lvds_loop_demo/
- 07_Ti60F225_MIPI_C2D_Demo/
- 08_ti60f225_soc_demo/
- 09_Ti60F225_hdmi2dsi_Demo/
- 10_Ti60f225_sc431hai2hdmi_demo/
- 11_TI60F225_MIPI_CSI_loop_demo/
- 12_mipi_dsi_loop_demo/
- 13_carrychain_prj_demo/
- 17_Ti60F225_uart_demo/
- 子卡原理图/
- 驱动安装及说明/

- my/fpga/旧new_project。
- 原my/first_light中的旧releases、outflow、ModelSim工作库、编译缓存/中间产物及旧验证输出。

三份根目录板卡PDF移入docs/board，保留原内容。docs/GIT_TEAM_GUIDE.md保留。
当前vendor/与ROM .bin不是冗余例程，作为独立构建依赖保留。旧官方完整包未从用户本地删除。

发布配置为my/first_light/releases/enemy270_20261030/first_light.bit与.hex，来自同名本地已验证产物，字节校验一致。
源码未改游戏功能或RTL；只调整仓库文档、忽略规则与产物布局。导入后验证结果见该release的evidence/及manifest.json。

导入my/first_light后的固件重建与原first_light.bin逐字节一致；在不包含官方例程目录的新工作树中重新执行网格/270池/避让/移速/UI/CPU启动检查，全部通过。RTL、约束、素材和vendor哈希均与已编译270版一致，预编译.bit/hex保持原已验证文件。
