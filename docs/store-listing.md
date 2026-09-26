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

## 5. 還沒做

- 截圖（至少 1 張、建議 4 張，`.png`、最小 1366×768；⚠️ 每種語言的截圖要是那個語言的介面，desk-pet 經驗：英文清單配中文截圖會被退件）
- Store 標誌、IARC 年齡分級問卷、runFullTrust 說明、給審核人員的認證注意事項（示範模式）
