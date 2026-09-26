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

## 0.5 Submission 1 進度（2026-09-26 由 AI 代填）

提交 ID `1152921505701980551`。

| 步驟 | 狀態 | 內容 |
|---|---|---|
| 定價和供應狀況 | ✅ 已存 | 基本價格 **TWD 0**（免費）、全球所有市場、公用對象、可搜尋、發行「盡快」（重新載入確認過） |
| 屬性 | ✅ 完成 | 類別**開發人員工具**／子類別**公用程式**、隱私「是」＋政策 URL、網站、支援 `hello@fish-zero.com`；產品宣告**取消**預設勾選的「錄製與廣播」（只給遊戲），「可裝到其他磁碟」「OneDrive 備份」維持預設勾選；**不勾**生成式 AI（App 不產生內容） |
| 年齡分級 | ✅ 已存 | 類型「所有其他應用程式類型」、9 題全「否」、實體媒體「否」→ IARC 全域 **3+**、ESRB 所有人、PEGI 3+、USK 所有人、巴西／智利／俄羅斯所有年齡。分級識別碼 `4d370a4a-64ae-8232-8d00-3f9b9fdb6e1e`。🔴 儲存前要勾「同意 IARC 使用規定、已達成年年齡」——同意條款＋本人聲明，**AI 不代勾**，業主自己勾的 |
| 套件 | ✅ 完成 | 業主人工拖 `AiUsageMeter-0.1.0.0-x64.msix`（加版本資訊那版，WACK PASS 14:19），狀態 Validated；帶進 `zh-TW`／`en` 兩個語言 |
| Store 清單 | ✅ 完成 | 中英文各：說明、10 條功能、3 張截圖（桌面）、1:1 應用程式磚圖示 300×300、簡短描述、7 個關鍵字、著作權 `© 2026 Fish-Zero`、開發者 `Fish-Zero`。**簡短標題留白**（見 §4） |
| 提交選項 | ✅ 維持預設 | 「通過認證後立即發佈」。⚠️ **runFullTrust 說明欄沒有出現**（desk-pet 2026-09 首發時是紅框必填）：可能流程改了、也可能按「提交以進行認證」才跳出來——跳出來就貼 §5 的英文 |
| 其他測試資訊 | ✅ 已存 | §6 的英文全文（1,462 字，重新載入確認過）。💡 這頁的 textarea 用 JS 設值不會被存，要真的點進去用鍵盤打 |

💡 **這次代填踩到的**：①截圖的檔案上傳欄位會「換位子」——同一個參照有時是「＋」空格、有時變成替換第一張，還有一次跑進 Xbox 分頁；每傳一張就看分頁上的「桌面 (n)／Xbox (n)」計數，錯了就刪掉重傳。②關鍵字每組打完按 Enter 變成標籤，最後輸入框會殘留一段文字，要清掉；頁面會跳出 AI 建議關鍵字，不採用。③關鍵字的實際限制是**最多 7 個、每個 ≤40 字元、所有關鍵字加起來 ≤21 個單字**（跟 desk-pet 記的「各 ≤30」不同，以畫面為準）。④textarea 用 JS 設值不會被存，要真的點進去打字（中文也能直接打）。

IARC「線上內容」題（「是否提供或推廣不屬於初始下載、但可從 App 存取的內容，例如 Netflix 的電影、Amazon 的商品、生成式 AI 內容」）答**否**：卡片顯示的是用量數字，不是這類內容；設定視窗的自家推廣橫幅屬於廣告，而問卷開頭明寫「回答時不應該考慮廣告內容」。

## 0.6 Submission 2：0.1.1.0（2026-09-26）

v0.1.0.0 送審不到一小時就通過並上架（Submission 1）。業主決定首波就要有下面這些功能 → 維持上架、馬上送 0.1.1.0 更新（Partner Center 同時只能有一份提交，暫時下架反而要多送兩次）。

**這一版改了什麼**：系統匣圖示霓虹外圈旋轉（一律開著，鎖定／螢幕關閉／省電／Windows 關動畫時自停；業主決定不給開關）、Store 版「發現新版本」通知＋設定右上「版本可更新」（直通 Store）、設定標題顯示版號、設定底部隱私權政策／官網連結＋無隸屬聲明、語言下拉改圓角、exe 版本資訊、MSIX 檔名改用產品名。
**要一起更新的**：隱私權政策（檢查更新、兩個新連結；fish-zero-web）、商店說明與功能（下面 §2／§3 已改）、截圖（設定視窗變了，`store_shots.py` 重拍）、其他測試資訊（§6 的英文已改，要重貼）。

