"""Provider 解析邏輯測試。Codex 官方回傳夾具依 App Server 文件。
只測純函式，不打網路。

    python -m unittest discover -s tests
"""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from ai_quota_tray import wincred
from ai_quota_tray.model import (AUTH_EXPIRED, DISABLED, ERROR, OK, STALE, AuthExpired,
                                 label_for_duration, mask_secrets, parse_time, to_float)
from ai_quota_tray.providers import ALL, antigravity, claude, codex, copilot, fetch_one

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

    def test_legacy_token_flag_still_uses_local_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "usage-cache.json"
            path.write_text(json.dumps(self.cache(EPOCH_NOW * 1000, EPOCH_NOW + 3600,
                                                  EPOCH_NOW + 86400)), encoding="utf-8")
            with mock.patch.dict(os.environ, {"CLAUDE_USAGE_CACHE": str(path)}):
                state = claude.fetch(use_token=True, now=NOW)
        self.assertEqual(state.source, "statusline-cache")

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

    def test_app_server_weekly_in_primary_window(self):
        state = codex.parse_app_server({"rateLimitsByLimitId": {"codex": {
            "limitId": "codex", "planType": "plus",
            "primary": {"usedPercent": 20, "windowDurationMins": 10080,
                        "resetsAt": EPOCH_NOW + 3600}, "secondary": None}}}, NOW)
        self.assertEqual([w.label for w in state.windows], ["週"])
        self.assertEqual(state.windows[0].resets_at, NOW + timedelta(hours=1))
        self.assertEqual(state.source, "codex-app-server")
        self.assertEqual(state.detail["plan_type"], "plus")

    def test_app_server_does_not_show_another_bucket_as_codex(self):
        with self.assertRaises(ValueError):
            codex.parse_app_server({"rateLimitsByLimitId": {"other": {
                "limitId": "other", "primary": {"usedPercent": 42}}}}, NOW)

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
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}), \
                    mock.patch.object(codex.client, "rate_limits", side_effect=codex.AppServerError("unavailable")):
                state = codex.fetch(now=NOW)
        self.assertEqual(state.detail["file"], "rollout-a.jsonl")
        self.assertEqual(state.windows[0].used_pct, 5.0)
        self.assertEqual(state.detail["api_error"], "unavailable")


