"""Grok：解析 `x.ai/billing` 回傳、透過 `grok agent stdio`（ACP）查詢、登入失效與失敗處理。

查詢的測試真的起一個子行程（假的 ACP agent，Python 寫的），走同一套 stdin/stdout JSON-RPC。
夾具是編出來的，不放真實資料。
"""
import os
import sys
import tempfile
import textwrap
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from ai_quota_tray.model import AUTH_EXPIRED, OK
from ai_quota_tray.providers import fetch_one, grok
from ai_quota_tray.model import ERROR

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
BILLING = {
    "config": {
        "creditUsagePercent": 61.0,
        "currentPeriod": {"type": "USAGE_PERIOD_TYPE_WEEKLY", "start": "2026-09-26T00:00:00+00:00",
                          "end": "2026-10-03T00:00:00+00:00"},
        "onDemandCap": {"val": 0}, "onDemandUsed": {"val": 0}, "prepaidBalance": {"val": 0},
        "isUnifiedBillingUser": True,
        "billingPeriodStart": "2026-09-26T00:00:00+00:00",
        "billingPeriodEnd": "2026-10-03T00:00:00+00:00",
    },
    "subscription_tier": "TestTier",
}

FAKE_AGENT = textwrap.dedent('''
    import json, os, sys
    scenario = os.environ.get("FAKE_GROK_SCENARIO", "ok")
    calls_file = os.environ["FAKE_GROK_CALLS"]
    result = json.loads(os.environ["FAKE_GROK_RESULT"])
    calls = 0

    def send(obj):
        sys.stdout.write(json.dumps(obj) + "\\n")
        sys.stdout.flush()

    for line in sys.stdin:
        msg = json.loads(line)
        mid, method = msg.get("id"), msg.get("method")
        if method == "initialize":
            # 真的 grok 會在回應前後穿插通知，沒有 id
            send({"jsonrpc": "2.0", "method": "_x.ai/mcp/servers_updated", "params": {"mcpServers": []}})
            send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": 1, "agentCapabilities": {}}})
        elif method == "_x.ai/billing":
            calls += 1
            open(calls_file, "w").write(str(calls))
            if scenario == "silent":
                continue
            if scenario == "auth_required":
                send({"jsonrpc": "2.0", "id": mid, "error": {
                    "code": -32000, "message": "Authentication required",
                    "data": "Authentication required to fetch billing data"}})
            elif scenario == "unauthorized" or (scenario == "unauthorized_once" and calls == 1):
                send({"jsonrpc": "2.0", "id": mid, "error": {
                    "code": -32603, "message": "Internal error", "data": "Billing service error: HTTP 401"}})
            elif scenario == "server_error":
                send({"jsonrpc": "2.0", "id": mid, "error": {
                    "code": -32603, "message": "Internal error", "data": "Billing service error: HTTP 500"}})
            else:
                send({"jsonrpc": "2.0", "id": mid, "result": result})
        else:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found"}})
''')


class ParseTest(unittest.TestCase):
    def test_weekly_window_uses_whole_pool_percent_and_period_length(self):
        state = grok.parse_billing(BILLING, NOW)
        self.assertEqual(state.status, OK)
        self.assertEqual(state.source, "grok-cli")
        (window,) = state.windows
        self.assertEqual(window.used_pct, 61)
        self.assertEqual(window.duration_s, 7 * 86400)
        self.assertEqual(window.label, "週")
        self.assertEqual(state.detail["subscription_tier"], "TestTier")
        self.assertEqual(state.detail["period_type"], grok.WEEKLY)

    def test_proto3_omitted_zero_is_zero_percent_not_missing(self):
        cfg = {"config": {"currentPeriod": {"type": grok.WEEKLY, "end": "2026-10-03T00:00:00+00:00"}}}
        (window,) = grok.parse_billing(cfg, NOW).windows
        self.assertEqual(window.used_pct, 0.0)

    def test_monthly_window_only_with_positive_limit(self):
        monthly = {"config": dict(BILLING["config"], monthlyLimit={"val": 200}, used={"val": 50},
                                  billingPeriodStart="2026-10-01T00:00:00+00:00",
                                  billingPeriodEnd="2026-10-31T00:00:00+00:00")}
        windows = grok.parse_billing(monthly, NOW).windows
        self.assertEqual([w.label for w in windows], ["週", "月"])
        self.assertEqual(windows[1].used_pct, 25)
        empty = {"config": dict(BILLING["config"], monthlyLimit={"val": 0}, used={"val": 75})}
        self.assertEqual(len(grok.parse_billing(empty, NOW).windows), 1)

    def test_garbage_payload_gives_no_windows(self):
        self.assertEqual(grok.parse_billing({}, NOW).windows, [])


