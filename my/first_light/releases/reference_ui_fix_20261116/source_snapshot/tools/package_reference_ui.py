"""Package the verified local-reference UI build without programming hardware.

Record inputs immediately before compile, then package only if those exact
inputs remain current, timing passes and independent regressions succeeded.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'releases/reference_ui_fix_20261116'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def inputs():
    sources = {ROOT / n for n in ('first_light.xml', 'first_light.peri.xml', 'first_light.sdc')}
    for node in ET.parse(ROOT / 'first_light.xml').getroot().iter():
        if node.tag.endswith('}design_file'):
            sources.add(ROOT / node.attrib['name'])
    for pattern in ('software/*.c', 'software/*.h', 'software/*.S', 'software/*.ld',
                    'rtl/*.vh', 'vendor/**/*.vh', 'EfxSapphireSoc*.bin',
                    'vendor/soc/EfxSapphireSoc*.bin',
                    'assets/ui/magic_book_v5/runtime/reference/rom_*.hex'):
        sources.update(p for p in ROOT.glob(pattern) if p.is_file())
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(sources)}


parser = argparse.ArgumentParser()
parser.add_argument('--record-inputs', action='store_true')
args = parser.parse_args()
record = ROOT / 'reports/reference_build_inputs.json'
if args.record_inputs:
    save(record, inputs())
    print(f'Recorded {len(inputs())} FPGA build inputs.')
    raise SystemExit(0)
assert json.loads(record.read_text(encoding='utf-8')) == inputs(), 'Build inputs changed after recording'
compile_log = (ROOT / 'reports/compile.log').read_text(encoding='utf-8')
for stage in ('map', 'interface', 'pnr', 'pgm'):
    assert re.search(r'\b' + stage + r'\s*:\s*PASS', compile_log), stage
assert (ROOT / 'outflow/first_light.map.rpt').stat().st_mtime > record.stat().st_mtime
timing = (ROOT / 'outflow/first_light.timing.rpt').read_text()
section = timing.split('Setup (Max) Clock Relationship', 1)[1].split('---------- Clock Relationship Summary (end)', 1)[0]
setup, hold = section.split('Hold (Min) Clock Relationship', 1)
minimum = lambda s: min(map(float, re.findall(r'^\S+\s+\S+\s+[\d.]+\s+(-?[\d.]+)\s+\(', s, re.M)))
assert minimum(setup) > 0 and minimum(hold) > 0, 'Timing has not passed'
checks = {'reference_ui_check.log': 'PASS native reference UI',
          'basic_demo_host.log': 'EFFECTS HOST PASSED', 'ui_check.log': 'UI CHECK PASSED',
          'simulation.log': 'ALL TESTS PASSED', 'ui_scanout_run.log': 'UI SCANOUT RTL PASSED',
          'bench_entry_run.log': 'BENCH ENTRY RTL PASSED',
          'cpu150_boot_run.log': 'OCR128 CPU BOOT PASSED'}
cycles = {}
for case in ('bridge', 'curved', 'final', 'chapter_forward', 'chapter_back', 'pause'):
    checks['ui_compositor_' + case + '.log'] = 'PASS UI actual curved book frame'
    log = (ROOT / 'reports' / ('ui_compositor_' + case + '.log')).read_text()
    cycles[case] = int(re.search(r'cycles=\s*(\d+)', log)[1])
for name, marker in checks.items():
    log = (ROOT / 'reports' / name).read_text(encoding='utf-8')
    assert marker in log, name
    if name.endswith('_run.log') or name.startswith('ui_compositor_') or name == 'simulation.log':
        assert 'Errors: 0, Warnings: 0' in log, name
pixel = json.loads((ROOT / 'software/build/reference_ui_check/pixel_comparison.json').read_text())
assert len(pixel) == 11 and all(v == 0 for v in pixel.values())
demo_pixel = json.loads((ROOT / 'reports/demo_reference/comparison.json').read_text())
assert len(demo_pixel) == 16 and all(v['different_pixels'] == 0 for v in demo_pixel.values())
before_log = (ROOT / 'reports/ui_done_before_fix.log').read_text()
assert 'CPU missed UI completion: status=00000008' in before_log
firmware = (ROOT / 'software/build/first_light.bin').read_bytes()
for lane in range(4):
    name = f'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol{lane}.bin'
    for folder in (ROOT, ROOT / 'vendor/soc'):
        assert bytes(int(v, 2) for v in (folder / name).read_text().split()) == firmware.ljust(131072, b'\0')[lane::4]
stack = json.loads((ROOT / 'reports/reference_stack.json').read_text())
assert stack['binary_identical'] and stack['sum_of_all_C_frames_upper_bound'] < 4096
assert (ROOT / 'software/build/reference_stack/check.bin').read_bytes() == firmware
old = ROOT / 'releases/fullscreen_art_20261116'
assert sha(old / 'first_light.bit') == 'afc044871464ad175cfef1be42718150197db491d4f295bdcfae8b8424a3c7d4'
assert sha(old / 'first_light.hex') == 'ed8313efd2428b6c695dd1b61e0be64abde40a9e4d154fb00627854e4c144298'
previous = ROOT / 'releases/reference_ui_20261116'
assert sha(previous / 'first_light.bit') == '750c7e7c314c3c8c4c499cd19df20433a6723f2489705846583787d62809cff5'
assert sha(previous / 'first_light.hex') == 'a5d5b00d1b713766770b0df7aac8c84e6d52a006c7e3b3bc41ac1185da1398e2'
for name, info in json.loads((previous / 'manifest.json').read_text())['files'].items():
    assert sha(previous / name) == info['sha256'], 'Previous release was modified: ' + name
OUT.mkdir(exist_ok=True)
evidence = OUT / 'evidence'
evidence.mkdir(exist_ok=True)
for name in ('first_light.bit', 'first_light.hex'):
    assert sha(ROOT / 'outflow' / name) != sha(old / name)
    shutil.copy2(ROOT / 'outflow' / name, OUT / name)
shutil.copy2(ROOT / 'software/build/first_light.bin', OUT / 'first_light.bin')
for name in (*checks, 'firmware.log', 'firmware_size.log', 'compile.log',
             'reference_stack_usage.txt', 'reference_stack.json', 'book_assets.log', 'ui_done_before_fix.log'):
    shutil.copy2(ROOT / 'reports' / name, evidence / name)
for name in ('first_light.timing.rpt', 'first_light.route.rpt', 'first_light.map.rpt'):
    shutil.copy2(ROOT / 'outflow' / name, evidence / name)
shutil.copy2(ROOT/'reports/reference_demo_gallery.png', evidence/'reference_demo_gallery.png')
shutil.copytree(ROOT/'reports/demo_reference', evidence/'demo_reference', dirs_exist_ok=True,
                ignore=shutil.ignore_patterns('*diagnostic*'))
for image in (ROOT / 'reports').glob('book_reference_*.png'):
    if 'open_' not in image.name:
        shutil.copy2(image, evidence / image.name)
font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 14)
names = [('封面', 'cover'), ('书页目录', 'menu_0_0'), ('游戏准备', 'game_0'),
         ('游戏运行', 'game_play'), ('选择强化', 'game_2'), ('暂停', 'game_paused')]
gallery = Image.new('RGB', (1280, 1512), '#111827')
draw = ImageDraw.Draw(gallery)
for i, (label, name) in enumerate(names):
    x, y = i % 2 * 640, i // 2 * 504
    draw.text((x + 10, y + 2), label, fill='#e5dcaf', font=font)
    gallery.paste(Image.open(ROOT / 'reports' / ('book_reference_' + name + '.png')), (x, y + 24))
gallery.save(evidence / 'reference_ui_gallery.png')
frames = [Image.open(ROOT / 'reports/book_reference_cover.png')]
frames += [Image.open(ROOT / f'reports/book_reference_open_{n:03}.png') for n in range(2, 120, 2)]
frames += [Image.open(ROOT / 'reports/book_reference_menu_0_0.png')]
frames[0].save(evidence / 'reference_opening.gif', save_all=True, append_images=frames[1:],
               duration=[40] * 60 + [800], loop=0, optimize=False)
runtime_dir=ROOT/'assets/ui/magic_book_v5/runtime'
shutil.copy2(evidence/'reference_ui_gallery.png',runtime_dir/'reference_ui_gallery.png')
shutil.copy2(evidence/'reference_opening.gif',runtime_dir/'reference_opening.gif')
shutil.copy2(evidence/'reference_demo_gallery.png',runtime_dir/'fullscreen_demo_gallery.png')
size = re.search(r'\n\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+[a-f\d]+\s',
                 (ROOT / 'reports/firmware_size.log').read_text())
assert size
text, data, bss, total = map(int, size.groups())
runtime = json.loads((ROOT / 'assets/ui/magic_book_v5/runtime/reference/manifest.json').read_text())
assert hashlib.sha256((ROOT/'assets/ui/magic_book_v5/魔法书交互预览.html').read_text(encoding='utf-8').encode()).hexdigest() == runtime['reference_html_sha256'], 'Reference HTML changed'
validation = {'release': OUT.name, 'reference_html_sha256': runtime['reference_html_sha256'],
              'reference_html_raw_sha256': sha(ROOT/'assets/ui/magic_book_v5/魔法书交互预览.html'),
              'static_page_pixel_differences_RGB565': pixel,
              'fullscreen_demo_layout_pixel_comparison_RGB565': demo_pixel,
              'enter_cover_freeze': {'cause': 'UI DONE was one clock pulse; CPU APB polling missed it',
                                    'fix': 'Hold DONE until next accepted UI command',
                                    'before_fix_reproduced': True, 'after_fix_APB_read_delay_cycles': 257},
              'game_UI_states_integrated': ['ready', 'play', 'pause', 'upgrade', 'over', 'won'],
              'game_background': 'solid 0x1085; zero scenery texture bytes',
              'resource_pool_bytes': 1048576, 'UI_ROM_bytes': runtime['rom_bytes'],
              'FPGA_new_UI_scanline_compositor': True, 'CPU_MHz': 150,
              'FPGA_build_stages': ['map PASS', 'interface PASS', 'pnr PASS', 'pgm PASS'],
              'minimum_setup_ns': minimum(setup), 'minimum_hold_ns': minimum(hold),
              'firmware': {'text': text, 'data': data, 'bss': bss, 'static_total': total,
                           'stack_reserve': 4096, 'spare_after_stack': 131072 - total - 4096},
              'stack': stack, 'RTL_cases_cycles_random_stalls': cycles,
              'RTL_scanout': '4 menu + 4 curved UI frames; no mixed pixels/front writes/underflows/read errors',
              'bench_entry_scanout': '3 menu + 3 pressure frames; continuous display',
              'native_game_checks': 'actual game_draw; 48 alternating states/choices; pause/resume restores atlas and hero',
              'animation_target_seconds': {'opening': 2.4, 'chapter': 0.64},
              'animated_geometry': 'reference layered 154-strip projection with fixed-point sampling and compact textures',
              'all_animation_pixels_equal_HTML': False,
              'real_Sapphire_CPU_boot_simulated': True,
              'full_Sapphire_CPU_simulated': False, 'board_tested': False,
              'board_FPS_measured': False, 'preview_note': 'Native C rendering; fixture numbers; GIF timing is illustrative'}
save(OUT / 'validation.json', validation)
save(OUT / 'build_input_hashes.json', inputs())
save(evidence / 'pixel_comparison.json', pixel)
shutil.copy2(ROOT / 'assets/ui/magic_book_v5/runtime/reference/manifest.json', evidence / 'ui_resources.json')
source_files = ['first_light.xml', 'first_light.sdc', 'software/main.c', 'software/game_view.h',
                'software/basic_demo.h', 'software/basic_demo_data.h', 'software/effects_demo.h',
                'software/book_menu.h', 'software/reference_ui_assets.h', 'software/reference_book_animation.h',
                'software/reference_game_ui.h', 'software/demo_skin.h', 'rtl/ui_compositor.v',
                'rtl/ui_asset_rom.v', 'rtl/ui_front_palette.vh', 'rtl/ui_rom_size.vh',
                'rtl/render_regs.v', 'rtl/render_subsystem.v', 'rtl/fill_engine.v', 'sim/tb_ui_compositor.sv', 'sim/tb_render.sv',
                'tools/build.py', 'tools/prepare_reference_ui.py', 'tools/check_reference_ui.py',
                'tools/check_ui_compositor.py', 'tools/check_ui_scanout.py', 'tools/check_reference_stack.py',
                'tools/check_demo_reference.py', 'tools/check_basic_demo.py', 'tools/check_soc_ram_boot.py',
                'tools/check_book_menu.py', 'tools/check_bench_entry.py', 'tools/check_ui.py',
                'tools/package_reference_ui.py']
source_files += [p.relative_to(ROOT).as_posix() for p in (ROOT/'assets/ui/magic_book_v5/runtime/reference').glob('rom_*.hex')]
source_files += ['assets/ui/magic_book_v5/runtime/reference/ui_stream.bin']
for name in source_files:
    target = OUT / 'source_snapshot' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / name, target)
save(ROOT/'assets/ui/magic_book_v5/runtime/validation.json', validation)
for filename in ('assets/game/frost_v1/validation.json','assets/ui/magic_book_v5/source/background_memory.json'):
    path=ROOT/filename
    if path.exists():
        value=json.loads(path.read_text(encoding='utf-8'))
        value.update(current_release=OUT.name,current_firmware=validation['firmware'],fullscreen_game_HUD_skin_integrated=True,book_UI_scope='Reference cover and menus, hardware animation and complete fullscreen game UI integrated')
        save(path,value)
# Documentation is written separately before packaging, so the final manifest
# includes its exact contents and does not overwrite reviewable release notes.
assert (OUT / 'README.md').exists(), 'Write release notes before packaging'
files = {p.relative_to(OUT).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
         for p in sorted(OUT.rglob('*')) if p.is_file() and p != OUT / 'manifest.json'}
save(OUT / 'manifest.json', {'release': OUT.name, 'board_tested': False, 'files': files})
print(json.dumps({'release': str(OUT), 'setup_ns': minimum(setup), 'hold_ns': minimum(hold),
                  'static_firmware_bytes': total, 'files': len(files)}, ensure_ascii=False, indent=2))

# Refresh the optional art archive with the same actual-runtime previews.
with zipfile.ZipFile(ROOT/'assets/ui/magic_book_v5.zip','w',zipfile.ZIP_DEFLATED) as z:
    for path in sorted((ROOT/'assets/ui/magic_book_v5').rglob('*')):
        if path.is_file():z.write(path,path.relative_to(ROOT).as_posix())
    for name in source_files:
        if name.startswith(('tools/','software/','rtl/')):z.write(ROOT/name,name)
