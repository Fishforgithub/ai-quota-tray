# ai-quota-tray — 專案交接文件

Windows 系統匣常駐工具（產品名 **AI Usage Meter**，repo／內部 ID 仍叫 ai-quota-tray）：顯示 Claude / Codex / Antigravity CLI / GitHub Copilot 各視窗的剩餘 %、重置倒數（預設只啟用 Claude、Codex）。
滑鼠 hover 系統匣圖示 → 彈出自訂卡片（非原生 tooltip）。

> 本文件最初來自 2026-09-25 的研究與規劃。現行來源：Claude 本機 statusLine cache、Codex 官方 App Server（失敗退回本機 rollout）、Antigravity 官方 agy CLI、Copilot 官方 SDK。Grok 原本使用未公開端點，現已停用並從介面移除。下文 Grok 與私有端點記錄僅供歷史參考，不代表現行實作。

## 0. 目前進度與怎麼跑（2026-09-25）

**P1–P4 全部完成**（個人版），P5 加了 Antigravity／Copilot；Grok 因沒有確認獲授權的自動額度介面而停用。上線版（MSIX）還沒做，見 §5。repo：`github.com/Fishforgithub/ai-quota-tray`（⚠️ **PUBLIC**，測試夾具不准放真實 id／姓名／email；無 CI，push ≠ 上線）。

```
python -m venv .venv && .venv\Scripts\pip install -e .   # PySide6-Essentials + Pillow
.venv\Scripts\python -m ai_quota_tray probe                     # 依各 provider 固定來源抓取
.venv\Scripts\python -m ai_quota_tray probe --raw               # 附原始回傳（token/姓名/email/id/UUID 已遮罩）
.venv\Scripts\python -m ai_quota_tray tray --debug              # 系統匣常駐（pythonw 可免主控台；--log FILE 寫檔）
powershell -ExecutionPolicy Bypass -File packaging\build.ps1  # 打包 → dist\AiQuotaTray\AiQuotaTray.exe（onedir，約 91 MB）
.venv\Scripts\python -m unittest discover -s tests              # 測試（無 linter 設定）
```

