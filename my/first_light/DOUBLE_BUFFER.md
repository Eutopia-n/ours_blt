# 第三阶段：双缓冲最小可运行版本

历史版本记录。当前默认程序已改为连续动画，见 MOTION_DEMO.md。本页所述 bitstream 请从 releases/double_buffer_20260921/ 取用，而非当前 outflow。

日期：2026-09-21。上一阶段的 Block Copy 画面已经由用户确认上板正常。本轮实现和离线验证双 framebuffer；不自动下载 FPGA，也不写 SPI Flash。

## 实现范围

保留 RGB565 Fill、Block Copy、640×480 HDMI 和原 DDR/板级引脚配置，增加后台绘制页、显示页请求和帧边界确认。Demo 在 A 页绘制并校验，开启显示后在后台 B 页绘制并校验，最后切换到 B 页停留。硬件支持重复换页，模块测试覆盖 A→B→A 等多次提交；软件 Demo 本轮只展示一次 A→B。

本轮不包含持续运动、CPU/HW FPS 对比、Alpha、Color Key、独立图片资源区、跨页 Block Copy 或可变行距，尚不能宣布整道赛题或全部基础要求完成。

## 地址与接口

| 项目 | 数值 |
|---|---|
| A 页 | `0x01000000` 到 `0x01095FFF` |
| B 页 | `0x01096000` 到 `0x0112BFFF` |
| 单页大小 | 614400 字节，640×480×2 |
| 行距 | 1280 字节 |
| APB 基址 | `0xF8100000`，沿用官方 SoC 外设窗口 |
| 0x38 DRAW_PAGE | 读写，0=A、1=B，渲染命令的合法地址窗口 |
| 0x3C SWAP_PAGE | 读写，下一次提交的显示页，0=A、1=B |
| 0x40 SWAP | 写 1 提交；读取返回请求翻转位，不是完成标志 |
| STATUS bit6 | 当前生效的显示页，0=A、1=B |
| STATUS bit7 | SWAP_PENDING，1=已提交但尚未确认 |

`DST` 和 `SRC` 仍是绝对 DDR 字节地址，不是页内偏移。两者必须在 DRAW_PAGE 指定的同一页范围内；宽高、2 字节对齐和固定行距检查保留。页范围来自当前 28 位 DDR AXI 地址接口内的空闲区域，不修改 DDR 容量、控制器或引脚。

## 为什么要确认握手

只增加第二块内存不等于完成双缓冲。必须先等硬件写响应结束，再提交显示页，并在旧页不再被显示端读取后才能复用旧页。

1. CPU 在后台页完成 Fill/Copy，等待 DONE 且 BUSY=0。
2. 写 SWAP_PAGE，再写 SWAP=1，bit7 立即表示请求待确认。
3. 像素域在 `v=524, h=0` 的消隐边界处理请求，且要求此前行读取已完成。该位置在下一帧第 0 行预取之前。
4. 页信号先同步，请求额外延迟一级；寄存器在待确认期间保持页和请求不变。行预取请求也额外延迟一级，让页信息先稳定。
5. 视频端更新页并返回确认；核心域先同步显示页，再同步确认。软件看到 bit7=0 且 bit6 为目标页后，才将旧前台页用于下一帧绘制。

同页提交也必须等待确认。等待时重复写 SWAP、修改 SWAP_PAGE 或启动新的渲染命令均被 APB 拒绝，防止请求覆盖或翻转两次抵消。请求错过本次边界时自然等到下一次；关闭显示时光栅计数仍运行，因此也能确认提交。

硬件没有禁止所有人为的前台页写入；避免撕裂仍要求调用者遵守上述页归属顺序。本 Demo 与测试会检查后台绘制不写前台页。

## 改动文件与函数

- `rtl/render_regs.v`：新页寄存器、bit6/bit7、待确认写保护。
- `rtl/framebuffer_video.v`：页请求/确认的跨时钟同步、旧行读取完成检查、帧边界换页和带页地址的预取。
- `rtl/render_subsystem.v`：绘制页地址与跨时钟状态连接。
- `rtl/fill_engine.v`：地址窗口随 DRAW_PAGE 选择，原填充/拷贝状态机保留。
- `software/main.c`、`render.h`：驱动和两页 Demo。`present_frame()` 提交并等待确认，成功后交换软件绘制页；`select_draw_page()` 配置硬件绘制窗口；`verify_page()` 与 `expected_pixel_page()` 校验指定页的像素。
- `sim/tb_render.sv`、`tb_soc.sv`：两页 DDR 模型、完整画面和页面归属检查。

