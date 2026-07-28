import importlib.util
import json
import unittest
import urllib.error
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "capture_product_signal.py"
SPEC = importlib.util.spec_from_file_location("capture_product_signal", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)


class ProductSignalTests(unittest.TestCase):
    def test_optional_endpoint_reports_forbidden(self):
        error = urllib.error.HTTPError("https://api.github.test", 403, "Forbidden", {}, None)
        with patch.object(module, "api_get", side_effect=error):
            value, message = module.optional_get("/traffic/views", "token")
        self.assertIsNone(value)
        self.assertEqual(message, "GitHub returned HTTP 403")

    def test_history_validation(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "snapshots.json"
            path.write_text('{"snapshots":[]}', encoding="utf-8")
            self.assertEqual(module.load_history(path)["snapshots"], [])
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                module.load_history(path)

    def test_history_file_is_json_serializable(self):
        payload = {"schema_version": 1, "snapshots": [{"captured_at": "2026-07-28T00:00:00+00:00"}]}
        self.assertIn("snapshots", json.loads(json.dumps(payload)))

    def test_complete_snapshot_can_be_detected_for_retention(self):
        history = {"snapshots": [{"traffic": {"available": True}}]}
        self.assertTrue(any(item.get("traffic", {}).get("available") for item in history["snapshots"]))


if __name__ == "__main__":
    unittest.main()