- 結構：`model.py`（資料模型、時間解析、label 推導、遮罩、檔案來源的過期／歸零規則）、`codex_app_server.py`（Codex 官方 stdio 協定，登入由 Codex CLI 管理）、`providers/{claude,codex,antigravity,copilot}.py`、`__main__.py`（probe／tray）、`win32tray.py`、`icon.py`、`placement.py`、`card.py`、`app.py`。測試要在 venv 跑（`test_icon` 要 Pillow、`test_card` 要 PySide6，用 offscreen 平台）。
- 更新策略（業主 2026-09-26 定：人不會時時盯著看，不要不斷去打對方的服務）：**背景每 2 分鐘只讀本機檔案、不連網**——Claude 的 statusLine 快取、Codex 的 rollout（`providers.fetch_local_one`／`codex.fetch_local`，`app.BACKGROUND_LOCAL`），低額度通知靠這個。**雲端來源只在打開卡片時查**（Codex App Server 2 分鐘、Antigravity／Copilot 5 分鐘內不重查），或右鍵「立即刷新」強制查。背景讀到的本機紀錄若比手上的數字舊（例如剛用 App Server 查過）就丟掉，讀不到也不蓋掉（`TrayApp._on_fetched_local`）。⚠️ 代價：在網頁版／IDE 用掉的 Codex 額度不會寫進本機 rollout，背景察覺不到，要等打開卡片；Antigravity、Copilot 沒有本機紀錄，只能看的時候才知道。
- Copilot 的 SDK `reset_date` 在此環境回傳過去日期；若無有效的未來日期，有限額度依 GitHub 官方規則推算下一個月 1 日 00:00 UTC 重置，卡片倒數前顯示「約」／`~` 以區分推算值。
- Copilot runtime（約 111 MB，含微軟專有元件、授權不允許我們重新散佈，所以不打包）：**勾選 Copilot 時、或啟動時已勾選但還沒下載，就在背景先下載**（`copilot.start_prepare`，呼叫 SDK 內部 `_cli_download.ensure_runtime_wrapper`——SDK 沒有公開下載函式，官方做法 `python -m copilot download-runtime` 打包版用不了；pyproject 已釘死 SDK 版本）。下載完成前 fetch 回 `preparing`，卡片顯示「正在下載 Copilot 元件」，不會在查詢途中卡住下載；下載失敗下次查詢時回報並重試。判斷是否下載好要用 SDK 自己的 `_runtime_bundle_is_complete`（`get_cached_cli_path` 會要求一個實際不存在的 `copilot.exe`，永遠回 None）。2026-09-26 用 `COPILOT_CLI_EXTRACT_DIR` 指到空資料夾模擬新電腦：第一次查詢 0.01 秒回 preparing、下載 11 秒、之後正常查到。查詢加 45 秒逾時（SDK 預設不設逾時，卡住一次 Poller 就永遠不再送出這家；正常約 5 秒）。沒登入：SDK 1.0.14 的 `account.getCurrentAuth` 解析不了 runtime 的回傳（SDK 自己的 bug），改成看錯誤訊息的字（`copilot.AUTH_WORDS`）→ `auth_expired`，卡片提示 `copilot login`。
- Codex App Server 關閉：先關 stdin 讓它自己退（正常時 `cmd.exe → node.exe → codex.exe` 三層一起結束，實測過）；2 秒沒退才 `taskkill /T /F`——Windows 上 `codex` 是 npm 的 `codex.CMD`，`Popen.kill()` 只殺得到 `cmd.exe`，裡面兩層會變孤兒（`codex_app_server._kill_tree`，實測三層都清掉）。
- probe 除了 Copilot 以外只用標準函式庫（Copilot 要 `github-copilot-sdk`，延後到查詢時才 import，沒裝時只有 Copilot 那一家變 error）；`requires-python >= 3.11`。
- **P2 與 §4 的差異**：系統匣走 **ctypes** 而不是 pywin32（pywin32 沒包 `Shell_NotifyIconGetRect`，VERSION_4 的 union 也難填）。右鍵選單用原生 `TrackPopupMenu`（先 `SetForegroundWindow`，否則點外面不會關）。收回呼訊息的是隱藏的**頂層**視窗、不是 message-only（`TaskbarCreated` 只廣播給頂層視窗，Explorer 重啟會自動重新登錄圖示）。對該視窗送 `WM_CLOSE` ＝ 正常結束（會 `NIM_DELETE`，不留殘影）。單一實例用具名 mutex `Local\AiQuotaTray.SingleInstance`。
- 工作列圖示：啟動時呼叫 `SetCurrentProcessExplicitAppUserModelID("AiQuotaTray.App")`（`win32tray.set_app_id`），否則 venv 版的視窗會被歸到 `pythonw.exe`、工作列顯示 Python 圖示。
- 💡 模擬按選單（PostMessage）開出的視窗會被 Windows 擋在後面（前景鎖，工作列按鈕閃爍）；真人點選單才有前景權。測試腳本要截被擋住的視窗用 `PrintWindow(hwnd, dc, PW_RENDERFULLCONTENT)`。
- 圖示：⚠️ **取代 §4「動態繪製最低剩餘 %」**——業主 2026-09-25 決定**系統匣一律顯示品牌圖示**，不畫數字也不變色；數字只在 hover 卡片，剩餘 < 10% 靠通知。顏色門檻（< 10 紅、< 30 黃、其餘綠，`icon.level_for`）只剩卡片進度條在用。圖示在啟動時設一次，之後抓到資料只更新 tooltip；過期或抓取失敗時 tooltip 不顯示舊百分比。品牌圖示 `ai_quota_tray/assets/app.png`（512px）／`app.ico`（16–256）是業主設計的（原圖 `D:\FISH\Desktop\ai-quota.png`，裁掉四周光暈：alpha > 128 的方塊外留 3%）；也用在 exe 圖示、通知大圖示（`NIIF_USER | NIIF_LARGE_ICON`）、Qt 對話框。szTip 有填（給螢幕閱讀器），但不設 `NIF_SHOWTIP`，所以不會跳原生 tooltip。
- ⚠️ **Windows 11 預設把新圖示收進溢位區（`^`）**，此時 `Shell_NotifyIconGetRect` 回的是 `^` 箭頭的位置（2026-09-25 實測），卡片就會出現在 `^` 上方。使用者要自己在「設定 → 個人化 → 工作列 → 其他系統匣圖示」打開。
- ⚠️ DPI：Qt 6 預設 Per-Monitor v2，系統匣回呼座標、`GetRect` 都是實體像素；**外部測試腳本沒設 DPI aware 的話拿到的是虛擬化座標**（125% 時差 1.25 倍）。
- 已驗證（P2）：啟動→三家抓取→圖示登錄、右鍵選單「立即刷新」會重抓、`WM_CLOSE` 正常退出（exit 0、視窗銷毀）。
- **P3 卡片**：`NIN_POPUPOPEN` 或點一下圖示（`NIN_SELECT`）→ 開；**關閉不靠 `NIN_POPUPCLOSE`**（滑鼠從圖示移到卡片途中就會收到 CLOSE），改成每 150ms 看滑鼠，離開「圖示矩形＋卡片（外擴 6px）」超過 0.4 秒才關。位置：`Shell_NotifyIconGetRect`（實體像素）→ 換算成該螢幕的邏輯像素 → 依圖示落在可用區域哪一側判斷工作列方向（上下左右／inside＝溢位面板或自動隱藏）→ 貼著圖示朝內、夾在可用區域內。取不到圖示位置時用事件的錨點座標。深淺色跟系統（`styleHints().colorScheme()`）。進度條＝剩餘、顏色門檻與圖示共用（`icon.level_for`）；stale 區塊整塊變灰、右上顯示「n 分鐘前」；檔案來源已歸零的視窗倒數顯示「已重置」；右上平常顯示方案（`team`、`GrokPro`）；API 失敗退回本機資料時顯示警示。
- 已驗證（P3）：實際送 `NIN_POPUPOPEN` → 卡片出現在 `^` 上方、貼齊工作列（截圖看過），滑鼠不在上面 1.4 秒後確認已關閉；也收到過使用者真實 hover 的 `popup_open`/`popup_close`。**多螢幕、工作列在其他邊、非 125% DPI 只有單元測試，沒實機測**。
- **P4**：
  - 過期偵測：API 失敗／token 過期時 `model.carry_over` 保留上一次的視窗（狀態維持 `auth_expired`/`error`、`fetched_at` 用上次成功的時間），卡片整塊變灰＋「n 分鐘前」＋失敗原因；期間過了重置時間照樣歸零。睡眠喚醒（`WM_POWERBROADCAST`）10 秒後重讀 Claude 本機快取。
  - 通知（`alerts.py`）：剩餘 < 10%（＝卡片進度條變紅）時用 `NIF_INFO` 發 toast（`NIIF_RESPECT_QUIET_TIME`），點通知開卡片。**每個視窗每個重置週期只一次**：鍵＝`provider|label|resets_at`，記在 `%LOCALAPPDATA%\ai-quota-tray\state.json`（重開不重複；重置時間過了自動清掉；壞檔直接覆寫）。只看 `ok`/`stale`，失敗後保留的舊數字不發。
  - 右鍵選單（業主要求保持乾淨）：立即刷新／設定…／開機時啟動／關閉。
  - 設定視窗（`settings.py`，非模態、只開一個）：標題「AI Usage Meter · 服務設定」，只提供服務啟用勾選和語言選擇；資料來源由各 provider 固定決定。來源說明收在可展開區。預設只啟用 Claude、Codex；未啟用的服務不抓取、不顯示、不發通知。底部有自家「萌寵桌面精靈／Taskbar Buddy」中英文廣告橫幅，素材取自官網 repo，僅點擊時開啟 Microsoft Store 商品頁。設定存於 `%LOCALAPPDATA%\ai-quota-tray\config.json` 的 `enabled`／`language`，舊 `token_sources` 在下次儲存時移除。
  - 開機啟動（`startup.py`）：切換 HKCU `Run` 機碼的 `AiQuotaTray` 值；寫入目前的啟動方式（venv → `pythonw.exe -m ai_quota_tray tray`；打包版 → `AiQuotaTray.exe tray`），不帶 `--debug`/`--log`。⚠️ MSIX 無效，上線要改 `startupTask`。
  - 打包（`packaging/`）：`launch.py` 當進入點（`__main__.py` 是相對 import）；⚠️ 必須 `--paths .`，否則 editable 安裝的套件 PyInstaller 追不到，exe 一啟動就 `ModuleNotFoundError`，windowed 版會卡在錯誤對話框。打包後刪 `opengl32sw.dll`（20 MB）與 Qt `translations`。⚠️ `build.ps1` 有中文，**必須存成 UTF-8 with BOM**（PowerShell 5.1 會把無 BOM 當 cp950）。打包版不帶參數直接雙擊＝`tray`（啟用服務照 config.json）。Copilot SDK 要 `--copy-metadata github-copilot-sdk`（它從套件 metadata 讀自己的版本號，沒帶會變 `0.0.0.dev0`）；SDK 帶進 pydantic／httpx，整包約 91 MB（2026-09-26 第一次記成 110.5 MB 是錯的：那次 `opengl32sw.dll` 20 MB 沒刪掉，刪除指令設了 SilentlyContinue 所以沒報錯），runtime（111 MB）不在包裡、執行時才下載。2026-09-26 打包版實測：啟動只讀本機、hover 後四家都抓到、卡片截圖（PrintWindow）正常、廣告 webp 有 `qwebp.dll`；查完 Copilot runtime 與 agy 都會結束，只有 Codex App Server 三層常駐，關閉程式後全部清掉。
  - 已驗證：unittest 55 過（含 `MenuTest`：真的走 `_on_tray_event("context_menu")` → `handle_menu`；`SettingsDialogTest`）；實跑發出 Grok 8% 通知並寫進 state.json；venv 版與打包版都實跑過右鍵選單截圖＋三家抓取；實際從右鍵開設定視窗截圖看過；exe 圖示取出來看過。**toast 畫面本身沒截到、睡眠喚醒沒實測、開機啟動只測了暫用機碼**。
  - 🔴 教訓（2026-09-25）：P4 用「字串替換」插入 `_context_menu` 時比對到**第一個** `def shutdown`（`Poller` 的），方法進了錯的類別 → 右鍵一按 `AttributeError`（被 `_proc` 吞掉只寫 log，畫面上就是「右鍵沒反應」），當時的測試都沒走到選單。改 `app.py` 要用能看到上下文的編輯方式，選單相關改動要跑 `MenuTest`。
