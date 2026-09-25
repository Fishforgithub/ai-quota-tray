"""Copilot's official SDK quota result maps to the tray's display model."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

import asyncio
import threading

from ai_quota_tray.model import AUTH_EXPIRED, ERROR, OK, PREPARING
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
        with mock.patch.object(copilot, "runtime_ready", return_value=True),                 mock.patch.object(copilot, "_read_quota", new=mock.AsyncMock(return_value=result)) as read:
            state = copilot.fetch(use_token=False, now=NOW)
        read.assert_awaited_once_with()
        self.assertEqual(state.windows[0].used_pct, 25)

    def test_unrecognized_quota_is_not_reported_as_success(self):
        with self.assertRaises(ValueError):
            copilot.parse_quota(SimpleNamespace(quota_snapshots={}), NOW)


class CopilotRuntimeTest(unittest.TestCase):
    def setUp(self):
        ready = mock.patch.object(copilot, "runtime_ready", return_value=True)
        ready.start()
        self.addCleanup(ready.stop)

    def test_hung_sdk_times_out_instead_of_blocking_forever(self):
        async def hang():
            await asyncio.sleep(3600)
        with mock.patch.object(copilot, "FETCH_TIMEOUT_S", 0.05),                 mock.patch.object(copilot, "_read_quota", new=hang):
            with self.assertRaisesRegex(TimeoutError, "沒有回應"):
                copilot.fetch(now=NOW)

    def test_not_signed_in_becomes_auth_expired(self):
        err = RuntimeError("Not authenticated. Please run copilot login")
        with mock.patch.object(copilot, "_read_quota", new=mock.AsyncMock(side_effect=err)):
            state = copilot.fetch(now=NOW)
        self.assertEqual(state.status, AUTH_EXPIRED)

    def test_other_errors_still_raise(self):
        with mock.patch.object(copilot, "_read_quota",
                               new=mock.AsyncMock(side_effect=RuntimeError("socket closed"))):
            with self.assertRaises(RuntimeError):
                copilot.fetch(now=NOW)


class CopilotPrepareTest(unittest.TestCase):
    def tearDown(self):
        if copilot._prep_thread is not None:
            copilot._prep_thread.join(timeout=5)
        copilot._prep_thread, copilot._prep_error = None, None

    def test_fetch_while_downloading_reports_preparing_without_starting_sdk(self):
        gate = threading.Event()
        with mock.patch.object(copilot, "runtime_ready", return_value=False),                 mock.patch.object(copilot, "_runtime_pair",
                                  return_value=(mock.Mock(ensure_runtime_wrapper=gate.wait), None, "")),                 mock.patch.object(copilot, "_read_quota") as read:
            first = copilot.fetch(now=NOW)
            second = copilot.fetch(now=NOW)
            gate.set()
        self.assertEqual((first.status, second.status), (PREPARING, PREPARING))
        read.assert_not_called()

    def test_start_prepare_runs_once_and_calls_back(self):
        gate, done = threading.Event(), threading.Event()
        downloader = mock.Mock(ensure_runtime_wrapper=mock.Mock(side_effect=lambda: gate.wait()))
        with mock.patch.object(copilot, "runtime_ready", return_value=False),                 mock.patch.object(copilot, "_runtime_pair", return_value=(downloader, None, "")):
            self.assertTrue(copilot.start_prepare(done.set))
            self.assertTrue(copilot.start_prepare(done.set))  # 已經在下載，不會再開一條
            gate.set()
            self.assertTrue(done.wait(5))
        downloader.ensure_runtime_wrapper.assert_called_once()

    def test_already_ready_does_nothing(self):
        with mock.patch.object(copilot, "runtime_ready", return_value=True),                 mock.patch.object(copilot, "_runtime_pair") as pair:
            self.assertFalse(copilot.start_prepare())
        pair.assert_not_called()

    def test_failed_download_is_reported_then_retried(self):
        broken = mock.Mock(ensure_runtime_wrapper=mock.Mock(side_effect=OSError("network down")))
        with mock.patch.object(copilot, "runtime_ready", return_value=False),                 mock.patch.object(copilot, "_runtime_pair", return_value=(broken, None, "")):
            copilot.start_prepare()
            copilot._prep_thread.join(timeout=5)
            state = copilot.fetch(now=NOW)
            copilot._prep_thread.join(timeout=5)
        self.assertEqual(state.status, ERROR)
        self.assertIn("network down", state.error)
        self.assertEqual(broken.ensure_runtime_wrapper.call_count, 2)  # 那次 fetch 順便重試


if __name__ == "__main__":
    unittest.main()
