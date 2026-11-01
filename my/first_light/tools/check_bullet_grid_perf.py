"""Compare saved full-scan and grid game_tick on real CPU150 (OCR only)."""
from pathlib import Path
import subprocess,sys,re,json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'sim/bullet_grid_probe';OUT.mkdir(exist_ok=True)
SIM=Path('D:/modelsim/win64');TC=Path('C:/Efinity/efinity-riscv-ide-2026.1/toolchain/bin')
def run(command,label,timeout=600):
    path=ROOT/f'reports/bullet_grid_perf_{label}.log'
    with path.open('w',encoding='utf-8') as log:
        result=subprocess.run(list(map(str,command)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
    text=path.read_text(encoding='utf-8',errors='replace');print(label,text[-2200:],flush=True)
    if result.returncode:raise SystemExit(result.returncode)
    return text
run([sys.executable,'tools/prepare_soc_sim.py'],'prepare')
boot=(ROOT/'sim/tb_soc_ram_boot.sv').read_text()
header=boot[:boot.index('    integer upper_writes')].replace('module tb_soc_ram_boot;','module tb_bullet_grid_perf;')
tail=r'''
    reg [7:0] ch;
    string line="";
    integer records=0;
    initial begin repeat(50) @(negedge clk);reset=0;end
    initial forever begin
        @(negedge uart_tx);#12960;
        for(integer n=0;n<8;n++)begin ch[n]=uart_tx;#8640;end
        line={line,ch};
        if(ch==10)begin
            $display("%s",line);
            if(line.substr(0,9)=="GRID PERF " && line.len()>30)records++;
            if(line=="GRID PERF FAIL\015\012")$fatal(1,"Timing probe failed");
            if(line=="GRID PERF PASS\015\012")begin
                if(records!=5)$fatal(1,"Missing timing cases");
                $display("BULLET GRID CPU TIMING PASSED");$finish;
            end
            line="";
        end
    end
    initial begin #1000000000;$fatal(1,"Timing probe timeout");end
endmodule
'''
(OUT/'tb_perf.sv').write_text(header+tail)
summary={}
for label,source in [('baseline',ROOT/'sim/bullet_grid_baseline.c'),('current',ROOT/'software/survivor_game.c')]:
    elf=OUT/f'{label}.elf';binary=OUT/f'{label}.bin'
    run([TC/'riscv-none-elf-gcc.exe','-march=rv32im_zicsr_zifencei','-mabi=ilp32','-Os','-flto',
         '-ffreestanding','-fno-builtin','-msmall-data-limit=0','-nostdlib','-Wall','-Wextra','-Werror',
         '-Isoftware','-Tsoftware/link.ld','software/start.S','sim/bullet_grid_perf.c',source,'-o',elf],label+'_build')
    run([TC/'riscv-none-elf-objcopy.exe','-O','binary',elf,binary],label+'_binary')
    data=binary.read_bytes();assert len(data)<=131072-4096;data=data.ljust(131072,b'\0')
    model=(ROOT/'sim/soc_modelsim.v').read_text(encoding='utf-8')
    for lane in range(4):
        name=f'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol{lane}.bin'
        target=OUT/f'{label}_{lane}.bin';target.write_text(''.join(f'{v:08b}\n' for v in data[lane::4]))
        model=model.replace('"'+name+'"','"'+target.as_posix()+'"')
    (OUT/f'{label}_soc.v').write_text(model,encoding='utf-8')
    lib='sim/work_bullet_grid_'+label
    if not (ROOT/lib).exists():run([SIM/'vlib.exe',lib],label+'_vlib')
    run([SIM/'vlog.exe','-sv','-work',lib,'+incdir+sim',OUT/f'{label}_soc.v',OUT/'tb_perf.sv'],label+'_vlog')
    output=run([SIM/'vsim.exe','-batch','-t','1ps','-lib',lib,'tb_bullet_grid_perf',
                '-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],label+'_cpu')
    assert 'BULLET GRID CPU TIMING PASSED' in output
    cases=re.findall(r'GRID PERF (\d) MAX_CYCLES (\d+) AVG_CYCLES (\d+) STATE_HASH (\d+)',output)
    assert len(cases)==5
    summary[label]=[{'case':int(c),'max_cycles':int(m),'avg_cycles':int(a),'max_ms':int(m)/150000,'state_hash':int(h)}for c,m,a,h in cases]
    (ROOT/'reports/bullet_grid_cpu_timings.json').write_text(json.dumps(summary,indent=2))
assert [x['state_hash']for x in summary['baseline']]==[x['state_hash']for x in summary['current']],'Real CPU state mismatch'
print(json.dumps(summary,indent=2));print('BULLET GRID CPU BASELINE/CURRENT COMPARISON PASSED')