- 狀態值比 §2 多一個 `disabled`（歷史相容狀態）。`ProviderState` 另有 `source` / `error` / `raw`（raw 只給 probe）。
- 檔案來源規則（`model.apply_file_freshness`）：`resets_at` 已過的視窗 → `used_pct=0`、`resets_at=None`、記進 `detail.rolled_over`；資料 > 15 分鐘或有歸零 → `stale`。
- **P5（2026-09-25）加 Antigravity CLI、GitHub Copilot**，預設不啟用（細節見 §3）。Copilot 透過官方 Python SDK 的 `account.getQuota`，使用 Copilot CLI 登入；Antigravity 執行官方 `agy -p /usage --output-format json`，由 agy 自己處理登入。額度不是固定長度的視窗 → Copilot 用 `make_window(label=...)`；Antigravity 依 agy 的群組顯示。卡片：Copilot unlimited 顯示「無上限：…」；全部沒勾選時顯示「沒有啟用任何服務…」；Antigravity 未登入提示先用 agy 登入。
- **介面中／英切換（2026-09-25，業主要求）**：`i18n.py` 集中所有畫面文字（`STRINGS = {key: (繁中, English)}`、`tr(key)`）。設定視窗左下角「語言」下拉：跟隨系統／繁體中文／English，存 `config.json` 的 `language`（`auto`／`zh-TW`／`en`，預設 auto：Windows 介面語言是中文 → 繁中，其他 → English）。在下拉切換會**整個設定視窗立刻換語言預覽**（`tr(key, lang)`，不動全域），按儲存才套用到選單、卡片、通知、tooltip；只換語言不重抓。⚠️ **視窗 label 在資料裡一律維持中文**（週／月／進階／補全…），只在顯示時 `i18n.window_label` 翻——通知去重鍵含 label，切語言不能讓同一週期再通知一次。provider 的錯誤細節（`state.error`）是除錯用、不翻。`i18n` 模組預設繁中、只有 `run()` 依設定切換，所以既有測試不受本機語言影響；改英文的測試要 `addCleanup(i18n.set_language, "zh-TW")`。QMessageBox 的是／否按鈕字自己給（打包版刪了 Qt 翻譯檔）。卡片進度條改成 60–110px 可縮（英文 “Completions” 會把第一欄撐寬，原本固定 110 會讓 % 壓到條上）。