class AntigravityTest(unittest.TestCase):
    SAMPLE_USAGE = {
        "status": "SUCCESS",
        "command": {
            "name": "usage",
            "data": {
                "description": "Within each group, models share a weekly limit.",
                "groups": [
                    {
                        "name": "Gemini Models",
                        "description": "Models within this group: Gemini Flash, Gemini Pro",
                        "buckets": [
                            {
                                "id": "gemini-weekly",
                                "name": "Weekly Limit Remaining",
                                "window": "weekly",
                                "remaining_fraction": 0.8,
                                "reset_time": "2026-10-02T15:00:00Z",
                            }
                        ],
                    },
                    {
                        "name": "Claude and GPT models",
                        "description": "Models within this group: Claude Opus, Claude Sonnet, GPT-OSS",
                        "buckets": [
                            {
                                "id": "3p-weekly",
                                "name": "Weekly Limit Remaining",
                                "window": "weekly",
                                "remaining_fraction": 1.0,
                                "reset_time": "2026-10-02T16:00:00Z",
                            }
                        ],
                    },
                ],
            },
        },
    }

    def test_parse_usage_groups(self):
        state = antigravity.parse_usage(self.SAMPLE_USAGE, NOW)
        self.assertEqual(state.status, OK)
        self.assertEqual(state.source, "agy-cli")
        self.assertEqual(len(state.windows), 2)
        w0, w1 = state.windows[0], state.windows[1]
        self.assertEqual((w0.label, w0.used_pct, w0.remaining_pct), ("Gemini", 20.0, 80.0))
        self.assertEqual(w0.resets_at, datetime(2026, 10, 2, 15, 0, tzinfo=timezone.utc))
        self.assertEqual(w0.duration_s, 604800)
        self.assertEqual((w1.label, w1.used_pct, w1.remaining_pct), ("Claude/GPT", 0.0, 100.0))
        self.assertEqual(w1.resets_at, datetime(2026, 10, 2, 16, 0, tzinfo=timezone.utc))
        self.assertEqual(state.detail["description"], "Within each group, models share a weekly limit.")

    def test_unrecognized_usage_is_not_reported_as_success(self):
        with self.assertRaises(ValueError):
            antigravity.parse_usage({"status": "SUCCESS", "command": {"data": {}}}, NOW)

    def test_proto3_omitted_remaining_fraction(self):
        data = {
            "status": "SUCCESS",
            "command": {
                "data": {
                    "groups": [
                        {"name": "Gemini Models", "buckets": [{"window": "weekly", "reset_time": "2026-10-02T15:00:00Z"}]}
                    ]
                }
            },
        }
        state = antigravity.parse_usage(data, NOW)
        w = state.windows[0]
        self.assertEqual((w.label, w.used_pct, w.remaining_pct), ("Gemini", 100.0, 0.0))

    def test_tsv_fallback_when_groups_missing(self):
        data = {
            "status": "SUCCESS",
            "response": "Gemini Models\tWeekly Limit Remaining\t75%\t2026-10-02T15:00:00Z\nClaude and GPT models\tWeekly Limit Remaining\t100%\t2026-10-02T16:00:00Z\n",
        }
        state = antigravity.parse_usage(data, NOW)
        self.assertEqual(len(state.windows), 2)
        self.assertEqual(state.windows[0].label, "Gemini")
        self.assertEqual(state.windows[0].used_pct, 25.0)
        self.assertEqual(state.windows[1].label, "Claude/GPT")
        self.assertEqual(state.windows[1].used_pct, 0.0)

    def test_use_token_does_not_matter(self):
        # 只有 agy CLI 一種來源、不碰 token
        with mock.patch.object(antigravity, "run_agy_usage", return_value=self.SAMPLE_USAGE):
            self.assertEqual(antigravity.fetch(use_token=False, now=NOW).status, OK)

    def test_fetch_success_with_token(self):
        with mock.patch.object(antigravity, "run_agy_usage", return_value=self.SAMPLE_USAGE):
            state = antigravity.fetch(use_token=True, now=NOW)
        self.assertEqual(state.status, OK)
        self.assertEqual(state.source, "agy-cli")
        self.assertEqual(len(state.windows), 2)

    def test_unauthenticated_error_raises_auth_expired(self):
        with mock.patch.object(antigravity, "run_agy_usage", side_effect=AuthExpired("未登入")):
            state = antigravity.fetch(use_token=True, now=NOW)
        self.assertEqual(state.status, AUTH_EXPIRED)
        self.assertIn("未登入", state.error)


class WinCredTest(unittest.TestCase):
    def test_decode_blob(self):
        self.assertEqual(wincred.decode_blob(b"gho_abc"), "gho_abc")
        self.assertEqual(wincred.decode_blob("gho_abc".encode("utf-16-le")), "gho_abc")
        self.assertEqual(wincred.decode_blob(b"go-keyring-base64:Z2hvX2FiYw=="), "gho_abc")
        self.assertEqual(wincred.decode_blob(b'{"access_token": "x"}'), '{"access_token": "x"}')
        self.assertIsNone(wincred.decode_blob(b""))
        self.assertIsNone(wincred.decode_blob(b"\xff\xfe\x00\x01\x02"))

    def test_missing_target_is_none(self):
        self.assertIsNone(wincred.read_generic("ai-quota-tray:unittest:does-not-exist"))


class ProbeTest(unittest.TestCase):
    def test_one_provider_crash_does_not_break_others(self):
        with mock.patch.object(claude, "fetch", side_effect=KeyError("boom")):
            state = fetch_one("claude", False, NOW)
        self.assertEqual(state.status, ERROR)
        self.assertIn("boom", state.error)

    def test_private_grok_provider_is_not_registered(self):
        self.assertNotIn("grok", ALL)


if __name__ == "__main__":
    unittest.main()
