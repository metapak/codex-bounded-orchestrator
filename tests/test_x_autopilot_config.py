from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from x_autopilot.config import load_config
from x_autopilot.domain import ConfigurationError

ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_defaults_are_luna_only_human_approved(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config(ROOT / "config/x-autopilot.example.toml")
        self.assertEqual(config.route("luna").model, "gpt-5.6-luna")
        self.assertFalse(config.routes["sol"].enabled)
        self.assertFalse(config.routes["astra"].enabled)
        self.assertFalse(config.publish_enabled)
        self.assertEqual(config.max_drafts, 4)
        self.assertEqual(config.verified_user_context, ())

    def test_cloud_requires_postgres_and_respects_port(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigurationError):
                load_config(ROOT / "config/x-autopilot.cloud.toml")
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test", "PORT": "8080"}, clear=True):
            config = load_config(ROOT / "config/x-autopilot.cloud.toml")
            self.assertTrue(config.cloud)
            self.assertEqual(config.port, 8080)

    def test_sol_cannot_be_enabled_or_runtime_swapped(self):
        original = (ROOT / "config/x-autopilot.example.toml").read_text()
        for altered in [original.replace('[models.sol]\nenabled = false', '[models.sol]\nenabled = true'),
                        original.replace('model = "gpt-5.6-luna"', 'model = "gpt-5.6-sol"')]:
            with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
                path = Path(temp) / "config.toml"
                path.write_text(altered)
                with self.assertRaises(ConfigurationError):
                    load_config(path)

    def test_invalid_env_switch_does_not_enable_publishing(self):
        with patch.dict(os.environ, {"X_PUBLISH_ENABLED": "yes"}, clear=True):
            with self.assertRaises(ConfigurationError):
                load_config(ROOT / "config/x-autopilot.example.toml")


if __name__ == "__main__":
    unittest.main()