- **Claude 狀態列擷取安裝器（2026-09-26，`claude_hook.py`）**：Claude 的資料原本只靠業主自己寫的 Node hook（`D:\FISH\tools\claude-monitor\statusline-usage.js`），一般使用者沒有 → Store 版 Claude 會永遠沒資料。設定視窗 Claude 那列加「安裝／移除」按鈕，**按下立刻執行、先跳確認**（改的是 Claude Code 的 `~/.claude/settings.json`，不是我們的設定）。做法：
  - hook 是 PowerShell 腳本 `~/.claude/ai-quota-tray/statusline.ps1`（不用 Node：官方安裝程式裝的 Claude Code 不一定有 Node），把 stdin 的 `rate_limits` 存成 `~/.claude/usage-cache.json`（跟 Node 版同格式），再**照常執行使用者原本的狀態列**、印出它的輸出。原本的 statusLine 存在 `original-statusline.json`（移除時原樣還原，padding／refreshInterval 等欄位保留），指令本身另存 `original.sh`／`original.ps1`：環境有 `MSYSTEM`（Claude Code 經 Git Bash 呼叫）就用 bash 跑 .sh，否則用 PowerShell 跑 .ps1——跟官方文件「有 Git Bash 用 Git Bash，沒有用 PowerShell」一致。
  - 🔴 踩過的坑（都有測試）：①指令字串不能直接當參數丟給 bash，PowerShell 5.1 會吃掉參數裡的雙引號、反斜線路徑跟著被 bash 吃光 → 存成檔案讓 shell 自己讀；②PowerShell 5.1 轉手 stdin 給子程式會在開頭加 BOM，Node 的 `JSON.parse` 直接失敗 → `original.ps1` 自己讀 stdin、去 BOM、用無 BOM UTF-8 轉交；hook 本身也 `TrimStart(0xFEFF)`；③帶引號的路徑在 PowerShell 是字串不是指令 → 加 `&`；④💡 從 Git Bash 啟動的任何 Windows 程式都會被塞回 `MSYSTEM`（`env -u` 也沒用），要測「沒有 Git Bash」的路徑得從 PowerShell 起。
  - 檔案放 `~/.claude/` 不放 App 目錄：MSIX 解除安裝不能跑清理程式，殘留的指令仍指向還在的腳本，使用者原本的狀態列照常運作。設定檔寫之前備份成 `settings.json.ai-quota-tray.bak`；讀不懂（例如有註解）就整個不動（`UNREADABLE`，按鈕隱藏）。業主自己的 Node hook 會被認成 `LEGACY`（已相容，按鈕隱藏）。
  - 效能：PowerShell 5.1 空跑 `-File` 就要約 0.7 秒，hook 整體 1～2 秒（腳本本身只 0.24 秒，其餘是載入與 Defender 掃描），Node 版約 0.25 秒。官方文件說狀態列指令太慢會被新的更新取消；Claude Code 是變動停 300ms 後才跑、數字只在每次回應後變，判斷可接受。✅ 2026-09-26 業主同意後裝進業主真正的 `~/.claude/settings.json`（串接原本的 Node hook）實測：2 分鐘內 Claude Code 呼叫 8 次、每次約 0.15～1.6 秒（每 0.1 秒抽查的估計）、快取持續更新且 tray 讀得到、沒有殘留行程或暫存檔、其他 17 個設定欄位不變；業主決定保留新 hook。💡 業主這台現在是 `INSTALLED`（不再是 `LEGACY`），設定裡的按鈕會顯示「移除」。
  - 卡片：沒有快取時 Claude 顯示「還沒有資料：到設定安裝 Claude 狀態列擷取，再用一下 Claude Code」（`detail.needs_hook`），不再是 `FileNotFoundError`。
- **示範模式（2026-09-26，`demo.py`）**：給 Store 審核人員（他們的電腦沒有任何 CLI，正常模式只會看到一排「沒有資料」，容易被判 App 沒功能）。設定視窗左下「示範模式」勾選，存 `config.json` 的 `demo`（預設關）。開著時：不查詢任何服務、不下載 Copilot runtime、不發通知，四家一律顯示固定範例（涵蓋綠／黃／紅與「約」），卡片頂端紅字「示範模式・以下為範例資料，不是你的額度」；關掉時照常讀一次本機紀錄。

