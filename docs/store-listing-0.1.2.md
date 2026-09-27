# AI Usage Meter 0.1.2.0 商店清單文案

供 Microsoft Partner Center 更新提交使用。套件 `AiUsageMeter-0.1.2.0-x64.msix` 宣告 `zh-TW`、`en`、`ja`、`de`、`zh-CN`。各語言產品名稱都選 **AI Usage Meter**，簡短標題留白。說明欄請貼純文字，不貼本檔的 Markdown 標題或項目符號。產品功能在 Partner Center 逐條新增，不要輸入序號。著作權各語言均填 `© 2026 Fish-Zero`。

Microsoft 的 MSIX 清單規則：說明必填、至少一張截圖；「此版本的新增功能」最多 1,500 字元；產品功能最多 20 條、每條最多 200 字元；簡短描述最多 1,000 字元，建議前 270 字元內講完。各套件語言可分別建立清單，也可匯出／匯入 CSV。參考：[Microsoft Learn：編輯 MSIX 商店清單](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/add-and-edit-store-listing-info)。

五種語言各有 3 張桌面截圖，在 `docs/store/shots/<語言>-1.png` 到 `-3.png`；第 3 張可看到新版設定。商店圖示在 `docs/store/logo-300.png`。截圖由 `packaging/store_shots.py` 使用真正的卡片與設定元件、示範資料產生。隱私權政策仍使用產品屬性中的 `https://fish-zero.com/aiusagemeter-privacy`。審核人員測試說明沿用 [store-listing.md](store-listing.md) 第 6 節；其中已列出五種語言。

## English (en)

**Short description**

See your AI coding tools' remaining usage from the Windows system tray. Hover for each limit's reset time and, for Codex, available reset credits and the nearest known expiry. No separate account or sign-in tokens needed.

**Description**

AI Usage Meter keeps the usage limits of your AI coding tools one hover away. Hover over its Windows system tray icon to see the percentage left, a progress bar, and the time until each limit resets.

Supported tools: Claude Code, Codex, Antigravity CLI, and GitHub Copilot. Claude Code and Codex are enabled by default. Install and sign in to each tool you want to track on the same PC.

If Codex provides reset-credit details, the card shows how many credits are available and the nearest known expiration date. Reset-credit details currently work with Codex only.

When a limit falls below 10%, the app sends one Windows notification per reset period. Old or unavailable numbers are shown in grey with their age. The tray icon's neon ring slowly rotates and pauses when the screen is locked or off, battery saver is on, or Windows animations are disabled. The app also tells you when a new version is available in the Microsoft Store.

AI Usage Meter does not read or store passwords or sign-in tokens. It has no server of its own, analytics, or third-party ads. In the background it reads local usage records; when you open the card, it asks the official tools already signed in on your PC for updated numbers. The Settings window contains a small banner for another app from the same developer.

Settings offers Traditional Chinese, English, Japanese, German, and Simplified Chinese. The Claude Code “Install capture” and “Remove capture” buttons manage usage capture; they do not install or remove Claude Code. The developer's promoted app supports English and Traditional Chinese, so its banner appears in English in the other interface languages.

On Windows 11, the tray icon may initially be under the hidden icons arrow (^). Drag it onto the taskbar for quick access.

AI Usage Meter is an independent app and is not affiliated with Anthropic, OpenAI, GitHub, or Google. Product names belong to their respective owners.

**What's new in this version**

- Added Japanese, German, and Simplified Chinese interface options, alongside Traditional Chinese and English.
- The Codex card now shows available reset credits and the nearest known expiry when Codex provides them. Reset-credit details currently support Codex only.
- Settings now makes clear that Claude's install and remove buttons manage usage capture, not Claude Code itself.
- The developer's app banner appears in English when its app does not support the selected interface language.

**Product features**

