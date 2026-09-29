"""Grok（只在個人版）：解析 billing 回傳、token 過期與續期、失敗處理。夾具是編出來的，不放真實資料。"""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from ai_quota_tray import net
from ai_quota_tray.model import AUTH_EXPIRED, OK
from ai_quota_tray.providers import grok

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
WEEKLY = {"config": {
    "currentPeriod": {"type": "USAGE_PERIOD_TYPE_WEEKLY", "start": "2026-09-26T00:00:00+00:00",
                      "end": "2026-10-03T00:00:00+00:00"},
    "creditUsagePercent": 92,
    "productUsage": [{"product": "GrokBuild", "usagePercent": 92}],
    "onDemandCap": {"val": 0}, "prepaidBalance": {"val": 0},
}}


class ParseTest(unittest.TestCase):
    def test_weekly_window_uses_whole_pool_percent_and_period_length(self):
        state = grok.parse_billing(WEEKLY, None, {"subscriptionTier": "TestTier"}, NOW)
        self.assertEqual(state.status, OK)
        (window,) = state.windows
        self.assertEqual(window.used_pct, 92)
        self.assertEqual(window.duration_s, 7 * 86400)
        self.assertEqual(window.label, "週")
        self.assertEqual(state.detail["subscription_tier"], "TestTier")
        self.assertEqual(state.detail["products"], [{"product": "GrokBuild", "usage_pct": 92.0}])

    def test_proto3_omitted_zero_is_zero_percent_not_missing(self):
        cfg = {"config": {"currentPeriod": {"type": grok.WEEKLY, "end": "2026-10-03T00:00:00+00:00"}}}
        (window,) = grok.parse_billing(cfg, None, None, NOW).windows
        self.assertEqual(window.used_pct, 0.0)

    def test_monthly_window_only_with_positive_limit(self):
        monthly = {"config": {"monthlyLimit": {"val": 200}, "used": {"val": 50},
                              "billingPeriodEnd": "2026-10-31T00:00:00+00:00"}}
        windows = grok.parse_billing(WEEKLY, monthly, None, NOW).windows
        self.assertEqual([w.label for w in windows], ["週", "月"])
        self.assertEqual(windows[1].used_pct, 25)
        empty = {"config": {"monthlyLimit": {"val": 0}, "used": {"val": 75}}}
        self.assertEqual(len(grok.parse_billing(WEEKLY, empty, None, NOW).windows), 1)

    def test_garbage_payload_gives_no_windows(self):
        self.assertEqual(grok.parse_billing({}, None, None, NOW).windows, [])


class FetchTest(unittest.TestCase):
    def write_auth(self, expires_at):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.auth_file = Path(tmp.name) / "auth.json"
        self.put_token("test-token", expires_at)
        return mock.patch.dict("os.environ", {"GROK_HOME": tmp.name})

    def put_token(self, key, expires_at):
        self.auth_file.write_text(json.dumps(
            {"entry": {"key": key, "expires_at": expires_at}}), encoding="utf-8")

    def test_expired_token_and_cli_cannot_renew_is_auth_expired(self):
        with self.write_auth("2020-01-01T00:00:00+00:00"), \
                mock.patch.object(grok, "refresh_via_cli", return_value=False) as refresh, \
                mock.patch.object(net, "get_json") as get_json:
            state = grok.fetch(now=NOW)
        self.assertEqual(state.status, AUTH_EXPIRED)
        refresh.assert_called_once()  # 過期先請官方 CLI 續期，續不了才回報
        get_json.assert_not_called()

    def test_expired_token_is_renewed_by_the_official_cli(self):
        seen = []

        def fake(url, headers):
            seen.append(headers["Authorization"])
            return WEEKLY

        with self.write_auth("2020-01-01T00:00:00+00:00"):
            def cli_renews():
                self.put_token("renewed-token", "2099-01-01T00:00:00+00:00")  # CLI 自己寫回 auth.json
                return True

            with mock.patch.object(grok, "refresh_via_cli", side_effect=cli_renews) as refresh, \
                    mock.patch.object(net, "get_json", fake):
                state = grok.fetch(now=NOW)
        self.assertEqual(state.status, OK)
        refresh.assert_called_once()
        self.assertEqual(set(seen), {"Bearer renewed-token"})

    def test_token_about_to_expire_is_renewed_too(self):
        soon = NOW.replace(minute=1).isoformat()  # 距離現在不到 2 分鐘
        with self.write_auth(soon), \
                mock.patch.object(grok, "refresh_via_cli", return_value=False) as refresh:
            self.assertEqual(grok.fetch(now=NOW).status, AUTH_EXPIRED)
        refresh.assert_called_once()

    def test_valid_token_never_runs_the_cli(self):
        with self.write_auth("2099-01-01T00:00:00+00:00"), \
                mock.patch.object(grok, "refresh_via_cli") as refresh, \
                mock.patch.object(net, "get_json", return_value=WEEKLY):
            self.assertEqual(grok.fetch(now=NOW).status, OK)
        refresh.assert_not_called()

    def test_refresh_without_cli_installed_is_false(self):
        with mock.patch.object(grok, "find_cli", return_value=None):
            self.assertFalse(grok.refresh_via_cli())

    def test_refresh_runs_models_without_a_console_window(self):
        with mock.patch.object(grok, "find_cli", return_value="grok"), \
                mock.patch.object(grok.subprocess, "run") as run:
            self.assertTrue(grok.refresh_via_cli())
        self.assertEqual(run.call_args.args[0], ["grok", "models"])
        self.assertEqual(run.call_args.kwargs["timeout"], grok.REFRESH_TIMEOUT_S)

    def test_missing_auth_file_is_reported_by_fetch_one(self):
        from ai_quota_tray.providers import fetch_one
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {"GROK_HOME": tmp}):
            state = fetch_one("grok", False, NOW)
        self.assertNotEqual(state.status, OK)  # 每家獨立失敗，不丟例外

    def test_fetch_sends_bearer_and_survives_optional_failures(self):
        def fake(url, headers):
            self.assertEqual(headers["Authorization"], "Bearer test-token")
            if "format=credits" in url:
                return WEEKLY
            raise net.HttpError("HTTP 500")

        with self.write_auth("2099-01-01T00:00:00+00:00"), mock.patch.object(net, "get_json", fake):
            state = grok.fetch(now=NOW)
        self.assertEqual(state.status, OK)
        self.assertEqual(len(state.windows), 1)
        self.assertIn("monthly", state.detail["optional_errors"])


if __name__ == "__main__":
    unittest.main()