- **MSIX 打包（2026-09-26）**：`packaging/pack_msix.py`（先跑 build.ps1 → 複製 `dist\AiQuotaTray` 到 `build\msix\stage` → Pillow 從 `app.png` 產磚塊／工作列圖示（含 targetsize-16～256 的 unplated）→ makepri（去掉 `<packaging>` 免得英文被拆包，dump 逐字串核對）→ makeappx）＋`packaging/msix/AppxManifest.xml` 樣板，流程照 desk-pet 的 `scripts/pack-msix.mjs`。`--register` 做 loose registration（開發者模式、免簽章、就地參照 stage）。Identity 預設是佔位值 `FishZero.AIQuotaTray`／`CN=FishZero`，正式值用 `AIQT_MSIX_IDENTITY`／`AIQT_MSIX_PUBLISHER`／`AIQT_MSIX_PUBLISHER_DISPLAY`（環境變數或 gitignore 的 `.env.local`）覆蓋。✅ 2026-09-26 已在 Partner Center 保留「AI Usage Meter」：Store ID `9PLDWKRFDGDC`、Identity `Fish-Zero.AIUsageMeter`、Publisher `CN=4319650D-F7B6-45CE-AADC-75DF43C84A99`、顯示名稱 `Fish-Zero`、PFN `Fish-Zero.AIUsageMeter_40s82rc19mztm`（都是會出現在公開套件裡的值，不是機密；本機 `.env.local` 已填）。⚠️ 保留後三個月內要送審，否則名稱會被釋出（期限約 2026-12-26）。💡 從 Git Bash 跑要加 `PYTHONIOENCODING=utf-8`，否則 cp950 印不出 ▶ 直接 `UnicodeEncodeError`。產出 `build\msix\AiUsageMeter-0.1.0.0-x64.msix` 約 47 MB（dist 資料夾約 99 MB）。檔名 2026-09-26 起用產品名（Store 只看 manifest 的 Identity，檔名給人看）；exe 仍叫 `AiQuotaTray.exe`，但嵌了版本資訊（`packaging/version_info.py` 由 build.ps1 產生 `buildersion_info.txt` → `--version-file`，ProductName／FileDescription＝AI Usage Meter、版本號讀 pyproject），工作管理員的描述欄才不是空的；`VersionInfoTest` 守著。
  - 開機啟動：`startup.py` 分兩條路，有套件身分（`GetCurrentPackageFullName` ≠ 15700）就用 WinRT `StartupTask`（`winrt-Windows.ApplicationModel`，TaskId `AiQuotaTrayStartup` 要與 manifest 一致，`test_msix` 會檢查），否則 HKCU `Run`。使用者在 Windows 設定關過（`DISABLED_BY_USER`）App 不能自己打開 → `StartupBlocked`，右鍵選單跳通知教他去「設定 → 應用程式 → 啟動」。有套件身分時不呼叫 `set_app_id`（ID 由套件決定）。
  - 新 `startup` 子命令（`status`／`on`／`off`，`--out FILE`）給 MSIX 實測用：`Invoke-CommandInDesktopPackage -PackageFamilyName <PFN> -AppId AiQuotaTray -Command <stage>\AiQuotaTray.exe -Args "startup on --out <檔案>"` 就能以套件身分驗證（結果檔別放 AppData 底下，會被重導）。
  - ✅ 2026-09-26 loose registration 實測：套件身分偵測正確、打包版的 winrt 能用、StartupTask 出廠 DISABLED → on 變 ENABLED → off 變 DISABLED；以套件身分跑 tray＋模擬 hover，**四家都抓到**（Codex 的 `codex.CMD`→node、agy、Copilot SDK 在套件裡都叫得動）；開始功能表出現「AI Quota Tray」（改名前）。`%LOCALAPPDATA%` 是讀穿：設定與 Copilot runtime 都讀到原本位置的那份。🔴 **更正（2026-09-26 第二次實測）**：修改**已經存在**的 `%LOCALAPPDATA%i-quota-tray\config.json` 時，寫入的是**真正的那一份**，不是 `Packages\<PFN>\LocalCache`（封裝版存了 `welcomed` 之後，LocalCache 底下沒有 ai-quota-tray、真正的 config.json 多了 `welcomed`）。所以同一台電腦上 Store 版與個人版**共用同一份設定**，不是「之後各改各的」；只有新建立的檔案才可能被重導（推測，沒測）。💡 從 PowerShell 用 `Add-Type` 宣告的 `FindWindow` 傳 `$null` 送 `WM_CLOSE` 沒送到，改用 Python ctypes 才正常（不是 App 卡住）。
  - 還沒做：從開始功能表真人啟動、StartupTask 真的開機跑一次、套件內的寫入（存設定）。
  - WACK（2026-09-26 第一次，業主在管理員視窗跑；指令：`Add-AppxPackage -Register <stage>\AppxManifest.xml` → `appcert reset` → `appcert test -packagefullname <PFN> -reportoutputpath build\msix\wack-report.xml` → `Remove-AppxPackage`，⚠️ 管理員視窗會切到本機的系統管理員帳號（不是業主平常的帳號），註冊與 WACK 要在同一個視窗做完）：總結果 `WARNING`。兩個 FAIL 都是 `OPTIONAL="TRUE"`、不影響總結果：「封鎖的可執行檔」（Python／Qt／OpenSSL DLL 內含 cmd、CreateProcessW 字串，desk-pet 也有）、「封存檔案」（dateutil 附帶的 zoneinfo tar.gz）。拉成 WARNING 的是 DPIAwarenessValidation：Qt 在執行時才設 PerMonitorV2，WACK 靜態看不到 → 加 `packaging/app.manifest`（build.ps1 的 `--manifest`）。⚠️ 自己給資訊清單時 PyInstaller 不再用它的預設清單，trustInfo／supportedOS／longPathAware 要自己抄進去（第一次漏掉，grep exe 才發現）；⚠️ XML 註解裡不能有 `--`。重打後實跑：視窗 awareness＝per-monitor、log 無 DPI 警告、WM_CLOSE exit 0；`ExeManifestTest` 守著。✅ **重跑 WACK：`OVERALL_RESULT="PASS"`**（2026-09-26 13:16，24 項 22 PASS，剩兩個 optional FAIL）。💡 `appcert test` 遇到報告檔已存在不會覆蓋、也不會寫新的，重跑前要先把舊的 `wack-report.xml` 移走（第一次重跑就因此白跑）。

