# BASIC 切换停机处理 R1

2026-10-05。保持 800×600、40 MHz 像素时钟和约 60.317 Hz 刷新率。
应用仍内置在 bit 中，素材继续从已有 Flash 读取。

## 已确认与尚未确认

旧应用的 `wait_display_page()` 将粘滞的 `GFX_UNDERFLOW` 标志视为致命错误，
随后 `fail("FAIL present")` 永久循环。扫描器对迟到行输出黑色，后续行仍会继续取数，
因此一次显示欠载不应永久终止演示。

未改动应用时，真实 RISC-V SoC 的针对性仿真完成了菜单、BASIC CPU 帧、KEY0 切换，
以及两帧硬件绘制/换页，零错误。没有开发板串口记录，尚不能证明用户实板卡死由欠载触发。
本修订消除上述明确的永久停机路径，并保留后续定位信息。

## 修改

- `software/main.c`：显示欠载改为一次 UART 警告，继续等待有效换页。
- 命令错误、AXI 读错误、换页超时仍保留原处理，避免把损坏或未完成页面当作成功。
- 致命错误打印 STATUS、OP、DST、SIZE；启动标识增加 R1。
- `sim/tb_resolution_soc.sv`、`tools/build.py`：加入 BASIC 切换与欠载标志注入专项测试。
- 未修改 RTL、PLL、DDR IP、视频时序或 Flash 素材。

## 构建和验证

```powershell
python tools/build.py firmware
python tools/build.py sim-basic-hw-recovery --modelsim D:/modelsim/win64
python tools/build.py compile
```

专项测试使用真实 CPU 和应用，在第一条硬件全屏填充开始后强制置位显示欠载标志，
要求继续完成两次换页并输出欠载警告，且没有硬件命令或 AXI 错误。
此注入验证软件不会因为欠载标志停机，不模拟实板 DDR 的具体欠载原因。

实际结果：固件编译通过；专项仿真输出欠载警告后继续完成 PRESENT 3、PRESENT 4，
最终 `BASIC HW SWITCH TEST PASSED`，0 errors / 0 warnings。
Efinity map/interface/pnr/pgm 全部 PASS，最终时序 core setup/hold 为 1.917/0.026 ns，
像素时钟 setup/hold 为 20.192/0.045 ns。Efinity 启动脚本有既存的 conda 环境提示，
未影响上述 FPGA 编译阶段完成。未执行实板下载。

## 上板

下载 `releases/fixed800_hw_recovery_20261005/fixed800_hw_recovery.bit`，进入 BASIC 后按 KEY0。
不需要重刷素材。此工程构建工具不执行下载，实板结果需用户确认。

若仍卡住，使用 115200、8N1 读取串口报错行。启动应出现
`Ti60 FIXED 800X600 20261005 R1`；欠载警告为 `WARN video underflow; rendering continues`。
若出现 FAIL 行，STATUS 中 bit2 为命令错误、bit4 为显示欠载、bit5 为 AXI 读错误，
bit0 为渲染忙、bit7 为换页待完成。保留完整行用于定位，不能只凭 bit4 判定根因。

修改前应用源码保存在 `releases/pre_basic_hw_recovery_20261005/main.c`。
