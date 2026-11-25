"""Regression for the UTF-8 log failure in Actions 45016703953."""
from pathlib import Path
import sys
import tempfile
import unittest
from scripts.check_r14_core import ROOT, run_logged


class LoggingTests(unittest.TestCase):
    def test_invalid_utf8_and_failure_are_preserved(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            p = Path(tmp)/'failed.txt'
            row = run_logged([sys.executable, '-c',
                              "import sys;sys.stdout.buffer.write(b'\\xfffailure');sys.exit(7)"], p)
            self.assertEqual(row['returncode'], 7)
            self.assertEqual(p.with_suffix('.txt.raw').read_bytes(), b'\xfffailure')
            self.assertIn('\\xfffailure', p.read_text())

    def test_success_keeps_exit_code(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            p = Path(tmp)/'ok.txt'
            row = run_logged([sys.executable, '-c', "print('OK')"], p)
            self.assertEqual(row['returncode'], 0)
            self.assertEqual(p.with_suffix('.txt.raw').read_bytes(), b'OK\n')
