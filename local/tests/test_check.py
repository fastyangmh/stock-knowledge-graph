"""Report/exit-code seam; subprocesses are the external execution boundary."""
import contextlib
import io
import json
import platform
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local import check


class CheckReportTests(unittest.TestCase):
    def test_report_identifies_source_environment_and_failed_command(self):
        commit = "a" * 40
        platform.platform()  # Resolve macOS platform's own subprocess before the boundary stub.

        def execute(command, **kwargs):
            outputs = {
                ("git", "rev-parse", "HEAD"): (0, commit + "\n"),
                ("git", "status", "--porcelain"): (0, " M local/check.py\n"),
                ("uv", "--version"): (0, "uv 0.6.13\n"),
                ("node", "--version"): (0, "v22.16.0\n"),
            }
            code, output = outputs.get(tuple(command), (7, "synthetic process failure\n"))
            return subprocess.CompletedProcess(command, code, output, "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("local/example.py", "index.html", "history.html", "event-study.html", "css/style.css"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("")
            (root / "uv.lock").write_bytes(b"abc")
            report_path = root / "report.json"
            with patch.object(check, "ROOT", root), patch("subprocess.run", side_effect=execute), contextlib.redirect_stdout(io.StringIO()):
                exit_code = check.main(["--report", str(report_path), "--runner", "unittest"])
            report = json.loads(report_path.read_text())

        self.assertEqual(exit_code, 1)
        self.assertFalse(report["passed"])
        self.assertEqual(report["checks"][0]["exit_code"], 7)
        self.assertEqual(report["repository"], {"commit": commit, "dirty": True})
        self.assertEqual(report["lock_sha256"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertEqual(report["runner"], "unittest")
        self.assertEqual(report["environment"]["os"], platform.system())
        self.assertEqual(report["environment"]["architecture"], platform.machine())
        self.assertEqual(report["environment"]["python_version"], platform.python_version())
        self.assertEqual(report["environment"]["uv_version"], "uv 0.6.13")
        self.assertEqual(report["environment"]["node_version"], "v22.16.0")
        self.assertTrue(all(probe["exit_code"] == 0 for probe in report["environment_probes"]))

    def test_missing_tools_remain_unknown_and_frontend_does_not_silently_pass(self):
        platform.platform()

        def execute(command, **kwargs):
            if command[0] in ("git", "uv", "node"):
                raise FileNotFoundError("tool unavailable")
            return subprocess.CompletedProcess(command, 0, "synthetic check passed\n", "")

        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            with patch("subprocess.run", side_effect=execute), patch("shutil.which", return_value=None), contextlib.redirect_stdout(io.StringIO()):
                exit_code = check.main(["--report", str(report_path), "--frontend"])
            report = json.loads(report_path.read_text())

        self.assertEqual(exit_code, 1)
        self.assertFalse(report["passed"])
        self.assertEqual(report["repository"], {"commit": None, "dirty": None})
        self.assertIsNone(report["environment"]["uv_version"])
        self.assertIsNone(report["environment"]["node_version"])
        self.assertTrue(all(probe["exit_code"] is None for probe in report["environment_probes"]))
        self.assertEqual(report["checks"][-1]["exit_code"], 1)
        self.assertIn("no silent skip", report["checks"][-1]["output"])
