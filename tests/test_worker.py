from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import worker


class ActiveBlocklistTests(unittest.TestCase):
    def test_removing_domain_does_not_shrink_active_snapshot(self) -> None:
        state = {"active_blocklist": ["reddit.com", "youtube.com"]}

        effective, changed = worker._locked_blocklist(state, ["reddit.com"])

        self.assertEqual(effective, ["reddit.com", "youtube.com"])
        self.assertFalse(changed)

    def test_new_domain_is_added_to_active_snapshot(self) -> None:
        state = {"active_blocklist": ["reddit.com"]}

        effective, changed = worker._locked_blocklist(
            state, ["reddit.com", "news.ycombinator.com"]
        )

        self.assertEqual(effective, ["reddit.com", "news.ycombinator.com"])
        self.assertTrue(changed)
        self.assertEqual(state["active_blocklist"], effective)

    def test_override_does_not_end_underlying_block(self) -> None:
        now = datetime.now()
        state = {
            "mode": "block_until",
            "end_time": (now + timedelta(hours=1)).isoformat(),
            "override_until": (now + timedelta(minutes=5)).isoformat(),
        }

        self.assertTrue(worker._underlying_block_active(state, now))
        self.assertFalse(worker._desired_block(state, now))


if __name__ == "__main__":
    unittest.main()
