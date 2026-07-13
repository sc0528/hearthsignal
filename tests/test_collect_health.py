import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_health as collector


class CollectorTests(unittest.TestCase):
    thresholds = {"disk_warning_percent": 85, "disk_critical_percent": 92, "backup_warning_hours": 24, "backup_critical_hours": 48, "container_cpu_warning_percent": 75, "container_cpu_critical_percent": 90, "container_memory_warning_percent": 80, "container_memory_critical_percent": 92, "container_restart_warning": 3, "container_restart_critical": 10}

    def test_state_status_uses_thresholds(self):
        self.assertEqual(collector.state_status({"status": "auto", "type": "disk_usage", "value": 93}, self.thresholds), "critical")
        self.assertEqual(collector.state_status({"status": "auto", "type": "backup_freshness", "value": 30}, self.thresholds), "warning")

    def test_no_checks_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no live checks"):
            collector.collect({"checks": {"docker": {"enabled": False}, "disks": [], "backups": [], "http": []}})

    def test_history_is_capped_and_scored(self):
        from datetime import datetime, timezone
        checks = [{"service_id": "disk-0", "type": "disk_usage", "status": "auto", "value": 86}]
        history = collector.update_history(checks, self.thresholds, datetime.now(timezone.utc), [{}] * 35)
        self.assertEqual(len(history), 30)
        self.assertEqual(history[-1]["score"], 93)

    def test_capacity_forecast_uses_growth_rate(self):
        history = [
            {"timestamp": "2026-07-01T00:00:00+00:00", "measurements": {"disk-0:disk_usage": 80}},
            {"timestamp": "2026-07-06T00:00:00+00:00", "measurements": {"disk-0:disk_usage": 85}},
        ]
        checks = [{"service_id": "disk-0", "type": "disk_usage", "value": 85, "summary": "Storage used"}]
        forecasts = collector.add_capacity_forecasts(checks, history, 92)
        self.assertEqual(len(forecasts), 1)
        self.assertIn("7 days", checks[0]["forecast"])

    def test_discord_message_prioritizes_critical(self):
        services = {"disk-0": {"name": "Storage"}}
        checks = [{"service_id": "disk-0", "type": "disk_usage", "status": "auto", "value": 94, "summary": "Storage capacity used"}]
        message = collector.build_discord_message(services, checks, self.thresholds)
        self.assertIn("CRITICAL", message)
        self.assertIn("Storage", message)


if __name__ == "__main__":
    unittest.main()
