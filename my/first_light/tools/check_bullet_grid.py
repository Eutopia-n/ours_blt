"""Compare complete game state against the linear collision oracle with the same current body/spawn policy."""
from pathlib import Path
import subprocess,os,re,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
CC=Path('D:/Xilinx/Vivado/2018.3/msys64/mingw64/bin/gcc.exe')
OUT=ROOT/'software/build';OUT.mkdir(exist_ok=True)
env=dict(os.environ);env['PATH']=str(CC.parent)+os.pathsep+env.get('PATH','')
header=(ROOT/'software/survivor_game.h').read_text()
names=re.findall(r'\b(game_\w+)\s*\(',header)
defines=['-D'+name+'=baseline_'+name for name in names]
commands=[([CC,'-std=c99','-O2','-Wall','-Wextra','-Werror','-Isoftware',*defines,'-c','sim/bullet_grid_policy_reference.c','-o',OUT/'bullet_grid_baseline.o'],'baseline_build'),
          ([CC,'-std=c99','-O2','-Wall','-Wextra','-Werror','-Isoftware','sim/test_bullet_grid.c','software/survivor_game.c',OUT/'bullet_grid_baseline.o','-o',OUT/'bullet_grid_test.exe'],'test_build'),
          ([OUT/'bullet_grid_test.exe'],'differential'),
          ([CC,'-std=c99','-O2','-Wall','-Wextra','-Werror','-Isoftware','sim/test_entity256.c','software/survivor_game.c','-o',OUT/'bullet_grid_pool.exe'],'pool_build'),
          ([OUT/'bullet_grid_pool.exe'],'pool'),
          ([CC,'-std=c99','-O2','-Wall','-Wextra','-Werror','-Isoftware','sim/test_enemy_separation.c','software/survivor_game.c','-o',OUT/'bullet_grid_separation.exe'],'separation_build'),
          ([OUT/'bullet_grid_separation.exe'],'separation')]
for command,label in commands:
    result=subprocess.run(list(map(str,command)),cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
    output=result.stdout+result.stderr
    (ROOT/f'reports/bullet_grid_{label}.log').write_text(output,encoding='utf-8')
    print(label,output[-2000:],flush=True)
    if result.returncode:raise SystemExit(result.returncode)
print('BULLET GRID HOST CHECKS PASSED')