1. Hover over the system tray icon to see usage limits at a glance
2. Percentage left, progress bar, and reset countdown for each limit
3. Supports Claude Code, Codex, Antigravity CLI, and GitHub Copilot
4. Shows Codex reset-credit count and nearest known expiry
5. Never reads or stores passwords or sign-in tokens
6. Uses each tool's official interface and your existing sign-in
7. One alert below 10% per reset period
8. Grey, time-stamped sections for old or unavailable numbers
9. No server, analytics, third-party ads, or separate account
10. Animated tray ring that pauses when the screen is locked or off
11. Notification when a Microsoft Store update is available
12. Traditional Chinese, English, Japanese, German, and Simplified Chinese interface

**Search terms**: `AI usage` / `usage limit` / `rate limit` / `AI quota` / `system tray` / `developer tools` / `coding assistant`

## 繁體中文 (zh-TW)

**簡短描述**

在 Windows 系統匣查看 AI 程式開發工具的剩餘用量與重置時間。滑鼠移到圖示上，還能查看 Codex 重置券的可用張數與最近已知的到期日。不需另建帳號，也不讀取登入權杖。

**說明**

AI Usage Meter 讓 AI 程式開發工具的用量，滑鼠移過去就看得到。將滑鼠移到 Windows 系統匣圖示上，每項額度的剩餘百分比、進度條與下次重置倒數會顯示在同一張卡片上。

支援 Claude Code、Codex、Antigravity CLI 和 GitHub Copilot。預設啟用 Claude Code 與 Codex；你需要先在同一台電腦安裝並登入想追蹤的工具。

如果 Codex 提供重置券資料，卡片會顯示可用張數與最近已知的到期日。重置券資訊目前僅支援 Codex。

額度剩不到 10% 時，每個重置週期只會收到一次 Windows 通知。過時或無法取得的數字會變灰並標示資料時間。系統匣圖示的霓虹外圈會慢慢旋轉，鎖定畫面、螢幕關閉、省電模式或關閉 Windows 動畫效果時會自動停下。Microsoft Store 有新版本時，App 也會提醒你。

AI Usage Meter 不讀取、不保存密碼或登入權杖，沒有自己的伺服器、分析追蹤或第三方廣告。平常在背景只讀本機用量紀錄；打開卡片時才請已登入的官方工具查詢較新的數字。設定視窗底部有一個推廣同一位開發者另一款 App 的小橫幅。

介面提供繁體中文、英文、日文、德文與簡體中文。Claude Code 的「安裝擷取」與「移除擷取」只管理用量擷取，不會安裝或移除 Claude Code。被推廣的 App 目前只支援英文與繁體中文，因此選擇其他介面語言時，該橫幅會顯示英文。

Windows 11 可能先把新圖示放在隱藏圖示區（^）。將圖示拖到工作列，就能隨時查看。

AI Usage Meter 是獨立開發的 App，與 Anthropic、OpenAI、GitHub、Google 沒有隸屬或合作關係。各產品名稱屬於其權利人。

**此版本的新增功能**

- 新增日文、德文與簡體中文介面，並保留繁體中文與英文。
- Codex 卡片新增重置券可用張數，以及有提供時最近已知的到期日；目前僅支援 Codex。
- 設定中說明 Claude 的安裝／移除按鈕管理的是用量擷取，不會安裝或移除 Claude Code。
- 被推廣的 App 不支援所選介面語言時，推廣橫幅顯示英文。

**產品功能**

1. 滑鼠移到系統匣圖示上，所有額度一次看完
2. 每項額度都有剩餘百分比、進度條與重置倒數
3. 支援 Claude Code、Codex、Antigravity CLI、GitHub Copilot
4. 顯示 Codex 重置券張數與最近已知的到期日
5. 不讀取、不保存密碼或登入權杖
6. 使用各工具的官方介面與原本的登入查詢
7. 額度剩不到 10% 時，每個重置週期提醒一次
8. 過時或無法取得的資料會變灰並標示時間
9. 沒有伺服器、分析追蹤、第三方廣告或額外帳號
10. 系統匣動畫在鎖定畫面或螢幕關閉時自動停下
11. Microsoft Store 有新版時通知你
12. 繁體中文、英文、日文、德文與簡體中文介面

