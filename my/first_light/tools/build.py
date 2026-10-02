"""Build helpers. Only creates outputs inside my/first_light; never programs hardware."""
from pathlib import Path
import argparse
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('step',choices=['prepare','firmware','sim','sim-fifo','sim-mode','sim-key','sim-menu-keys','sim-alpha','sim-alpha-soc','sim-soc','sim-menu-soc','sim-basic-soc','sim-stress-soc','sim-moving-soc','sim-perf-soc','sim-controls-soc','sim-boot-uart','interface','map','compile','inspect'])
parser.add_argument('--efinity',default='S:/Efinity')
parser.add_argument('--modelsim',default='S:/ModelSim/win64')
parser.add_argument('--demo',choices=['motion','double-buffer'],default='motion')
parser.add_argument('--board-root',type=Path,help='Complete board examples, only needed for prepare')
args=parser.parse_args()
EF=Path(args.efinity)
board_root=args.board_root.resolve() if args.board_root else None
os.chdir(ROOT)
(ROOT/'reports').mkdir(exist_ok=True)
def run(command, name):
    print('Running:', ' '.join(map(str,command)),flush=True)
    with (ROOT/'reports'/name).open('w',encoding='utf-8') as log:
        result=subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT)
    print((ROOT/'reports'/name).read_text(encoding='utf-8',errors='replace')[-7000:],flush=True)
    if result.returncode: raise SystemExit(result.returncode)
if args.step=='prepare':
    extra=['--board-root',board_root] if board_root else []
    run([sys.executable,ROOT/'tools/prepare.py',*extra],'prepare.log')
elif args.step=='firmware':
    out=ROOT/'software/build'; out.mkdir(exist_ok=True)
    gcc=EF/'toolchain/bin/riscv-none-elf-gcc.exe'
    flags=['-march=rv32im_zicsr_zifencei','-mabi=ilp32','-Os','-g','-flto',
           '-ffreestanding','-fno-builtin','-msmall-data-limit=0','-nostdlib',
           '-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections',
           '-Wl,--gc-sections']
    if args.demo=='motion':
        run([gcc,*flags,'-Wl,-Map,software/build/animation.map','-Tsoftware/link_ddr.ld',
             'software/start.S','software/main.c','-lgcc','-o',out/'animation.elf'],'firmware_app.log')
        run([EF/'toolchain/bin/riscv-none-elf-objcopy.exe','-O','binary',
             out/'animation.elf',out/'animation.bin'],'objcopy_app.log')
        run([EF/'toolchain/bin/riscv-none-elf-size.exe',out/'animation.elf'],'firmware_app_size.log')
        if len((out/'animation.bin').read_bytes())>65536:
            raise SystemExit('DDR animation program exceeds its 64 KiB region')
        source='software/boot.c'
    else:
        source='software/double_buffer_demo.c'
    run([gcc,*flags,'-Wl,-Map,software/build/first_light.map','-Tsoftware/link.ld',
         'software/start.S',source,'-o',out/'first_light.elf'],'firmware.log')
    run([EF/'toolchain/bin/riscv-none-elf-objcopy.exe','-O','binary',
         out/'first_light.elf',out/'first_light.bin'],'objcopy.log')
    run([EF/'toolchain/bin/riscv-none-elf-size.exe',out/'first_light.elf'],'firmware_size.log')
    data=(out/'first_light.bin').read_bytes()
    if len(data)>3584: raise SystemExit('Firmware overlaps reserved stack')
    data=data.ljust(4096,b'\0')
    for lane in range(4):
        name=f'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol{lane}.bin'
        content='\n'.join(f'{b:08b}' for b in data[lane::4])+'\n'
        (ROOT/'vendor/soc'/name).write_text(content)
        # Efinity and ModelSim resolve readmemb relative to the build working directory.
        (ROOT/name).write_text(content)
    print('Embedded firmware into 4 KiB on-chip RAM (no SPI flash programming).')
