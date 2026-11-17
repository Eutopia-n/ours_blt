"""Exercise the actual SoC CDC and renderer with independent 120/100 MHz clocks.

Simulation-only probe initialization files are substituted into a separate copy
of the actual vendor model. The game firmware / configuration files are untouched.
"""
from pathlib import Path
import argparse,subprocess,sys
parser=argparse.ArgumentParser()
parser.add_argument('--game',action='store_true',help='Run current game firmware menu/start/pause smoke')
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'sim/cpu150_probe'
OUT.mkdir(exist_ok=True)
SIM=Path('D:/modelsim/win64')
TC=Path('C:/Efinity/efinity-riscv-ide-2026.1/toolchain/bin')
def run(cmd,label):
    log=ROOT/f'reports/cpu150_{label}.log'
    with log.open('w',encoding='utf-8') as stream:
        try:
            r=subprocess.run(list(map(str,cmd)),cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=300)
        except subprocess.TimeoutExpired:
            raise SystemExit(f'{label}: 300-second host timeout; no PASS; see {log}')
    output=log.read_text(encoding='utf-8',errors='replace')
    print(label,output[-2200:],flush=True)
    if r.returncode: raise SystemExit(r.returncode)
    return output
run([sys.executable,'tools/prepare_soc_sim.py'],'prepare')
run([TC/'riscv-none-elf-gcc.exe','-march=rv32im_zicsr_zifencei','-mabi=ilp32','-Os',
     '-ffreestanding','-fno-builtin','-msmall-data-limit=0','-nostdlib','-Wall','-Wextra','-Werror',
     '-Isoftware','-Tsoftware/link.ld','software/start.S','sim/cpu150_probe.c','-o',OUT/'probe.elf'],'probe_build')
run([TC/'riscv-none-elf-objcopy.exe','-O','binary',OUT/'probe.elf',OUT/'probe.bin'],'probe_binary')
data=(OUT/'probe.bin').read_bytes().ljust(131072,b'\0')
model=(ROOT/'sim/soc_modelsim.v').read_text(encoding='utf-8')
for lane in range(4):
    name=f'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol{lane}.bin'
    target=OUT/name
    target.write_text(''.join(f'{v:08b}\n' for v in data[lane::4]))
    assert model.count('"'+name+'"')==1
    model=model.replace('"'+name+'"','"'+target.as_posix()+'"')
(OUT/'soc_probe.v').write_text(model,encoding='utf-8')
lib='sim/work_cpu150_game' if args.game else 'sim/work_cpu150'
if not (ROOT/lib).exists(): run([SIM/'vlib.exe',lib],'vlib')
run([SIM/'vlog.exe','-sv','-work',lib,'+incdir+sim',*(['+define+CPU150_GAME'] if args.game else []),
     'rtl/button_input.v','rtl/sync_fifo.v','rtl/fill_engine.v',
     'rtl/render_regs.v','rtl/framebuffer_video.v','rtl/video_mode_measure.v','rtl/render_subsystem.v',
     ROOT/'sim/soc_modelsim.v' if args.game else OUT/'soc_probe.v','sim/tb_cpu150.sv'],
     'game_vlog' if args.game else 'vlog')
out=run([SIM/'vsim.exe','-batch',*(['-voptargs=+acc'] if args.game else []),
         '-t','1ps','-lib',lib,'tb_cpu150',
         '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],
        'game_run' if args.game else 'cdc_run')
if ('CPU150 GAME SMOKE PASSED' if args.game else 'CPU150 CDC TEST PASSED') not in out:
    raise SystemExit('CPU150 test missing success marker')
