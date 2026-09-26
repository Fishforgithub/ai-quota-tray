# Microsoft Store 上架資料（AI Usage Meter）

> 這份只放「Partner Center 要填什麼、怎麼填」。格式與踩過的坑照 desk-pet 的 `docs/store-listing.md`（已在 Store 上架）。
> 欄位上限 2026-09-26 查證自 Microsoft Learn〈Add and edit Store listing info for MSIX app〉；搜尋字詞的上限是 desk-pet 的經驗值。

## 0. 產品身分與連結

| 項目 | 值 |
|---|---|
| Store ID | `9PLDWKRFDGDC`（商店頁上架後才有效：`https://apps.microsoft.com/detail/9PLDWKRFDGDC`） |
| Identity／Publisher | `Fish-Zero.AIUsageMeter`／`CN=4319650D-F7B6-45CE-AADC-75DF43C84A99`（顯示名稱 `Fish-Zero`） |
| 隱私權政策 URL | `https://fish-zero.com/aiusagemeter-privacy`（✅ 2026-09-26 上線，四個網址實測 200） |
| 網站 | `https://fish-zero.com/aiusagemeter` |
| 支援聯絡方式 | `hello@fish-zero.com`（🔴 填**純 email**，填 `mailto:` 會被擋，desk-pet 經驗） |
| 保留期限 | 2026-12-26 前要送審，否則名稱會被釋出 |

## 1. 屬性

| 欄位 | 建議 | 理由 |
|---|---|---|
| 產品型別 | **MSIX app**（已建立，不是 game） | — |
| 類別 | **開發人員工具**（Developer tools），子類別留空 | 使用者就是用 AI 程式開發工具的人 |
| 隱私權：會存取、收集或傳送個人資訊嗎？ | **是**＋上面的政策 URL | App 會讀 Codex 的本機紀錄檔，檔案裡含對話內容（雖然只取額度欄位）。答「否」在審查追問時說不清楚，答「是」並附政策最安全 |
| 定價 | 免費、全球市場 | 沒有內購、沒有廣告 |
| 產品宣告 | 全部**不勾**；若有預設勾選「可用 Windows 錄製與廣播此產品的片段」要**取消**（那項只給遊戲） | desk-pet 經驗 |
| 系統需求 | 最低需求可不填（套件已宣告 Windows 10 1903、x64） | — |

## 2. 商店清單：英文（en）

**Product name**：`AI Usage Meter`

**Short title**（≤50）：`AI usage limits in your system tray`

**Short description**（建議 ≤270，這份約 230）

> See how much of your AI coding tools' usage is left, right from the Windows system tray. Hover the icon for every limit, the percentage left, and when it resets. Your sign-in stays untouched: no tokens read, no data collected.

**Description**（純文字，⚠️ 不可放網址、HTML）

> AI Usage Meter keeps the usage limits of your AI coding tools one hover away.
>
> Each service has its own 5-hour, weekly, or monthly limits, and the worst time to find out is when you have already hit one. AI Usage Meter sits in the Windows system tray. Hover its icon and a small card lists every limit: the percentage left, a progress bar, and a countdown to the next reset.
>
> Supported tools
> Claude Code, Codex, Antigravity CLI, and GitHub Copilot. Claude Code and Codex are on by default; turn on the others in Settings. Each tool must be installed and signed in on your PC.
>
> Your sign-in stays untouched
> AI Usage Meter never reads or stores your passwords or sign-in tokens. When it needs live numbers, it asks the official tool that is already signed in on your computer to look them up. In the background it only reads local records, without using the network, and it checks online only when you open the card.
>
> A heads-up before you run out
> When any limit drops below 10%, you get one Windows notification, and only one per reset period. If a lookup fails or the numbers are out of date, that section turns grey and shows how old it is, so old numbers are never passed off as current ones.
>
> Private by design
> No server of its own, no analytics, no advertising, no account. Nothing is sent to the developer.
>
> Tip: Windows 11 may place new tray icons in the hidden icons area (^). Drag the AI Usage Meter icon onto the taskbar so it is always one hover away.
>
> AI Usage Meter is an independent app and is not affiliated with Anthropic, OpenAI, GitHub, or Google. Product names belong to their respective owners.

**Product features**（每條 ≤200、不要自己加項目符號）

