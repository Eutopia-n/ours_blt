"""Freeze the tested Alpha bitstream, matching DDR application and uploader."""
from pathlib import Path
import hashlib
import json
import shutil

root=Path(__file__).resolve().parents[1]
release=root/'releases/alpha_key2_20261002'
markers={
    'reports/alpha_control.log':'ALPHA CONTROL TEST PASSED',
    'reports/alpha_blend.log':'ALPHA BLEND TEST PASSED',
    'reports/key_down.log':'KEY DOWN TEST PASSED',
    'reports/simulation.log':'ALPHA RENDER TEST PASSED',
    'reports/simulation_alpha_soc.log':'ALPHA SOC TEST PASSED',
}
for name,marker in markers.items():
    if marker not in (root/name).read_text(errors='replace'):
        raise SystemExit(f'Missing successful validation: {name}')
compile_log=(root/'reports/compile.log').read_text(errors='replace')
for step in ['map','interface','pnr','pgm']:
    if not any(step in line and 'PASS' in line for line in compile_log.splitlines()):
        raise SystemExit(f'Missing compile phase: {step}')
tested_app=bytes.fromhex((root/'sim/app_image_compact.memh').read_text())
if tested_app[16:]!=(root/'software/build/animation.bin').read_bytes():
    raise SystemExit('Application changed after SoC simulation preparation')
for name,digest in json.loads((root/'reports/alpha_build_manifest.json').read_text()).items():
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
        raise SystemExit(f'Build snapshot changed before packaging: {name}')
files=[
    'ALPHA_KEY2.md','software/build/animation.bin','software/build/animation.elf',
    'assets/sprite77.raw','assets/sprite77.upload','tools/upload_sprite77.py',
    'reports/compile.log','reports/firmware_app_size.log','reports/simulation.log',
    'reports/alpha_build_manifest.json',
    'reports/alpha_control.log','reports/alpha_blend.log','reports/key_down.log',
    'reports/simulation_alpha_soc.log','reports/soc_progress.log',
    'outflow/first_light.map.rpt','outflow/first_light.timing.rpt',
    'reports/alpha_4.png','reports/alpha_6.png',
]
mapping={name:name for name in files}
mapping['outflow/first_light.bit']='first_light.bit'
sources=['rtl/alpha_blend.v','rtl/fill_engine.v','rtl/render_regs.v',
         'rtl/render_subsystem.v','rtl/key_toggle.v','rtl/competition_top.v',
         'software/main.c','software/render.h','software/alpha_control.h',
         'sim/tb_alpha_blend.sv','sim/tb_key_down.sv','sim/tb_render.sv',
         'sim/tb_soc_sprite77.sv','tools/test_alpha_control.c','tools/build.py',
         'tools/prepare.py','tools/package_alpha.py']
mapping.update({name:'source_snapshot/'+name for name in sources})
for src,dst in mapping.items():
    p=release/dst;p.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/src,p)
guide=release/'ALPHA_KEY2.md'
guide.write_text(guide.read_text(encoding='utf-8').replace(
    'releases/alpha_key2_20261002/README.md','README.md'),encoding='utf-8')
readme='''# KEY2 透明度循环上板包

在 ADVANCED 中短按 KEY2：0 → 2 → 4 → … → 100 → 0。
按住 0.5 秒后，每 0.1 秒增加 2；松开停止。数值越大越透明。
菜单中 KEY2 仍是确认，进入高级展示时不会把确认长按当作透明度调节；松开再按生效。
每次重新进入高级展示从 0 开始。KEY1 去背开关、KEY3 返回菜单。
基础展示仍为 KEY0 CPU/FPGA 切换，KEY1 循环 32/128/256 个方块。

## 使用

1. Type-C 和 HDMI 连接开发板，冷启动。
2. Efinity Programmer 通过 JTAG 下载本目录的 first_light.bit。
3. 在本目录运行以下命令，COMx 使用查询得到的实际串口号：

```powershell
python tools/upload_sprite77.py --list-ports
python tools/upload_sprite77.py --port COMx
```

上传需要 pyserial。正常提示 ASSET READY → ASSET OK；应用启动标识
为 Ti60 ALPHA KEY2 20261002。JTAG 下载后不要按配置复位或断电，否则需重新下载。
新功能同时依赖本包的新 bitstream 和 animation.bin，请配套使用。

## 验证范围

控制逻辑、混合模块、完整渲染回归、真实 Sapphire 固件联合仿真和 Efinity 全流程编译通过。
长按计时和完整 51 档循环由实际软件控制函数的主机测试覆盖；联合仿真覆盖菜单确认
隔离、KEY2 0/2/4、CPU/HW、键控开关、返回重入、逐像素与实际扫描输出。
混合运算在综合报告中映射到 12 个 DSP48。时序、寄存器和复现方法见 ALPHA_KEY2.md。

reports/alpha_4.png 和 alpha_6.png 是仿真扫描画面，分别对应 2% CPU 与 4% FPGA。
这些不是实板照片；本版还需上板确认手感、长按回绕和持续运行。
source_snapshot 为本轮相关源文件快照；完整可编译工程仍在上级 my/first_light。
SHA256SUMS.txt 可核验包内文件。
'''
(release/'README.md').write_text(readme,encoding='utf-8')
names=['README.md',*mapping.values()]
(release/'SHA256SUMS.txt').write_text(''.join(
    f'{hashlib.sha256((release/name).read_bytes()).hexdigest()}  {name}\n'
    for name in sorted(names)),encoding='ascii')
print(f'Packaged {len(names)} files: {release}')
