"""Test actual synthesis and ModelSim public OCR modules with Icarus Verilog."""
from pathlib import Path
import argparse
import re
import subprocess
from expand_soc_ram import ROOT, OCR_BYTES, ram_module, verify_project

parser=argparse.ArgumentParser()
parser.add_argument('--iverilog',default='iverilog')
parser.add_argument('--vvp',default='vvp')
args=parser.parse_args()
verify_project()
build=ROOT/'sim/work_ocr128'
build.mkdir(parents=True,exist_ok=True)
lanes=[]
for lane in range(4):
    name=f'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol{lane}.bin'
    raw=(ROOT/name).read_text().splitlines()
    assert len(raw)==OCR_BYTES//4 and all(re.fullmatch('[01]{8}',v) for v in raw)
    assert raw==(ROOT/'vendor/soc'/name).read_text().splitlines()
    lanes.append(raw)
first=sum(int(lanes[n][0],2)<<(8*n) for n in range(4))
logs=[]
for name in ('soc.v','EfxSapphireSoc_modelsim.v'):
    source=(ROOT/'vendor/soc'/name).read_text(encoding='utf-8')
    ram=re.sub(r'^module \w+', 'module actual_ocr',ram_module(source).group())
    decode=re.search(r'assign logic_hitsS0_0 = (\(\(io_input_cmd_payload_fragment_address & .*f9000000\));',source)
    assert decode,'Missing actual OCR decoder'
    expr=decode[1].replace('io_input_cmd_payload_fragment_address','address')
    wrapper=f'''
`define OCR_INITIAL_WORD 32'h{first:08x}
module ocr_test_wrapper(input clk,reset,input [31:0] address,input valid,write,
 input [31:0] data,input [3:0] mask,tag,input ready,
 output selected,cmd_ready,rsp_valid,output [31:0] rsp_data,output [3:0] rsp_context);
 wire ram_ready;
 assign selected={expr};
 assign cmd_ready=selected && ram_ready;
 actual_ocr ram(.io_systemClk(clk),.systemCd_logic_outputReset(reset),
 .io_bus_cmd_valid(valid && selected),.io_bus_cmd_ready(ram_ready),
 .io_bus_cmd_payload_last(1'b1),.io_bus_cmd_payload_fragment_opcode(write),
 .io_bus_cmd_payload_fragment_address(address[16:0]),
 .io_bus_cmd_payload_fragment_length(2'd2),.io_bus_cmd_payload_fragment_data(data),
 .io_bus_cmd_payload_fragment_mask(mask),.io_bus_cmd_payload_fragment_context(tag),
 .io_bus_rsp_valid(rsp_valid),.io_bus_rsp_ready(ready),
 .io_bus_rsp_payload_fragment_data(rsp_data),.io_bus_rsp_payload_fragment_context(rsp_context),
 .io_bus_rsp_payload_last(),.io_bus_rsp_payload_fragment_opcode());
endmodule
'''
    generated=build/(name+'.sv')
    generated.write_text(ram+'\n'+wrapper,encoding='utf-8')
    exe=build/(name+'.vvp')
    result=subprocess.run([args.iverilog,'-g2012','-s','tb_soc_ram','-o',str(exe),
                           str(generated),str(ROOT/'sim/tb_soc_ram.sv')],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    run=subprocess.run([args.vvp,str(exe)],cwd=ROOT,capture_output=True,text=True)
    text=name+'\n'+run.stdout+run.stderr
    logs.append(text)
    print(text,flush=True)
    (ROOT/'reports/ocr128_memory_check.log').write_text('\n'.join(logs),encoding='utf-8')
    assert run.returncode==0 and 'OCR128 TEST PASSED' in run.stdout
print('Both SoC OCR models and all eight initialization files verified.')