1. Hover the tray icon to see every usage limit at a glance
2. Percentage left, progress bar, and reset countdown for each limit
3. Supports Claude Code, Codex, Antigravity CLI, and GitHub Copilot
4. Never reads or stores your passwords or sign-in tokens
5. Uses each tool's official interface and your existing sign-in
6. One notification when a limit drops below 10%, once per reset period
7. Grey, time-stamped sections when numbers are out of date
8. No server, no analytics, no ads, no account
9. Starts with Windows (optional)
10. English and Traditional Chinese interface

**Search terms**（最多 7 組、各 ≤30，不顯示在頁面上）：
`AI usage`／`usage limit`／`rate limit`／`AI quota`／`system tray`／`developer tools`／`coding assistant`

**Copyright**：`© 2026 Fish-Zero`

## 3. 商店清單：繁體中文（zh-TW）

**產品名稱**：`AI Usage Meter`（中英同名：只保留了這一個名稱，套件的顯示名稱中英文也都是它；微軟建議清單名稱與套件一致）

**簡短標題**（≤50）：`在系統匣看 AI 用量還剩多少`

**簡短描述**

> 在 Windows 系統匣直接看 AI 程式開發工具的用量還剩多少。滑鼠移到圖示上，每個額度的剩餘百分比和重置倒數一次看完。不讀取你的登入權杖，也不收集任何資料。

**說明**（純文字，⚠️ 不可放網址、HTML）

> AI Usage Meter 讓 AI 程式開發工具的用量，滑鼠移過去就看得到。
>
> 每一家都有 5 小時、每週或每月不同的額度，用完了才發現最麻煩。AI Usage Meter 待在 Windows 系統匣裡，滑鼠移到圖示上就會彈出一張小卡片，列出每個額度的剩餘百分比、進度條和下次重置的倒數。
>
> 支援的工具
> Claude Code、Codex、Antigravity CLI、GitHub Copilot。預設啟用 Claude Code 與 Codex，其他的到設定裡勾選。你需要先在電腦上安裝並登入對應的工具。
>
> 不碰你的登入
> AI Usage Meter 不讀取、不保存你的密碼或登入權杖。需要即時數字時，它請你電腦上已經登入的官方工具自己去查。平常在背景只讀本機紀錄、不連網，只有在你打開卡片時才查詢雲端。
>
> 快用完時提醒你
> 任何一個額度剩不到 10%，就用 Windows 通知提醒一次，同一個重置週期不會重複提醒。查詢失敗或資料過時，那一塊會變灰並標示是多久以前的數字，不會把舊數字當成現在的。
>
> 隱私優先
> 沒有自己的伺服器、沒有分析追蹤、沒有廣告，也不需要註冊帳號。不會把任何資料傳給開發者。
>
> 小提醒：Windows 11 可能會把新的系統匣圖示收進隱藏區（^）。把 AI Usage Meter 的圖示拖到工作列上，就能隨時看到。
>
> AI Usage Meter 是獨立開發的 App，與 Anthropic、OpenAI、GitHub、Google 沒有隸屬或合作關係。各產品名稱屬於其權利人。

**產品功能**

1. 滑鼠移到系統匣圖示上，所有額度一次看完
2. 每個額度都有剩餘百分比、進度條與重置倒數
3. 支援 Claude Code、Codex、Antigravity CLI、GitHub Copilot
4. 不讀取、不保存你的密碼或登入權杖
5. 透過各工具的官方介面與你原本的登入查詢
6. 額度剩不到 10% 時通知一次，每個重置週期只通知一次
7. 資料過時會變灰並標示時間
8. 沒有伺服器、沒有分析追蹤、沒有廣告、不需要帳號
9. 可設定開機自動啟動
10. 繁體中文／English 介面

**搜尋字詞**：`AI 用量`／`用量`／`額度`／`系統匣`／`開發人員工具`／`AI usage`／`usage limit`

**著作權**：`© 2026 Fish-Zero`

## 4. 寫法上的決定（下次改文案前先看）

- **產品名稱、簡短標題不放任何一家的產品名**（商標）。說明與功能裡提到 Claude Code 等名稱，是為了說明「相容哪些工具」，並在說明最後加上無隸屬聲明。競品「AI Limits」的商店頁也是這樣寫。
- **搜尋字詞刻意不放 Claude、Codex、Copilot 等產品名**：用別人的商標當搜尋字詞，審查上風險比放在說明裡高；使用者搜這些字時，說明內文仍可能被比對到（推測）。
- **不寫「即時」「隨時更新」**：背景只讀本機紀錄，雲端只在打開卡片時查，寫「即時」會跟隱私權政策與實際行為對不上。
- **不承諾各家都有 5 小時視窗**：額度結構由各服務決定，文案一律寫「5 小時、每週或每月不同的額度」。
- 跟直接競品「AI Limits」（會讀取各工具的登入權杖）的差異就是**不碰登入**，所以放在說明第三段與功能第 4、5 條。
- Windows 11 會把新圖示收進 `^`，卡片會出現在 `^` 上方（CLAUDE.md §0 實測），所以說明裡教使用者把圖示拖出來。