`present_frame()` 返回 0 才允许复用旧页；-2 表示命令/换页忙，-3 表示渲染或视频错误，-4 表示 2 秒超时。超时不撤销总线事务或换页请求，必须停止渲染并排查/复位，不可盲目继续。CPU 若自行写像素，需要保证写入已到达 DDR；当前核实际采用 write-through 缓存，不能套用其他配置的 clean/flush 指令，具体处理见 MOTION_DEMO.md。本静态 Demo 像素全部由硬件写入。

## 离线验证

- C 编译通过：text=3423、data=4、bss=0，总计 3427 字节；保留链接器至少 512 字节栈检查。LOAD 段 RWX 提示与片内 RAM 布局有关，仍保留。
- 模块仿真通过：保留原 33 组非均匀拷贝回归，并检查 10 个完整画面、5 次确认，包含 A/B 后台重绘、重复往返、同页、迟到和关闭显示时提交；随机 AXI 反压下没有混帧或前台页写入。待确认时非法写被拒绝。日志 `reports/simulation.log`，Errors=0、Warnings=0。
- 最终 CPU 联合仿真通过：真实固件发出 14 次填充和 2 次拷贝，CPU 以 19200 个 burst 读回两页共 1228800 字节。逐像素检查 7 个完整 A 页画面、2 个完整 B 页画面，两次提交均得到帧边界确认，未写前台页，串口实际解码得到 PASS 与 `VIDEO status=0x0000004A`。`reports/simulation_soc.log` 最终为 `SOC TEST PASSED`、Errors=0、Warnings=0；模拟时间约 299.942 ms。使用官方 Sapphire CPU/缓存/总线模型，DDR 使用行为模型，不能据此估计实板 FPS 或 DDR 训练成功率。
- 最终 Efinity 编译通过：map/interface/pnr/pgm 均 PASS，`pgm` 仅生成文件。资源为 XLR 18685/60800（30.73%）、Memory Blocks 82/256（32.03%）、DSP 4/160（2.50%）。最小 setup slack +0.315 ns、hold slack +0.026 ns，仅代表现有 SDC 的受约束路径。
- 板级接口仍有 DDR `GPIOR_P_09` 与 HDMI `tmds_clk` 相邻可能噪声耦合的告警，未擅自改引脚。原始 DDR/SoC 网表提示仍保留，不宣称全工程零告警。仿真不包含 DDR PHY 训练、线缆或显示器电气行为。

最终下载文件为 `outflow/first_light.bit`，生成于 2026-09-21 12:50:14，大小 2004867 字节。SHA256：

```text
5574357E0AB37A7905186FE5D5F518461EED4D5AB932B6728369498F20000E03
```

本版归档目录为 `releases/double_buffer_20260921/`。已上板验证的旧单页版 `releases/block_copy_20260921/` 保持不变。

## 上板步骤与预期

1. 用 Efinity Programmer 的 JTAG 临时配置加载 `outflow/first_light.bit`，无需另外下载 C 程序，固件已嵌入 bitstream。
2. HDMI 接原 TX，串口使用原 COM 口，115200、8N1。观察启动日志，没有 FAIL/TRAP。
3. 最终显示三个红/绿/蓝矩形与两块青/品红/黄彩条；背景由 A 页 `0x1082` 变为 B 页 `0x18C3`，之后保持静态。显示器锁定 HDMI 较慢时，可能看不到短暂 A 页，因此串口是重要检查项。

```text
Ti60: RISC-V -> AXI FILL/COPY -> DDR -> HDMI
PASS DOUBLE BUFFER: page A -> page B at frame boundary
VIDEO status=0x0000004A
```

| 异常 | 下一步具体检查 |
|---|---|
| 背景变化不明显或只看到最终图 | 先核对新 bitstream 时间/hash，再看串口 PASS 与状态 0x4A；不要仅凭背景亮度判断 |
| FAIL page A/B DDR pixels | DRAW_PAGE 是否匹配 SRC/DST 页基址；检查 WSTRB、1280 stride、DDR 校准 |
| FAIL page A/B present | STATUS bit7 是否一直为 1、bit6 是否不变；检查 v=524/h=0、未完成行读、swap_toggle/seen_swap/确认同步 |
| 黑线或 FAIL video | STATUS bit4/bit5，读仲裁是否完整结束 burst、行预取是否按时完成 |
| 仅出现旧 PASS FILL/COPY | 下载了旧单页 bitstream；不要覆盖旧归档，重新选当前 outflow 文件 |

## 复现

在仓库根目录逐步执行，前一步失败时停止并检查 reports 对应日志：

```powershell
python my\first_light\tools\build.py firmware --demo double-buffer
python my\first_light\tools\build.py sim
python my\first_light\tools\build.py sim-soc --demo double-buffer
python my\first_light\tools\build.py compile
```

不需要重新运行 `prepare`；若运行过，必须紧接 `firmware` 恢复自己的片内固件初始化文件。本轮未更改引脚、PLL、DDR 参数或官方 Demo 目录。
