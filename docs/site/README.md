# fish-zero.com 上的 AI Usage Meter 頁面（副本）

這四份是 `D:\FISH\git\WEB\fish-zero-web` 內容檔的**副本**，格式照 desk-pet 的 `web/fish-zero-pages/`。
Microsoft Store 送審要一個公開的隱私權政策網址；產品頁給 Store 的「網站」欄位。

⚠️ **真相在 fish-zero-web，不在這裡。** 之後要改文案改那邊（改完 `npm run build`、`npm run verify`），再把副本抄回來。

| 這裡 | fish-zero-web 的 | 網址 |
|---|---|---|
| `zh-TW/aiusagemeter.md` | `site/content/zh-TW/aiusagemeter.md` | `https://fish-zero.com/aiusagemeter` |
| `en/aiusagemeter.md` | `site/content/en/aiusagemeter.md` | `https://fish-zero.com/en/aiusagemeter` |
| `zh-TW/aiusagemeter-privacy.md` | `site/content/zh-TW/aiusagemeter-privacy.md` | `https://fish-zero.com/aiusagemeter-privacy` |
| `en/aiusagemeter-privacy.md` | `site/content/en/aiusagemeter-privacy.md` | `https://fish-zero.com/en/aiusagemeter-privacy` |

⚠️ **政策內容是照程式實際行為寫的（2026-09-26 逐項核對原始碼）**。改到下列任何一項，政策要一起改：
讀取的本機路徑（`providers/claude.py`、`providers/codex.py`）、啟動的官方工具與查詢時機
（`app.py` 的節流、`codex_app_server.py`、`providers/antigravity.py`、`providers/copilot.py`）、
Claude hook 寫什麼（`claude_hook.py` 的 `HOOK_SCRIPT`）、本機存檔（`config.py`、`alerts.py`）、設定視窗的外部連結（`settings.py` 的 `STORE_URL`）。

💡 中文段落不要在句中斷行：站台的 Markdown 會把換行變成空格，中文字之間就多一個空白。

✅ 2026-09-26 已 push 上線（部署 run 成功、四個網址實測 200）。還沒做：Store 上架後把商店網址補進產品頁的「下載」，並考慮加進 fish-zero.com 首頁的自家 App 輪播（`site/lib/site-config.mjs`，smoke 測試有逐字鎖商店網址）。
🔴 fish-zero-web 的 push main ＝ 全世界立刻看得到，push 前要問業主。
