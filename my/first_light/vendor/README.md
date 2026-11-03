# 原厂依赖来源

本目录是当前 Ti60F225 集成工程使用的板级依赖，不是全部由团队自研的代码。保留源文件中的版权、许可证与加密保护信息。

- DDR3、common、Sapphire SoC：随板资料 08_ti60f225_soc_demo/09_Ti60F225_co_debug_demo。
- HDMI dvi_encoder.v、encode.v：随板资料 03_hdmi_tx_demo/hdmi_tx_demo_v2/rtl/hdmi_src/dvi_tx。
- soc/EfxSapphireSoc_modelsim.v：来自 SoC IP 的 source/hardware/netlist/source_modelsim/EfxSapphireSoc.v，供真实 CPU 联合仿真使用。当前与综合版一起应用了下述片内 RAM 扩容补丁。
- Sapphire 许可文本见 Sapphire_LICENSE.MD；它不能自动代表其他原厂文件的许可。

集成修改由 tools/prepare.py 明确记录，包括 DDR 事务 ID 宽度适配；片内 RAM 四路 .bin 由 tools/build.py firmware 写入团队固件。自身渲染逻辑在 ../rtl/，C 驱动和 Demo 在 ../software/。

2026-10-06：`tools/expand_soc_ram.py` 将公开的片内 RAM 字节地址线从 12 位扩到 14 位、每条 8 位存储 lane 从 1024 扩到 4096 项，并将 0xF9000000 的地址译码窗口从 4 KiB 扩到 16 KiB。综合版与 ModelSim 版使用相同变换，不修改受保护的 CPU 实现。`settings.json` 仍保留原厂导入配置；重新导入由 `prepare.py` 自动应用该补丁，之后必须重新编译固件。

正常编译使用已包含的依赖。重新导入时需要完整随板资料，通过 prepare 的 --board-root 参数指定其根目录。

2026-10-08 游戏版进一步扩为 64 KiB：公开 RAM 字节地址线 16 位、四路 8 位 lane 各 16384 项、OCR 解码掩码 `0x0000FFFF`。综合与 ModelSim 版同步更新，CPU 受保护实现未修改。链接脚本预留至少 4096 字节栈，初始化 lane 由当前固件构建生成。