**代填狀態（2026-09-26）**：提交 ID `1152921505701981084`。套件換成 `AiUsageMeter-0.1.1.0-x64.msix`（WACK PASS 16:02；舊的 0.1.0 被標成移除，⚠️ 要在套件頁**再按一次 Save** 才真的移除）；中英文清單的說明、12 條功能、此版本新增功能、第 3 張截圖已換；其他測試資訊（產品層級）已補最後一段。runFullTrust 欄位仍沒出現。剩業主按「提交以進行認證」。

**此版本的新增功能**（What's new，≤1500 字元）

> English：
> - The ring around the tray icon now slowly rotates, and pauses on its own when the screen is locked or off, in battery saver, or when Windows animation effects are turned off.
> - You get a notification when a new version is available, and Settings shows an "Update available" button that opens the Microsoft Store.
> - The Settings window shows the version number and links to the privacy policy and website.
> - A cleaner language menu in Settings.

> 繁體中文：
> - 系統匣圖示的霓虹外圈會慢慢旋轉；鎖定畫面、螢幕關閉、省電模式，或 Windows 關掉「動畫效果」時會自動停下。
> - 有新版本時會通知你，設定視窗也會出現「版本可更新」按鈕，直接開啟 Microsoft Store。
> - 設定視窗顯示版號，並加上隱私權政策與官網連結。
> - 設定視窗的語言選單改得更簡潔。

## 1. 屬性

| 欄位 | 建議 | 理由 |
|---|---|---|
| 產品型別 | **MSIX app**（已建立，不是 game） | — |
| 類別 | **開發人員工具**（Developer tools），子類別留空 | 使用者就是用 AI 程式開發工具的人 |
| 隱私權：會存取、收集或傳送個人資訊嗎？ | **是**＋上面的政策 URL | App 會讀 Codex 的本機紀錄檔，檔案裡含對話內容（雖然只取額度欄位）。答「否」在審查追問時說不清楚，答「是」並附政策最安全 |
| 定價 | 免費、全球市場 | 沒有內購、沒有第三方廣告（設定視窗底部有一個標示「廣告」的自家 App 推廣橫幅，見 §4） |
| 產品宣告 | 全部**不勾**；若有預設勾選「可用 Windows 錄製與廣播此產品的片段」要**取消**（那項只給遊戲） | desk-pet 經驗 |
| 系統需求 | 最低需求可不填（套件已宣告 Windows 10 1903、x64） | — |

## 2. 商店清單：英文（en）

**Product name**：`AI Usage Meter`

**Short title**：**留白**（Partner Center 的說明是「產品的簡短名稱，用在 Xbox 安裝過程等處」，不是標語；AI Usage Meter 本身就夠短。原本擬的 `AI usage limits in your system tray` 不用）

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
> AI Usage Meter never reads or stores your passwords or sign-in tokens. When it needs live numbers, it asks the official tool that is already signed in on your computer to look them up. In the background it only reads local records, and it checks the tools online only when you open the card.
>
> A heads-up before you run out
> When any limit drops below 10%, you get one Windows notification, and only one per reset period. If a lookup fails or the numbers are out of date, that section turns grey and shows how old it is, so old numbers are never passed off as current ones.
>
> A little neon in your tray
> The ring around the icon slowly rotates. It pauses on its own when the screen is locked or off, in battery saver, or when Windows animation effects are turned off.
>
> Always up to date
> When a new version is available in the Microsoft Store, you get a notification, and Settings shows a button that takes you straight to it.
>
> Private by design
> No server of its own, no analytics, no third-party ads, no account. Nothing is sent to the developer. The only ad is a small banner for another app by the same developer at the bottom of the Settings window.
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
8. No server, no analytics, no third-party ads, no account
9. Slowly rotating neon ring that pauses when the screen is locked or off
10. Notifies you when a new version is available
11. Starts with Windows (optional)
12. English and Traditional Chinese interface

**Search terms**（最多 7 個、各 ≤40 字元、合計 ≤21 個單字，不顯示在頁面上）：
`AI usage`／`usage limit`／`rate limit`／`AI quota`／`system tray`／`developer tools`／`coding assistant`

**Copyright**：`© 2026 Fish-Zero`

## 3. 商店清單：繁體中文（zh-TW）

**產品名稱**：`AI Usage Meter`（中英同名：只保留了這一個名稱，套件的顯示名稱中英文也都是它；微軟建議清單名稱與套件一致）

