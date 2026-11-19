import subprocess
import unittest
from pathlib import Path


class BrowserAcceptanceSupportTests(unittest.TestCase):
    def test_browser_waiting_and_failure_evidence(self):
        result=subprocess.run(['node','--test',str(Path(__file__).with_suffix('.cjs'))],
                              capture_output=True,text=True,encoding='utf8',errors='replace')
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
