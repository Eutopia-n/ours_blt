"""Check generated PLL frequencies against SDC and both clock domains.

Run after Efinity interface/compile. A successful compile alone does not prove
that the PLL generates the clock assumed by timing analysis and firmware.
"""
from pathlib import Path
import re,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
ns={'p':'http://www.efinixinc.com/peri_design'}
tree=ET.parse(ROOT/'first_light.peri.xml')
pll=next(e for e in tree.getroot().iter() if e.tag.endswith('}pll') and e.get('name')=='pll_inst1')
adv=next(e for e in pll if e.tag.endswith('}adv_prop'))
assert adv.get('feedback_clock_name')=='core_clk', 'PLL feedback must remain core_clk'
outputs={e.get('name'):int(e.get('out_divider')) for e in pll if e.tag.endswith('}comp_output_clock')}
base=float(pll.get('ref_clock_freq'))*int(pll.get('multiplier'))/int(pll.get('pre_divider'))
assert abs(base-100)<1e-6
assert abs(base*outputs['core_clk']/outputs['cpu_clk']-120)<1e-6
generated=(ROOT/'outflow/first_light.pt_timing.rpt').read_text(errors='replace')
for name,period in [('core_clk',10.0),('cpu_clk',1000/120),('sdram_clk',2.5),
                    ('rx_cal_clk',2.5),('tx_cal_clk',2.5),('hdmi_tx_slow_clk',39.669421)]:
    match=re.search(r'\|\s*'+name+r'\s*\|\s*([\d.]+)\s*\|',generated)
    assert match and abs(float(match[1])-period)<0.001, f'Actual PLL frequency mismatch: {name}'
sdc=(ROOT/'first_light.sdc').read_text()
assert '-name cpu_clk -period 8.333333' in sdc
assert '-name core_clk -period 10.000' in sdc
top=(ROOT/'rtl/competition_top.v').read_text()
for connection in ['.io_systemClk (cpu_clk)','.io_memoryClk (user_clk)',
                   '.io_ddrMasters_0_clk (cpu_clk)',
                   '.clk(cpu_clk),.reset(renderer_reset)',
                   'assign user_clk = core_clk;']:
    assert connection in top, connection
assert '#define SYSTEM_CLINT_HZ 120000000' in (ROOT/'software/soc.h').read_text()
print('CPU120 CONFIG PASSED: actual PLL CPU120/DDR100/SDRAM400/HDMI25.208; SDC, firmware and clock connections agree')
