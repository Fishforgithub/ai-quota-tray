# ai-quota-tray — 專案交接文件

Windows 系統匣常駐工具：顯示 Claude / Codex / Grok 各視窗的剩餘 %、重置倒數。
滑鼠 hover 系統匣圖示 → 彈出自訂卡片（非原生 tooltip）。

> 本文件來自 claude.ai 上的研究與規劃（2026-09-25）。所有端點皆為非公開內部 API，隨時可能改版，實作前請先用 P1 的 probe 驗證實際回傳。

## 0. 目前進度與怎麼跑（2026-09-25）

**P1–P4 全部完成**（個人版）。上線版（MSIX）還沒做，見 §5。repo：`github.com/Fishforgithub/ai-quota-tray`（⚠️ **PUBLIC**，測試夾具不准放真實 id／姓名／email；無 CI，push ≠ 上線）。

```
python -m venv .venv && .venv\Scripts\pip install -e .   # PySide6-Essentials + Pillow
.venv\Scripts\python -m ai_quota_tray probe                     # 只用不碰 token 的來源
.venv\Scripts\python -m ai_quota_tray probe --token codex,grok  # 這幾家改用 token 來源（API 失敗會退回檔案來源）
.venv\Scripts\python -m ai_quota_tray probe --raw               # 附原始回傳（token/姓名/email/id/UUID 已遮罩）
.venv\Scripts\python -m ai_quota_tray tray --debug              # 系統匣常駐（pythonw 可免主控台；--log FILE 寫檔）
.venv\Scripts\python -m ai_quota_tray tray --token codex,grok   # 同上，並把 token 來源寫進 config.json（之後用右鍵選單改）
powershell -ExecutionPolicy Bypass -File packaging\build.ps1  # 打包 → dist\AiQuotaTray\AiQuotaTray.exe（onedir，約 88 MB）
.venv\Scripts\python -m unittest discover -s tests              # 測試（無 linter 設定）
```