**搜尋字詞**：`AI 用量`／`用量限制`／`額度`／`系統匣`／`開發人員工具`／`AI usage`／`usage limit`

## 日本語 (ja)

**短い説明**

Windows の通知領域から AI コーディングツールの利用枠を確認。残量、リセットまでの時間、Codex のリセットクレジット枚数と直近の有効期限を表示します。

**説明**

AI Usage Meter は、AI コーディングツールの利用枠を Windows の通知領域で確認できるアプリです。アイコンにマウスを合わせると、各利用枠の残量、進捗バー、次のリセットまでの時間が表示されます。

対応ツールは Claude Code、Codex、Antigravity CLI、GitHub Copilot です。Claude Code と Codex は初期状態で有効です。利用するツールは同じ PC にインストールしてサインインしてください。

Codex のリセットクレジットが取得できる場合は、利用可能な枚数と、確認できた中で最も近い有効期限も表示します。この表示は現在 Codex のみに対応しています。

残量が 10% 未満になると、リセット期間ごとに 1 回だけ Windows 通知を送ります。取得に失敗した情報や古い情報は、更新からの経過時間とともに灰色で示します。

パスワードやサインイントークンの読み取り・保存は行いません。アプリ独自のサーバー、アクセス解析、サードパーティー広告はありません。バックグラウンドではローカルの利用記録を参照し、カードを開いたときに、サインイン済みの公式ツールへ新しい情報を問い合わせます。

設定画面の Claude Code の「取得を導入／取得を削除」は、利用情報を保存するステータスライン連携を設定・解除する操作です。Claude Code 本体をインストールまたはアンインストールする操作ではありません。

表示言語は繁体字中国語、英語、日本語、ドイツ語、簡体字中国語に対応しています。設定画面には、開発者の別アプリを紹介する小さなバナーがあります。紹介先のアプリが日本語に対応していないため、バナーは英語で表示されます。

Windows 11 では、通知領域のアイコンが最初は隠しアイコン（^）に入ることがあります。

AI Usage Meter は独立したアプリで、Anthropic、OpenAI、GitHub、Google と提携していません。

**このバージョンの新機能**

- 日本語、ドイツ語、簡体字中国語の UI を追加しました。表示言語は設定から選択できます。
- Codex のリセットクレジットの利用可能枚数と、確認できた中で最も近い有効期限を通知領域のカードに表示します。現在は Codex のみに対応しています。
- Claude Code のボタンが取得機能の設定を指すことを明確にしました。
- 開発者の別アプリを紹介するバナーは、日本語表示時には英語で表示します。

**製品の特長**

1. 通知領域のアイコンにマウスを合わせて、利用枠をまとめて確認
2. 利用枠ごとの残量、進捗バー、リセットまでの時間を表示
3. Claude Code、Codex、Antigravity CLI、GitHub Copilot に対応
4. Codex のリセットクレジット枚数と直近の有効期限を表示
5. 残量が 10% 未満になると、リセット期間ごとに 1 回通知
6. 古い情報や取得できない情報は、経過時間とともに灰色で表示
7. パスワードやサインイントークンを読み取り・保存しない
8. 独自サーバー、アクセス解析、別途のアカウント登録なし
9. 画面のロック時や省電力時に停止する通知領域アイコンのアニメーション
10. Microsoft Store の更新が利用可能になると通知
11. Windows の起動時に自動起動（任意）
12. 繁体字中国語、英語、日本語、ドイツ語、簡体字中国語の UI

**検索語**：`AI 使用量`／`利用制限`／`AI クォータ`／`通知領域`／`開発ツール`／`コーディング支援`／`使用量管理`

## Deutsch (de)

**Kurzbeschreibung**

Behalte die Nutzungslimits deiner KI-Codingtools direkt im Windows-Infobereich im Blick. Beim Zeigen auf das Symbol siehst du Restkontingent, Rücksetzzeit und verfügbare Codex-Rücksetzgutschriften. Ohne eigenes Konto oder Analyse-Tracking.

