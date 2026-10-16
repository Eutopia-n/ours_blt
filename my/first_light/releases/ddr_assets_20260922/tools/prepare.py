"""Reproducible mechanical import of the board vendor's DDR/SoC/HDMI files.
Run only to (re)generate vendor/, competition_top.v and the Efinity project.
Handwritten renderer RTL and firmware are not overwritten.
"""
from pathlib import Path
import argparse
import copy
import re
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--board-root', type=Path, default=ROOT.parents[1])
args = parser.parse_args()
REPO = args.board_root.resolve()
SOC = REPO / '08_ti60f225_soc_demo/09_Ti60F225_co_debug_demo'
PAR = SOC / 'par/ddr_demo_ti60'
HDMI = REPO / '03_hdmi_tx_demo/hdmi_tx_demo_v2'
if not SOC.is_dir() or not HDMI.is_dir():
    raise SystemExit('prepare requires the complete board examples: pass --board-root PATH. '
                     'A normal clone can build without running prepare.')
EFX = 'http://www.efinixinc.com/enf_proj'
PT = 'http://www.efinixinc.com/peri_design_db'
ET.register_namespace('efx', EFX)
ET.register_namespace('efxpt', PT)
def e(tag): return '{'+EFX+'}'+tag
def p(tag): return '{'+PT+'}'+tag
def save(tree, path):
    ET.indent(tree, space='    ')
    tree.write(path, encoding='UTF-8', xml_declaration=True)

for name in ['rtl','vendor','software/build','sim','reports']:
    (ROOT/name).mkdir(parents=True, exist_ok=True)
shutil.copytree(SOC/'rtl/ddr3_controller', ROOT/'vendor/ddr3_controller', dirs_exist_ok=True)
shutil.copytree(SOC/'rtl/common', ROOT/'vendor/common', dirs_exist_ok=True)
(ROOT/'vendor/soc').mkdir(exist_ok=True)
for src in (PAR/'ip/soc').glob('*'):
    if src.suffix in ['.v','.bin','.json','.vh']:
        shutil.copy2(src, ROOT/'vendor/soc'/src.name)
for name in ['dvi_encoder.v','encode.v']:
    shutil.copy2(HDMI/'rtl/hdmi_src/dvi_tx'/name, ROOT/'vendor'/name)
shutil.copy2(PAR/'embedded_sw/soc/bsp/efinix/EfxSapphireSoc/include/soc.h', ROOT/'software/soc.h')
shutil.copy2(PAR/'embedded_sw/soc/bsp/efinix/EfxSapphireSoc/include/LICENSE.MD', ROOT/'vendor/Sapphire_LICENSE.MD')
shutil.copy2(PAR/'ip/soc/source/hardware/netlist/source_modelsim/EfxSapphireSoc.v',
             ROOT/'vendor/soc/EfxSapphireSoc_modelsim.v')

# Preserve the full 8-bit Sapphire DDR transaction ID, including arbitration bits.
param_path = ROOT/'vendor/ddr3_controller/ddr3_parameter.vh'
params = param_path.read_text()
params, n = re.subn(r'(`define AXI_ID_WIDTH\s+)4\b', r'\g<1>8', params)
assert n == 1
param_path.write_text(params)

