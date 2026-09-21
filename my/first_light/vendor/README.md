# 原厂依赖来源

本目录是当前 Ti60F225 集成工程使用的板级依赖，不是全部由团队自研的代码。保留源文件中的版权、许可证与加密保护信息。

- DDR3、common、Sapphire SoC：随板资料 08_ti60f225_soc_demo/09_Ti60F225_co_debug_demo。
- HDMI dvi_encoder.v、encode.v：随板资料 03_hdmi_tx_demo/hdmi_tx_demo_v2/rtl/hdmi_src/dvi_tx。
- soc/EfxSapphireSoc_modelsim.v：SoC IP 的 source/hardware/netlist/source_modelsim/EfxSapphireSoc.v 原样副本，供真实 CPU 联合仿真使用。
- Sapphire 许可文本见 Sapphire_LICENSE.MD；它不能自动代表其他原厂文件的许可。

集成修改由 tools/prepare.py 明确记录，包括 DDR 事务 ID 宽度适配；片内 RAM 四路 .bin 由 tools/build.py firmware 写入团队固件。自身渲染逻辑在 ../rtl/，C 驱动和 Demo 在 ../software/。

正常编译使用已包含的依赖。重新导入时需要完整随板资料，通过 prepare 的 --board-root 参数指定其根目录。