- **啟動時的可見回應（2026-09-26，為了 Store 審核）**：App 沒有主視窗，原本從開始功能表啟動後畫面上什麼都沒出現、已在執行時再點一次新行程直接結束，審核人員會以為沒啟動。現在：①第一次啟動跳歡迎通知（`welcome.*` 字串，只一次，config 的 `welcomed`；在 `run()` 觸發而不是 `TrayApp` 建構式，免得測試寫到真的設定檔），**不帶 `NIIF_RESPECT_QUIET_TIME`**（全新電腦登入後第一小時是 quiet time，審核 VM 會碰到；這則是回應使用者自己的動作）；②已在執行時再啟動一次 → `win32tray.activate_running_instance()` 用 `FindWindowW(AiQuotaTrayWindow)`＋`RegisterWindowMessage("AiQuotaTray.Activate")` 請原本那份打開卡片，新行程 exit 0；③點通知或 activate 打開的卡片先停留 `HOLD_OPEN_S`（8 秒），滑鼠進過卡片或圖示後回到 0.4 秒規則（否則滑鼠在開始功能表那邊，卡片一開就被關掉）。`tests/test_launch.py`（含真的建隱藏視窗、真的 PostMessage；測試會換掉 `CLASS_NAME`，免得送到本機正在跑的那份）。實測：venv 版（`LOCALAPPDATA` 指到暫存）與封裝版（loose registration、從 `shell:AppsFolder\<PFN>!AiQuotaTray` 啟動＝開始功能表的路徑）都截圖看過；封裝版通知的來源顯示「AI Usage Meter」，venv／打包版 exe 顯示 AUMID `AiQuotaTray.App`（個人版才有，沒處理）。

### 下一版（v0.2）規劃（業主 2026-09-26 定）

1. **Store 版「發現新版本」提示**（照 desk-pet `src-tauri/src/store_update.rs` 的做法，見 `desk-pet/docs/store-listing.md` 的「Store 版的『有新版』提示」）：
   - 有套件身分時用 WinRT `StoreContext.GetAppAndOptionalStorePackageUpdatesAsync()`（`winrt-Windows.Services.Store`）問 Store；個人版（沒有套件身分）不查。
   - 有新版 → 系統匣通知「發現新版本」（點通知開設定）；設定視窗右上角多一顆「**版本可更新**」按鈕，直接開 `ms-windows-store://pdp/?productid=9PLDWKRFDGDC`，使用者在 Store 按更新。沒有新版時按鈕不顯示。
   - 設定視窗標題加版號：`AI Usage Meter · 服務設定（Ver. 0.1.0.0）`（業主給的示意圖）。版號有套件身分時取 `Package.Current.Id.Version`，否則讀 pyproject／`__version__`，四段式與 MSIX 一致。⚠️ `test_p4`／`test_i18n` 有測試逐字比對視窗標題，要一起改。
   - desk-pet 實測的限制：API 拿到的 `Package.Id.Version` 是**已安裝版**，拿不到新版版號 → 文字一律寫「發現新版本」不寫版號；Partner Center 的「強制更新」OS 不會強制也不會提示；更新時 App 可能被關掉、裝完不保證重開（開機啟動下次登入會帶回來）。
   - 通知別吵：每次啟動最多提示一次（拿不到新版版號，無法「每個版本一次」）。查詢頻率先定啟動時＋每 6 小時（desk-pet 是 25 分鐘，這個 App 不需要那麼勤）。
   - 🔴 **隱私權政策與商店文案要一起改**：現在寫「App 自己不會連到任何伺服器」，檢查更新會連 Microsoft Store 的服務（只問有沒有更新、不送個人資料）。fish-zero-web 的兩份政策、`docs/site/` 副本、`docs/store-listing.md` 的說明與 runFullTrust 說明都要補一句。
   - 🔴 **這功能要等帶著它的那一版裝到使用者手上，才能提示再下一版**：v0.1 的使用者只能靠 Store 自己的自動更新升到 v0.2。
2. **設定視窗底部加「隱私權政策」「官網」連結＋無隸屬聲明**（業主 2026-09-26 同意）：放在版號旁邊，兩個小連結分別開 `https://fish-zero.com/aiusagemeter-privacy`／`https://fish-zero.com/aiusagemeter`（英文介面開 `/en/…`），再一行小字「非 Anthropic／OpenAI／GitHub／Google 官方產品」（中英文走 `i18n.py`）。
   Store 政策 7.20 的 10.5.1 只要求 Partner Center 填政策網址，App 內連結是「may」——做這個不是為了過審，而是：加回 Grok（讀 token 的例外）時使用者要點得到政策、App 畫面直接顯示各家產品名要有無隸屬聲明、使用者找得到支援信箱。
   ⚠️ 設定視窗目前的外部連結只有桌寵橫幅（`STORE_URL`），多了這兩個要一起寫進隱私權政策 §3「其他連線」，也要進 `store_shots.py` 重拍的截圖。
3. **xAI（Grok）**：看回信決定（見上方 📨）。
4. ✅ 已先做（2026-09-26，會跟 v0.2 一起出去）：設定視窗的語言下拉改成整塊圓角＋自己的 SVG 箭頭（`assets/chevron-down-{dark,light}.svg`），原本右邊是 Windows 原生的方塊下拉鈕、凸出一截；寬度改成依內容（寫死 108px 時英文「System default」被切掉）。

