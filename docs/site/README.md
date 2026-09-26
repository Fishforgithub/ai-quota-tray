# fish-zero.com 上的 AI Usage Meter 頁面（底稿）

這裡是要放進 `D:\FISH\git\WEB\fish-zero-web` 的內容檔底稿，格式照 desk-pet 的 `web/fish-zero-pages/`。
Microsoft Store 送審要一個公開的隱私權政策網址。

| 這裡 | 放到 fish-zero-web 的 | 網址 |
|---|---|---|
| `zh-TW/aiusagemeter-privacy.md` | `site/content/zh-TW/aiusagemeter-privacy.md` | `https://fish-zero.com/aiusagemeter-privacy` |
| `en/aiusagemeter-privacy.md` | `site/content/en/aiusagemeter-privacy.md` | `https://fish-zero.com/en/aiusagemeter-privacy` |

⚠️ **政策內容是照程式實際行為寫的（2026-09-26 逐項核對原始碼）**。改到下列任何一項，這兩份要一起改：
讀取的本機路徑（`providers/claude.py`、`providers/codex.py`）、啟動的官方工具與查詢時機
（`app.py` 的節流、`codex_app_server.py`、`providers/antigravity.py`、`providers/copilot.py`）、
Claude hook 寫什麼（`claude_hook.py` 的 `HOOK_SCRIPT`）、本機存檔（`config.py`、`alerts.py`）、設定視窗的外部連結（`settings.py` 的 `STORE_URL`）。

⚠️ 搬過去時照 desk-pet `web/fish-zero-pages/README.md` 的步驟（`lib/app.mjs` 的 `PAGES`＋content＋`test/smoke.test.mjs`，`npm run build`）。
🔴 fish-zero-web 的 push main ＝ 全世界立刻看得到，push 前要問業主。
