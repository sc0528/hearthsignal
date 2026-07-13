import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_hearthsignal as runner


class ContainerRunnerTests(unittest.TestCase):
    def test_interval_rejects_values_below_five_minutes(self):
        with self.assertRaisesRegex(ValueError, "at least 300"):
            runner.interval_seconds("299")

    def test_interval_rejects_non_numeric_values(self):
        with self.assertRaisesRegex(ValueError, "whole number"):
            runner.interval_seconds("daily")

    def test_docker_mode_enables_only_docker_by_default(self):
        config = runner.built_in_docker_config()
        self.assertTrue(config["checks"]["docker"]["enabled"])
        self.assertEqual(config["checks"]["disks"], [])
        self.assertEqual(config["outputs"]["html"], "reports/latest-digest.html")

    def test_demo_command_has_explicit_safe_mode(self):
        command = runner.command_for("demo")
        self.assertIn("--dry-run", command)
        self.assertNotIn("--live", command)

    def test_unknown_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "demo, docker, or live"):
            runner.command_for("automatic")

    def test_error_page_preserves_last_good_report(self):
        with tempfile.TemporaryDirectory() as directory:
            original_reports = runner.REPORTS
            try:
                runner.REPORTS = Path(directory)
                report = runner.REPORTS / "latest-digest.html"
                report.write_text("last good report", encoding="utf-8")
                runner.error_page("new failure")
                self.assertEqual(report.read_text(encoding="utf-8"), "last good report")
            finally:
                runner.REPORTS = original_reports

    def test_live_config_is_copied_and_outputs_are_container_managed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "hearthsignal.json"
            source.write_text(
                json.dumps(
                    {
                        "report": {},
                        "outputs": {"html": "somewhere/private.html"},
                        "checks": {"docker": {"enabled": False}},
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"HEARTHSIGNAL_CONFIG": str(source)}):
                path = runner.prepare_live_config("live")
            copied = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(copied["outputs"]["html"], "reports/latest-digest.html")


if __name__ == "__main__":
    unittest.main()
