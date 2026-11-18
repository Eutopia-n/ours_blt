"""Check the delivered firmware's static stack frames with the same compiler.

This firmware uses no recursion and starts with interrupts disabled. Summing
every linked C function's frame is deliberately more conservative than any
normal UI/game call chain. The diagnostic build must be byte-identical.
"""
from pathlib import Path
import argparse,json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'software/build/reference_stack'
OUT.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser()
parser.add_argument('--efinity',type=Path,default=Path('C:/Efinity/efinity-riscv-ide-2026.1'))
args=parser.parse_args()
EF = args.efinity/'toolchain/bin'
command = [EF / 'riscv-none-elf-gcc.exe', '-march=rv32im_zicsr_zifencei',
           '-mabi=ilp32', '-Os', '-g', '-flto', '-ffreestanding', '-fno-builtin',
           '-msmall-data-limit=0', '-nostdlib', '-Wall', '-Wextra', '-Werror',
           '-ffunction-sections', '-fdata-sections', '-fstack-usage',
           '-Wl,--gc-sections', '-Tsoftware/link.ld', 'software/start.S',
           'software/main.c', 'software/survivor_game.c', '-o', OUT / 'check.elf']
subprocess.run(list(map(str, command)), cwd=ROOT, check=True)
subprocess.run([str(EF / 'riscv-none-elf-objcopy.exe'), '-O', 'binary',
                str(OUT / 'check.elf'), str(OUT / 'check.bin')], check=True)
assert (OUT / 'check.bin').read_bytes() == (ROOT / 'software/build/first_light.bin').read_bytes()
usage = ''.join(p.read_text() for p in OUT.glob('*.su'))
frames = {}
for line in usage.splitlines():
    location, size, kind = line.split('\t')
    assert kind == 'static', line
    frames[location.rsplit(':', 1)[-1]] = int(size)
bound = sum(frames.values())
assert bound <= 4096, bound
report = {'binary_identical': True, 'stack_reserve': 4096,
          'sum_of_all_C_frames_upper_bound': bound,
          'largest_frame': max(frames.values()), 'frames': frames,
          'assumptions': 'No recursion; interrupts disabled in start.S; fatal traps do not return.'}
(ROOT / 'reports/reference_stack_usage.txt').write_text(usage, encoding='utf-8')
(ROOT / 'reports/reference_stack.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS reference stack: identical firmware; all static C frames sum to {bound} bytes within the 4096-byte reserve.')