- 結構：`model.py`（資料模型、時間解析、label 推導、遮罩、檔案來源的過期／歸零規則）、`net.py`（urllib GET，401 或非 HTML 的 403 → `AuthExpired`）、`providers/{claude,codex,grok}.py`（各自 `fetch(use_token, now)`；`providers.fetch_one` 把例外收斂成該家 `error`）、`__main__.py`（probe／tray）、`win32tray.py`、`icon.py`、`placement.py`（卡片定位純計算）、`card.py`、`app.py`。測試要在 venv 跑（`test_icon` 要 Pillow、`test_card` 要 PySide6，用 offscreen 平台）。
- probe **只用標準函式庫**；`requires-python >= 3.11`。
- **P2 與 §4 的差異**：系統匣走 **ctypes** 而不是 pywin32（pywin32 沒包 `Shell_NotifyIconGetRect`，VERSION_4 的 union 也難填）。右鍵選單用原生 `TrackPopupMenu`（先 `SetForegroundWindow`，否則點外面不會關）。收回呼訊息的是隱藏的**頂層**視窗、不是 message-only（`TaskbarCreated` 只廣播給頂層視窗，Explorer 重啟會自動重新登錄圖示）。對該視窗送 `WM_CLOSE` ＝ 正常結束（會 `NIM_DELETE`，不留殘影）。單一實例用具名 mutex `Local\AiQuotaTray.SingleInstance`。
- 圖示：⚠️ **取代 §4「動態繪製最低剩餘 %」**——業主 2026-09-25 決定**系統匣一律顯示品牌圖示**，不畫數字也不變色；數字只在 hover 卡片，剩餘 < 10% 靠通知。顏色門檻（< 10 紅、< 30 黃、其餘綠，`icon.level_for`）只剩卡片進度條在用。圖示在啟動時設一次，之後抓到資料只更新 tooltip。品牌圖示 `ai_quota_tray/assets/app.png`（512px）／`app.ico`（16–256）是業主設計的（原圖 `D:\FISH\Desktop\ai-quota.png`，裁掉四周光暈：alpha > 128 的方塊外留 3%）；也用在 exe 圖示、通知大圖示（`NIIF_USER | NIIF_LARGE_ICON`）、Qt 對話框。szTip 有填（給螢幕閱讀器），但不設 `NIF_SHOWTIP`，所以不會跳原生 tooltip。
- ⚠️ **Windows 11 預設把新圖示收進溢位區（`^`）**，此時 `Shell_NotifyIconGetRect` 回的是 `^` 箭頭的位置（2026-09-25 實測），卡片就會出現在 `^` 上方。使用者要自己在「設定 → 個人化 → 工作列 → 其他系統匣圖示」打開。
- ⚠️ DPI：Qt 6 預設 Per-Monitor v2，系統匣回呼座標、`GetRect` 都是實體像素；**外部測試腳本沒設 DPI aware 的話拿到的是虛擬化座標**（125% 時差 1.25 倍）。
- 已驗證（P2）：啟動→三家抓取→圖示登錄、右鍵選單「立即刷新」會重抓、`WM_CLOSE` 正常退出（exit 0、視窗銷毀）。
- **P3 卡片**：`NIN_POPUPOPEN` 或點一下圖示（`NIN_SELECT`）→ 開；**關閉不靠 `NIN_POPUPCLOSE`**（滑鼠從圖示移到卡片途中就會收到 CLOSE），改成每 150ms 看滑鼠，離開「圖示矩形＋卡片（外擴 6px）」超過 0.4 秒才關。位置：`Shell_NotifyIconGetRect`（實體像素）→ 換算成該螢幕的邏輯像素 → 依圖示落在可用區域哪一側判斷工作列方向（上下左右／inside＝溢位面板或自動隱藏）→ 貼著圖示朝內、夾在可用區域內。取不到圖示位置時用事件的錨點座標。深淺色跟系統（`styleHints().colorScheme()`）。進度條＝剩餘、顏色門檻與圖示共用（`icon.level_for`）；stale 區塊整塊變灰、右上顯示「n 分鐘前」；檔案來源已歸零的視窗倒數顯示「已重置」；右上平常顯示方案（`team`、`GrokPro`）；API 失敗退回本機資料時顯示警示。
- 已驗證（P3）：實際送 `NIN_POPUPOPEN` → 卡片出現在 `^` 上方、貼齊工作列（截圖看過），滑鼠不在上面 1.4 秒後確認已關閉；也收到過使用者真實 hover 的 `popup_open`/`popup_close`。**多螢幕、工作列在其他邊、非 125% DPI 只有單元測試，沒實機測**。
- **P4**：
  - 過期偵測：API 失敗／token 過期時 `model.carry_over` 保留上一次的視窗（狀態維持 `auth_expired`/`error`、`fetched_at` 用上次成功的時間），卡片整塊變灰＋「n 分鐘前」＋失敗原因；期間過了重置時間照樣歸零。睡眠喚醒（`WM_POWERBROADCAST`）10 秒後全部重抓。
  - 通知（`alerts.py`）：剩餘 < 10%（＝卡片進度條變紅）時用 `NIF_INFO` 發 toast（`NIIF_RESPECT_QUIET_TIME`），點通知開卡片。**每個視窗每個重置週期只一次**：鍵＝`provider|label|resets_at`，記在 `%LOCALAPPDATA%\ai-quota-tray\state.json`（重開不重複；重置時間過了自動清掉；壞檔直接覆寫）。只看 `ok`/`stale`，失敗後保留的舊數字不發。
  - 右鍵選單（業主要求保持乾淨）：立即刷新／設定…／開機時啟動／關閉。
  - 設定視窗（`settings.py`，非模態、只開一個）：每家二選一「本機紀錄」或「API」，每個選項下寫說明與風險，框標題寫預設值；Grok 的本機紀錄停用（`config.HAS_LOCAL_SOURCE`）。預設 `config.DEFAULT_TOKEN_SOURCES`＝只有 Grok 用 API（Claude、Codex 讀本機紀錄）；「還原預設」按鈕。改選 Claude API 按確定時跳 ToS 確認（預設「否」，選否會退回本機紀錄並留在視窗）。沒改就不套用；有改只重抓有變的那幾家。存在 `%LOCALAPPDATA%\ai-quota-tray\config.json` 的 `token_sources`（沒有本機紀錄的 provider 讀取時一律補進去）。命令列 `--token` 只是把值寫進 config（給第一次設定用）。
  - 開機啟動（`startup.py`）：切換 HKCU `Run` 機碼的 `AiQuotaTray` 值；寫入的是**目前這份的啟動方式**（venv → `pythonw.exe -m ai_quota_tray tray`；打包版 → `AiQuotaTray.exe tray`），**刻意不帶 `--token`**（帶了每次開機都會蓋掉選單的選擇），也不帶 `--debug`/`--log`。⚠️ MSIX 無效，上線要改 `startupTask`。
  - 打包（`packaging/`）：`launch.py` 當進入點（`__main__.py` 是相對 import）；⚠️ 必須 `--paths .`，否則 editable 安裝的套件 PyInstaller 追不到，exe 一啟動就 `ModuleNotFoundError`，windowed 版會卡在錯誤對話框。打包後刪 `opengl32sw.dll`（20 MB）與 Qt `translations`。⚠️ `build.ps1` 有中文，**必須存成 UTF-8 with BOM**（PowerShell 5.1 會把無 BOM 當 cp950）。打包版不帶參數直接雙擊＝`tray`（token 來源照 config.json）。
  - 已驗證：unittest 54 過（含 `MenuTest`：真的走 `_on_tray_event("context_menu")` → `handle_menu`；`SettingsDialogTest`）；實跑發出 Grok 8% 通知並寫進 state.json；venv 版與打包版都實跑過右鍵選單截圖＋三家抓取；實際從右鍵開設定視窗截圖看過；exe 圖示取出來看過。**toast 畫面本身沒截到、睡眠喚醒沒實測、開機啟動只測了暫用機碼**。
  - 🔴 教訓（2026-09-25）：P4 用「字串替換」插入 `_context_menu` 時比對到**第一個** `def shutdown`（`Poller` 的），方法進了錯的類別 → 右鍵一按 `AttributeError`（被 `_proc` 吞掉只寫 log，畫面上就是「右鍵沒反應」），當時的測試都沒走到選單。改 `app.py` 要用能看到上下文的編輯方式，選單相關改動要跑 `MenuTest`。