**下次開工：MSIX 上線版**（業主 2026-09-25 收工時說下次再處理；細節見 §5）

> ⏸️ **2026-09-26 收工時的狀態**：v0.1.0.0 已送 Microsoft Store 認證（Submission 1，明細 `docs/store-listing.md` §0.5），等結果；送出的套件是 `build\msix\AiUsageMeter-0.1.0.0-x64.msix`（WACK PASS 14:19）。程式與文件都已 push 到 GitHub（`main`），隱私權政策／產品頁在 fish-zero.com 上線（含「沒有第三方廣告」更正）。unittest 141 過。本機沒有任何 MSIX 註冊；個人版平常跑 `dist\AiQuotaTray\AiQuotaTray.exe`，開機啟動（HKCU Run）指向 venv 的 `pythonw.exe -m ai_quota_tray tray`。下一步：等認證結果（退件就照原因修）→ v0.2（上方規劃）。

> 📨 **xAI（Grok）詢問中**：業主 2026-09-26 12:44 寄信給 `sales@x.ai`，問第三方 App 能不能讀 Grok Build CLI 的本機 token、呼叫 `cli-chat-proxy.grok.com/v1/billing` 等端點來顯示使用者自己的用量，或有沒有官方介面可用。業主決定：**回覆 OK 才在下一版加回來**。⚠️ 信裡附的 `blob/main/.../providers/grok.py` 已經 404（P5 `236e126` 刪掉了）；對方要看程式碼時改給固定版本 `https://github.com/Fishforgithub/ai-quota-tray/blob/7376facef447ea03969deed62bfe4aaf9a6a30f2/ai_quota_tray/providers/grok.py`（實測 200）。信裡的產品名是舊的 AI Quota Tray。🔴 **加回來不只是改程式**：隱私權政策、商店說明與功能（「不讀取、不保存登入權杖」）、runFullTrust 說明（「reads no tokens」）、認證注意事項、產品頁都寫死了「不碰 token」，Grok 若仍是讀 token 的做法，這些都要改成「Grok 例外、需使用者自行啟用」並重新送審；若 xAI 給的是官方 API／CLI 指令，就能維持「不碰 token」的說法。

