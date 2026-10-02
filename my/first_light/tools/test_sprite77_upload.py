"""Exercise upload retry behavior without a physical COM port."""
from __future__ import annotations

from collections import deque
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import upload_sprite77 as uploader


class ScriptedBoard:
    def __init__(self, packet: bytes, first_fault: str):
        self.packet = packet
        self.first_fault = first_fault
        self.lines = deque([b"ASSET READY\r\n"])
        self.received = bytearray()
        self.attempts = 0
        self.closed = False
        self.cleanup = []
        self.ready = False

    def readline(self) -> bytes:
        if self.closed:
            raise AssertionError("Uploader reused a closed COM handle")
        if self.first_fault == "read":
            raise OSError("ClearCommError failed (PermissionError(13, 'access denied'))")
        if not self.lines:
            raise AssertionError("Uploader waited without a pending board response")
        line = self.lines.popleft()
        if line == b"ASSET READY\r\n":
            self.ready = True
        return line

    def write(self, data: bytes) -> int:
        if self.closed or not self.ready:
            raise AssertionError("Uploader wrote without a new READY")
        if self.attempts == 0 and self.first_fault == "interrupted":
            self.attempts += 1
            raise OSError("simulated cable interruption")
        if self.first_fault == "partial":
            return len(data) - 1
        self.received.extend(data)
        return len(data)

    def flush(self) -> None:
        if self.first_fault == "flush":
            raise OSError("simulated flush failure")
        if bytes(self.received) != self.packet:
            raise AssertionError("Uploader sent bytes in the wrong order")
        self.received.clear()
        self.attempts += 1
        if self.attempts == 1 and self.first_fault == "checksum":
            self.lines.extend([b"ASSET ERR\r\n", b"ASSET READY\r\n"])
        else:
            self.lines.append(b"ASSET OK\r\n")

    def cancel_write(self) -> None:
        self.cleanup.append("cancel")
        if self.first_fault == "read":
            raise OSError("disconnected during cancel")

    def reset_output_buffer(self) -> None:
        self.cleanup.append("purge")
        if self.first_fault == "read":
            raise OSError("disconnected during purge")

    def close(self) -> None:
        self.cleanup.append("close")
        self.closed = True


class UploadTests(unittest.TestCase):
    def run_retry(self, fault: str) -> list[ScriptedBoard]:
        packet = uploader.packet()
        boards = []

        def open_port():
            if boards:
                self.assertTrue(boards[-1].closed)
            board = ScriptedBoard(packet, fault if not boards else "")
            boards.append(board)
            return board

        with redirect_stdout(StringIO()), patch.object(uploader.time, "sleep") as sleep:
            uploader.transfer(open_port, packet, 2)
        self.assertEqual(len(boards), 2)
        self.assertTrue(all(board.closed for board in boards))
        self.assertEqual(boards[-1].attempts, 1)
        sleep.assert_called_once_with(3)
        return boards

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
        self.run_retry("checksum")

    def test_retries_after_interrupted_write(self) -> None:
        boards = self.run_retry("interrupted")
        self.assertEqual(boards[0].cleanup, ["cancel", "purge", "close"])

    def test_read_access_denied_and_cleanup_errors_still_reopen(self) -> None:
        boards = self.run_retry("read")
        self.assertEqual(boards[0].cleanup, ["cancel", "purge", "close"])

    def test_flush_failure_reopens(self) -> None:
        self.run_retry("flush")

    def test_partial_write_restarts_packet(self) -> None:
        self.run_retry("partial")

    def test_open_failure_retries_and_reports_last_error(self) -> None:
        with redirect_stdout(StringIO()), patch.object(uploader.time, "sleep") as sleep:
            with self.assertRaisesRegex(SystemExit, "after 2 attempts: access denied"):
                uploader.transfer(lambda: (_ for _ in ()).throw(OSError("access denied")), b"", 2)
        sleep.assert_called_once_with(3)

    def test_recovers_after_initial_open_failure(self) -> None:
        packet = uploader.packet()
        board = ScriptedBoard(packet, "")
        opener = Mock(side_effect=[OSError("device absent"), board])
        with redirect_stdout(StringIO()), patch.object(uploader.time, "sleep"):
            uploader.transfer(opener, packet, 2)
        self.assertEqual(opener.call_count, 2)
        self.assertTrue(board.closed)

    def test_valid_cached_ddr_skips_transfer(self) -> None:
        board = ScriptedBoard(b"unused", "")
        board.lines.clear()
        board.lines.append(b"ASSET CACHED\r\n")
        with redirect_stdout(StringIO()):
            uploader.transfer(lambda: board, b"unused", 1)
        self.assertEqual(board.attempts, 0)
        self.assertTrue(board.closed)


if __name__ == "__main__":
    unittest.main()
