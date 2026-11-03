"""Boot current firmware at CPU150 / memory100 and check the expanded OCR stack."""
import argparse
from pathlib import Path
import subprocess
import sys
from expand_soc_ram import ROOT, verify_project

parser=argparse.ArgumentParser()
parser.add_argument('--modelsim',default='D:/modelsim/win64',type=Path)
args=parser.parse_args()
verify_project()
library='sim/work_ocr_boot'
commands=[([sys.executable,ROOT/'tools/prepare_soc_sim.py'],'prepare'),
          *([] if (ROOT/library).exists() else [([args.modelsim/'vlib.exe',library],'vlib')]),
          ([args.modelsim/'vlog.exe','-sv','-work',library,'+incdir+sim',
            'sim/soc_modelsim.v','sim/tb_soc_ram_boot.sv'],'vlog'),
          ([args.modelsim/'vsim.exe','-batch','-t','1ps','-lib',library,'tb_soc_ram_boot',
            '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'run')]
for command,label in commands:
    print('OCR boot:',label,flush=True)
    run=subprocess.run(list(map(str,command)),cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    text=run.stdout+run.stderr
    (ROOT/f'reports/cpu150_boot_{label}.log').write_text(text,encoding='utf-8')
    print(text[-3000:],flush=True)
    if run.returncode: raise SystemExit(run.returncode)
    if label=='run' and 'OCR128 CPU BOOT PASSED' not in text:
        raise SystemExit('CPU boot success marker missing')
