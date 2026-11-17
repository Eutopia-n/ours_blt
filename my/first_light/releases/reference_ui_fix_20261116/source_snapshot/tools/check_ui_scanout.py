"""Run the actual UI engine through APB while HDMI scans the other page.

Uses real firmware frame-60 descriptors and compares every displayed pixel.
The two complete painted pages are swapped only at vertical blanking.
"""
from pathlib import Path
import ast,struct,subprocess
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'software/build/ui_scanout';OUT.mkdir(exist_ok=True)
SIM=Path('S:/ModelSim/win64');LIB='sim/work_ui_scanout'
base=ROOT/'software/build/reference_ui_check'
metadata=struct.unpack('<III',(base/'curved_metadata.bin').read_bytes())
assets=bytearray((base/'curved_assets.bin').read_bytes())
for n in range(metadata[0]&1023):
    at=0x4000+n*32;address=struct.unpack_from('<I',assets,at)[0]
    if address:struct.pack_into('<I',assets,at,address-0x10000000+0x01200000)
(OUT/'assets.hex').write_text(''.join(f'{v:08x}\n' for v in struct.unpack('<262144I',assets)))
pixels=struct.unpack('<307200H',(base/'curved_expected.bin').read_bytes())
(OUT/'expected.hex').write_text(''.join(f'{v:04x}\n' for v in pixels))
original=(ROOT/'sim/tb_render.sv').read_text()
prefix=original[:original.index('    reg repainted_a=')]
prefix=prefix.replace('module tb_render;','module tb_ui_scanout;').replace('always #5 clk=~clk;','always #3.333333 clk=~clk;')
# Continuous W beats are a legacy copy-engine performance assertion.
# The scanline UI core legitimately pauses WVALID while loading row RAM.
prefix=prefix.replace('if(writing&&wready) begin','if(writing&&wready&&dut.operation!=3) begin')
tree=ast.parse((ROOT/'tools/check_bench_entry.py').read_text())
tail=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='tail' for t in n.targets)))
tail=tail.replace('reg [15:0] menu_pixels','reg [31:0] ui_assets[0:262143];\n    reg [15:0] menu_pixels')
tail=tail.replace('software/build/bench_entry/pressure.hex','software/build/ui_scanout/expected.hex')
tail=tail.replace('        for(integer n=0;n<MEM_BYTES;n++)mem[n]=0;','        $readmemh("software/build/ui_scanout/assets.hex",ui_assets);\n        for(integer n=0;n<MEM_BYTES;n++)mem[n]=0;')
tail=tail.replace('        for(integer n=0;n<307200;n++)begin\n            {mem[ASSET_BASE-BASE+n*2+1],mem[ASSET_BASE-BASE+n*2]}=pressure ? pressure_pixels[n]:menu_pixels[n];\n        end','        if(pressure)begin\n            for(integer n=0;n<262144;n++)\n                {mem[ASSET_BASE-BASE+n*4+3],mem[ASSET_BASE-BASE+n*4+2],mem[ASSET_BASE-BASE+n*4+1],mem[ASSET_BASE-BASE+n*4]}=ui_assets[n];\n        end else for(integer n=0;n<307200;n++)\n            {mem[ASSET_BASE-BASE+n*2+1],mem[ASSET_BASE-BASE+n*2]}=menu_pixels[n];')
bg=metadata[1]-0x10000000+0x01200000
render=f"""        if(pressure)begin
            write_reg(48,3);write_reg(52,ASSET_BASE+32'h4000);write_reg(76,32'h{bg:08x});
            write_reg(12,draw_base);write_reg(16,640);write_reg(20,480);write_reg(24,1280);
            write_reg(28,{metadata[0]});write_reg(88,{metadata[2]});write_reg(8,1);
            status=1;while(status&1)begin repeat(100)@(posedge clk);read_reg(4,status);end
            if(status&4)$fatal(1,\"UI command failed\");
            // Match firmware wait_render(): DONE must survive slow APB polling.
            repeat(257)@(posedge clk);read_reg(4,status);
            if((status&7)!=2)$fatal(1,\"CPU missed UI completion: status=%h\",status);
        end else raw_copy(ASSET_BASE,1280,draw_base,640,480);"""
tail=tail.replace('        raw_copy(ASSET_BASE,1280,draw_base,640,480);',render)
tail=tail.replace('BENCH ENTRY RTL PASSED','UI SCANOUT RTL PASSED').replace('menu + %0d pressure','menu + %0d curved UI')
tail=tail.replace('#220000000','#300000000')
bench=OUT/'tb_ui_scanout.sv';bench.write_text(prefix+tail)
commands=[]
if not (ROOT/LIB).exists():commands.append(([SIM/'vlib.exe',LIB],'vlib'))
commands.extend([([SIM/'vlog.exe','-sv','-work',LIB,'rtl/sync_fifo.v','rtl/fill_engine.v','rtl/ui_compositor.v','rtl/ui_asset_rom.v','rtl/render_regs.v','rtl/framebuffer_video.v','rtl/video_mode_measure.v','rtl/render_subsystem.v',bench],'vlog'),([SIM/'vsim.exe','-batch','-t','1ps','-lib',LIB,'tb_ui_scanout','-do','onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'run')])
for cmd,label in commands:
    r=subprocess.run(list(map(str,cmd)),cwd=ROOT,capture_output=True,text=True)
    log=r.stdout+r.stderr;(ROOT/f'reports/ui_scanout_{label}.log').write_text(log,encoding='utf-8')
    r.check_returncode();print(log[-1500:],flush=True)
    if label=='run':assert 'UI SCANOUT RTL PASSED' in log
