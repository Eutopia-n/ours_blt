"""Compare the real FPGA menu compositor to independent native RGB565 output.

Run check_reference_ui.py first. This test adds random AXI backpressure and
checks every output word, source bounds and writes confined to the back page.
It does not simulate the concurrent HDMI reader or measure board frame rate.
"""
from pathlib import Path
import argparse,subprocess

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--modelsim',type=Path,default=Path('D:/modelsim/win64'))
args=parser.parse_args()
SIM = args.modelsim
LIB = 'sim/work_reference'


def run(command, report):
    result = subprocess.run([str(x) for x in command], cwd=ROOT,
                            capture_output=True, text=True, errors='replace')
    output = result.stdout + result.stderr
    (ROOT / 'reports' / report).write_text(output, encoding='utf-8')
    result.check_returncode()
    return output


if not (ROOT / LIB).exists():
    run([SIM / 'vlib.exe', LIB], 'ui_compositor_vlib.log')
run([SIM / 'vlog.exe', '-work', LIB, '-sv', 'rtl/ui_compositor.v',
     'sim/tb_ui_compositor.sv'], 'ui_compositor_vlog.log')
for case in ('bridge', 'curved', 'eyes', 'final', 'chapter_forward', 'chapter_back', 'pause'):
    output = run([SIM / 'vsim.exe', '-batch', '-t', '1ps', '-lib', LIB,
                  'tb_ui_compositor', '+CASE=' + case,
                  '-do', 'onerror {quit -code 1 -force}; run -all; quit -f'],
                 'ui_compositor_' + case + '.log')
    assert 'PASS UI actual curved book frame' in output, output[-3000:]
    assert '# Errors: 0, Warnings: 0' in output, output[-3000:]
    print(next(line for line in output.splitlines() if 'PASS UI' in line), flush=True)
print('PASS UI compositor: seven real firmware lists including opaque black pupils, exact RGB565 output, randomized AXI stalls.')
