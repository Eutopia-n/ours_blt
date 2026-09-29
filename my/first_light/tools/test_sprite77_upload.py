"""Exercise upload retry behavior without a physical COM port."""
from __future__ import annotations

from collections import deque
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import upload_sprite77 as uploader


class ScriptedBoard:
    def __init__(self, packet: bytes, first_fault: str):
        self.packet = packet
        self.first_fault = first_fault
        self.lines = deque([b"ASSET READY\r\n"])
        self.received = bytearray()
        self.attempts = 0

    def readline(self) -> bytes:
        if not self.lines:
            raise AssertionError("Uploader waited without a pending board response")
        return self.lines.popleft()

    def write(self, data: bytes) -> int:
        if self.attempts == 0 and self.first_fault == "interrupted":
            self.attempts += 1
            self.lines.extend([b"ASSET ERR\r\n", b"ASSET READY\r\n"])
            raise OSError("simulated cable interruption")
        self.received.extend(data)
        return len(data)

    def flush(self) -> None:
        if bytes(self.received) != self.packet:
            raise AssertionError("Uploader sent bytes in the wrong order")
        self.received.clear()
        self.attempts += 1
        if self.attempts == 1 and self.first_fault == "checksum":
            self.lines.extend([b"ASSET ERR\r\n", b"ASSET READY\r\n"])
        else:
            self.lines.append(b"ASSET OK\r\n")


class UploadTests(unittest.TestCase):
    def test_rejects_corrupted_compressed_pixels_before_sending(self) -> None:
        original_root = uploader.ROOT
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets").mkdir()
            (root / "software/build").mkdir(parents=True)
            for name in ("sprite77.raw", "sprite77.upload"):
                (root / "assets" / name).write_bytes((original_root / "assets" / name).read_bytes())
            (root / "software/build/animation.bin").write_bytes(
                (original_root / "software/build/animation.bin").read_bytes())
            wire = bytearray((root / "assets/sprite77.upload").read_bytes())
            wire[-2] ^= 1
            (root / "assets/sprite77.upload").write_bytes(wire)
            try:
                uploader.ROOT = root
                with self.assertRaises(ValueError):
                    uploader.packet()
            finally:
                uploader.ROOT = original_root

    def test_retries_after_board_rejects_checksum(self) -> None:
        packet = uploader.packet()
        board = ScriptedBoard(packet, "checksum")
        with redirect_stdout(StringIO()):
            uploader.transfer(board, packet, 2)
        self.assertEqual(board.attempts, 2)

    def test_retries_after_interrupted_write(self) -> None:
        packet = uploader.packet()
        board = ScriptedBoard(packet, "interrupted")
        with redirect_stdout(StringIO()):
            uploader.transfer(board, packet, 2)
        self.assertEqual(board.attempts, 2)

    def test_valid_cached_ddr_skips_transfer(self) -> None:
        board = ScriptedBoard(b"unused", "")
        board.lines.clear()
        board.lines.append(b"ASSET CACHED\r\n")
        with redirect_stdout(StringIO()):
            uploader.transfer(board, b"unused", 1)
        self.assertEqual(board.attempts, 0)


if __name__ == "__main__":
    unittest.main()