**Beschreibung**

AI Usage Meter zeigt dir die Nutzungslimits deiner KI-Codingtools im Windows-Infobereich. Zeige auf das Symbol, um für jedes Limit das verbleibende Kontingent, einen Fortschrittsbalken und die Zeit bis zur Rücksetzung zu sehen.

Unterstützte Tools: Claude Code, Codex, Antigravity CLI und GitHub Copilot. Claude Code und Codex sind standardmäßig aktiviert; die anderen Tools kannst du in den Einstellungen einschalten. Die jeweiligen Tools müssen auf deinem PC installiert und angemeldet sein.

Wenn Codex diese Angaben bereitstellt, zeigt die Infokarte, wie viele Rücksetzgutschriften verfügbar sind und wann die nächste bekannte Gutschrift abläuft. Diese Anzeige wird derzeit nur für Codex unterstützt.

Fällt ein Limit unter 10 %, erhältst du pro Rücksetzzeitraum eine Windows-Benachrichtigung. Veraltete oder nicht verfügbare Werte sind entsprechend gekennzeichnet. Der Leuchtring des Symbols pausiert, wenn der Bildschirm gesperrt oder ausgeschaltet ist, beim Energiesparen oder wenn Windows-Animationen deaktiviert sind. Die App informiert dich auch, wenn im Microsoft Store eine neue Version verfügbar ist.

Die App liest und speichert keine Passwörter oder Anmeldetoken. Sie nutzt vorhandene lokale Nutzungsdaten und fragt beim Öffnen der Infokarte die bereits angemeldeten offiziellen Tools ab. Sie hat keinen eigenen Server, kein Analyse-Tracking und keine Anzeigen von Drittanbietern. In den Einstellungen erscheint lediglich ein Hinweis auf eine weitere App desselben Entwicklers.

Wähle zwischen Deutsch, Japanisch, vereinfachtem Chinesisch, traditionellem Chinesisch und Englisch. Die Claude-Schaltflächen installieren bzw. entfernen nur die Erfassung der Nutzungsdaten, nicht Claude Code selbst. Der Hinweis auf die andere App ist auf Deutsch, Japanisch und vereinfachtem Chinesisch auf Englisch verfügbar.

Unter Windows 11 erscheint ein neues Symbol möglicherweise zunächst im ausgeblendeten Bereich (^). Ziehe es auf die Taskleiste, um die Infokarte schnell zu öffnen.

AI Usage Meter ist eine unabhängige App und steht in keiner Verbindung zu Anthropic, OpenAI, GitHub oder Google. Die Produktnamen gehören ihren jeweiligen Inhabern.

**Neu in Version 0.1.2.0**

- Codex: Verfügbare Rücksetzgutschriften und der nächste bekannte Ablauf erscheinen jetzt direkt in der Infokarte.
- Neue Oberflächensprachen: Deutsch, Japanisch und vereinfachtes Chinesisch. Englisch und traditionelles Chinesisch bleiben verfügbar.
- Die Claude-Schaltflächen erklären nun deutlicher, dass sie die Erfassung der Nutzungsdaten installieren oder entfernen.
- Die Einstellungen weisen darauf hin, dass Rücksetzgutschriften derzeit nur für Codex angezeigt werden.
- Der Hinweis auf eine weitere App desselben Entwicklers erscheint in den neuen Sprachen auf Englisch.

**Produktmerkmale**

1. Alle Nutzungslimits beim Zeigen auf das Symbol im Windows-Infobereich sehen
2. Restkontingent, Fortschrittsbalken und Countdown bis zur Rücksetzung
3. Unterstützt Claude Code, Codex, Antigravity CLI und GitHub Copilot
4. Anzahl verfügbarer Codex-Rücksetzgutschriften und nächster bekannter Ablauf
5. Benachrichtigung bei weniger als 10 % Restkontingent
6. Veraltete Werte werden mit Zeitangabe gekennzeichnet
7. Liest und speichert keine Passwörter oder Anmeldetoken
8. Kein eigener Server, kein Analyse-Tracking und kein zusätzliches Konto
9. Animierter Leuchtring, der bei gesperrtem Bildschirm oder Energiesparen pausiert
10. Benachrichtigt dich über neue Versionen im Microsoft Store
11. Optionaler Start mit Windows
12. Oberfläche auf Deutsch, Englisch, Japanisch sowie traditionellem und vereinfachtem Chinesisch

