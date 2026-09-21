# Ti60F225 赛题二：连续动画与 CPU/HW 对比

目标：RISC-V 通过 APB 寄存器下发填充/图像拷贝，硬件通过 AXI4 Burst 读写 DDR3，显示模块读取 DDR3 并输出 HDMI。

独立工程位于 [first_light](first_light/README.md)，Efinity 入口为 `first_light/first_light.xml`。

最新说明与验收结果见 [MOTION_DEMO.md](first_light/MOTION_DEMO.md)。双缓冲与 Block Copy 历史记录见 [DOUBLE_BUFFER.md](first_light/DOUBLE_BUFFER.md)、[BLOCK_COPY.md](first_light/BLOCK_COPY.md)，第一阶段历史验收见 [VALIDATION.md](first_light/VALIDATION.md)。原有独立模块保留在仓库根目录 rtl/、sim/ 和 efinity/；本仓库不包含整套随板示例。
