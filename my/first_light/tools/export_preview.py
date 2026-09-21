"""Convert the actual simulated RGB scanout from PPM to PNG (standard library only)."""
from pathlib import Path
import struct
import sys
import zlib

root = Path(__file__).resolve().parents[1]
def chunk(kind, data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
for name in sys.argv[1:] or ['sim_frame']:
    source=root/'reports'/f'{name}.ppm'
    header,size,maximum,pixels=source.read_bytes().split(b'\n',3)
    assert (header,size,maximum)==(b'P6',b'640 480',b'255')
    assert len(pixels)==640*480*3
    rows=b''.join(b'\0'+pixels[y*1920:(y+1)*1920] for y in range(480))
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',640,480,8,2,0,0,0))
    png+=chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')
    source.with_suffix('.png').write_bytes(png)
    print(f'Exported verified simulation scanout to reports/{name}.png')