**簡短標題**：**留白**（理由同英文）

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
> AI Usage Meter 不讀取、不保存你的密碼或登入權杖。需要即時數字時，它請你電腦上已經登入的官方工具自己去查。平常在背景只讀本機紀錄，只有在你打開卡片時才向各工具查詢雲端。
>
> 快用完時提醒你
> 任何一個額度剩不到 10%，就用 Windows 通知提醒一次，同一個重置週期不會重複提醒。查詢失敗或資料過時，那一塊會變灰並標示是多久以前的數字，不會把舊數字當成現在的。
>
> 會動的霓虹圖示
> 系統匣圖示外圈的霓虹會慢慢旋轉；鎖定畫面、螢幕關閉、省電模式，或 Windows 關掉「動畫效果」時會自動停下。
>
> 有新版本就告訴你
> Microsoft Store 上有新版本時會跳通知，設定視窗也會出現直通 Store 的按鈕。
>
> 隱私優先
> 沒有自己的伺服器、沒有分析追蹤、沒有第三方廣告，也不需要註冊帳號。不會把任何資料傳給開發者。唯一的廣告是設定視窗底部一個推廣開發者另一款 App 的小橫幅。
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
8. 沒有伺服器、沒有分析追蹤、沒有第三方廣告、不需要帳號
9. 霓虹外圈慢慢旋轉，鎖定畫面或螢幕關閉時自動停下
10. 有新版本時通知你
11. 可設定開機自動啟動
12. 繁體中文／English 介面

**搜尋字詞**：`AI 用量`／`用量`／`額度`／`系統匣`／`開發人員工具`／`AI usage`／`usage limit`

**著作權**：`© 2026 Fish-Zero`

## 4. 寫法上的決定（下次改文案前先看）

- **產品名稱、簡短標題不放任何一家的產品名**（商標）。說明與功能裡提到 Claude Code 等名稱，是為了說明「相容哪些工具」，並在說明最後加上無隸屬聲明。競品「AI Limits」的商店頁也是這樣寫。
- **搜尋字詞刻意不放 Claude、Codex、Copilot 等產品名**：用別人的商標當搜尋字詞，審查上風險比放在說明裡高；使用者搜這些字時，說明內文仍可能被比對到（推測）。
- 🔴 **不寫「沒有廣告」，一律寫「沒有第三方廣告」**：設定視窗底部的桌寵橫幅本身標著「廣告／Ad」（`i18n.py` 的 promo 字串），審核人員一打開設定就看得到，寫「沒有廣告」會自相矛盾（2026-09-26 拍截圖時才發現，隱私權政策與產品頁同日一起改）。
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
> 6. It animates its notification area icon by swapping pre-rendered frames (NIM_MODIFY), and registers for session lock (WTSRegisterSessionNotification) and display power (RegisterPowerSettingNotification) notifications so the animation pauses when the screen is locked or off. It also asks the Microsoft Store whether an update is available (StoreContext.GetAppAndOptionalStorePackageUpdatesAsync) and, only if the user clicks, opens the Store product page.
>
> The app runs as the current user (asInvoker) and never asks for administrator rights. It installs no drivers or services, does not inject into or modify other processes, reads no passwords, tokens, or credential stores, has no server of its own, and sends no data to the developer. Start with Windows uses the windows.startupTask extension.

**中文對照（給業主核對，不用貼）**

