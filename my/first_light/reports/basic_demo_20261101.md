# 基础演示重设计验收（2026-11-01）

下载 `first_light.bit`；操作见同目录 `BASIC_DEMO.md`。当前版本未烧录、未写 Flash、未提交或推送 GitHub。

## 修改范围

本地工程为 `output/upload_270_20261030/my/first_light`。保留任务开始时的 256 怪物、256 子弹、128px 祭坛、W1 围墙、20 宝石显示、透明度方向及五步调节。
新增 `software/basic_demo.h`、`software/basic_demo_data.h`，main.c 仅增加 include 和基础三页分流两行。
新增两个检查工具及基础操作文档，MENU_DEMO.md 顶部链接到新版说明。
生成新的固件与 RAM 初始化文件。

baseline_hashes.json 对比确认：游戏源文件、全部高阶控制、现有测试工具、所有生产 RTL、素材、PLL/DDR/HDMI/约束输入均保持任务起点哈希。
build_hashes.json 与编译后输入再次核对一致。源码与文档改动在 changes.patch 和 source_snapshot；原文件和原 bit/hex 在 baseline，可回退。

## 行为

- 基础填充：8/32/64/128 个 32×24 方块，固定可重复运动序列；CPU/FPGA 自动轮换，30 帧一个窗口，两条路径从相同帧序列开始。
- 基础复制：两张 256×192 独立 DDR 测试图、1/2/4/8 次复制负载；源图预览、清屏、UI 与 COPY_US 分开。CPU 使用对齐 32 位读写。
- 基础总线视图：OP、SRC、DST、尺寸、任务批次突发与等待周期；明确标识 FIFO/最大突发长度为 RTL 配置。
- 双缓冲：FRONT/BACK A/B 页、帧号、交换诊断、实测显示 OUT_HZ、可调速度/参考线/运动暂停；删除该页无关 CPU/FPGA 性能栏。
- 文字与数字按页缓存；没有设置假 FPS、加速比或带宽值。

## 已通过

- 固件 `-Wall -Wextra -Werror` 编译；text 92,536，data 12，BSS 16,968，总计 109,516 字节。128KiB RAM 预留 4KiB 栈后余 17,460 字节。构建器既有 RWX LOAD segment 链接提示保留。
- Basic host：32 组复制＋32 组填充，两页完整字节对照，资源边界和源图不变，真实驱动寄存器提交、计数器/计时回绕、按键、比例边界、13 幅布局与实际主循环 AUTO/手动/配置重置/退出。
- 新独立 RTL 总线检查：两张源地址×两页，256×192、512 字节源步长，每次各 1536 读/写突发，全 DDR 对照；空操作、错误步长、越界拒绝；随机 AXI 反压、稳定信号及 FIFO 越界断言。日志 0 error/0 warning。
- 从上述实际仿真 CSV 导出 `evidence/basic_bus_waveform.png/.svg`，可用于说明 AXI 16 拍突发和 FIFO 入出队。没有修改生产 RTL。
- 既有透明度/压测五步、全部透明度方向检查通过；29 幅旧菜单/游戏/高阶 UI 回归通过。旧工具生成的基础 hud 图是历史函数，本版使用 previews/basic_demo*.png。
- 当前固件真实 Sapphire CPU150/memory100 启动通过，含 UART banner、APB ID、128KiB 程序 RAM 高地址栈。
- Efinity map/interface/pnr/pgm 全部 PASS，pgm 仅生成文件；最终时序 setup +0.076ns、hold +0.024ns。启动器既有 conda 导入提示未影响完成。
- CPU/图形 150MHz、DDR fabric 100MHz、PHY 400MHz、像素约 25.208MHz 配置和所有受约束正 setup/hold 检查通过。
- 资源 XLR 20479/60800（33.68%）、RAM 210/256（82.03%）、DSP 18/160（11.25%），与任务起点相同。

## 证据的边界与上板步骤

previews 中的 13 幅宿主预览采用合成指标，仅证明布局和绘图，不能当作实板性能。RTL 波形来自模型内存，不是 DDR 板上抓取。真实 CPU 启动测试不覆盖完整菜单按键和基础页场景。
尚未实板测量 FPS、COPY_US/FILL_US、最大稳定负载和显示器观感。

建议先临时加载本 bit：

1. 填充页等两路各完成 30 帧，观察 AUTO 轮换与同负载读数；W 切负载、D 切颜色、S 切模式、Enter 切详情，确认变化后旧样本清空。
2. 复制页 D 切两图，确认源/结果一致；W 切负载。FPGA 的 BUS 详情在 LOAD=1 时预期 AR=1536、AW=1536，LOAD=2/4/8 对应倍增；等待周期允许随实板竞争变化。CPU 路径总线统计应为“-”。
3. 双缓冲观察 A/B、竖条和 OUT_HZ；切速度、参考线、暂停运动，确认画面完整。PAUSED 为 YES 时交换仍继续。
4. A 返回，逐一进入高阶三项与游戏，确认既有交互和效果。

FIFO 峰值没有硬件可读寄存器。本版用配置说明＋实际仿真波形展示 FIFO；如果以后需要板上峰值，需另行设计只读监测并重新验证共享 RTL。

## 文件校验

- bit SHA-256：0740bbd2856f77ab2ceddf7c18f1d2ffe9bf0aae89ddc1174226ca19a2639929
- hex SHA-256：e1d0dee697a4f7b8b687dd049b61f553d2f1bc362360847921989ef3c3467cef

完整输入与产物校验见 manifest.json、SHA256SUMS.txt。
