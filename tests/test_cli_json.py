import json
import unittest
from pathlib import Path

from rice_manager.cli import _plan_json
from rice_manager.planner import SwitchPlan, SwitchPlanItem


class PlanJsonTests(unittest.TestCase):
    def test_exports_read_only_plan_as_json_data(self):
        plan = SwitchPlan(
            profile_id="test-rice",
            profile_name="Test Rice",
            items=(
                SwitchPlanItem(
                    "hyprland", "Hyprland", Path("/home/test/.config/hypr"),
                    "ready", "Destination exists.",
                ),
                SwitchPlanItem(
                    "system-shell", "System shell", Path("/etc/xdg/example"),
                    "skipped", "System-scoped or read-only component.",
                ),
            ),
        )

        result = _plan_json(plan)
        encoded = json.dumps(result)
        decoded = json.loads(encoded)

        self.assertEqual(decoded["profile"]["id"], "test-rice")
        self.assertEqual(decoded["summary"], {"ready": 1, "skipped": 1, "blocked": 0})
        self.assertTrue(decoded["dry_run"])
        self.assertFalse(decoded["blocked"])
        self.assertEqual(decoded["items"][0]["status"], "ready")


if __name__ == "__main__":
    unittest.main()
