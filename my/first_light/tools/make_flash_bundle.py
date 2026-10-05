"""Build the user-data image stored after the FPGA bitstream in SPI Flash.

The FPGA bitstream remains the normal Efinity Programmer image at address
0x000000. This script creates the independent user image written at 0x380000:
fixed header + animation.bin + sprite77.raw. The legacy two-payload layout is retained for compatibility. The current
bootloader reads only the assets; its application comes from the bitstream ROM.
"""
from pathlib import Path
import argparse
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
FLASH_USER_BASE = 0x380000
FLASH_SIZE = 0x800000
MAGIC = 0x314C5446  # FTL1, little endian
VERSION = 1
HEADER_BYTES = 40
APP_OFFSET = HEADER_BYTES
ASSET_OFFSET = 0x4000


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def write_byte_hex(path: Path, data: bytes) -> None:
    path.write_text("".join(f"{value:02X}\n" for value in data), encoding="ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the local Ti60F225 SPI Flash user bundle")
    parser.add_argument("--app", type=Path, default=ROOT / "software" / "build" / "animation.bin")
    parser.add_argument("--asset", type=Path, default=ROOT / "assets" / "sprite77.raw")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "software" / "build")
    args = parser.parse_args()

    app = args.app.read_bytes()
    asset = args.asset.read_bytes()
    if not app or len(app) > 65536:
        raise SystemExit(f"animation.bin must be 1..65536 bytes (got {len(app)})")
    if len(asset) <= 632 or len(asset) > 0x100000 or len(asset) & 1:
        raise SystemExit(f"sprite77.raw has an invalid size: {len(asset)}")
    if asset[:4] != b"AS77" or struct.unpack_from("<I", asset, 4)[0] != 1:
        raise SystemExit("sprite77.raw does not have the expected AS77 v1 header")
    if struct.unpack_from("<I", asset, 8)[0] != len(asset):
        raise SystemExit("sprite77.raw header length does not match the file")
    asset_crc = crc32(asset[16:])
    if struct.unpack_from("<I", asset, 12)[0] != asset_crc:
        raise SystemExit("sprite77.raw payload CRC is invalid")

    total_length = ASSET_OFFSET + len(asset)
    if FLASH_USER_BASE + total_length > FLASH_SIZE:
        raise SystemExit("Flash bundle does not fit in the 8 MiB GD25LQ64")
    header = struct.pack(
        "<10I",
        MAGIC,
        VERSION,
        APP_OFFSET,
        len(app),
        crc32(app),
        ASSET_OFFSET,
        len(asset),
        asset_crc,
        total_length,
        0,
    )
    bundle = bytearray(total_length)
    bundle[:HEADER_BYTES] = header
    bundle[APP_OFFSET:APP_OFFSET + len(app)] = app
    bundle[ASSET_OFFSET:ASSET_OFFSET + len(asset)] = asset

    args.out_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = args.out_dir / "flash_user.bin"
    hex_path = args.out_dir / "flash_user.hex"
    manifest_path = args.out_dir / "flash_user.txt"
    bundle_path.write_bytes(bundle)
    write_byte_hex(hex_path, bytes(bundle))
    manifest_path.write_text(
        "".join([
            "Ti60F225 local SPI Flash user image\n",
            f"flash offset: 0x{FLASH_USER_BASE:06X}\n",
            f"bundle bytes: {len(bundle)}\n",
            f"app offset: 0x{APP_OFFSET:04X}, bytes: {len(app)}, CRC32: 0x{crc32(app):08X}\n",
            f"asset offset: 0x{ASSET_OFFSET:04X}, bytes: {len(asset)}, payload CRC32: 0x{asset_crc:08X}\n",
        ]),
        encoding="ascii",
    )
    print(f"Wrote {bundle_path} ({len(bundle)} bytes)")
    print(f"Wrote {hex_path} (one byte per line, program at SPI address 0x{FLASH_USER_BASE:06X})")
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
