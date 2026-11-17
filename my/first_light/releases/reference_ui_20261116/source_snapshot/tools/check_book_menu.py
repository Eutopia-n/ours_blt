"""Compatibility entry point for the exact local-HTML firmware regression.

The reference checker now covers resource decoding, native menus, hardware
projection descriptors, navigation, real game states and pressure entry.
"""
from pathlib import Path
import subprocess,sys
raise SystemExit(subprocess.call([sys.executable,str(Path(__file__).with_name('check_reference_ui.py')),*sys.argv[1:]]))
