"""Actual CPU150 planning/culling cost only; excludes rendering and DDR."""
from pathlib import Path
import subprocess,sys,re,json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'sim/scenery_probe';OUT.mkdir(exist_ok=True)
SIM=Path('D:/modelsim/win64');TC=Path('C:/Efinity/efinity-riscv-ide-2026.1/toolchain/bin')
def run(command,label,timeout=180):
    path=ROOT/f'reports/scenery_cpu_{label}.log'
    with path.open('w',encoding='utf-8')as log:r=subprocess.run(list(map(str,command)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
    text=path.read_text(encoding='utf-8',errors='replace');print(label,text[-1800:],flush=True)
    if r.returncode:raise SystemExit(r.returncode)
    return text
run([sys.executable,'tools/prepare_soc_sim.py'],'prepare')
boot=(ROOT/'sim/tb_soc_ram_boot.sv').read_text()
header=boot[:boot.index('    integer upper_writes')].replace('module tb_soc_ram_boot;','module tb_scenery_perf;')
tail=r'''
    reg [7:0] ch;
    string line="";
    integer records=0;
    initial begin repeat(50)@(negedge clk);reset=0;end
    initial forever begin
        @(negedge uart_tx);#12960;
        for(integer n=0;n<8;n++)begin ch[n]=uart_tx;#8640;end
        line={line,ch};
        if(ch==10)begin
            $display("%s",line);
            if(line.substr(0,10)=="SCENE PERF " && line.len()>30)records++;
            if(line=="SCENE PERF FAIL\015\012")$fatal(1,"Scenery planning failed");
            if(line=="SCENE PERF PASS\015\012")begin
                if(records!=4)$fatal(1,"Missing cases");
                $display("SCENERY CPU TIMING PASSED");$finish;
            end
            line="";
        end
    end
    initial begin #200000000;$fatal(1,"Scenery probe timeout");end
endmodule
'''
(OUT/'tb.sv').write_text(header+tail)
run([TC/'riscv-none-elf-gcc.exe','-march=rv32im_zicsr_zifencei','-mabi=ilp32','-Os','-flto','-ffreestanding','-fno-builtin',
     '-msmall-data-limit=0','-nostdlib','-Wall','-Wextra','-Werror','-Isoftware','-Tsoftware/link.ld','software/start.S',
     'sim/scenery_plan_perf.c','-o',OUT/'probe.elf'],'build')
run([TC/'riscv-none-elf-objcopy.exe','-O','binary',OUT/'probe.elf',OUT/'probe.bin'],'binary')
data=(OUT/'probe.bin').read_bytes().ljust(131072,b'\0')
model=(ROOT/'sim/soc_modelsim.v').read_text(encoding='utf-8')
for lane in range(4):
    name=f'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol{lane}.bin';target=OUT/f'lane{lane}.bin'
    target.write_text(''.join(f'{v:08b}\n'for v in data[lane::4]));model=model.replace('"'+name+'"','"'+target.as_posix()+'"')
(OUT/'soc.v').write_text(model,encoding='utf-8');lib='sim/work_scenery_cpu'
if not(ROOT/lib).exists():run([SIM/'vlib.exe',lib],'vlib')
run([SIM/'vlog.exe','-sv','-work',lib,'+incdir+sim',OUT/'soc.v',OUT/'tb.sv'],'vlog')
text=run([SIM/'vsim.exe','-batch','-t','1ps','-lib',lib,'tb_scenery_perf','-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'run')
assert 'SCENERY CPU TIMING PASSED'in text
cases=re.findall(r'SCENE PERF (\d) MAX_CYCLES (\d+) AVG_CYCLES (\d+)',text);assert len(cases)==4
summary=[{'case':int(c),'max_cycles':int(m),'avg_cycles':int(a),'max_us':int(m)/150}for c,m,a in cases]
(ROOT/'reports/scenery_cpu_timings.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
