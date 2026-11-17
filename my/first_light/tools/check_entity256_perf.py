"""Measure game_tick on the actual CPU150 model; excludes render/DDR costs."""
from pathlib import Path
import subprocess, sys, re, json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'sim/entity256_probe'; OUT.mkdir(exist_ok=True)
(ROOT/'reports').mkdir(exist_ok=True)
SIM=Path('D:/modelsim/win64')
TC=Path('C:/Efinity/efinity-riscv-ide-2026.1/toolchain/bin')
def run(cmd,label,timeout=300):
    path=ROOT/f'reports/entity256_perf_{label}.log'
    with path.open('w',encoding='utf-8') as log:
        result=subprocess.run(list(map(str,cmd)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
    text=path.read_text(encoding='utf-8',errors='replace')
    print(label,text[-2000:],flush=True)
    if result.returncode: raise SystemExit(result.returncode)
    return text
run([sys.executable,'tools/prepare_soc_sim.py'],'prepare')
boot=(ROOT/'sim/tb_soc_ram_boot.sv').read_text()
header=boot[:boot.index('    integer upper_writes')].replace('module tb_soc_ram_boot;','module tb_entity256_perf;')
tail=r'''
    reg [7:0] ch;
    string line="";
    integer records=0;
    initial begin repeat(50) @(negedge clk); reset=0; end
    initial forever begin
        @(negedge uart_tx); #12960;
        for(integer n=0;n<8;n++) begin ch[n]=uart_tx; #8640; end
        line={line,ch};
        if(ch==10) begin
            $display("%s",line);
            if(line.substr(0,8)=="SEP PERF " && line.len()>20) records++;
            if(line=="SEP PERF FAIL\015\012") $fatal(1,"CPU performance probe failed");
            if(line=="SEP PERF PASS\015\012") begin
                if(records!=4) $fatal(1,"Missing timing cases");
                $display("ENTITY256 CPU TIMING PASSED"); $finish;
            end
            line="";
        end
    end
    initial begin #400000000; $fatal(1,"CPU performance timeout"); end
endmodule
'''
(OUT/'tb_perf.sv').write_text(header+tail)
source=(ROOT/'sim/enemy_separation_perf.c').read_text()
source=source.replace('maximum[3],total[3]','maximum[4],total[4]').replace('kind<3','kind<4')
source=source.replace('if(kind==2) for(uint32_t i=0;i<GAME_MAX_BOLTS;i++)',
                      'if(kind>=2) for(uint32_t i=0;i<(kind==2 ? 48u : GAME_MAX_BOLTS);i++)')
(OUT/'perf.c').write_text(source)
elf=OUT/'perf.elf'; binary=OUT/'perf.bin'
run([TC/'riscv-none-elf-gcc.exe','-march=rv32im_zicsr_zifencei','-mabi=ilp32','-Os','-flto',
     '-ffreestanding','-fno-builtin','-msmall-data-limit=0','-nostdlib','-Wall','-Wextra','-Werror',
     '-Isoftware','-Tsoftware/link.ld','software/start.S',OUT/'perf.c','software/survivor_game.c','-o',elf],'build')
run([TC/'riscv-none-elf-objcopy.exe','-O','binary',elf,binary],'binary')
data=binary.read_bytes(); assert len(data)<=131072-4096
data=data.ljust(131072,b'\0')
model=(ROOT/'sim/soc_modelsim.v').read_text(encoding='utf-8')
for lane in range(4):
    name=f'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol{lane}.bin'
    target=OUT/f'lane{lane}.bin'
    target.write_text(''.join(f'{v:08b}\n' for v in data[lane::4]))
    model=model.replace('"'+name+'"','"'+target.as_posix()+'"')
(OUT/'soc.v').write_text(model,encoding='utf-8')
lib='sim/work_entity256_perf'
if not (ROOT/lib).exists(): run([SIM/'vlib.exe',lib],'vlib')
run([SIM/'vlog.exe','-sv','-work',lib,'+incdir+sim',OUT/'soc.v',OUT/'tb_perf.sv'],'vlog')
output=run([SIM/'vsim.exe','-batch','-t','1ps','-lib',lib,'tb_entity256_perf',
            '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'cpu')
assert 'ENTITY256 CPU TIMING PASSED' in output
cases=re.findall(r'SEP PERF (\d) MAX_CYCLES (\d+) AVG_CYCLES (\d+)',output)
assert len(cases)==4
summary=[{'case':int(c),'max_cycles':int(m),'avg_cycles':int(a),'max_us':int(m)/150}
         for c,m,a in cases]
(ROOT/'reports/entity256_cpu_timings.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