class CommandTest(unittest.TestCase):
    def test_uses_official_agent_mode_without_shared_leader(self):
        self.assertEqual(grok.agent_command("grok.exe"), ["grok.exe", "agent", "--no-leader", "stdio"])

    def test_missing_cli_is_an_error_not_a_crash(self):
        with mock.patch.object(grok, "find_cli", return_value=None):
            state = fetch_one("grok", False, NOW)
        self.assertEqual(state.status, ERROR)
        self.assertIn("grok login", state.error)

    def test_never_reads_the_cli_credentials(self):
        source = Path(grok.__file__).read_text(encoding="utf-8")
        self.assertNotIn("auth.json\")", source)
        self.assertNotIn("read_text", source)  # 不讀 ~/.grok 底下任何檔案
        self.assertNotIn("Authorization", source)


class AgentFetchTest(unittest.TestCase):
    """真的起子行程，走 stdin/stdout。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        script = Path(tmp.name) / "fake_grok_agent.py"
        script.write_text(FAKE_AGENT, encoding="utf-8")
        self.calls_file = Path(tmp.name) / "calls.txt"
        import json
        for patcher in (
            mock.patch.object(grok, "find_cli", return_value=sys.executable),
            mock.patch.object(grok, "agent_command", lambda exe: [exe, str(script)]),
            mock.patch.object(grok, "AUTH_RETRY_DELAYS_S", (0.01, 0.01)),
            mock.patch.dict(os.environ, {"FAKE_GROK_CALLS": str(self.calls_file),
                                         "FAKE_GROK_RESULT": json.dumps(BILLING)}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_scenario(self, scenario):
        with mock.patch.dict(os.environ, {"FAKE_GROK_SCENARIO": scenario}):
            return grok.fetch(now=NOW)

    def calls(self):
        return int(self.calls_file.read_text())

    def test_ok(self):
        state = self.run_scenario("ok")
        self.assertEqual(state.status, OK)
        self.assertEqual(state.windows[0].used_pct, 61)
        self.assertEqual(state.detail["subscription_tier"], "TestTier")
        self.assertEqual(self.calls(), 1)

    def test_401_right_after_start_waits_for_cli_to_renew_then_retries(self):
        state = self.run_scenario("unauthorized_once")
        self.assertEqual(state.status, OK)
        self.assertEqual(self.calls(), 2)

    def test_401_that_never_clears_is_auth_expired(self):
        state = self.run_scenario("unauthorized")
        self.assertEqual(state.status, AUTH_EXPIRED)
        self.assertEqual(self.calls(), 1 + len(grok.AUTH_RETRY_DELAYS_S))

    def test_not_signed_in_is_auth_expired_without_retrying(self):
        state = self.run_scenario("auth_required")
        self.assertEqual(state.status, AUTH_EXPIRED)
        self.assertIn("尚未登入", state.error)
        self.assertEqual(self.calls(), 1)

    def test_server_error_becomes_error_state(self):
        with mock.patch.dict(os.environ, {"FAKE_GROK_SCENARIO": "server_error"}):
            state = fetch_one("grok", False, NOW)
        self.assertEqual(state.status, ERROR)
        self.assertIn("HTTP 500", state.error)
        self.assertEqual(self.calls(), 1)

    def test_no_reply_times_out_and_the_process_is_closed(self):
        with mock.patch.object(grok, "RESPONSE_TIMEOUT_S", 0.5):
            started = time.monotonic()
            state = None
            with mock.patch.dict(os.environ, {"FAKE_GROK_SCENARIO": "silent"}):
                state = fetch_one("grok", False, NOW)
        self.assertEqual(state.status, ERROR)
        self.assertIn("逾時", state.error)
        self.assertLess(time.monotonic() - started, 5)

    def test_process_exits_after_each_query(self):
        real_agent = grok._Agent
        seen = []

        class Spy(real_agent):
            def __exit__(self, *exc_info):
                super().__exit__(*exc_info)
                seen.append(self._process.poll())

        with mock.patch.object(grok, "_Agent", Spy):
            self.run_scenario("ok")
        self.assertEqual(seen, [0])  # 關 stdin 後自己正常結束，不常駐


if __name__ == "__main__":
    unittest.main()