- 狀態值比 §2 多一個 `disabled`（來源沒啟用；probe 沒給 `--token grok` 時會出現，系統匣程式裡 Grok 一律用 API 所以不會）。`ProviderState` 另有 `source` / `error` / `raw`（raw 只給 probe）。
- 檔案來源規則（`model.apply_file_freshness`）：`resets_at` 已過的視窗 → `used_pct=0`、`resets_at=None`、記進 `detail.rolled_over`；資料 > 15 分鐘或有歸零 → `stale`。

**實測結果（本機帳號，2026-09-25）**

| Provider | 來源 | 實際視窗 |
|---|---|---|
| Claude | statusLine cache ✅ | 5h + 週。hook 是 `D:\FISH\tools\claude-monitor\statusline-usage.js`，寫 `{"fetchedAt": ms, "rate_limits": {"five_hour": {"used_percentage", "resets_at": 秒}, "seven_day": …}}`（欄位名是 `used_percentage`，不是 API 的 `utilization`） |
| Claude | OAuth API | 已實作，**未實際呼叫**（ToS 風險，業主決定要不要跑 `--token claude`） |
| Codex | rollout ✅ / wham API ✅ | **5h + 週都在**（team 方案）：rollout `rate_limits.primary.window_minutes=300`、`secondary=10080`；API `primary_window.limit_window_seconds=18000`、`secondary_window=604800`，另有 `reset_after_seconds`、`additional_rate_limits`、`rate_limit_reset_credits`。閒置 4 天的 rollout 週 1% vs API 5% |
| Grok | billing API ✅ | **只有週視窗**（GrokPro）。`config` 包一層；`currentPeriod` 有 `type`/`start`/`end`（ISO，`+00:00`），`start→end` 正好 604800 秒；`creditUsagePercent` 與 `productUsage[GrokBuild]` 同為 92%；`onDemandCap`/`prepaidBalance` 都是 `{"val": 0}`；`isUnifiedBillingUser: true`。月額度 `/billing` 回 `monthlyLimit {"val":0}`、`used {"val":75}` → 依規則**無月視窗**（另有 `history[]` 近三個月）。`/user` 有 `subscriptionTier`、`hasGrokCodeAccess`，也有姓名、xUserId 等個資（`--raw` 已遮）。⚠️ `~/.grok/auth.json` token 效期只有 **6 小時**，Grok CLI 沒開就會 `auth_expired` |

