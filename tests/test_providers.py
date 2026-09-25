"""P1 解析邏輯測試。夾具取自 2026-09-25 實測回傳（Claude cache、Codex rollout / wham）
與 quse 記錄的 Grok 格式。只測純函式，不打網路。

    python -m unittest discover -s tests
"""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from ai_quota_tray.model import (AUTH_EXPIRED, DISABLED, ERROR, OK, STALE,
                                 label_for_duration, mask_secrets, parse_time, to_float)
from ai_quota_tray.providers import claude, codex, fetch_one, grok

NOW = datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc)
EPOCH_NOW = int(NOW.timestamp())


class ModelTest(unittest.TestCase):
    def test_label_for_duration(self):
        self.assertEqual(label_for_duration(18000), "5h")
        self.assertEqual(label_for_duration(604800), "週")
        self.assertEqual(label_for_duration(30 * 86400), "月")
        self.assertEqual(label_for_duration(2 * 3600), "2h")
        self.assertEqual(label_for_duration(3 * 86400), "3d")
        self.assertEqual(label_for_duration(None), "?")

    def test_parse_time_accepts_seconds_ms_iso(self):
        expected = datetime(2026, 9, 25, 9, 40, tzinfo=timezone.utc)
        self.assertEqual(parse_time(1790329200), expected)
        self.assertEqual(parse_time(1790329200000), expected)
        self.assertEqual(parse_time("1790329200"), expected)
        self.assertEqual(parse_time("2026-09-25T09:40:00Z"), expected)
        self.assertEqual(parse_time("2026-09-25T09:40:00.000000000Z"), expected)  # 奈秒
        self.assertIsNone(parse_time("garbage"))
        self.assertIsNone(parse_time(True))

    def test_to_float_unwraps_proto_val(self):
        self.assertEqual(to_float({"val": 12}), 12.0)
        self.assertEqual(to_float("3.5"), 3.5)
        self.assertIsNone(to_float(False))
        self.assertIsNone(to_float({}))

    def test_mask_secrets(self):
        masked = mask_secrets({
            "access_token": "abcdefghijklmnop", "key": "short", "email": "someone@example.com",
            "account_id": "deadbeef-0000-0000-0000-000000000000", "limit_id": "codex",
            "nested": [{"id_token": "eyJhbGciOi.eyJzdWIi.sig"}], "note": "eyJhbGciOi.eyJzdWIi.x",
            "used_percent": 5,
            # 2026-09-25 Grok /user 實際回傳裡漏遮過的欄位
            "firstName": "SOMEONE", "xUserId": "1234567890123", "teamName": None,
            "profileImageAssetId": "users/00000000-1111-2222-3333-444444444444/p.webp",
            "path": "users/00000000-1111-2222-3333-444444444444/p.webp",
            "subscriptionTier": "GrokPro",
        })
        self.assertEqual(masked["access_token"], "***(16)")
        self.assertEqual(masked["key"], "***")
        self.assertNotIn("example", masked["email"])
        self.assertNotIn("beef", masked["account_id"])
        self.assertEqual(masked["limit_id"], "***")  # 寧可多遮
        self.assertEqual(masked["firstName"], "***")
        self.assertNotIn("1234567", masked["xUserId"])
        self.assertIsNone(masked["teamName"])
        self.assertNotIn("00000000-1111", masked["profileImageAssetId"])
        self.assertEqual(masked["path"], "users/<uuid>/p.webp")
        self.assertEqual(masked["subscriptionTier"], "GrokPro")
        self.assertNotIn("sig", masked["nested"][0]["id_token"])
        self.assertNotIn("sig", masked["note"])
        self.assertEqual(masked["used_percent"], 5)


