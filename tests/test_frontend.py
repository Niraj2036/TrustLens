import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from app import Application
from trustlens.agents import AGENTS

ROOT = Path(__file__).resolve().parents[1]


class FrontendRenderTests(unittest.TestCase):
    def test_views_and_untrusted_content(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is only needed for renderer verification, not running the app.")
        with tempfile.TemporaryDirectory() as directory:
            application = Application(Path(directory)/"frontend.db")
            fixture = {"config":{"agents":AGENTS},"overview":application.store.overview(),
                       "detail":application.store.detail("TL-1001"),"page":application.store.listing_page({})}
            checked = subprocess.run([node,str(ROOT/"tests/frontend_render.cjs")],
                input=json.dumps(fixture),text=True,encoding="utf-8",capture_output=True,cwd=ROOT,timeout=20)
            application.close()
            self.assertEqual(checked.returncode,0,checked.stdout+checked.stderr)