## 5. 受限功能 `runFullTrust` 的用途說明

**填在哪**：提交的「提交選項」頁，紅框必填（desk-pet 經驗：前五步都完成也送不出去，這一項是最後才冒出來的；首發核准過之後，更新就不會再問）。
套件只宣告這一個受限功能（`packaging/msix/AppxManifest.xml` 的 `rescap:Capability`）。填完後「提交選項」仍顯示「未完成」是正常的，要等微軟人工核准。

**要貼的英文**（2026-09-26 照原始碼逐項核對；每一條都對得到程式碼，改到這些行為要回來改這段）

> AI Usage Meter is a Win32 desktop app (Python with Qt, packaged with PyInstaller) that lives in the Windows notification area. It needs full trust for the following:
>
> 1. Notification area icon and hover card: it registers its icon with Shell_NotifyIconW (NOTIFYICON_VERSION_4) to receive hover events, uses Shell_NotifyIconGetRect to place its card next to the icon, TrackPopupMenu for the right-click menu, and balloon notifications (NIF_INFO) for low-usage alerts.
> 2. Reading usage records that other developer tools keep in the user's profile, outside the package: %USERPROFILE%\.claude\usage-cache.json and %USERPROFILE%\.codex\sessions\. Only the usage-limit fields are used.
> 3. Starting official command-line tools that the user installed and signed in to, as child processes: Codex CLI ("codex app-server", over stdin/stdout), Antigravity CLI ("agy -p /usage"), and the GitHub Copilot SDK runtime. These tools handle sign-in themselves; the app never reads their credentials or tokens. When it closes, the app makes sure the Codex processes it started exit: it closes their input first, and uses taskkill /T only if they are still running after 2 seconds.
> 4. Optional, only after the user presses "Install" and confirms: pointing Claude Code's status line setting (%USERPROFILE%\.claude\settings.json, backed up first) to a small script in %USERPROFILE%\.claude\ai-quota-tray\ that saves the usage fields. "Remove" restores the original setting.
> 5. When the user turns on GitHub Copilot, the official Copilot SDK downloads its runtime from GitHub into %LOCALAPPDATA%\github-copilot-sdk.
>
> The app runs as the current user (asInvoker) and never asks for administrator rights. It installs no drivers or services, does not inject into or modify other processes, reads no passwords, tokens, or credential stores, has no server of its own, and sends no data to the developer. Start with Windows uses the windows.startupTask extension.

**中文對照（給業主核對，不用貼）**

