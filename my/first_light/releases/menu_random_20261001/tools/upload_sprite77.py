"""Upload the DDR animation program and 77 RGB565 frames after cold boot.

Example: python tools/upload_sprite77.py --port COM5
Requires: python -m pip install pyserial
"""
from __future__ import annotations

from pathlib import Path
import argparse
import struct
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parents[1]


def available_ports() -> list[tuple[str, str]]:
    """List COM ports even when pyserial has not been installed yet."""
    try:
        from serial.tools import list_ports
        return sorted((entry.device, entry.description) for entry in list_ports.comports())
    except ImportError:
        pass
    if sys.platform != "win32":
        return []
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DEVICEMAP\SERIALCOMM") as key:
            result = []
            index = 0
            while True:
                try:
                    device, port, _ = winreg.EnumValue(key, index)
                except OSError:
                    break
                result.append((port, "Bluetooth virtual port" if "BthModem" in device
                               else device))
                index += 1
            return sorted(result)
    except OSError:
        return []


def show_ports() -> dict[str, str]:
    ports = dict(available_ports())
    if ports:
        print("Detected serial ports:", flush=True)
        for port, description in ports.items():
            print(f"  {port}: {description}", flush=True)
    else:
        print("No serial port detected. Connect the board Type-C USB cable and check its FT4232 driver.", flush=True)
    return ports


def packet() -> bytes:
    app = (ROOT / "software/build/animation.bin").read_bytes()
    asset = (ROOT / "assets/sprite77.upload").read_bytes()
    raw = (ROOT / "assets/sprite77.raw").read_bytes()
    if not 0 < len(app) <= 65536:
        raise ValueError("DDR program length is outside 1..65536")
    if len(raw) > 1 << 20 or len(raw) < 632:
        raise ValueError("Asset does not fit the dedicated DDR pool")
    magic, total, packed, checksum = struct.unpack_from("<4sIII", asset)
    if magic != b"S77U" or total != len(raw) or packed != len(asset) - 632:
        raise ValueError("Generated asset header or length mismatch")
    if checksum != zlib.crc32(raw[16:]) or asset[16:632] != raw[16:632]:
        raise ValueError("Generated asset checksum or frame table mismatch")
    decoded = bytearray()
    cursor = 632
    while cursor < len(asset):
        tag = asset[cursor]
        cursor += 1
        count = (tag & 127) + 1
        if tag & 128:
            decoded.extend(b"\x1f\xf8" * count)
        else:
            end = cursor + 2 * count
            if end > len(asset):
                raise ValueError("Generated RLE literal is truncated")
            decoded.extend(asset[cursor:end])
            cursor = end
        if len(decoded) > len(raw) - 632:
            raise ValueError("Generated RLE expands beyond the asset")
    if decoded != raw[632:]:
        raise ValueError("Generated RLE pixels do not match the validated DDR asset")
    return b"S77B" + struct.pack("<II", len(app), zlib.crc32(app)) + app + asset


def wait_prompt(port, deadline: float) -> str:
    last_notice = time.monotonic()
    while time.monotonic() < deadline:
        line = port.readline().decode("ascii", "replace").strip()
        if line:
            print(line, flush=True)
        if line == "ASSET READY" or line == "ASSET CACHED":
            return line
        if time.monotonic() - last_notice >= 5:
            print("Still waiting for ASSET READY from the board...", flush=True)
            last_notice = time.monotonic()
    raise TimeoutError("No ASSET READY: check the board's USB-UART COM port, loaded bitstream, "
                       "DDR calibration and 115200 8N1")


def transfer(port, data: bytes, retries: int, wait_timeout: float = 45) -> None:
    for attempt in range(1, retries + 1):
        print("Waiting for ASSET READY or ASSET CACHED...", flush=True)
        status = wait_prompt(port, time.monotonic() + wait_timeout)
        if status == "ASSET CACHED":
            print("Valid DDR animation was retained across reset; upload is unnecessary.")
            return
        print(f"Sending packet {attempt}/{retries}...", flush=True)
        start = time.monotonic()
        try:
            for offset in range(0, len(data), 4096):
                block = data[offset:offset + 4096]
                if port.write(block) != len(block):
                    raise OSError("UART wrote only part of a packet block")
                if offset // 65536 != (offset + len(block)) // 65536:
                    print(f"  {offset + len(block)}/{len(data)} bytes sent", flush=True)
            port.flush()
        except OSError as exc:
            # The boot ROM times out a truncated packet and advertises READY
            # again. Wait for that response before retrying from byte zero.
            print(f"UART transfer interrupted: {exc}")
            continue
        print(f"Transfer finished in {time.monotonic() - start:.1f}s; verifying board response")
        limit = time.monotonic() + 30
        while time.monotonic() < limit:
            line = port.readline().decode("ascii", "replace").strip()
            if line:
                print(line)
            if line == "ASSET OK":
                print("Animation is running. KEY1 toggles color keying.")
                return
            if line == "ASSET ERR":
                break
    raise SystemExit("Upload failed after all retries; inspect board UART and power")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Board UART COM port, for example COM5")
    parser.add_argument("--list-ports", action="store_true", help="Show COM ports without uploading")
    parser.add_argument("--wait-timeout", type=float, default=45,
                        help="Seconds to wait for ASSET READY (default: 45)")
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    ports = show_ports()
    if args.list_ports:
        return
    if not args.port:
        parser.error("select the board UART with --port COMx; VS Code's Run Python File "
                     "button does not pass command-line arguments")
    if args.retries < 1:
        raise SystemExit("--retries must be at least one")
    if args.wait_timeout <= 0:
        raise SystemExit("--wait-timeout must be positive")
    description = ports.get(args.port.upper(), "")
    if "bluetooth" in description.lower():
        print(f"Warning: {args.port} is a Bluetooth virtual port, not the board's USB-UART port.", flush=True)
    try:
        import serial
    except ImportError as exc:
        raise SystemExit("Install pyserial first: python -m pip install pyserial") from exc
    print("Validating animation packet...", flush=True)
    data = packet()
    print(f"Prepared {len(data)} UART bytes; opening {args.port} at 115200 8N1", flush=True)
    with serial.Serial(args.port, 115200, timeout=1, write_timeout=10) as port:
        transfer(port, data, args.retries, args.wait_timeout)


if __name__ == "__main__":
    try:
        main()
    except (OSError, TimeoutError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