top = (SOC/'rtl/ddr3_example_top.v').read_text(encoding='utf-8')
top = top.replace('module ddr3_example_top #', 'module competition_top #', 1)
top = top.replace('parameter FREQ = 200;', 'parameter FREQ = 100;', 1)
marker = '   // Clock and reset ports'
ports = '''   // HDMI TX serializer ports imported from the board HDMI demo.
   input hdmi_tx_locked,
   input hdmi_tx_slow_clk,
   output [9:0] tmds_data0_o, tmds_data1_o, tmds_data2_o, tmds_clk_o,
   output tmds_data0_TX_OE, tmds_data1_TX_OE, tmds_data2_TX_OE, tmds_clk_TX_OE,
   output tmds_data0_TX_RST, tmds_data1_TX_RST, tmds_data2_TX_RST, tmds_clk_TX_RST,
'''
assert marker in top
top = top.replace(marker, ports+marker, 1)
decl = '''
  wire [15:0] apb_paddr;
  wire [31:0] apb_pwdata, apb_prdata;
  wire apb_psel, apb_penable, apb_pready, apb_pwrite, apb_pslverror;
  wire soc_reset, master_reset;
  reg [1:0] calibration_sync;
  always @(posedge user_clk or negedge sys_rst)
    if (!sys_rst) calibration_sync <= 0;
    else calibration_sync <= {calibration_sync[0],cal_done};
  wire [31:0] cpu_ddr_awaddr, cpu_ddr_araddr;
  assign s_axi_awaddr = cpu_ddr_awaddr[27:0];
  assign s_axi_araddr = cpu_ddr_araddr[27:0];
  wire [31:0] gfx_awaddr, gfx_wdata, gfx_araddr, gfx_rdata;
  wire [7:0] gfx_awlen, gfx_arlen;
  wire [3:0] gfx_wstrb;
  wire [1:0] gfx_bresp, gfx_rresp;
  wire gfx_awvalid, gfx_awready, gfx_wvalid, gfx_wready, gfx_wlast;
  wire gfx_bvalid, gfx_bready, gfx_arvalid, gfx_arready, gfx_rvalid, gfx_rready, gfx_rlast;
  wire [15:0] video_pixel;
  wire video_hs, video_vs, video_de;
  wire [9:0] tmds_data0, tmds_data1, tmds_data2, tmds_clk;
  wire renderer_reset = soc_reset | master_reset | !hdmi_tx_locked;
'''
top = top.replace('  wire                              cal_done;', '  wire                              cal_done;\n'+decl, 1)
start = top.index('soc u_sapphire_soc(')
finish = top.index('\n);', start)+3
old_instance = top[start:finish]
mapping = dict(re.findall(r'\.([A-Za-z_0-9]+)\s*\(\s*([^()]*?)\s*\)', old_instance))
mapping.update(io_asyncReset='!calibration_sync[1]',io_systemReset='soc_reset',
    io_ddrMasters_0_reset='master_reset',io_ddrMasters_0_clk='user_clk',
    io_ddrA_aw_payload_addr='cpu_ddr_awaddr',io_ddrA_ar_payload_addr='cpu_ddr_araddr',
    io_ddrA_b_payload_resp='s_axi_bresp',io_ddrA_aw_payload_prot='s_axi_awprot',
    io_ddrA_aw_payload_cache='s_axi_awcache',io_ddrA_ar_payload_prot='s_axi_arprot',
    io_ddrA_ar_payload_cache='s_axi_arcache')
for channel in ['aw','w','b','ar','r']:
    for field in ['valid','ready']:
        mapping[f'io_ddrMasters_0_{channel}_{field}'] = f'gfx_{channel}{field}'
for channel, fields in [('aw',['addr','len']),('w',['data','strb','last']),
                         ('b',['resp']),('ar',['addr','len']),('r',['data','resp','last'])]:
    for field in fields:
        mapping[f'io_ddrMasters_0_{channel}_payload_{field}'] = f'gfx_{channel}{field}'
for channel in ['aw','ar']:
    for field,value in [('size',"3'd2"),('burst',"2'b01"),('id',"4'd0"),
                        ('prot',"3'd0"),('qos',"4'd0"),('cache',"4'd0"),
                        ('lock',"1'b0"),('region',"4'd0")]:
        mapping[f'io_ddrMasters_0_{channel}_payload_{field}'] = value
