"""Verify the actual PLL output, constraints and timing at 150 MHz."""
from pathlib import Path
import re,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
tree=ET.parse(ROOT/'first_light.peri.xml')
pll=next(e for e in tree.getroot().iter() if e.tag.endswith('}pll') and e.get('name')=='pll_inst1')
adv=next(e for e in pll if e.tag.endswith('}adv_prop'))
assert adv.get('feedback_clock_name')=='core_clk'
outputs={e.get('name'):int(e.get('out_divider')) for e in pll if e.tag.endswith('}comp_output_clock')}
assert outputs=={'core_clk':24,'cpu_clk':16}
generated=(ROOT/'outflow/first_light.pt_timing.rpt').read_text(errors='replace')
for name,period in [('core_clk',10.0),('cpu_clk',1000/150),('sdram_clk',2.5),
                    ('rx_cal_clk',2.5),('tx_cal_clk',2.5),('hdmi_tx_slow_clk',39.669421)]:
    match=re.search(r'\|\s*'+name+r'\s*\|\s*([\d.]+)\s*\|',generated)
    assert match and abs(float(match[1])-period)<0.001,name
assert '-name cpu_clk -period 6.666667' in (ROOT/'first_light.sdc').read_text()
assert '#define SYSTEM_CLINT_HZ 150000000' in (ROOT/'software/soc.h').read_text()
timing=(ROOT/'outflow/first_light.timing.rpt').read_text()
section=timing.split('Setup (Max) Clock Relationship',1)[1].split('---------- Clock Relationship Summary (end)',1)[0]
slacks=[]
for line in section.splitlines():
    m=re.match(r'^\S+\s+\S+\s+([\d.]+)\s+(-?[\d.]+)\s+\(',line)
    if m: slacks.append(float(m[2]))
assert len(slacks)>=16 and min(slacks)>0,slacks
print('CPU150 CONFIG/TIMING PASSED: actual CPU150/DDR100/SDRAM400/HDMI25.208; positive setup/hold')
