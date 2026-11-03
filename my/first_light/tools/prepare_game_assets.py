"""Prepare coherent RGB565 game art from user player frames and CC0 Kenney tiles."""
from pathlib import Path
import hashlib
import json
import struct
import binascii
import zlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/game'

def read_rgba_png(path):
    data = path.read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f'{path} is not a PNG image')
    width = height = color_type = bit_depth = interlace = None
    compressed = bytearray()
    at = 8
    while at < len(data):
        size = struct.unpack('>I', data[at:at+4])[0]
        kind = data[at+4:at+8]
        chunk = data[at+8:at+8+size]
        at += size + 12
        if kind == b'IHDR':
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack('>IIBBBBB', chunk)
        elif kind == b'IDAT':
            compressed.extend(chunk)
        elif kind == b'IEND':
            break
    if bit_depth != 8 or color_type not in (2, 6) or interlace != 0:
        raise ValueError('Game art must be a non-interlaced 8-bit RGB/RGBA PNG')
    bpp = 4 if color_type == 6 else 3
    stride = width * bpp
    raw = zlib.decompress(compressed)
    rows, previous, offset = [], bytearray(stride), 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        source = raw[offset:offset+stride]
        offset += stride
        row = bytearray(stride)
        for i, value in enumerate(source):
            left = row[i-bpp] if i >= bpp else 0
            above = previous[i]
            upper_left = previous[i-bpp] if i >= bpp else 0
            if filter_type == 1:
                value += left
            elif filter_type == 2:
                value += above
            elif filter_type == 3:
                value += (left + above) // 2
            elif filter_type == 4:
                estimate = left + above - upper_left
                distances = (abs(estimate-left), abs(estimate-above), abs(estimate-upper_left))
                predictor = left if distances[0] <= distances[1] and distances[0] <= distances[2] else \
                            above if distances[1] <= distances[2] else upper_left
                value += predictor
            elif filter_type != 0:
                raise ValueError(f'Unsupported PNG filter {filter_type}')
            row[i] = value & 255
        if bpp == 3:
            previous = row
            rgba = bytearray(width * 4)
            for x in range(width):
                rgba[x*4:x*4+3] = row[x*3:x*3+3]
                rgba[x*4+3] = 255
            row = rgba
        rows.append(row)
        if bpp == 4:
            previous = row
    return width, height, rows