elif args.step=='sim-alpha':
    sim=Path(args.modelsim)
    if not (ROOT/'sim/work').exists(): run([sim/'vlib.exe','sim/work'],'vlib.log')
    run(['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','tools/test_alpha_control.c',
         '-o','reports/test_alpha_control.exe'],'alpha_control_build.log')
    run([ROOT/'reports/test_alpha_control.exe'],'alpha_control.log')
    for name,source,marker in [('alpha_blend','rtl/alpha_blend.v','ALPHA BLEND TEST PASSED'),
                               ('key_down','rtl/key_toggle.v','KEY DOWN TEST PASSED')]:
        run([sim/'vlog.exe','-work','sim/work','-sv',source,f'sim/tb_{name}.sv'],f'vlog_{name}.log')
        run([sim/'vsim.exe','-batch','-t','1ps','-lib','sim/work',f'tb_{name}',
             '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],f'{name}.log')
        if marker not in (ROOT/f'reports/{name}.log').read_text(errors='replace'):
            raise SystemExit(f'{name} simulation did not reach its success marker')
elif args.step=='sim-alpha-soc':
    sim=Path(args.modelsim)
    run([sys.executable,ROOT/'tools/prepare_soc_sim.py','--compact-asset'],'prepare_alpha_soc.log')
    if not (ROOT/'sim/work').exists(): run([sim/'vlib.exe','sim/work'],'vlib.log')
    run([sim/'vlog.exe','-work','sim/work','-sv','rtl/sync_fifo.v','rtl/fill_engine.v',
         'rtl/render_regs.v','rtl/framebuffer_video.v','rtl/video_mode_measure.v',
         'rtl/render_subsystem.v','+incdir+sim','sim/soc_modelsim.v',
         'sim/tb_soc_sprite77.sv'],'vlog_alpha_soc.log')
    run([sim/'vsim.exe','-batch','-t','1ps','-lib','sim/work','tb_soc_sprite77','+ALPHA_TEST',
         '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'simulation_alpha_soc.log')
    if 'ALPHA SOC TEST PASSED' not in (ROOT/'reports/simulation_alpha_soc.log').read_text(errors='replace'):
        raise SystemExit('Alpha SoC simulation did not reach the success marker')
    run([sys.executable,ROOT/'tools/export_preview.py','alpha_4','alpha_6'],'preview_alpha_soc.log')
elif args.step=='sim-fifo':
    sim=Path(args.modelsim)
    if not (ROOT/'sim/work').exists():
        run([sim/'vlib.exe','sim/work'],'vlib.log')
    run([sim/'vlog.exe','-work','sim/work','-sv','rtl/sync_fifo.v',
         'sim/tb_sync_fifo.sv'],'vlog_fifo.log')
    run([sim/'vsim.exe','-batch','-t','1ps','-lib','sim/work','tb_sync_fifo',
         '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'simulation_fifo.log')
    if 'ALL FIFO TESTS PASSED' not in (ROOT/'reports/simulation_fifo.log').read_text(errors='replace'):
        raise SystemExit('FIFO simulation did not reach the success marker')
elif args.step=='sim-key':
    sim=Path(args.modelsim)
    if not (ROOT/'sim/work').exists():
        run([sim/'vlib.exe','sim/work'],'vlib.log')
    run([sim/'vlog.exe','-work','sim/work','-sv','rtl/key_toggle.v',
         'sim/tb_key_toggle.sv'],'vlog_key.log')
    run([sim/'vsim.exe','-batch','-t','1ps','-lib','sim/work','tb_key_toggle',
         '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'simulation_key.log')
    if 'KEY TOGGLE TEST PASSED' not in (ROOT/'reports/simulation_key.log').read_text(errors='replace'):
        raise SystemExit('KEY1 simulation did not reach the success marker')
elif args.step=='sim-menu-keys':
    sim=Path(args.modelsim)
    if not (ROOT/'sim/work').exists():
        run([sim/'vlib.exe','sim/work'],'vlib.log')
    run([sim/'vlog.exe','-work','sim/work','-sv','rtl/key_toggle.v',
         'sim/tb_menu_keys.sv'],'vlog_menu_keys.log')
    run([sim/'vsim.exe','-batch','-t','1ps','-lib','sim/work','tb_menu_keys',
         '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],
        'simulation_menu_keys.log')
    if 'MENU KEY TEST PASSED' not in (ROOT/'reports/simulation_menu_keys.log').read_text(errors='replace'):
        raise SystemExit('Menu key simulation did not reach the success marker')
elif args.step=='sim-boot-uart':
    sim=Path(args.modelsim)
    run([sys.executable,ROOT/'tools/prepare_soc_sim.py'],'prepare_soc_sim.log')
    if not (ROOT/'sim/work').exists():
        run([sim/'vlib.exe','sim/work'],'vlib.log')
    run([sim/'vlog.exe','-work','sim/work','-sv','rtl/sync_fifo.v','rtl/fill_engine.v',
         'rtl/render_regs.v','rtl/framebuffer_video.v','rtl/video_mode_measure.v',
         'rtl/render_subsystem.v','+incdir+sim','sim/soc_modelsim.v',
         'sim/tb_soc_sprite77.sv'],'vlog_boot_uart.log')
    run([sim/'vsim.exe','-batch','-t','1ps','-lib','sim/work','tb_soc_sprite77',
         '+BOOT_UART_ONLY',
         '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],
        'simulation_boot_uart.log')
    if 'BOOT UART TEST PASSED' not in (ROOT/'reports/simulation_boot_uart.log').read_text(errors='replace'):
        raise SystemExit('Boot UART simulation did not reach the success marker')
elif args.step=='sim-mode':
    sim=Path(args.modelsim)
    if not (ROOT/'sim/work').exists():
        run([sim/'vlib.exe','sim/work'],'vlib.log')
    run([sim/'vlog.exe','-work','sim/work','-sv','rtl/video_mode_measure.v',
         'sim/tb_video_mode_measure.sv'],'vlog_mode.log')
    run([sim/'vsim.exe','-batch','-t','1ps','-lib','sim/work','tb_video_mode_measure',
         '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'simulation_mode.log')
    if 'ALL VIDEO MODE TESTS PASSED' not in (ROOT/'reports/simulation_mode.log').read_text(errors='replace'):
        raise SystemExit('Video mode simulation did not reach the success marker')
elif args.step in ['sim','sim-soc','sim-menu-soc','sim-basic-soc','sim-stress-soc','sim-moving-soc','sim-perf-soc','sim-controls-soc']:
    sim=Path(args.modelsim)
    soc_test=args.step!='sim'
    menu_test=args.step=='sim-menu-soc'
    basic_test=args.step=='sim-basic-soc'
    moving_test=args.step=='sim-moving-soc'
    perf_test=args.step=='sim-perf-soc'
    controls_test=args.step=='sim-controls-soc'
    stress_test=args.step=='sim-stress-soc' or moving_test or perf_test or controls_test
    test=('tb_soc_sprite77' if args.demo=='motion' else 'tb_soc') if soc_test else 'tb_render'
    suffix='_controls_soc' if controls_test else ('_perf_soc' if perf_test else ('_moving_soc' if moving_test else ('_stress_soc' if stress_test else ('_basic_soc' if basic_test else ('_menu_soc' if menu_test else ('_soc' if soc_test else ''))))))
    extra=[]
    if soc_test:
        run([sys.executable,ROOT/'tools/prepare_soc_sim.py',*(['--compact-asset'] if stress_test else [])],'prepare_soc_sim.log')
        extra=['+incdir+sim','sim/soc_modelsim.v']
    if not (ROOT/'sim/work').exists():
        run([sim/'vlib.exe','sim/work'],'vlib.log')
    run([sim/'vlog.exe','-work','sim/work','-sv','rtl/sync_fifo.v','rtl/fill_engine.v','rtl/render_regs.v',
         'rtl/framebuffer_video.v','rtl/video_mode_measure.v','rtl/render_subsystem.v',*extra,
         'sim/tb_soc_double_buffer.sv' if soc_test and args.demo=='double-buffer' else f'sim/{test}.sv'],'vlog'+suffix+'.log')
    run([sim/'vsim.exe','-batch','-t','1ps','-lib','sim/work',test,
         *(['+MENU_SMOKE'] if menu_test else []),
         *(['+BASIC_RANDOM'] if basic_test else []),
         *(['+BASIC_CONTROLS' if controls_test else ('+BASIC_PERF' if perf_test else ('+BASIC_MOVING' if moving_test else '+BASIC_STRESS'))] if stress_test else []),
         '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'simulation'+suffix+'.log')
    marker='BASIC CONTROLS SOC TEST PASSED' if controls_test else ('BASIC PERF SOC TEST PASSED' if perf_test else ('BASIC MOVING SOC TEST PASSED' if moving_test else ('BASIC STRESS SOC TEST PASSED' if stress_test else ('BASIC RANDOM SOC TEST PASSED' if basic_test else ('MENU SOC TEST PASSED' if menu_test else ('SOC TEST PASSED' if soc_test else 'ALL TESTS PASSED'))))))
    if marker not in (ROOT/('reports/simulation'+suffix+'.log')).read_text(errors='replace'):
        raise SystemExit('Simulation did not reach the success marker')
    if not soc_test:
        run([sys.executable,ROOT/'tools/export_preview.py'],'preview.log')
    elif controls_test:
        run([sys.executable,ROOT/'tools/export_preview.py','basic_controls_2','basic_controls_4'],'preview_controls_soc.log')
    elif perf_test:
        run([sys.executable,ROOT/'tools/export_preview.py','basic_perf_8','basic_perf_15','basic_perf_23'],'preview_perf_soc.log')
    elif moving_test:
        run([sys.executable,ROOT/'tools/export_preview.py','basic_moving_2','basic_moving_8'],'preview_moving_soc.log')
    elif stress_test:
        run([sys.executable,ROOT/'tools/export_preview.py','basic_stress_2','basic_stress_8'],'preview_stress_soc.log')
    elif basic_test:
        run([sys.executable,ROOT/'tools/export_preview.py',*[f'basic_random_{n}' for n in range(1,5)]],'preview_basic_soc.log')
    elif args.demo=='motion' and not menu_test:
        run([sys.executable,ROOT/'tools/export_preview.py','motion_1','motion_2','motion_5','motion_6','motion_9'],'preview_soc.log')
elif args.step=='inspect':
    for pattern in ['outflow/*.err.log','outflow/*.timing.rpt','outflow/*.map.rpt']:
        for file in ROOT.glob(pattern):
            print(file.name, file.read_text(errors='replace')[:10000])
else:
    run([EF/'bin/efx_run.bat','first_light.xml','--flow',args.step],args.step+'.log')
