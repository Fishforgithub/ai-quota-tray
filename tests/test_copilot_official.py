"""Copilot's official SDK quota result maps to the tray's display model."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from ai_quota_tray.model import OK
from ai_quota_tray.providers import copilot


NOW = datetime(2026, 9, 26, tzinfo=timezone.utc)


def snapshot(entitlement, used, remaining, reset="2026-10-01T00:00:00Z",
             unlimited=False):
    return SimpleNamespace(entitlement_requests=entitlement, used_requests=used,
                           remaining_percentage=remaining, reset_date=reset,
                           is_unlimited_entitlement=unlimited)


class CopilotOfficialTest(unittest.TestCase):
    def test_finite_unlimited_and_absent_quotas(self):
        result = SimpleNamespace(quota_snapshots={
            "premium_interactions": snapshot(300, 270, 10),
            "chat": snapshot(-1, 20, 100, unlimited=True),
            "completions": snapshot(0, 0, 0),
        })
        state = copilot.parse_quota(result, NOW)
        self.assertEqual(state.status, OK)
        self.assertEqual(state.source, "copilot-sdk")
        self.assertEqual([(w.label, w.used_pct) for w in state.windows], [("進階", 90)])
        self.assertEqual(state.windows[0].resets_at,
                         datetime(2026, 10, 1, tzinfo=timezone.utc))
        self.assertEqual(state.detail["unlimited"], ["Chat"])

    def test_missing_percent_uses_official_counts_and_monthly_reset_when_sdk_date_is_stale(self):
        result = SimpleNamespace(quota_snapshots={
            "chat": snapshot(200, 50, None, reset="2026-09-26T00:01:00Z"),
        })
        state = copilot.parse_quota(result, NOW)
        self.assertEqual(state.windows[0].used_pct, 25)
        self.assertEqual(state.windows[0].resets_at,
                         datetime(2026, 10, 1, tzinfo=timezone.utc))
        self.assertEqual(state.detail["estimated_resets"], ["Chat"])

    def test_monthly_reset_rolls_over_year(self):
        result = SimpleNamespace(quota_snapshots={
            "premium_interactions": snapshot(300, 50, 83, reset=None),
        })
        state = copilot.parse_quota(result, datetime(2026, 12, 31, tzinfo=timezone.utc))
        self.assertEqual(state.windows[0].resets_at,
                         datetime(2027, 1, 1, tzinfo=timezone.utc))

    def test_fetch_uses_sdk_even_when_legacy_flag_is_false(self):
        result = SimpleNamespace(quota_snapshots={"chat": snapshot(100, 25, 75)})
        with mock.patch.object(copilot, "_read_quota", new=mock.AsyncMock(return_value=result)) as read:
            state = copilot.fetch(use_token=False, now=NOW)
        read.assert_awaited_once_with()
        self.assertEqual(state.windows[0].used_pct, 25)

    def test_unrecognized_quota_is_not_reported_as_success(self):
        with self.assertRaises(ValueError):
            copilot.parse_quota(SimpleNamespace(quota_snapshots={}), NOW)


if __name__ == "__main__":
    unittest.main()
