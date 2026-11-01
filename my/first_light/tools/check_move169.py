from pathlib import Path
import os,subprocess
ROOT=Path(__file__).resolve().parents[1]
CC=Path('D:/Xilinx/Vivado/2018.3/msys64/mingw64/bin/gcc.exe')
OUT=ROOT/'software/build';OUT.mkdir(exist_ok=True)
env=dict(os.environ);env['PATH']=str(CC.parent)+os.pathsep+env.get('PATH','')
for cmd,label in [([CC,'-std=c99','-O2','-Wall','-Wextra','-Werror','-Isoftware','sim/test_move169.c','-o',OUT/'move169.exe'],'build'),([OUT/'move169.exe'],'run')]:
    r=subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,capture_output=True,text=True)
    log=r.stdout+r.stderr;(ROOT/f'reports/move169_{label}.log').write_text(log);print(log,flush=True)
    if r.returncode:raise SystemExit(r.returncode)
