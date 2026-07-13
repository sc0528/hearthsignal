import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_health as collector


class CollectorTests(unittest.TestCase):
    thresholds = {"disk_warning_percent": 85, "disk_critical_percent": 92, "backup_warning_hours": 24, "backup_critical_hours": 48}

    def test_state_status_uses_thresholds(self):
        self.assertEqual(collector.state_status({"status": "auto", "type": "disk_usage", "value": 93}, self.thresholds), "critical")
        self.assertEqual(collector.state_status({"status": "auto", "type": "backup_freshness", "value": 30}, self.thresholds), "warning")

    def test_no_checks_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no live checks"):
            collector.collect({"checks": {"docker": {"enabled": False}, "disks": [], "backups": [], "http": []}})


if __name__ == "__main__":
    unittest.main()
