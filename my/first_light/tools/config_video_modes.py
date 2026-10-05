"""Configure fixed 800x600 HDMI clocks, without touching DDR or CPU PLLs."""
from pathlib import Path
import xml.etree.ElementTree as ET

PT = 'http://www.efinixinc.com/peri_design_db'

def configure(peri):
    p = lambda tag: '{'+PT+'}'+tag
    db = peri.getroot()
    plls = db.find(p('pll_info'))
    hdmi = next(node for node in plls if node.get('name') == 'pll_hdmi')
    # Fixed SVGA needs no reference PLL, fabric divider or reference mux.
    # 100 MHz * 32 = 3200 MHz VCO; /80 = 40 MHz pixels, /16 = 200 MHz DDR TX.
    for node in list(plls):
        if node.get('name') == 'pll_video_ref': plls.remove(node)
    hdmi.set('ref_clock_name','core_clk'); hdmi.set('ref_clock_freq','100.0000')
    hdmi.set('multiplier','1'); hdmi.set('pre_divider','1'); hdmi.set('post_divider','1')
    hdmi.set('reset_name','hdmi_pll_reset_n')
    adv = hdmi.find(p('adv_prop'))
    adv.set('ref_clock_mode','core'); adv.set('ref_clock1_name','')
    adv.set('clksel_name','')
    adv.set('feedback_clock_name','hdmi_fb'); adv.set('feedback_mode','local')
    for c in hdmi.findall(p('comp_output_clock')):
        num = int(c.get('number'))
        c.set('out_divider',['32','80','16'][num])
        c.set('phase_setting','4' if num == 2 else '0')

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    ET.register_namespace('efxpt', PT)
    tree = ET.parse(root/'first_light.peri.xml')
    configure(tree)
    ET.indent(tree,space='    ')
    tree.write(root/'first_light.peri.xml',encoding='UTF-8',xml_declaration=True)