# Explicitly terminate every unused input; do not leave enabled bus inputs floating.
soc_header = (ROOT/'vendor/soc/soc.v').read_text(encoding='utf-8').split('module soc',1)[1].split(');',1)[0]
soc_ports = re.findall(r'\b(input|output)\s*(\[[^]]+\])?\s*(\w+)\s*[,\n]',soc_header)
assert len(soc_ports)>130
instance=[]
for direction,width,name in soc_ports:
    value = mapping.get(name,'')
    if direction == 'input' and not value:
        # I2C open-drain input defaults to released/high; interrupts and bus responses are low.
        value = "1'b1" if name.startswith('system_i2c') else ("'b0" if width else "1'b0")
    instance.append(f'    .{name} ({value})')
top = top[:start]+'soc u_sapphire_soc(\n'+',\n'.join(instance)+'\n);'+top[finish:]
start = top.index('apb3_top u_apb3_top(')
finish = top.index(');',start)+2
graphics = '''render_subsystem graphics (
    .clk(user_clk),.reset(renderer_reset),.pixel_clk(hdmi_tx_slow_clk),
    .memory_ready(calibration_sync[1]),
    .paddr(apb_paddr),.psel(apb_psel),.penable(apb_penable),.pwrite(apb_pwrite),
    .pwdata(apb_pwdata),.prdata(apb_prdata),.pready(apb_pready),.pslverror(apb_pslverror),
    .awaddr(gfx_awaddr),.awlen(gfx_awlen),.awvalid(gfx_awvalid),.awready(gfx_awready),
    .wdata(gfx_wdata),.wstrb(gfx_wstrb),.wvalid(gfx_wvalid),.wready(gfx_wready),.wlast(gfx_wlast),
    .bresp(gfx_bresp),.bvalid(gfx_bvalid),.bready(gfx_bready),
    .araddr(gfx_araddr),.arlen(gfx_arlen),.arvalid(gfx_arvalid),.arready(gfx_arready),
    .rdata(gfx_rdata),.rresp(gfx_rresp),.rlast(gfx_rlast),.rvalid(gfx_rvalid),.rready(gfx_rready),
    .pixel(video_pixel),.hs(video_hs),.vs(video_vs),.de(video_de)
);
reg [1:0] hdmi_reset_pipe;
always @(posedge hdmi_tx_slow_clk or posedge renderer_reset)
    if (renderer_reset) hdmi_reset_pipe <= 2'b11;
    else hdmi_reset_pipe <= {hdmi_reset_pipe[0],1'b0};
dvi_encoder hdmi (
    .pixelclk(hdmi_tx_slow_clk),.rstin(hdmi_reset_pipe[1]),
    .red_din({video_pixel[15:11],video_pixel[15:13]}),
    .green_din({video_pixel[10:5],video_pixel[10:9]}),
    .blue_din({video_pixel[4:0],video_pixel[4:2]}),
    .hsync(video_hs),.vsync(video_vs),.de(video_de),
    .tmds_data0(tmds_data0),.tmds_data1(tmds_data1),.tmds_data2(tmds_data2),.tmds_clk(tmds_clk)
);
// The board swaps P/N on all four TX pairs: preserve the vendor inversion.
assign tmds_data0_o = ~tmds_data0;
assign tmds_data1_o = ~tmds_data1;
assign tmds_data2_o = ~tmds_data2;
assign tmds_clk_o = ~tmds_clk;
assign {tmds_data0_TX_OE,tmds_data1_TX_OE,tmds_data2_TX_OE,tmds_clk_TX_OE} = 4'b1111;
assign {tmds_data0_TX_RST,tmds_data1_TX_RST,tmds_data2_TX_RST,tmds_clk_TX_RST} = 4'b0000;
'''
top = top[:start]+graphics+top[finish:]
(ROOT/'rtl/competition_top.v').write_text(top,encoding='utf-8')

