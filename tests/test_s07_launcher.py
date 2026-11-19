"""Launcher ownership and exit reporting, independent of a native OS test."""
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('portable_launcher', ROOT / 'run.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def exercise(self, platform):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        venv = Path(temp.name)
        python = venv / ('Scripts/python.exe' if platform == 'nt' else 'bin/python')
        python.parent.mkdir()
        python.touch()
        fake_os = SimpleNamespace(name=platform, chdir=Mock(), execv=Mock())
        with (patch.object(launcher, 'os', fake_os), patch.object(launcher.sys, 'argv',
                ['run.py', '--venv', str(venv), 'status']), patch.object(launcher.subprocess, 'run') as check,
                patch.object(launcher.subprocess, 'call', return_value=7) as call):
            result = launcher.main()
        return result, fake_os, check, call, python

    def test_windows_waits_for_child_and_returns_actual_failure(self):
        result, operating_system, check, call, python = self.exercise('nt')
        self.assertEqual(result, 7)
        operating_system.execv.assert_not_called()
        call.assert_called_once()
        self.assertEqual(call.call_args.args[0][0], str(python))
        self.assertEqual(call.call_args.args[0][-1], 'status')
        check.assert_called_once()

    def test_posix_keeps_process_replacement_for_direct_signals(self):
        result, operating_system, check, call, python = self.exercise('posix')
        operating_system.execv.assert_called_once()
        self.assertEqual(operating_system.execv.call_args.args[0], str(python))
        call.assert_not_called()