**Suchbegriffe**: `KI-Nutzung` / `Nutzungslimit` / `KI-Kontingent` / `Ratenlimit` / `Infobereich` / `Entwicklerwerkzeuge` / `Programmierassistent`

## 简体中文 (zh-CN)

**简短说明**

在 Windows 系统托盘查看 AI 编程工具的剩余用量与重置时间。Codex 重置券可显示剩余张数及最近已知的到期日。无需另建账号，不读取或保存登录令牌。

**完整说明**

AI Usage Meter 让 AI 编程工具的用量限制始终近在眼前。将鼠标悬停在 Windows 系统托盘图标上，即可查看各项额度的剩余百分比、进度条和重置倒计时。

支持 Claude Code、Codex、Antigravity CLI 和 GitHub Copilot。Claude Code 与 Codex 默认启用，其他工具可在设置中开启。相应工具需已安装并在这台电脑上登录。

如果 Codex 提供重置券数据，卡片还会显示可用张数及最近已知的到期日。重置券详情目前仅支持 Codex。

某项额度低于 10% 时，每个重置周期只提醒一次。查询失败或数据过期时，相应区块会变灰，并显示数据时间。托盘图标的光环会缓慢旋转；锁屏、关闭屏幕、启用节电模式或关闭 Windows 动画效果时会暂停。发现 Microsoft Store 新版本时，应用也会通知你。

应用不会读取或保存密码、登录令牌。后台读取本地用量记录，打开用量卡片时才调用本机已登录工具的官方接口查询新数据。应用没有自有服务器、分析追踪、第三方广告或专用账号，不会把数据发送给开发者。设置页面底部有一个推广同一开发者其他应用的小横幅。

提供繁体中文、英语、日语、德语和简体中文界面。Claude 设置中的“安装采集／移除采集”仅管理用量采集，并非安装或卸载 Claude Code。被推广的应用目前仅支持英语和繁体中文，因此在其他界面语言下，横幅显示英文。

Windows 11 可能将新托盘图标放在隐藏图标区域（^）。可将图标拖到任务栏，随时悬停查看。

AI Usage Meter 是独立应用，与 Anthropic、OpenAI、GitHub 或 Google 没有关联。相关产品名称归各自所有者所有。

**此版本的新内容**

- 新增日语、德语及简体中文界面；设置中可从五种语言直接选择。
- Codex 用量卡片新增重置券可用张数与最近已知的到期日；目前仅支持 Codex。
- 设置页面说明 Claude 的“安装采集／移除采集”按钮仅管理用量采集，并非安装或卸载 Claude Code。
- 开发者其他应用的横幅在不支持所选语言时显示英文。

**产品功能**

1. 悬停系统托盘图标，即可查看各项用量限制
2. 显示剩余百分比、进度条与重置倒计时
3. 查看 Codex 重置券张数和最近已知的到期日
4. 支持 Claude Code、Codex、Antigravity CLI 和 GitHub Copilot
5. 不读取或保存密码及登录令牌
6. 使用本机现有登录状态和工具官方接口
7. 额度低于 10% 时，每个重置周期提醒一次
8. 过期数据变灰，并标明数据时间
9. 无自有服务器、分析追踪、第三方广告或专用账号
10. 托盘光环会在锁屏、息屏或节电时暂停动画
11. 新版本上架后通知，并可前往 Microsoft Store
12. 支持繁中、英语、日语、德语及简体中文界面

**搜索词**：`AI 用量`／`用量限制`／`速率限制`／`AI 额度`／`系统托盘`／`开发工具`／`编程助手`
