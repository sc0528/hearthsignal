import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import generate_digest as digest


class DigestTests(unittest.TestCase):
    thresholds = {
        "disk_warning_percent": 85,
        "disk_critical_percent": 92,
        "backup_warning_hours": 24,
        "backup_critical_hours": 48,
    }

    def test_threshold_classification(self):
        self.assertEqual(digest.classify({"type": "disk_usage", "status": "auto", "value": 94}, self.thresholds), "critical")
        self.assertEqual(digest.classify({"type": "backup_freshness", "status": "auto", "value": 31}, self.thresholds), "warning")
        self.assertEqual(digest.classify({"type": "disk_usage", "status": "auto", "value": 62}, self.thresholds), "ok")

    def test_value_units_are_readable(self):
        self.assertEqual(digest.display_value({"value": 31, "unit": "hours"}), "31 hours")
        self.assertEqual(digest.display_value({"value": 94, "unit": "%"}), "94%")

    def test_attention_item_has_recommended_action(self):
        check = {"type": "disk_usage"}
        self.assertIn("increase", digest.action(check).lower())

    def test_remote_and_parent_paths_are_rejected(self):
        with self.assertRaises(ValueError):
            digest.local_path("https://example.invalid/data.json", "test")
        with self.assertRaises(ValueError):
            digest.local_path("../private.json", "test")

    def test_html_content_is_escaped(self):
        config = {"report": {"title": "Digest", "owner_label": "<Owner>", "timezone_label": "Local"}}
        services = {"example": {"name": "<script>"}}
        checks = [{"service_id": "example", "type": "availability", "status": "ok", "resolved_status": "ok", "summary": "<script>", "value": True}]
        template = "{{PAGE_TITLE}}{{HEADER}}{{OVERVIEW}}{{TREND}}{{INCIDENTS}}{{CHANGES}}{{CATEGORIES}}{{HEALTHY}}{{SOURCE_NOTE}}"
        result = digest.render_html(config, services, checks, "now", template)
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_premium_report_sections_render(self):
        config = {"report": {"title": "Digest", "owner_label": "Lab", "timezone_label": "Local"}}
        services = {"example": {"name": "Example Service", "category": "service"}}
        checks = [{"service_id": "example", "type": "availability", "resolved_status": "ok", "summary": "Ready", "value": True}]
        template = Path(digest.ROOT / "templates" / "report.html").read_text(encoding="utf-8")
        result = digest.render_html(config, services, checks, "2026-07-12T08:00:00-04:00", template)
        for text in ("Health score", "Prioritized incidents", "Health trend", "Infrastructure overview", "Healthy systems"):
            self.assertIn(text, result)


if __name__ == "__main__":
    unittest.main()
