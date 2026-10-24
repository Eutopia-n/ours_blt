"""Build helpers. The explicit flash step writes the connected board's SPI Flash."""
from pathlib import Path
import argparse
import os
import subprocess
import sys

# Efinity logs may contain UTF-8 replacement characters; keep the wrapper
# usable on Windows consoles whose default code page is GBK.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('step',choices=['prepare','firmware','sim','sim-buttons','sim-fifo','sim-mode','sim-soc','sim-game','interface','map','compile','flash','inspect'])
parser.add_argument('--efinity',default='S:/Efinity')
parser.add_argument('--modelsim',default='S:/ModelSim/win64')
parser.add_argument('--demo',choices=['motion','double-buffer'],default='motion')
parser.add_argument('--ui-smoke',action='store_true',help='Focused real-CPU menu/player regression (sim-soc motion only)')
parser.add_argument('--board-root',type=Path,help='Complete board examples, only needed for prepare')
args=parser.parse_args()
if args.ui_smoke and (args.step!='sim-soc' or args.demo!='motion'):
    parser.error('--ui-smoke requires sim-soc --demo motion')
if args.step=='sim-game' and args.demo!='motion':
    parser.error('sim-game requires the motion firmware containing the survivor game')
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
    run([sys.executable,ROOT/'tools/prepare_game_assets.py'],'game_assets.log')
    out=ROOT/'software/build'; out.mkdir(exist_ok=True)
    gcc=EF/'toolchain/bin/riscv-none-elf-gcc.exe'
    run([gcc,'-march=rv32im_zicsr_zifencei','-mabi=ilp32','-Os','-g','-flto',
         '-ffreestanding','-fno-builtin','-msmall-data-limit=0','-nostdlib',
         '-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections',
         '-Wl,--gc-sections','-Wl,-Map,software/build/first_light.map',
         '-Tsoftware/link.ld','software/start.S',
         'software/main.c' if args.demo=='motion' else 'software/double_buffer_demo.c',
         *(['software/survivor_game.c'] if args.demo=='motion' else []),
         '-o',out/'first_light.elf'],'firmware.log')
    run([EF/'toolchain/bin/riscv-none-elf-objcopy.exe','-O','binary',
         out/'first_light.elf',out/'first_light.bin'],'objcopy.log')
    run([EF/'toolchain/bin/riscv-none-elf-size.exe',out/'first_light.elf'],'firmware_size.log')
    data=(out/'first_light.bin').read_bytes()
    if len(data)>61440: raise SystemExit('Firmware overlaps reserved stack')
    data=data.ljust(65536,b'\0')
    for lane in range(4):
        name=f'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol{lane}.bin'
        content='\n'.join(f'{b:08b}' for b in data[lane::4])+'\n'
        (ROOT/'vendor/soc'/name).write_text(content)
        # Efinity and ModelSim resolve readmemb relative to the build working directory.
        (ROOT/name).write_text(content)
    print('Embedded firmware into 64 KiB on-chip RAM (no SPI flash programming).')
elif args.step=='sim-buttons':
    sim=Path(args.modelsim)
    if not (ROOT/'sim/work').exists():
        run([sim/'vlib.exe','sim/work'],'vlib.log')
    run([sim/'vlog.exe','-work','sim/work','-sv','rtl/button_input.v',
         'sim/tb_button_input.sv'],'vlog_buttons.log')
    run([sim/'vsim.exe','-batch','-t','1ps','-lib','sim/work','tb_button_input',
         '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'simulation_buttons.log')
    if 'ALL BUTTON TESTS PASSED' not in (ROOT/'reports/simulation_buttons.log').read_text(errors='replace'):
        raise SystemExit('Button simulation did not reach the success marker')
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
elif args.step in ['sim','sim-soc','sim-game']:
    sim=Path(args.modelsim)
    soc_test=args.step in ['sim-soc','sim-game']
    test='tb_soc' if soc_test else 'tb_render'
    suffix='_soc_game' if args.step=='sim-game' else '_soc_ui' if args.ui_smoke else '_soc' if soc_test else ''
    extra=[]
    if soc_test:
        run([sys.executable,ROOT/'tools/export_font.py'],'font_export.log')
        run([sys.executable,ROOT/'tools/prepare_soc_sim.py'],'prepare_soc_sim.log')
        extra=['+incdir+sim','sim/soc_modelsim.v']
    library='sim/work_game' if args.step=='sim-game' else 'sim/work_ui' if args.ui_smoke else 'sim/work'
    if not (ROOT/library).exists():
        run([sim/'vlib.exe',library],'vlib'+suffix+'.log')
    run([sim/'vlog.exe','-work',library,'-sv','rtl/sync_fifo.v','rtl/fill_engine.v','rtl/render_regs.v',
         'rtl/framebuffer_video.v','rtl/video_mode_measure.v','rtl/render_subsystem.v','rtl/button_input.v',*extra,
         'sim/tb_soc_game.sv' if args.step=='sim-game' else 'sim/tb_soc_double_buffer.sv' if soc_test and args.demo=='double-buffer' else f'sim/{test}.sv'],'vlog'+suffix+'.log')
    run([sim/'vsim.exe','-batch','-t','1ps','-lib',library,test,*(['+UI_SMOKE'] if args.ui_smoke else []),
         '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'simulation'+suffix+'.log')
    marker='SOC GAME TEST PASSED' if args.step=='sim-game' else 'SOC UI TEST PASSED' if args.ui_smoke else 'SOC TEST PASSED' if soc_test else 'ALL TESTS PASSED'
    if marker not in (ROOT/('reports/simulation'+suffix+'.log')).read_text(errors='replace'):
        raise SystemExit('Simulation did not reach the success marker')
    if not soc_test:
        run([sys.executable,ROOT/'tools/export_preview.py'],'preview.log')
    elif args.demo=='motion' and args.step!='sim-game':
        # The button debounce delay can change the first frame of a new load.
        log=(ROOT/('reports/soc_game_progress.log' if args.step=='sim-game' else 'reports/soc_ui_progress.log' if args.ui_smoke else 'reports/soc_progress.log')).read_text()
        import re
        frames=re.findall(r'PREVIEW ((?:motion|menu_player|game)_\d+)',log)
        if len(frames)<6: raise SystemExit('Missing complete scene previews')
        run([sys.executable,ROOT/'tools/export_preview.py',*frames],'preview_soc_game.log' if args.step=='sim-game' else 'preview_soc_ui.log' if args.ui_smoke else 'preview_soc.log')
elif args.step=='inspect':
    for pattern in ['outflow/*.err.log','outflow/*.timing.rpt','outflow/*.map.rpt']:
        for file in ROOT.glob(pattern):
            print(file.name, file.read_text(errors='replace')[:10000])
elif args.step=='flash':
    # Efinity's active JTAG-bridge mode writes SPI Flash for power-on boot.
    # Unlike --flow pgm, this requires a connected Ti60 and changes its Flash.
    try:
        run([EF/'bin/efx_run.bat','first_light.xml','--flow','program',
             '--pgm_opts','mode=jtag_bridge'],'flash_program.log')
    except SystemExit:
        log=(ROOT/'reports/flash_program.log').read_text(encoding='utf-8',errors='replace')
        if 'list index out of range' in log:
            raise SystemExit('Efinity 没有枚举到 JTAG-bridge USB 编程目标；请连接并上电 Ti60 板卡、确认下载器驱动后重试。未能确认 SPI Flash 写入。')
        raise
else:
    run([EF/'bin/efx_run.bat','first_light.xml','--flow',args.step],args.step+'.log')
