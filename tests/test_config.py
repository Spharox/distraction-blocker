from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import config


class InstallLayoutTests(unittest.TestCase):
    def test_privileged_state_is_separate_from_user_config(self) -> None:
        self.assertEqual(config.BLOCKLIST_PATH.parent, config.CONFIG_DIR)
        self.assertEqual(config.SCHEDULE_PATH.parent, config.CONFIG_DIR)
        self.assertEqual(config.COMMAND_PATH.parent, config.CONFIG_DIR)
        self.assertEqual(config.STATE_PATH.parent, config.STATE_DIR)
        self.assertEqual(config.LOG_PATH.parent, config.STATE_DIR)
        self.assertNotEqual(config.CONFIG_DIR, config.STATE_DIR)

    def test_product_uses_transparent_names(self) -> None:
        self.assertEqual(config.INSTALL_DIR.name, "DistractionBlocker")
        self.assertEqual(config.TASK_NAME, "DistractionBlockerWorker")

    def test_installer_stops_worker_before_copying_executable(self) -> None:
        installer = (
            Path(__file__).resolve().parents[1] / "installer" / "install.ps1"
        ).read_text(encoding="utf-8")

        stop_position = installer.index("Stop-ScheduledTask")
        copy_position = installer.index("Copy-ReleaseFile `")
        self.assertLess(stop_position, copy_position)
        self.assertIn("because it is still running", installer)


if __name__ == "__main__":
    unittest.main()