class ClaudeTest(unittest.TestCase):
    def cache(self, fetched_at, five_reset, week_reset):
        return {"fetchedAt": fetched_at, "rate_limits": {
            "five_hour": {"used_percentage": 9, "resets_at": five_reset},
            "seven_day": {"used_percentage": 7, "resets_at": week_reset}}}

    def test_fresh_cache(self):
        data = self.cache(EPOCH_NOW * 1000 - 60_000, EPOCH_NOW + 3600, EPOCH_NOW + 86400)
        state = claude.parse_cache(data, NOW)
        self.assertEqual(state.status, OK)
        self.assertEqual([w.label for w in state.windows], ["5h", "週"])
        self.assertEqual(state.windows[0].remaining_pct, 91.0)

    def test_old_cache_is_stale_and_passed_window_rolls_over(self):
        data = self.cache((EPOCH_NOW - 7200) * 1000, EPOCH_NOW - 60, EPOCH_NOW + 86400)
        state = claude.parse_cache(data, NOW)
        self.assertEqual(state.status, STALE)
        self.assertEqual(state.windows[0].used_pct, 0.0)
        self.assertIsNone(state.windows[0].resets_at)
        self.assertEqual(state.windows[1].used_pct, 7.0)
        self.assertEqual(state.detail["rolled_over"], ["5h"])

    def test_oauth_usage_with_model_specific_and_unknown_keys(self):
        state = claude.parse_oauth_usage({
            "five_hour": {"utilization": 42.0, "resets_at": "2026-09-25T09:00:00Z"},
            "seven_day": {"utilization": 10.0, "resets_at": "2026-09-30T17:00:00Z"},
            "seven_day_opus": {"utilization": 3.0, "resets_at": "2026-09-30T17:00:00Z"},
            "seven_day_sonnet": None,
            "extra_usage": {"is_enabled": False},
        }, NOW)
        self.assertEqual([w.label for w in state.windows], ["5h", "週", "週·opus"])
        self.assertIn("extra_usage", state.detail["unknown_keys"])

    def test_cache_without_rate_limits_raises(self):
        with self.assertRaises(ValueError):
            claude.parse_cache({"fetchedAt": 0}, NOW)


def codex_event(ts, primary, secondary):
    return {"timestamp": ts, "type": "event_msg", "payload": {"type": "token_count", "rate_limits": {
        "limit_id": "codex", "primary": primary, "secondary": secondary, "plan_type": "team"}}}


class CodexTest(unittest.TestCase):
    def test_event_labels_follow_window_minutes(self):
        event = codex_event("2026-09-25T05:59:00Z",
                            {"used_percent": 10.0, "window_minutes": 300, "resets_at": EPOCH_NOW + 600},
                            {"used_percent": 1.0, "window_minutes": 10080, "resets_at": EPOCH_NOW + 9999})
        state = codex.parse_event(event, NOW)
        self.assertEqual(state.status, OK)
        self.assertEqual([(w.label, w.used_pct) for w in state.windows], [("5h", 10.0), ("週", 1.0)])
        self.assertEqual(state.detail["plan_type"], "team")

    def test_weekly_only_primary_and_null_secondary(self):
        # 2026 年中 Codex 拿掉 5h 時的形狀：primary 裝週視窗、secondary 為 null
        event = codex_event("2026-09-25T05:59:00Z",
                            {"used_percent": 30, "window_minutes": 10080, "resets_at": EPOCH_NOW + 600},
                            None)
        state = codex.parse_event(event, NOW)
        self.assertEqual([w.label for w in state.windows], ["週"])

    def test_legacy_resets_in_seconds(self):
        event = codex_event("2026-09-25T05:59:00Z",
                            {"used_percent": 1, "window_minutes": 300, "resets_in_seconds": 120}, None)
        state = codex.parse_event(event, NOW)
        self.assertEqual(state.windows[0].resets_at, datetime(2026, 9, 25, 6, 1, tzinfo=timezone.utc))

    def test_api_weekly_in_primary_window(self):
        state = codex.parse_api({"plan_type": "plus", "rate_limit": {
            "primary_window": {"used_percent": 20, "limit_window_seconds": 604800,
                               "reset_after_seconds": 3600},
            "secondary_window": None}}, NOW)
        self.assertEqual([w.label for w in state.windows], ["週"])
        self.assertEqual(state.windows[0].resets_at, NOW + timedelta(hours=1))

    def test_rollout_discovery_skips_files_without_rate_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            day = Path(tmp) / "sessions" / "2026" / "09" / "25"
            day.mkdir(parents=True)
            good = codex_event("2026-09-25T05:59:00Z",
                               {"used_percent": 5, "window_minutes": 300, "resets_at": EPOCH_NOW + 60},
                               None)
            older = day / "rollout-a.jsonl"
            older.write_text(json.dumps(good) + "\n", encoding="utf-8")
            newer = day / "rollout-b.jsonl"
            no_limits = {"type": "event_msg", "payload": {"type": "token_count", "rate_limits": None}}
            newer.write_text(json.dumps(no_limits) + "\n{\"truncated", encoding="utf-8")
            os.utime(older, (1, 1))
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}):
                state = codex.fetch(now=NOW)
        self.assertEqual(state.detail["file"], "rollout-a.jsonl")
        self.assertEqual(state.windows[0].used_pct, 5.0)


