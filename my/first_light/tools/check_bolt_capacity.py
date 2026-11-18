"""Verify the 512-slot compact projectile pool with the actual game rules."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--cc',type=Path,default=Path('C:/mingw64/bin/gcc.exe'))
args=parser.parse_args()
sources=('software/survivor_game.h','software/survivor_game.c',
         'software/game_view.h','sim/test_survivor_game.c','tools/check_bolt_capacity.py')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={n:sha(ROOT/n) for n in sources}
binary=ROOT/'software/build/test_survivor_game.exe'
env=dict(os.environ)
env['PATH']=str(args.cc.parent)+os.pathsep+env.get('PATH','')
command=[str(args.cc),'-std=c99','-O2','-Wall','-Wextra','-Werror','-o',str(binary),
         'sim/test_survivor_game.c','software/survivor_game.c']
build=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True)
build.check_returncode()
run=subprocess.run([str(binary)],cwd=ROOT,env=env,capture_output=True,text=True)
log=build.stdout+build.stderr+run.stdout+run.stderr
(ROOT/'reports/bolt_capacity.log').write_text(log,encoding='utf-8')
print(log,end='')
run.check_returncode()
assert 'BOLT CAPACITY PASSED: 256->512, 12-byte storage' in log
assert 'GAME LOGIC TESTS PASSED:' in log and '30000 deterministic ticks' in log
assert 'GAME RELICS PASSED:' in log
assert 'ENEMY SEPARATION PASSED:' in log
assert 'CROWN ATTACKS PASSED:' in log
assert before=={n:sha(ROOT/n) for n in sources}
report={'previous_capacity':256,'capacity':512,'previous_record_bytes':20,'record_bytes':12,
        'previous_pool_bytes':5120,'pool_bytes':6144,'additional_static_bytes':1024,
        'source_sha256':before,'enemy_capacity':384,'crown_attackers':2,
        'checks':['full pool rejects without replacing a live bolt','last slot 511 can be reused',
                  'last-slot collision','unsigned coordinate crosses bit 15',
                  'signed 32-bit edge checks before narrowing','512 independent Q5 trajectories',
                  'diagonal separation, steering decay, coincident pair and full pools at a world corner',
                  '30000 deterministic gameplay ticks'],
        'board_performance_measured':False}
(ROOT/'reports/bolt_capacity.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