def frame_bounds(frame):
    """Half-open Color-Key bounds in the original 32x32 frame; no resampling."""
    if len(frame)!=1024: raise ValueError('Expected one 32x32 RGB565 frame')
    points=[(i%32,i//32) for i,p in enumerate(frame) if p!=0]
    if not points: return (0,0,0,0)
    return (min(x for x,y in points),min(y for x,y in points),
            max(x for x,y in points)+1,max(y for x,y in points)+1)


def main():
    # Reuse the checked-in source frames, then append only the new sprites.
    # This keeps normal regeneration independent of external Python packages.
    original = (OUT / 'game.rgb565').read_bytes()
    assert len(original)>=23*2048
    frames = [list(struct.unpack('<1024H',original[n*2048:(n+1)*2048])) for n in range(23)]
    def rgb(r,g,b): return ((r>>3)<<11)|((g>>2)<<5)|(b>>3)
    # Convert the user's red heart icon into the 32x32 RGB565 game frame.
    # Its gray canvas is removed by an edge-connected flood fill, preserving
    # the dark contour enclosed by the heart and leaving the outside Color-Key zero.
    heart_width,heart_height,heart_rows=read_rgba_png(OUT/'source/healing_heart.png')
    corners=[heart_rows[y][x*4:x*4+3] for y in (0,heart_height-1)
             for x in (0,heart_width-1)]
    background=tuple((sorted(px[c] for px in corners)[1]+
                      sorted(px[c] for px in corners)[2])//2 for c in range(3))
    def is_canvas(x,y):
        pixel=heart_rows[y][x*4:x*4+4]
        return not pixel[3] or max(abs(pixel[c]-background[c]) for c in range(3))<=10
    canvas=bytearray(heart_width*heart_height)
    edge=[]
    for x in range(heart_width):
        for y in (0,heart_height-1):
            index=y*heart_width+x
            if not canvas[index] and is_canvas(x,y): canvas[index]=1; edge.append(index)
    for y in range(heart_height):
        for x in (0,heart_width-1):
            index=y*heart_width+x
            if not canvas[index] and is_canvas(x,y): canvas[index]=1; edge.append(index)
    while edge:
        index=edge.pop()
        x=index%heart_width; y=index//heart_width
        for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if 0<=nx<heart_width and 0<=ny<heart_height:
                neighbor=ny*heart_width+nx
                if not canvas[neighbor] and is_canvas(nx,ny):
                    canvas[neighbor]=1; edge.append(neighbor)
    colored=[(x,y) for y in range(heart_height) for x in range(heart_width)
             if heart_rows[y][x*4+3] and not canvas[y*heart_width+x]]
    if not colored:
        raise ValueError('Healing-heart source contains no visible pixels')
    min_x=min(x for x,_ in colored); max_x=max(x for x,_ in colored)
    min_y=min(y for _,y in colored); max_y=max(y for _,y in colored)
    min_x=max(0,min_x-2); max_x=min(heart_width-1,max_x+2)
    min_y=max(0,min_y-2); max_y=min(heart_height-1,max_y+2)
    crop_w,crop_h=max_x-min_x+1,max_y-min_y+1
    out_w=max(1,round(32*crop_w/max(crop_w,crop_h)))
    out_h=max(1,round(32*crop_h/max(crop_w,crop_h)))
    offset_x=(32-out_w)//2; offset_y=(32-out_h)//2
    heart=[0]*1024
    sampled=[]
    for y in range(out_h):
        row=[]
        sy=min_y+y*crop_h//out_h
        for x in range(out_w):
            sx=min_x+x*crop_w//out_w
            pixel=heart_rows[sy][sx*4:sx*4+4]
            row.append((pixel[0],pixel[1],pixel[2],pixel[3],canvas[sy*heart_width+sx]))
        sampled.append(row)
    for y in range(out_h):
        for x in range(out_w):
            r,g,b,a,is_canvas_pixel=sampled[y][x]
            if not a or is_canvas_pixel:
                continue
            if r+g+b<=24:
                near_icon=any(
                    sampled[ny][nx][3] and not sampled[ny][nx][4] and
                    sum(sampled[ny][nx][:3])>64
                    for ny in range(max(0,y-2),min(out_h,y+3))
                    for nx in range(max(0,x-2),min(out_w,x+3)))
                if not near_icon:
                    continue
                r,g,b=5,10,22
            heart[(offset_y+y)*32+offset_x+x]=rgb(r,g,b)
    frames.append(heart)
    skeleton=frames[17]; warden=[]
    for p in skeleton:
        if not p: warden.append(0); continue
        shade=(((p>>11)&31)*255//31+((p>>5)&63)*255//63+(p&31)*255//31)//3
        color=(6,30,60) if shade<45 else (8,67,113) if shade<105 else (17,126,178) if shade<190 else (111,220,255)
        warden.append(rgb(*color))
    frames.append(warden)
    # Shared palette RLE: 6-bit run, 10-bit index, no runtime heap or floats.
    palette = sorted({p for f in frames for p in f}); assert len(palette)<=1024
    index = {v:i for i,v in enumerate(palette)}
    tokens, offsets = [], [0]
    for f in frames:
        at=0
        while at<len(f):
            n=1
            while at+n<len(f) and n<63 and f[at+n]==f[at]: n+=1
            tokens.append((n<<10)|index[f[at]]); at+=n
        offsets.append(len(tokens))
    decoded = [palette[t&1023] for t in tokens for _ in range(t>>10)]
    assert decoded == [p for f in frames for p in f]
    def array(name, values):
        lines = [f'static const uint16_t {name}[{len(values)}] = {{']
        lines += ['    '+', '.join(f'0x{v:04x}' for v in values[i:i+12])+',' for i in range(0,len(values),12)]
        return '\n'.join(lines+['};'])
    header = '#ifndef GAME_ASSETS_H\n#define GAME_ASSETS_H\n#include <stdint.h>\n'
    header += '/* Generated by tools/prepare_game_assets.py; Kenney art is CC0, source player supplied by user. */\n'
    header += f'#define GAME_FRAME_COUNT {len(frames)}u\n#define GAME_ASSET_BYTES {len(frames)*2048}u\n'
    header += f'#define GAME_COMPRESSED_BYTES {2*(len(palette)+len(tokens)+len(offsets))}u\n'
    header += array('game_palette',palette)+'\n'+array('game_rle',tokens)+'\n'+array('game_offsets',offsets)+'\n#endif\n'
    (ROOT/'software/game_assets.h').write_text(header,encoding='utf-8')
    bounds=[frame_bounds(frame) for frame in frames]
    bounds_header='#ifndef GAME_FRAME_BOUNDS_H\n#define GAME_FRAME_BOUNDS_H\n#include <stdint.h>\n'
    bounds_header+='/* Generated Color-Key bounds: left, top, right, bottom (exclusive). */\n'
    bounds_header+=f'#define GAME_FRAME_BOUNDS_COUNT {len(bounds)}u\n'
    bounds_header+=f'static const uint8_t game_frame_bounds[{len(bounds)}][4] = {{\n'
    bounds_header+=''.join('    {'+', '.join(map(str,box))+'},\n' for box in bounds)
    bounds_header+='};\n#endif\n'
    (ROOT/'software/game_frame_bounds.h').write_text(bounds_header,encoding='utf-8')

    (OUT/'game.rgb565').write_bytes(b''.join(struct.pack('<H',p) for p in decoded))
    (ROOT/'sim/game_expected.hex').write_text(''.join(f'{p:04x}\n' for p in decoded),encoding='ascii')
    width,height=32*8,32*4
    preview_pixels=[(8,16,30)]*(width*height)
    for i,f in enumerate(frames):
        ox=(i%8)*32; oy=(i//8)*32
        for y in range(32):
            for x in range(32):
                p=f[y*32+x]; color=((p>>11)*255//31,((p>>5)&63)*255//63,(p&31)*255//31) if p else (8,16,30)
                preview_pixels[(oy+y)*width+ox+x]=color
    scale=3; png_width,png_height=width*scale,height*scale
    rows=[]
    for y in range(height):
        row=bytes([0]+[channel for x in range(width) for channel in (preview_pixels[y*width+x]*scale)])
        rows.extend([row]*scale)
    def chunk(tag,data): return struct.pack('>I',len(data))+tag+data+struct.pack('>I',binascii.crc32(tag+data)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',png_width,png_height,8,2,0,0,0))
    png+=chunk(b'IDAT',zlib.compress(b''.join(rows),9))+chunk(b'IEND',b'')
    (OUT/'atlas_preview.png').write_bytes(png)
    manifest={'frames':len(frames),'player':'direction*4+walk_frame','slime':16,'skeleton':17,'bat':18,
              'gem':19,'bolt':20,'orb':21,'spark':22,'healing_heart':23,'ice_warden':24,
              'healing_heart_source':'healing_heart.png (user-supplied red heart, edge-connected gray canvas removed to Color Key)',
              'width':32,'height':32,'stride':64,
              'format':'RGB565 little endian','key':0,'ddr_base':'0x01204000','compressed_bytes':2*(len(palette)+len(tokens)+len(offsets)),
              'kenney_source_sha256':hashlib.sha256((OUT/'source/kenney_tiny_dungeon.png').read_bytes()).hexdigest()}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Game: {len(frames)} frames, {len(decoded)*2} DDR bytes, {len(palette)} palette entries, {manifest["compressed_bytes"]} compressed bytes.')

if __name__=='__main__': main()