class GrokTest(unittest.TestCase):
    def test_weekly_pool_uses_credit_usage_percent(self):
        credits = {"config": {
            "currentPeriod": {"type": "USAGE_PERIOD_TYPE_WEEKLY",
                              "start": "2026-09-21T00:00:00Z", "end": "2026-09-28T00:00:00Z"},
            "creditUsagePercent": 37.5,
            "productUsage": [{"product": "GrokBuild", "usagePercent": 20}, {"product": "Chat"}],
            "onDemandCap": {"val": 100}}}
        state = grok.parse_billing(credits, None, {"subscriptionTier": "SuperGrok"}, NOW)
        self.assertEqual(len(state.windows), 1)
        week = state.windows[0]
        self.assertEqual((week.label, week.used_pct), ("週", 37.5))
        self.assertEqual(week.resets_at, datetime(2026, 9, 28, tzinfo=timezone.utc))
        self.assertEqual(state.detail["products"],
                         [{"product": "GrokBuild", "usage_pct": 20.0}, {"product": "Chat", "usage_pct": 0.0}])
        self.assertEqual(state.detail["subscription_tier"], "SuperGrok")

    def test_proto3_omitted_percent_means_zero(self):
        credits = {"currentPeriod": {"type": "USAGE_PERIOD_TYPE_WEEKLY"},
                   "billingPeriodEnd": "2026-09-28T00:00:00Z"}
        state = grok.parse_billing(credits, None, None, NOW)
        week = state.windows[0]
        self.assertEqual((week.label, week.used_pct, week.duration_s), ("週", 0.0, 604800))
        self.assertEqual(week.resets_at, datetime(2026, 9, 28, tzinfo=timezone.utc))

    def test_on_demand_fallback_and_monthly_window(self):
        credits = {"onDemandUsed": {"val": 25}, "onDemandCap": {"val": 50}}
        monthly = {"monthlyLimit": {"val": 200}, "used": {"val": 50},
                   "billingPeriodEnd": "2026-10-01T00:00:00Z"}
        state = grok.parse_billing(credits, monthly, None, NOW)
        self.assertEqual([(w.label, w.used_pct) for w in state.windows], [("?", 50.0), ("月", 25.0)])

    def test_no_weekly_period_and_no_monthly_limit(self):
        state = grok.parse_billing({}, {"monthlyLimit": 0}, None, NOW)
        self.assertEqual(state.windows, [])

    def test_disabled_without_token(self):
        self.assertEqual(grok.fetch(use_token=False, now=NOW).status, DISABLED)

    def test_expired_token_is_not_refreshed(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "auth.json").write_text(json.dumps({"https://auth.x.ai::x": {
                "key": "tok", "refresh_token": "r", "expires_at": "2026-09-24T20:07:18.2379537Z"}}),
                encoding="utf-8")
            with mock.patch.dict(os.environ, {"GROK_HOME": tmp}), \
                    mock.patch.object(grok.net, "get_json") as get_json:
                state = grok.fetch(use_token=True, now=NOW)
            content = (Path(tmp) / "auth.json").read_text(encoding="utf-8")
        self.assertEqual(state.status, AUTH_EXPIRED)
        get_json.assert_not_called()
        self.assertIn('"tok"', content)  # 檔案沒被動過


class ProbeTest(unittest.TestCase):
    def test_one_provider_crash_does_not_break_others(self):
        with mock.patch.object(grok, "fetch", side_effect=KeyError("boom")):
            state = fetch_one("grok", True, NOW)
        self.assertEqual(state.status, ERROR)
        self.assertIn("boom", state.error)


if __name__ == "__main__":
    unittest.main()
