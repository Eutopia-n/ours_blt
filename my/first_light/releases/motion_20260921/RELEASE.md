# 连续动画与 CPU/HW 对比：归档版本

下载文件：本目录 first_light.bit。Ti60F225I3，640×480 RGB565，32 个运动彩条块，默认每 4 秒切换 CPU/HW，屏幕显示真实计时 FPS 和 US。C 固件已嵌入 bitstream。

固件、模块仿真、真实 RISC-V 联合仿真和完整 FPGA 编译均通过；尚未下载本版本或测量实板性能。联合仿真覆盖 CPU→HW→CPU、9 次换页和 16 个完整扫描帧。详见 MOTION_DEMO.md 和 reports/。

此目录是交付文件与对应源码快照，不含大型 vendor IP，因此不是独立可编译工程。复现请使用仓库 my/first_light 工程与原厂依赖；software/、rtl/、sim/、tools/ 用于保存本轮源文件。原 double_buffer_20260921 归档未覆盖。

SHA256：

| 文件 | SHA256 |
|---|---|
| first_light.bit | 2720C8BF140B795FD6AE7EE38947468FBC1488214422F5A8A110DBFE17E466CA |
| first_light.elf | C8643D83BECA46E560EEDC79F457E5C18FDF3FC4E0E506429BCD440FBD87FCA1 |
| first_light.bin | D39C7D5EFDE65A9DF0174A1BCD483D56EC573E09C4060E57FD3DC5DAF680CB8E |
| software/main.c | 7C2EDC780251DCDCB70D6E898895706FF2B8EAA099BCD53F5879D80D14A8C475 |
