"""Host behavior regression plus actual CPU120 cycle measurements.

Supply --baseline with the saved pre-change survivor_game.c for an apples-to-
apples comparison. Probe init files are private; game firmware is not replaced.
"""
from pathlib import Path
import argparse,subprocess,sys,re,os,json
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--baseline',type=Path)
parser.add_argument('--cc',type=Path,default=Path('D:/Xilinx/Vivado/2018.3/msys64/mingw64/bin/gcc.exe'))
args=parser.parse_args()
OUT=ROOT/'sim/enemy_separation_probe'
OUT.mkdir(exist_ok=True)
SIM=Path('D:/modelsim/win64')
TC=Path('C:/Efinity/efinity-riscv-ide-2026.1/toolchain/bin')
env=dict(os.environ);env['PATH']=str(args.cc.parent)+';'+env.get('PATH','')
def run(cmd,label,timeout=180):
    p=ROOT/f'reports/separation_{label}.log'
    with p.open('w',encoding='utf-8') as log:
        r=subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
    text=p.read_text(encoding='utf-8',errors='replace')
    print(label,text[-1600:],flush=True)
    if r.returncode: raise SystemExit(r.returncode)
    return text
run([sys.executable,'tools/prepare_soc_sim.py'],'prepare')
# Use the same actual wrapper and two-clock wiring as the checked CPU boot TB.
boot=(ROOT/'sim/tb_soc_ram_boot.sv').read_text()
header=boot[:boot.index('    integer upper_writes')].replace('module tb_soc_ram_boot;','module tb_enemy_separation_perf;')
tail=r'''
    reg [7:0] ch;
    string line="";
    integer records=0;
    initial begin repeat(50) @(negedge clk);reset=0;end
    initial forever begin
        @(negedge uart_tx);#13000;
        for(integer n=0;n<8;n++) begin ch[n]=uart_tx;#8666.667;end
        line={line,ch};
        if(ch==10) begin
            $display("%s",line);
            if(line.substr(0,8)=="SEP PERF " && line.len()>20) records++;
            if(line=="SEP PERF FAIL\015\012") $fatal(1,"CPU performance probe failed");
            if(line=="SEP PERF PASS\015\012") begin
                if(records!=3) $fatal(1,"Missing CPU timing cases");
                $display("SEPARATION CPU TIMING PASSED");$finish;
            end
            line="";
        end
    end
    initial begin #120000000;$fatal(1,"CPU separation probe timeout");end
endmodule
'''
# Raw text is emitted as SystemVerilog, without shell interpolation.
(OUT/'tb_perf.sv').write_text(header+tail.replace('\\"','"'))
summary={}
for label,source in ([('baseline',args.baseline.resolve())] if args.baseline else [])+[('current',ROOT/'software/survivor_game.c')]:
    exe=OUT/f'{label}_host.exe'
    run([args.cc,'-std=c99','-O2','-Wall','-Wextra','-Werror','-Isoftware',
         *(['-DSEPARATION_BASELINE'] if label=='baseline' else []),
         'sim/test_enemy_separation.c',source,'-o',exe],label+'_host_build')
    host=run([exe],label+'_host')
    assert 'ENEMY SEPARATION TESTS PASSED' in host
    elf=OUT/f'{label}.elf';binary=OUT/f'{label}.bin'
    run([TC/'riscv-none-elf-gcc.exe','-march=rv32im_zicsr_zifencei','-mabi=ilp32','-Os','-flto',
         '-ffreestanding','-fno-builtin','-msmall-data-limit=0','-nostdlib','-Wall','-Wextra','-Werror',
         '-Isoftware','-Tsoftware/link.ld','software/start.S','sim/enemy_separation_perf.c',source,'-o',elf],label+'_build')
    run([TC/'riscv-none-elf-objcopy.exe','-O','binary',elf,binary],label+'_binary')
    data=binary.read_bytes().ljust(131072,b'\0')
    model=(ROOT/'sim/soc_modelsim.v').read_text(encoding='utf-8')
    for lane in range(4):
        name=f'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol{lane}.bin'
        target=OUT/f'{label}_{lane}.bin'
        target.write_text(''.join(f'{v:08b}\n' for v in data[lane::4]))
        model=model.replace('"'+name+'"','"'+target.as_posix()+'"')
    model_path=OUT/f'{label}_soc.v';model_path.write_text(model,encoding='utf-8')
    lib=f'sim/work_separation_{label}'
    if not (ROOT/lib).exists(): run([SIM/'vlib.exe',lib],label+'_vlib')
    run([SIM/'vlog.exe','-sv','-work',lib,'+incdir+sim',model_path,OUT/'tb_perf.sv'],label+'_vlog')
    output=run([SIM/'vsim.exe','-batch','-t','1ps','-lib',lib,'tb_enemy_separation_perf',
                '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],label+'_cpu')
    assert 'SEPARATION CPU TIMING PASSED' in output
    timings=re.findall(r'SEP PERF (\d) MAX_CYCLES (\d+) AVG_CYCLES (\d+)',output)
    assert len(timings)==3
    summary[label]=[{'case':int(c),'max_cycles':int(m),'avg_cycles':int(a)} for c,m,a in timings]
(ROOT/'reports/separation_cpu_timings.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