# Keep vendor DDR/GPIO assignments, add only HDMI TX LVDS and its PLL.
peri = ET.parse(PAR/'ddr_demo_ti60.peri.xml')
db = peri.getroot(); db.set('name','first_light')
hdmi = ET.parse(HDMI/'hdmi_tx.peri.xml').getroot()
pll = copy.deepcopy(hdmi.find(p('pll_info')).find(p('pll')))
pll.set('ref_clock_name','clk_25m')
pll.set('multiplier','1'); pll.set('pre_divider','1')
pll.find(p('adv_prop')).set('feedback_clock_name','hdmi_fb')
# Local feedback: 25 MHz * 121 = 3025 MHz VCO.
# Even divisors /120 and /24 give 25.208333/126.041667 MHz without duty distortion.
# 800x525 totals give 60.01984 Hz (nominal 60 Hz).
# Fast phase setting 4 = 2 VCO cycles = 0.661 ns; meets the LVDS phase rule.
for c in pll.findall(p('comp_output_clock')):
    name=c.get('name')
    if name=='FB': c.set('name','hdmi_fb'); c.set('out_divider','121')
    elif name=='hdmi_tx_slow_clk': c.set('out_divider','120')
    elif name=='hdmi_tx_fast_clk': c.set('out_divider','24'); c.set('phase_setting','4')
for bank in db.find(p('device_info')).find(p('iobank_info')):
    if bank.get('name') == '3A': bank.set('iostd','1.8 V LVCMOS')
db.find(p('pll_info')).append(pll)
for lvds in hdmi.find(p('lvds_info')): db.find(p('lvds_info')).append(copy.deepcopy(lvds))
# ROW_WIDTH=14: the vendor peripheral file also contains two unused address pins.
gpio=db.find(p('gpio_info'))
for node in list(gpio):
    if node.get('name') in ['ddr_addr[14]','ddr_addr[15]']: gpio.remove(node)
    if node.tag==p('bus') and node.get('name')=='ddr_addr': node.set('msb','13')
save(peri,ROOT/'first_light.peri.xml')

project=ET.parse(PAR/'ddr_demo_ti60.xml'); pr=project.getroot()
for key in list(pr.attrib):
    if key not in ['name','description','sw_version']: del pr.attrib[key]
pr.set('name','first_light'); pr.set('description','RISC-V AXI solid fill and DDR HDMI first light')
di=pr.find(e('design_info'))
for node in list(di):
    if node.tag==e('design_file'): di.remove(node)
di.find(e('top_module')).set('name','competition_top')
sources=['rtl/competition_top.v','rtl/render_subsystem.v','rtl/render_regs.v',
         'rtl/sync_fifo.v','rtl/fill_engine.v','rtl/framebuffer_video.v','rtl/video_mode_measure.v','vendor/soc/soc.v',
         'vendor/common/simple_dual_port_ram.v','vendor/dvi_encoder.v','vendor/encode.v']
sources += [str(x.relative_to(ROOT)).replace('\\','/') for x in (ROOT/'vendor/ddr3_controller').rglob('*.v')
            if x.name not in ['simple_dual_port_ram.v','axi_upsizer.v']]
insert_at = list(di).index(di.find(e('top_vhdl_arch')))
for offset, source in enumerate(sources):
    node = ET.Element(e('design_file'),name=source,version='default',library='default')
    di.insert(insert_at + offset, node)
pr.find(e('ip_info')).clear()
ci=pr.find(e('constraint_info')); ci.clear(); ET.SubElement(ci,e('sdc_file'),name='first_light.sdc')
ii=pr.find(e('interface_info'))
if ii is None:
    ii=ET.Element(e('interface_info'))
    pr.insert(list(pr).index(pr.find(e('constraint_info'))),ii)
ii.clear(); ET.SubElement(ii,e('default_peri_file'),name='first_light.peri.xml')
for node in pr.find(e('synthesis')).findall(e('param')):
    if node.get('name')=='include': node.set('value','vendor')
    if node.get('name')=='max_threads': node.set('value','4')
for node in pr.find(e('place_and_route')).findall(e('param')):
    if node.get('name')=='max_threads': node.set('value','4')
save(project,ROOT/'first_light.xml')
print('Prepared',ROOT)
print('SoC ports:',len(soc_ports),'RTL sources:',len(sources))