---

## 1. 核心設計原則

1. **視窗不寫死**：三家視窗結構已不同，UI 不得假設「5h + 週」。視窗名稱由實際長度（秒）推導。
2. **只存 `resets_at`（UTC 絕對時間）**，倒數在本地算。抓取頻率與畫面更新頻率分離。
3. **Token 只讀不寫**：不自行 refresh。refresh token 多為一次性輪替，自行刷新會讓 CLI 那組失效。過期 → status=`auth_expired`，卡片提示「請開一下 CLI」。
4. **每個 provider 獨立失敗**：格式變了只影響該區塊（顯示「Grok：格式變了」），整支程式不能掛。
5. **上線版不碰 token**（見 §5），個人版可選配 token 來源並清楚標示風險。

## 2. 資料模型

```python
@dataclass
class Window:
    label: str              # "5h" / "週" / "月"，由 duration_s 推導
    used_pct: float | None
    resets_at: datetime | None  # UTC
    duration_s: int | None

@dataclass
class ProviderState:
    name: str
    windows: list[Window]
    fetched_at: datetime
    status: str             # ok / stale / auth_expired / error
    detail: dict            # e.g. Grok 的 GrokBuild 佔比
```

## 3. Provider 資料來源

### Claude
- **首選（不碰 token，上線版唯一來源）**：Claude Code statusLine hook 推出的資料 → 寫本地 cache（沿用舊專案 usage-cache.json 的做法）。缺點：Claude Code 沒在跑時不會更新 → 顯示「最後更新時間」。
- **個人版選配（有條款風險）**：`GET https://api.anthropic.com/api/oauth/usage`
  - token：`~/.claude/.credentials.json`（可被 config dir 環境變數覆寫）
  - headers：`Authorization: Bearer <token>`、`anthropic-beta: oauth-2025-04-20`
  - 回傳 `five_hour` / `seven_day`，各有 `utilization`（已用 %）、`resets_at`
  - 輪詢 ≥ 120 秒
  - ⚠️ Anthropic 2026-02 起明文：Free/Pro/Max 的 OAuth token 用於 Claude Code / claude.ai 以外的任何產品、工具、服務皆違反 Consumer ToS，且曾技術封鎖。

### Codex
- **首選（不碰 token）**：解析 `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` 最新檔的最後一筆 `token_count` 事件 → `rate_limits`。用 watchdog 監看。缺點：閒置時資料會過時。
- **個人版選配**：`GET https://chatgpt.com/backend-api/wham/usage`，token 取自 `~/.codex/auth.json` 的 `tokens.access_token`。
  - `rate_limit.primary_window` / `secondary_window`，各有 `used_percent`、重置時間、`limit_window_seconds`
- ⚠️ **Codex 在 2026 年中暫時移除 5h 視窗**，`primary_window` 現在裝的是週視窗（604800 秒），`secondary_window` 可能為 null。**一律依 `limit_window_seconds` 決定 label**，null 視窗直接略過。
  - 2026-09-25 實測：本帳號（team 方案）**5h 視窗仍在**（見 §0），上面這條可能只適用部分方案或已恢復；程式不假設任何一種。

### Grok（最脆弱）
- 2026-06 起 Grok 改制：不再計訊息數，付費方案共用**每週運算額度池**（Chat/Imagine/Voice/Build/API 共用），**沒有 5h 視窗**。部分方案另有月額度。
- 舊的 grok.com `/rest/rate-limits`（remainingQueries / windowSizeSeconds，需瀏覽器 cookie、會被 Cloudflare 擋）是改制前模型，**不採用**。
- **可行做法**（需先用 Grok Build CLI 登入）：
  - token：`~/.grok/auth.json`，每個 entry 有 `key`（access token）、`refresh_token`、`expires_at`、`oidc_issuer`、`oidc_client_id`
  - 共同 headers：`Authorization: Bearer <token>`、`Accept: application/json`、`x-grok-client-mode: cli`
  - 週額度：`GET https://cli-chat-proxy.grok.com/v1/billing?format=credits`
    - `currentPeriod.type == "USAGE_PERIOD_TYPE_WEEKLY"`，`currentPeriod.end` = 重置時間（缺時 fallback `billingPeriodEnd`）
    - `creditUsagePercent`：整池已用 % → **主數字用這個**（共用池，真正會擋人的是整池）
    - `productUsage[]`：`{product: "GrokBuild", usagePercent}` → 放 detail
    - 無百分比時 fallback：`onDemandUsed / onDemandCap`
  - 月額度：`GET https://cli-chat-proxy.grok.com/v1/billing` → `monthlyLimit`、`used`、`billingPeriodEnd`（`monthlyLimit` 缺或 ≤0 → 無月視窗）
  - 方案資訊：`GET .../v1/user?include=subscription` → `subscriptionTier`
  - ⚠️ **proto3 陷阱**：值為 0 的欄位會被省略。週期型別是 WEEKLY 但沒有百分比欄位 → 當成 **0%**，不是「無資料」。
  - 數值欄位可能包成 `{"val": ...}` 形式，要做 unwrap。
  - 參考實作：PyPI 套件 `quse`（`quse/grok_quota.py`），MIT。
