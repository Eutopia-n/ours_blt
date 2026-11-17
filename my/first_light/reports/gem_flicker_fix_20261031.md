# 270工程：经验宝石闪烁修复（2026-10-31）

直接修改现有270分支本地工程my/first_light（工作副本output/upload_270_20261030），没有另建游戏版本工程，也未推送GitHub。原releases/enemy270_20261030产物保留，可回退。此次只改显示与验证，不改变survivor_game.c、270怪物/256子弹、掉落/经验/吸附/合并逻辑、16:9移速补偿和512/448降档。

## 已复现原因

宝石池GAME_MAX_GEMS为96，但旧GAME_MAX_DRAW_GEMS为20。按槽位从低到高绘制时，新增低槽位掉落会将仍存活的高槽位宝石挤出显示，低槽位被拾取后高槽位又出现。测试保持95号宝石value=1，改变低槽位，旧版提交结果为1→0→1，复现“未拾取却消失/再出现”。

另一个问题是暂停/升级状态不记录前景脏区域；半透明宝石反复画在未清理的旧缓冲页上，RGB565颜色逐次累积。像素测试在暂停第197帧发现实际0861、参考0862的差异（编号含前述槽位检查），修复前失败、修复后通过。

## 修改

- software/game_view.h：GAME_MAX_DRAW_GEMS与现有96宝石池一致。新增game_draw_gems独立渲染函数，所有存活且可见掉落均可绘制，不因20个名额变化而隐去。
- 保留原颜色键、裁剪、220透明度和绘制顺序；使用已计算的镜头坐标直接提交精灵，减少重复镜头计算。
- 双缓冲前景脏块在暂停/升级状态也继续记录，绘制前先恢复旧背景，避免半透明颜色累积。每页仍独立恢复，恢复游戏时继续沿用全清边界。
- tools/check_gem_flicker.py对实际C宝石/精灵/背景/双页恢复函数做检查；sim/fixtures/game_view_before_gem_fix.h为复现旧问题的只读测试夹具。
- tools/check_ui.py纳入真实game_draw_gems函数，绘制预算检查随96宝石上限更新。

## 验证

- 旧版同一未拾取95号宝石可见序列1,0,1；本版为1,1,1，经验值始终为1。
- 235帧专项：3帧槽位切换检查＋232次整帧RGB565对照。覆盖96宝石槽位、低槽位反复生成/拾取、双缓冲、原Alpha/Key像素、镜头移动/边缘裁剪、前景覆盖/恢复、暂停/恢复、全部拾取清空、高槽位95及全96治疗掉落。
- 原祭坛/背景缓存321次整帧像素对照PASS；UI21幅预览、270怪物+256子弹及全部96宝石的实际绘制数量检查PASS。
- 当前固件真实Sapphire CPU150/memory100启动仿真PASS，覆盖UART/APB ID/高地址栈；不代表整局游戏或板卡DDR联调。
- Efinity map/interface/pnr/pgm全部PASS；pgm仅生成.bit/hex，未执行program。CPU setup +0.076ns、hold +0.024ns，所有已约束setup/hold为正。
- 所有RTL、PLL、DDR、HDMI、ISF/SDC、游戏逻辑C源码和素材SHA256均与修复前一致。没有新增RTL，未重复未改硬件的全量绘图TB；仅执行本次必要的显示/启动/构建验证。
- text=62420, data=12, bss=16888，合计79320字节；预留4KiB栈后余47656字节。相对修复前text增加4字节、BSS不变、宝石池不增加。

## 性能与上板

原来最多绘制20个，现可绘制96个，极端情况最多增加76条精灵命令；这些是已有掉落，逻辑对象总数没有增加。绘图/DDR开销可能增加，不能据此保证FPS不变。未上板验证本修复；下一步在同样270怪物和大量掉落场景观察消失/闪烁与FPS，再检查暂停/继续。

本地最新配置：releases/enemy270_gemfix_20261031/first_light.bit与.hex。未自动提交/推送本次修复，远端270分支仍为原fb1455f版本。

## 复现命令

python tools/check_gem_flicker.py --baseline-view sim/fixtures/game_view_before_gem_fix.h
python tools/check_gem_flicker.py
python tools/check_scenery.py
python tools/check_ui.py --cc D:/Xilinx/Vivado/2018.3/msys64/mingw64/bin/gcc.exe
python tools/build.py firmware --efinity C:/Efinity/efinity-riscv-ide-2026.1
python tools/check_soc_ram_boot.py
Efinity --flow compile及python tools/check_cpu150_config.py。