> AI Usage Meter 是住在 Windows 系統匣的 Win32 桌面程式（Python＋Qt，用 PyInstaller 打包），以下幾件事需要完全信任權限：
> 1. 系統匣圖示與懸停卡片：`Shell_NotifyIconW`（VERSION_4）收 hover 事件、`Shell_NotifyIconGetRect` 把卡片放在圖示旁、`TrackPopupMenu` 右鍵選單、`NIF_INFO` 低額度通知。
> 2. 讀取其他開發工具放在使用者資料夾（套件外）的用量紀錄：`.claude\usage-cache.json`、`.codex\sessions\`，只用額度欄位。
> 3. 以子程序啟動使用者自己安裝、登入的官方 CLI：`codex app-server`（stdin/stdout）、`agy -p /usage`、Copilot SDK runtime。登入由它們自己處理，本 App 不讀它們的憑證或權杖；關閉時先關掉 Codex 的輸入讓它自己結束，2 秒後還在才用 `taskkill /T` 結束自己啟動的程序樹。
> 4. 選用，使用者按「安裝」並確認後才做：把 Claude Code 的狀態列設定（先備份）指向 `.claude\ai-quota-tray\` 裡的小程式，只存額度欄位；按「移除」還原。
> 5. 使用者啟用 Copilot 時，官方 SDK 會從 GitHub 下載 runtime 到 `%LOCALAPPDATA%\github-copilot-sdk`。
> 6. 系統匣圖示動畫：預先算好的畫格用 `NIM_MODIFY` 換圖；註冊鎖定畫面（`WTSRegisterSessionNotification`）與螢幕電源（`RegisterPowerSettingNotification`）通知，鎖定或螢幕關閉時停轉。另外向 Microsoft Store 查詢有沒有更新（`StoreContext`），使用者點了才開 Store 商品頁。
>
> 以目前使用者身分執行（asInvoker）、不要求系統管理員；不裝驅動或服務、不注入或修改其他程序、不讀密碼／權杖／認證存放區、沒有自己的伺服器、不傳資料給開發者。開機啟動走 `windows.startupTask`。

**對照的程式碼**：①`win32tray.py`、`placement.py` ②`providers/claude.py`、`providers/codex.py` ③`codex_app_server.py`（`shutil.which("codex")`、`_kill_tree`）、`providers/antigravity.py`、`providers/copilot.py` ④`claude_hook.py` ⑤`providers/copilot.py` 的 `start_prepare` ⑥`packaging/app.manifest`（asInvoker）、`startup.py`（StartupTask）。

## 6. 給審核人員的認證注意事項

**填在哪**：左側「補充資訊」→「其他測試資訊」（產品層級，不跟著提交走；desk-pet 經驗）。不需要測試帳號，⚠️ 也不要把任何帳號資訊寫進這裡或商店描述。

**為什麼一定要寫**：
- 審核人員的電腦上不會有 Claude Code、Codex 等 CLI，正常模式下卡片只會顯示「還沒有資料」或查詢失敗，很容易被判成「App 沒有功能」→ 要教他開示範模式。
- **App 沒有主視窗**：從開始功能表啟動後只會在系統匣加一個圖示，Windows 11 預設還會把它收進 `^`。2026-09-26 起第一次啟動會跳歡迎通知、已在執行時再啟動一次會打開卡片（`tests/test_launch.py`），但審核人員不一定會注意到通知，所以這裡仍要寫清楚。

**要貼的英文**（按鈕與選單文字照 `i18n.py` 的英文字串，審核機若是英文介面就會一模一樣）

> AI Usage Meter has no main window. After you start it, it adds an icon to the notification area (system tray). On Windows 11 the icon may first appear in the hidden icons area: click the ^ arrow on the taskbar to find it. The first time it starts, a notification says it is running; clicking the notification opens the card. Starting the app again from the Start menu while it is already running also opens the card.
>
> The app shows the usage limits of AI coding tools (Claude Code, Codex, Antigravity CLI, GitHub Copilot) that are installed and signed in on the same PC. A test machine won't have these tools, so the card would only say there is no data yet. To review the full interface without any of them, please use the built-in demo mode:
>
> 1. Right-click the tray icon and choose "Settings…".
> 2. Check "Demo mode" at the bottom left and press "Save".
> 3. Hover the mouse over the tray icon (or click it once). A card opens with sample data for all four services: percentage left, progress bars in green, yellow, and red, and reset countdowns. A red line at the top of the card says "Demo mode: sample data, not your actual quota".
>
> In demo mode the app makes no queries and starts no other tools. No sign-in or account is needed, and there are no in-app purchases.
>
> Other things to try: the right-click menu also has "Refresh now", "Start with Windows", and "Quit". The Settings window switches the interface language between English and Traditional Chinese, and links to the privacy policy and website. The ring around the tray icon slowly rotates; it pauses when the screen is locked or off, in battery saver, or when Windows animation effects are off.

**中文對照（給業主核對，不用貼）**

> AI Usage Meter 沒有主視窗。啟動後會在系統匣加一個圖示；Windows 11 可能先把它放在隱藏圖示區，點工作列的 ^ 就找得到。第一次啟動時會跳一則通知說它在執行，點通知會打開卡片；已經在執行時從開始功能表再啟動一次，也會打開卡片。
>
> 這個 App 顯示同一台電腦上已安裝並登入的 AI 程式開發工具的用量。測試機不會有這些工具，卡片只會顯示還沒有資料。要在沒有這些工具的情況下看完整介面，請用內建的示範模式：
> 1. 在系統匣圖示按右鍵，選「設定…」。
> 2. 勾選左下角的「示範模式」，按「儲存」。
> 3. 滑鼠移到系統匣圖示上（或點一下）。會彈出四個服務的範例資料卡片：剩餘百分比、綠／黃／紅進度條與重置倒數，卡片頂端有一行紅字「示範模式・以下為範例資料，不是你的額度」。
>
> 示範模式下不查詢任何服務、不啟動其他工具。不需要登入或帳號，也沒有內購。
>
> 其他可以試的：右鍵選單還有「立即刷新」「開機時啟動」「關閉」；設定視窗可以切換中英文介面，也有隱私權政策與官網連結。系統匣圖示的外圈會慢慢旋轉，鎖定畫面、螢幕關閉、省電模式或 Windows 關掉動畫效果時會停下。

⚠️ 改到右鍵選單、設定視窗的按鈕文字、示範模式的行為或提示字時，這段要一起改。

## 7. 年齡分級（IARC 問卷）

Partner Center 的「年齡分級」是線上問卷，答完當場產生各地區分級。第一題選產品類型時選**非遊戲的應用程式**（公用程式／生產力那一類，確切選項名稱以問卷畫面為準）。
照下表誠實作答；**依據欄是為了下次有人問「為什麼這樣答」**。預期結果是全年齡（3+／所有人）（推測，要看問卷實際產生的結果）。

| 題目類別 | 怎麼答 | 依據 |
|---|---|---|
| 暴力、血腥 | 無 | App 只顯示用量數字與進度條 |
| 性內容／裸露 | 無 | — |
| 粗俗語言 | 無 | 介面文字是固定字串（`i18n.py`）；卡片上的失敗原因可能是各工具回傳的錯誤訊息。都不是使用者產生的內容 |
| 受管制物質（菸酒毒品） | 無 | — |
| 賭博／模擬賭博 | 無 | — |
| 恐怖／驚嚇 | 無 | — |
| 使用者互動（聊天、分享使用者產生的內容） | **無** | App 沒有任何使用者之間的互動，也沒有帳號 |
| 分享個人資訊給其他人或第三方 | **無** | 隱私權政策 §1、§3：沒有自己的伺服器，不傳任何資料給開發者或第三方。各官方工具與自家服務之間的查詢不是本 App 在分享 |
| 分享位置 | 無 | 不取任何位置 |
| 數位購買（內購） | **無** | 免費、沒有內購、沒有訂閱 |
| 不受限的網際網路存取 | **無** | App 內沒有瀏覽器；唯一的外部連結是設定視窗底部那個自家 App 橫幅，點了用預設瀏覽器開 Microsoft Store 商品頁（`settings.py` 的 `STORE_URL`） |

⚠️ **政策 11.11 於 2026-09-15 更新（2026-10-22 生效）**：年齡分級要在產品的整個生命週期內維持正確。之後若加了聊天、帳號、內購、內建瀏覽器，要回來重填問卷。
💡 設定視窗那個「萌寵桌面精靈」橫幅是**自家產品的交叉推廣**，不是第三方廣告網路；問卷若問到廣告，照這個事實回答。

## 8. 截圖與 Store 標誌

**規格**：至少 1 張、最多 10 張，`.png`，最小 1366×768、最大 3840×2160。⚠️ 每種語言的截圖要是那個語言的介面（desk-pet 經驗：英文清單配中文截圖會被退件）；⚠️ 截圖一次只吃一張、每個語言要各傳一次（desk-pet 經驗）。

**已產生**（2026-09-26，`packaging/store_shots.py`，3840×2160）：

| 檔案 | 內容 | 傳到 |
|---|---|---|
| `docs/store/shots/zh-TW-1.png`／`en-1.png` | 深色卡片（四家範例資料）＋「每個額度還剩多少，滑鼠移過去就知道」 | 各自語言的清單，放第一張 |
| `docs/store/shots/zh-TW-2.png`／`en-2.png` | 淺色卡片＋「淺色、深色都好讀」 | 同上 |
| `docs/store/shots/zh-TW-3.png`／`en-3.png` | 設定視窗（Claude 那列顯示「安裝」）＋「選你用的工具，不用登入、不碰權杖」 | 同上 |

做法：直接用 Qt 畫真的 `Card`／`SettingsDialog` 元件（2 倍解析度），放在漸層背景上加一句說明；**不截桌面**（會拍到業主的視窗與系統匣裡別的 App）。
資料是示範模式的範例（`demo.sample_states`），但不畫示範模式那行紅字。設定視窗那張強制畫成「還沒安裝 Claude 狀態列擷取」的樣子（新使用者看到的）。
改到卡片或設定視窗的外觀後，重跑 `.venv\Scripts\python packaging\store_shots.py` 即可（輸出會覆蓋）。

**Store 標誌**（選填）：`docs/store/logo-300.png`（300×300，由 `ai_quota_tray/assets/app.png` 縮小）。不傳的話 Store 用套件裡的圖示。
**還沒做（選填）**：2:3 海報與 16:9 hero art（desk-pet 有做，這個 App 沒有必要）、系統匣低額度通知的實機截圖（通知是系統畫的，畫不出來，要真的觸發再截）。