- xAI 對第三方使用此 token 的條款未查到明確說法 → 上線版建議：選配 + 告知風險，或第一版不支援。

### 輪詢頻率
| Provider | 間隔 |
|---|---|
| Claude | 120 s |
| Codex | 120 s（檔案來源則用 watchdog） |
| Grok | 300 s |

UI：卡片開著每秒重算倒數；關閉時每 30 秒更新圖示。

## 4. 系統匣與 Hover 卡片

- **Qt 當主事件迴圈**（PySide6）。系統匣用隱藏 native window 或 `QAbstractNativeEventFilter` 接 Win32 訊息，避免兩個迴圈互相同步。
- pywin32 直接呼叫 `Shell_NotifyIcon`，設 `NOTIFYICON_VERSION_4`，**不設 `NIF_SHOWTIP`** → hover 時收到 `NIN_POPUPOPEN`、離開收到 `NIN_POPUPCLOSE`，且不顯示原生 tooltip。
- 卡片：`Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`，不搶焦點。用 `Shell_NotifyIconGetRect` 取圖示座標定位，貼圖示上方並處理螢幕邊界 / 多螢幕 / DPI。
- 卡片內容：每家一區塊，每個視窗一列：進度條 + 剩餘 % + 倒數。
  - 倒數格式：< 24h → `hh:mm`；≥ 24h → `3d04h`
  - 資料過期 → 區塊變灰 + 「n 分鐘前」
- 圖示：~~Pillow 動態繪製三家中最低剩餘 %~~ → 已改為一律顯示品牌圖示（見 §0）。
- 右鍵選單：立即刷新、結束。

## 5. 上線（MSIX）注意事項

- 技術可行：full trust（`runFullTrust`）下系統匣、pywin32、PySide6、DPAPI、讀 `%USERPROFILE%\.claude` 等皆正常。
- 開機啟動：HKCU 寫入被虛擬化，`Run` 機碼無效 → 用 manifest 的 `windows.startupTask`。
- `%LOCALAPPDATA%` 寫入會重導到套件目錄；解除安裝會清除。
- PyInstaller 用 `--onedir`，不要 `--onefile`。
- 簽章：Store 代簽；sideload 需受信任憑證（Azure Trusted Signing）。
- **政策**：上線版資料來源必須全部不碰 token；名稱與圖示避開「Claude / Codex / Grok」商標（例如中性名稱 AI Quota Tray）。
- 散佈選項：Microsoft Store / 公司內部 App Installer 或 Intune / GitHub 開源（provider 由使用者自行啟用）。尚未決定。

## 6. 開發階段

1. **P1 Provider 驗證**：三個 provider + `probe` 指令，輸出標準化 JSON（token 遮罩）。先確認實際帳號回傳哪些視窗。
2. **P2 系統匣骨架**：Qt 主迴圈、native 系統匣、動態圖示、右鍵選單。
3. **P3 Hover 卡片**：`NIN_POPUPOPEN` / `CLOSE`、定位、倒數。
4. **P4 收尾**：剩餘 < 10% toast 通知、過期偵測、開機啟動、打包。

## 7. 相關既有專案

- `Fishforgithub/claude-codex-usage-dashboard`：Node.js statusLine hook 擷取 quota 的做法，Claude 不碰 token 的來源可沿用。