> AI Usage Meter 是住在 Windows 系統匣的 Win32 桌面程式（Python＋Qt，用 PyInstaller 打包），以下幾件事需要完全信任權限：
> 1. 系統匣圖示與懸停卡片：`Shell_NotifyIconW`（VERSION_4）收 hover 事件、`Shell_NotifyIconGetRect` 把卡片放在圖示旁、`TrackPopupMenu` 右鍵選單、`NIF_INFO` 低額度通知。
> 2. 讀取其他開發工具放在使用者資料夾（套件外）的用量紀錄：`.claude\usage-cache.json`、`.codex\sessions\`，只用額度欄位。
> 3. 以子程序啟動使用者自己安裝、登入的官方 CLI：`codex app-server`（stdin/stdout）、`agy -p /usage`、Copilot SDK runtime。登入由它們自己處理，本 App 不讀它們的憑證或權杖；關閉時先關掉 Codex 的輸入讓它自己結束，2 秒後還在才用 `taskkill /T` 結束自己啟動的程序樹。
> 4. 選用，使用者按「安裝」並確認後才做：把 Claude Code 的狀態列設定（先備份）指向 `.claude\ai-quota-tray\` 裡的小程式，只存額度欄位；按「移除」還原。
> 5. 使用者啟用 Copilot 時，官方 SDK 會從 GitHub 下載 runtime 到 `%LOCALAPPDATA%\github-copilot-sdk`。
>
> 以目前使用者身分執行（asInvoker）、不要求系統管理員；不裝驅動或服務、不注入或修改其他程序、不讀密碼／權杖／認證存放區、沒有自己的伺服器、不傳資料給開發者。開機啟動走 `windows.startupTask`。

**對照的程式碼**：①`win32tray.py`、`placement.py` ②`providers/claude.py`、`providers/codex.py` ③`codex_app_server.py`（`shutil.which("codex")`、`_kill_tree`）、`providers/antigravity.py`、`providers/copilot.py` ④`claude_hook.py` ⑤`providers/copilot.py` 的 `start_prepare` ⑥`packaging/app.manifest`（asInvoker）、`startup.py`（StartupTask）。

## 6. 給審核人員的認證注意事項

**填在哪**：左側「補充資訊」→「其他測試資訊」（產品層級，不跟著提交走；desk-pet 經驗）。不需要測試帳號，⚠️ 也不要把任何帳號資訊寫進這裡或商店描述。

**為什麼一定要寫**：
- 審核人員的電腦上不會有 Claude Code、Codex 等 CLI，正常模式下卡片只會顯示「還沒有資料」或查詢失敗，很容易被判成「App 沒有功能」→ 要教他開示範模式。
- **App 沒有主視窗**：從開始功能表啟動後只會在系統匣加一個圖示，Windows 11 預設還會把它收進 `^`；已經在執行時再啟動一次會直接結束、畫面上什麼都沒有（`app.run()` 的單一實例檢查）。不寫清楚，審核人員可能以為 App 沒啟動。

**要貼的英文**（按鈕與選單文字照 `i18n.py` 的英文字串，審核機若是英文介面就會一模一樣）

> AI Usage Meter has no main window. After you start it, it adds an icon to the notification area (system tray). On Windows 11 the icon may first appear in the hidden icons area: click the ^ arrow on the taskbar to find it. Starting the app again while it is already running does nothing visible.
>
> The app shows the usage limits of AI coding tools (Claude Code, Codex, Antigravity CLI, GitHub Copilot) that are installed and signed in on the same PC. A test machine won't have these tools, so the card would only say there is no data yet. To review the full interface without any of them, please use the built-in demo mode:
>
> 1. Right-click the tray icon and choose "Settings…".
> 2. Check "Demo mode" at the bottom left and press "Save".
> 3. Hover the mouse over the tray icon (or click it once). A card opens with sample data for all four services: percentage left, progress bars in green, yellow, and red, and reset countdowns. A red line at the top of the card says "Demo mode: sample data, not your actual quota".
>
> In demo mode the app makes no queries and starts no other tools. No sign-in or account is needed, and there are no in-app purchases.
>
> Other things to try: the right-click menu also has "Refresh now", "Start with Windows", and "Quit". The Settings window switches the interface language between English and Traditional Chinese.

**中文對照（給業主核對，不用貼）**

> AI Usage Meter 沒有主視窗。啟動後會在系統匣加一個圖示；Windows 11 可能先把它放在隱藏圖示區，點工作列的 ^ 就找得到。已經在執行時再啟動一次，畫面上不會有任何變化。
>
> 這個 App 顯示同一台電腦上已安裝並登入的 AI 程式開發工具的用量。測試機不會有這些工具，卡片只會顯示還沒有資料。要在沒有這些工具的情況下看完整介面，請用內建的示範模式：
> 1. 在系統匣圖示按右鍵，選「設定…」。
> 2. 勾選左下角的「示範模式」，按「儲存」。
> 3. 滑鼠移到系統匣圖示上（或點一下）。會彈出四個服務的範例資料卡片：剩餘百分比、綠／黃／紅進度條與重置倒數，卡片頂端有一行紅字「示範模式・以下為範例資料，不是你的額度」。
>
> 示範模式下不查詢任何服務、不啟動其他工具。不需要登入或帳號，也沒有內購。
>
> 其他可以試的：右鍵選單還有「立即刷新」「開機時啟動」「關閉」；設定視窗可以切換中英文介面。

⚠️ 改到右鍵選單、設定視窗的按鈕文字、示範模式的行為或提示字時，這段要一起改。

## 7. 還沒做

- 截圖（至少 1 張、建議 4 張，`.png`、最小 1366×768；⚠️ 每種語言的截圖要是那個語言的介面，desk-pet 經驗：英文清單配中文截圖會被退件）
- Store 標誌、IARC 年齡分級問卷