1. ~~先決定散佈管道~~ ✅ 2026-09-26 定案：**Microsoft Store**，公司同事也等 Store 版（業主決定不先發可攜版 zip：未簽章 exe 會跳 SmartScreen、可能被公司政策擋，且開機啟動會記住解壓路徑）。個人版 `dist\AiQuotaTray\` 只給業主自己用；要發給別人的話記得是**整個資料夾**（PyInstaller onedir），不是只有 exe。
2. 上線版**不能由 tray 直接碰 token**（§1 原則 5、§5 政策）：設定視窗已沒有來源切換，Grok 已停用；Codex 走官方 App Server、Copilot 走官方 SDK、Antigravity 走官方 agy CLI。須驗證 MSIX 套件呼叫外部 CLI 與 SDK runtime 的行為。
3. ~~開機啟動改 `windows.startupTask`~~ ✅ 2026-09-26 已做並在 loose registration 實測（見上）。
4. ~~驗證 `%LOCALAPPDATA%` 重導與套件內讀 `.claude`／`.codex`~~ ✅ 讀取正常；修改既有設定檔會寫回真正的位置、與個人版共用（見上）。
5. 名稱與圖示避開 Claude／Codex／Grok／Antigravity／Copilot 商標：顯示名稱集中在 `model.DISPLAY_NAME`；產品名 2026-09-26 定為 **AI Usage Meter**（業主：quota 不直覺）。只換畫面上的名稱；exe、mutex、設定資料夾、Run 機碼、StartupTask ID、hook 資料夾仍是 `AiQuotaTray`／`ai-quota-tray`，舊設定不用搬。Store 已有「AI Limits」（直接競品、會讀 token）與「AI Usage Tracker」；Google Play 有同名 Android App「AI Usage Meter」。
6. 簽章：Store 代簽；sideload 要 Azure Trusted Signing。
7. 還沒實測、上線前要補：toast 畫面、睡眠喚醒重抓、真正寫入 `Run` 的開機啟動、多螢幕／工作列在其他邊／非 125% DPI 的卡片定位、真人點「設定…」時視窗是否在最前面。
8. 送審的「認證注意事項」要寫：右鍵系統匣圖示 →「設定…」→ 勾「示範模式」→ 儲存，再 hover 圖示看卡片（審核人員沒有 Claude Code／Codex 等 CLI）。

**歷史實測結果（本機帳號，2026-09-25；已移除的來源僅供格式參考）**

| Provider | 來源 | 實際視窗 |
|---|---|---|
| Claude | statusLine cache ✅ | 5h + 週。hook 是 `D:\FISH\tools\claude-monitor\statusline-usage.js`，寫 `{"fetchedAt": ms, "rate_limits": {"five_hour": {"used_percentage", "resets_at": 秒}, "seven_day": …}}`（欄位名是 `used_percentage`，不是 API 的 `utilization`） |
| Claude | OAuth API（已移除） | 因條款風險不再實作直接取用。 |
| Codex | rollout / wham API（wham 已移除） | 當時 team 方案有 5h + 週視窗；閒置 4 天的 rollout 週用量落後線上資料。現行改由官方 App Server 取即時額度。 |
| Antigravity | agy CLI ✅ | **打通**（2026-09-26）：使用 `agy -p "/usage" --output-format json`（非互動 print 模式預設展開 slash command，不消耗模型 token：`total_tokens: 0`）。回傳 `command.data.groups`，包含 Gemini（Gemini Flash/Pro 共用池）與 Claude/GPT（Claude Opus/Sonnet、GPT-OSS 共用池）兩大每週視窗。完全不需要碰 Windows 認證管理員或打報 403 的 Google Cloud Code PA API。 |
| Grok | billing API ✅ | **只有週視窗**（GrokPro）。`config` 包一層；`currentPeriod` 有 `type`/`start`/`end`（ISO，`+00:00`），`start→end` 正好 604800 秒；`creditUsagePercent` 與 `productUsage[GrokBuild]` 同為 92%；`onDemandCap`/`prepaidBalance` 都是 `{"val": 0}`；`isUnifiedBillingUser: true`。月額度 `/billing` 回 `monthlyLimit {"val":0}`、`used {"val":75}` → 依規則**無月視窗**（另有 `history[]` 近三個月）。`/user` 有 `subscriptionTier`、`hasGrokCodeAccess`，也有姓名、xUserId 等個資（`--raw` 已遮）。⚠️ `~/.grok/auth.json` token 效期只有 **6 小時**，Grok CLI 沒開就會 `auth_expired` |

---

## 1. 核心設計原則

1. **視窗不寫死**：三家視窗結構已不同，UI 不得假設「5h + 週」。視窗名稱由實際長度（秒）推導。
2. **只存 `resets_at`（UTC 絕對時間）**，倒數在本地算。抓取頻率與畫面更新頻率分離。
3. **身分驗證交給官方 CLI**：Codex／Antigravity 不由 tray 讀取憑證；Claude 僅讀本機紀錄。Grok／Copilot 目前仍讀取 CLI 憑證，但不自行 refresh。
4. **每個 provider 獨立失敗**：格式變了只影響該區塊（顯示「Grok：格式變了」），整支程式不能掛。
5. **上線版不碰 token**（見 §5）；Grok／Copilot 的發佈取捨仍待決定。

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
- **唯一來源（不碰 token）**：Claude Code statusLine hook 寫入的 `~/.claude/usage-cache.json`。Claude Code 沒在跑時資料會過時。舊 OAuth API 取得程式已移除。

### Codex
- **首選**：啟動官方 `codex app-server`（stdio），完成 `initialize`／`initialized`，呼叫 `account/rateLimits/read`。優先採 `rateLimitsByLimitId.codex`；沒有多額度回傳時採 `rateLimits`。Codex CLI 自行管理登入，tray 不讀 `auth.json`。
- **回退**：App Server 不可用或沒有 Codex 額度資料時，解析 `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` 最近一筆 `token_count.rate_limits`。本機資料可能過時，卡片會顯示回退警示。
- 兩種來源都依實際視窗長度決定 label，略過 null 視窗。舊 `wham/usage` 內部端點已移除。官方協定參考 [Codex App Server](https://learn.chatgpt.com/docs/app-server)。

### Grok（已停用；以下為歷史研究）
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

### Google Antigravity CLI（`agy`）
- 透過 agy CLI 原生非互動指令查詢額度：`agy -p "/usage" --output-format json`（非互動 print 模式會自動展開 slash commands，且 `total_tokens: 0` 不消耗任何模型 token）。
- 不碰 Windows 認證管理員中的 OAuth Token，完全由 `agy` 處理身分驗證與快取，解決了之前打內部 Cloud Code PA API 回傳 403 Forbidden 的問題。
- 回傳結構包含 `command.data.groups`：
  - `Gemini Models`（Gemini Flash/Pro 共用額度池）
  - `Claude and GPT models`（Claude Opus/Sonnet、GPT-OSS 共用額度池）
  - 各池 `buckets` 提供 `remaining_fraction`、`reset_time` 與每週視窗週期。
- Windows 下以 `subprocess.CREATE_NO_WINDOW` 背景執行，不彈出終端機黑視窗。

### GitHub Copilot
- 透過官方 Python SDK 的 `account.getQuota` 查詢帳號額度；tray 不直接讀取 token，也不呼叫舊 `copilot_internal/user` 端點。請先用 `copilot login` 登入。依 SDK 回傳的 `quota_snapshots` 顯示進階／Chat／補全；unlimited 不畫進度條，零額度項目略過。參考 [GitHub Copilot SDK 用量文件](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/usage-and-billing)。

### 輪詢頻率
| Provider | 間隔 |
|---|---|
| Claude | 120 s |
| Codex | 120 s（官方 App Server；失敗時讀本機 rollout） |
| Antigravity | 300 s |
| Copilot | 300 s |

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
- **政策**：上線版資料來源必須全部不碰 token；名稱與圖示避開「Claude / Codex / Grok / Antigravity / Copilot」商標（產品名 AI Usage Meter）。
- 散佈選項：Microsoft Store / 公司內部 App Installer 或 Intune / GitHub 開源（provider 由使用者自行啟用）。尚未決定。

## 6. 開發階段

1. **P1 Provider 驗證**：三個 provider + `probe` 指令，輸出標準化 JSON（token 遮罩）。先確認實際帳號回傳哪些視窗。
2. **P2 系統匣骨架**：Qt 主迴圈、native 系統匣、動態圖示、右鍵選單。
3. **P3 Hover 卡片**：`NIN_POPUPOPEN` / `CLOSE`、定位、倒數。
4. **P4 收尾**：剩餘 < 10% toast 通知、過期偵測、開機啟動、打包。

## 7. 相關既有專案

- `Fishforgithub/claude-codex-usage-dashboard`：Node.js statusLine hook 擷取 quota 的做法，Claude 不碰 token 的來源可沿用。
