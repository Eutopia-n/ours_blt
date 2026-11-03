from pathlib import Path
import subprocess,os
ROOT=Path(__file__).resolve().parents[1]
CC=Path('D:/Xilinx/Vivado/2018.3/msys64/mingw64/bin/gcc.exe')
OUT=ROOT/'software/build';OUT.mkdir(exist_ok=True)
env=dict(os.environ);env['PATH']=str(CC.parent)+os.pathsep+env.get('PATH','')
commands=[([CC,'-std=c99','-O2','-Wall','-Wextra','-Werror','-Isoftware','sim/test_altar_pass_policy.c','-o',OUT/'altar_pass_policy.exe'],'build'),([OUT/'altar_pass_policy.exe'],'run')]
for cmd,label in commands:
    r=subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,capture_output=True,text=True)
    text=r.stdout+r.stderr;(ROOT/f'reports/altar_pass_policy_{label}.log').write_text(text)
    print(label,text,flush=True)
    if r.returncode:raise SystemExit(r.returncode)
