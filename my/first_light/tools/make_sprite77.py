"""Build the 77-frame RGB565 color-key asset from the supplied original art.

The larger white-background picture supplies RGB.  The smaller transparent
picture is only a guide to the silhouette.  Everything outside the final
binary mask becomes the *opaque* RGB565 color key 0xf81f.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import struct
import zlib

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ORIGINAL = ASSETS / "sprite77_original.png"
ALPHA_GUIDE = ASSETS / "sprite77_alpha_reference.png"
KEY = 0xF81F
FRAME_COUNT = 77
TABLE_START = 16
PIXEL_START = TABLE_START + FRAME_COUNT * 8
POOL_BYTES = 1 << 20

# Measured from the transparent guide, in row-major order.  The ninth row has
# overlapping dust effects; its column dividers intentionally cut the shared
# trail instead of taking pixels from the next pose.
X_EDGES = (
    (110, 192, 272, 355, 450, 564, 661, 760),
    (110, 181, 269, 366, 445, 542, 638, 760),
    (110, 202, 291, 379, 474, 568, 660, 760),
    (110, 193, 274, 359, 454, 549, 643, 760),
    (110, 197, 280, 353, 449, 544, 639, 760),
    (110, 199, 286, 374, 463, 558, 652, 760),
    (110, 193, 273, 359, 454, 542, 643, 760),
    (110, 189, 279, 374, 470, 572, 666, 760),
    (110, 200, 286, 380, 475, 574, 665, 760),
    (110, 195, 281, 371, 464, 561, 658, 760),
    (110, 197, 280, 377, 473, 570, 671, 760),
)
Y_EDGES = (25, 124, 227, 319, 401, 497, 604, 700, 795, 899, 989, 1103)
Y_BASELINES = (115, 209, 302, 390, 485, 585, 678, 777, 877, 979, 1091)


def encode_rle(words: np.ndarray) -> bytes:
    """Top bit: key run; otherwise a literal run, with lengths 1..128."""
    out = bytearray()
    i = 0
    values = words.tolist()
    while i < len(values):
        key_run = values[i] == KEY
        end = i + 1
        while end < len(values) and end - i < 128 and (values[end] == KEY) == key_run:
            end += 1
        out.append((0x80 if key_run else 0) | (end - i - 1))
        if not key_run:
            out.extend(struct.pack("<" + "H" * (end - i), *values[i:end]))
        i = end
    return bytes(out)


def decode_rle(packed: bytes, expected_words: int) -> bytes:
    out = bytearray()
    i = 0
    while i < len(packed):
        tag = packed[i]
        i += 1
        count = (tag & 0x7F) + 1
        if tag & 0x80:
            out.extend(struct.pack("<H", KEY) * count)
        else:
            count_bytes = 2 * count
            if i + count_bytes > len(packed):
                raise ValueError("truncated literal run")
            out.extend(packed[i:i + count_bytes])
            i += count_bytes
        if len(out) > expected_words * 2:
            raise ValueError("RLE expands beyond declared asset")
    if len(out) != expected_words * 2:
        raise ValueError("RLE length mismatch")
    return bytes(out)


def make(scale: float) -> tuple[bytes, bytes, list[tuple[int, int, int, int, int]], list[np.ndarray]]:
    original = Image.open(ORIGINAL).convert("RGB")
    guide = Image.open(ALPHA_GUIDE).getchannel("A")
    if original.size != (1078, 1432) or guide.size != (863, 1146):
        raise ValueError("Unexpected source dimensions; review extraction coordinates")
    size = (round(original.width * scale), round(original.height * scale))
    color = np.asarray(original.resize(size, Image.Resampling.LANCZOS), dtype=np.uint8)
    alpha = np.asarray(guide.resize(size, Image.Resampling.LANCZOS), dtype=np.uint8)
    sx = size[0] / guide.width
    sy = size[1] / guide.height
    xedges = [[round(v * sx) for v in row] for row in X_EDGES]
    yedges = [round(v * sy) for v in Y_EDGES]
    ybaselines = [round(v * sy) for v in Y_BASELINES]
    table = bytearray()
    pixels = bytearray()
    frames = []
    previews = []
    for row in range(11):
        for col in range(7):
            left, right = xedges[row][col], xedges[row][col + 1]
            top, bottom = yedges[row], yedges[row + 1]
            rgb = color[top:bottom, left:right]
            a = alpha[top:bottom, left:right]
            # The alpha guide loses some white gloves and clothing because it
            # was derived from a light background.  Strong color differences
            # and enclosed holes recover those regions from the original.
            colored = np.max(np.abs(rgb.astype(np.int16) - (254, 253, 253)), axis=2) > 42
            mask = ndimage.binary_fill_holes((a >= 128) | colored)
            if row == 8 and col == 1:
                # The long dust trail joins adjacent poses on the source
                # sheet.  A detached triangular shard at this cell's left
                # edge belongs to frame 56, not to frame 57.
                labels, count = ndimage.label(mask)
                if count:
                    sizes = np.bincount(labels.ravel())
                    sizes[0] = 0
                    mask &= labels == int(sizes.argmax())
            yy, xx = np.nonzero(mask)
            if len(xx) == 0:
                raise ValueError(f"Empty pose {row * 7 + col}")
            pad = round(6 * sx)
            x0 = max(0, int(xx.min()) - pad)
            x1 = min(right - left, int(xx.max()) + 1 + pad)
            y0 = max(0, int(yy.min()) - pad)
            y1 = min(bottom - top, int(yy.max()) + 1 + pad)
            crop_rgb = rgb[y0:y1, x0:x1]
            crop_mask = mask[y0:y1, x0:x1]
            r, g, b = (crop_rgb[:, :, k].astype(np.uint16) for k in range(3))
            quant = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            # An opaque foreground pixel must never collide with the key.
            quant[(quant == KEY) & crop_mask] = KEY - 1
            frame = np.where(crop_mask, quant, KEY).astype("<u2")
            height, width = frame.shape
            dx = left + x0 - (left + right) // 2
            dy = top + y0 - ybaselines[row]
            if not (0 < width <= 255 and 0 < height <= 255 and -128 <= dx <= 127 and -128 <= dy <= 127):
                raise ValueError(f"Pose {row * 7 + col} does not fit the frame table")
            offset = PIXEL_START + len(pixels)
            table.extend(struct.pack("<IBBbb", offset, width, height, dx, dy))
            pixels.extend(frame.tobytes())
            if len(pixels) & 3:
                pixels.extend(struct.pack("<H", KEY))
            frames.append((offset, width, height, dx, dy))
            previews.append(frame)
    assert len(frames) == FRAME_COUNT and len(table) == FRAME_COUNT * 8
    body = bytes(table + pixels)
    crc = zlib.crc32(body) & 0xFFFFFFFF
    raw = struct.pack("<4sIII", b"AS77", 1, TABLE_START + len(body), crc) + body
    if len(raw) > POOL_BYTES:
        raise OverflowError(f"Packed asset {len(raw)} exceeds {POOL_BYTES}")
    packed_pixels = encode_rle(np.frombuffer(pixels, dtype="<u2"))
    if decode_rle(packed_pixels, len(pixels) // 2) != pixels:
        raise AssertionError("RLE round-trip failed")
    wire = struct.pack("<4sIII", b"S77U", len(raw), len(packed_pixels), crc) + bytes(table) + packed_pixels
    return raw, wire, frames, previews


def preview(frames: list[tuple[int, int, int, int, int]], images: list[np.ndarray], keyed: bool, path: Path) -> None:
    cell_w, cell_h = 160, 128
    canvas = Image.new("RGB", (7 * cell_w, 11 * cell_h), (31, 43, 58))
    draw = ImageDraw.Draw(canvas)
    for n, (entry, words) in enumerate(zip(frames, images)):
        _, width, height, dx, dy = entry
        x = (n % 7) * cell_w + 80 + dx
        y = (n // 7) * cell_h + 112 + dy
        if not keyed:
            draw.rectangle((x, y, x + width - 1, y + height - 1), fill=(255, 0, 255))
        rgb = np.empty((height, width, 3), dtype=np.uint8)
        rgb[:, :, 0] = ((words >> 11) & 31) * 255 // 31
        rgb[:, :, 1] = ((words >> 5) & 63) * 255 // 63
        rgb[:, :, 2] = (words & 31) * 255 // 31
        tile = Image.fromarray(rgb, "RGB")
        if keyed:
            tile.putalpha(Image.fromarray(np.where(words == KEY, 0, 255).astype(np.uint8), "L"))
            canvas.paste(tile, (x, y), tile)
        else:
            canvas.paste(tile, (x, y))
        draw.text(((n % 7) * cell_w + 4, (n // 7) * cell_h + 4), f"{n:02d}", fill=(255, 255, 255))
    canvas.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=float, default=0.8)
    args = parser.parse_args()
    try:
        raw, wire, frames, images = make(args.scale)
        scale = args.scale
    except OverflowError:
        if args.scale != 0.8:
            raise
        scale = 0.75
        raw, wire, frames, images = make(scale)
    (ASSETS / "sprite77.raw").write_bytes(raw)
    (ASSETS / "sprite77.upload").write_bytes(wire)
    preview(frames, images, True, ASSETS / "sprite77_key_on.png")
    preview(frames, images, False, ASSETS / "sprite77_key_off.png")
    print(f"77 frames, scale={scale}, DDR bytes={len(raw)}, UART bytes={len(wire)}, CRC32={struct.unpack_from('<I', raw, 12)[0]:08X}")


if __name__ == "__main__":
    main()
