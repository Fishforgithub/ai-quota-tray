# AI Usage Meter 0.1.4.0 商店清單文案

套件 `AiUsageMeter-0.1.4.0-x64.msix`。這版 **Store 版也有 Grok**（2026-10-03 業主決定不等 xAI 回信；政策查核與做法見 CLAUDE.md「0.1.4」）。
Grok 走官方 Grok Build CLI 的 `grok agent stdio`（ACP），**App 仍然不讀、不存任何 token**，所以說明、功能、runFullTrust、認證注意事項裡「不讀取權杖」的句子**都不用改**，只是把 Grok 加進工具清單。

要動的欄位（其他沿用 [store-listing-0.1.2.md](store-listing-0.1.2.md) 與 [store-listing.md](store-listing.md)）：

1. **此版本的新增功能**：五語全換（下方）。
2. **說明**：五語各換三句（支援工具、背景查詢、非官方聲明），下方「說明替換」逐句對照 0.1.2 的原句。
3. **產品功能**：五語各換一條（支援工具那條）。
4. **runFullTrust 說明**：已同步改在 [store-listing.md](store-listing.md) §5（第 3 條加上 Grok）。更新版通常不會再問；有跳出來才貼。
5. **認證注意事項**（產品層級的「其他測試資訊」）：已同步改在 [store-listing.md](store-listing.md) §6（工具清單加 Grok、示範模式「四個服務」→「五個服務」）。⚠️ Partner Center 裡實際存的是 0.1.2 時的五語版，那兩句要逐語更新。
6. 截圖：業主要求換成新版（淺藍服務名稱、Codex 重置券、Grok）→ `demo.py` 的 Codex 範例補了重置券 2 張，`packaging/store_shots.py` 重畫五語 15 張，已在 Submission 4 原位替換。業主要求套件也要一致 → 同版號 0.1.4.0 重新打包（`8f45f08` 之後），打包版以暫存設定開示範模式截圖確認有重置券與 Grok，業主重新上傳。
7. 隱私權政策網址不變（`https://fish-zero.com/aiusagemeter-privacy`），內容已改寫（fish-zero-web，⚠️ **送審前要先上線**）。

上限：新增功能 1,500 字元、每條功能 200 字元。貼純文字、一行一項、不加項目符號。

## 此版本的新增功能

### English (en)

```text
Added Grok (Grok Build CLI). Turn it on in Settings. It uses the official Grok Build CLI on your PC, so sign in with grok login first; your sign-in stays with the Grok CLI.
While you are using one of your tools, its numbers now update about every 25 seconds, and once more shortly after you stop. Nothing is checked while the screen is locked or off, or while you are away from your PC.
```

### 繁體中文 (zh-TW)

```text
新增 Grok（Grok Build CLI）：到設定勾選即可。透過你電腦上的官方 Grok Build CLI 查詢，請先執行 grok login 登入；登入資料由 Grok CLI 自己保管。
正在使用某個工具時，它的數字會改成約每 25 秒更新一次，停用後再補查一次；螢幕鎖定、關閉，或你不在電腦前時不會查詢。
```

### 日本語 (ja)

```text
Grok（Grok Build CLI）に対応しました。設定で有効にしてください。PC 上の公式 Grok Build CLI で照会するため、先に grok login でサインインしてください。サインイン情報は Grok CLI が管理します。
ツールを使っている間は、そのツールの数値を約 25 秒ごとに更新し、使い終わった少し後にもう一度確認します。画面のロック中やオフのとき、PC から離れているときは確認しません。
```

### Deutsch (de)

```text
Neu: Grok (Grok Build CLI). In den Einstellungen aktivieren. Die Abfrage läuft über die offizielle Grok Build CLI auf deinem PC, melde dich also zuerst mit grok login an; deine Anmeldung bleibt bei der Grok CLI.
Während du ein Tool nutzt, werden seine Werte etwa alle 25 Sekunden aktualisiert und kurz nach dem Ende noch einmal. Bei gesperrtem oder ausgeschaltetem Bildschirm oder wenn du nicht am PC bist, wird nichts abgefragt.
```

### 简体中文 (zh-CN)

```text
新增 Grok（Grok Build CLI）：在设置中勾选即可。通过你电脑上的官方 Grok Build CLI 查询，请先运行 grok login 登录；登录信息由 Grok CLI 自己保管。
正在使用某个工具时，它的数据会改为约每 25 秒更新一次，停止使用后再补查一次；锁屏、关闭屏幕或你不在电脑前时不会查询。
```

## 說明替換（對照 store-listing-0.1.2.md 的原句）

### English (en)

- 支援工具 → `Supported tools: Claude Code, Codex, Antigravity CLI, GitHub Copilot, and Grok Build CLI. Claude Code and Codex are enabled by default. Install and sign in to each tool you want to track on the same PC.`
- 背景查詢那段的中間一句 → `In the background it reads local usage records; when you open the card, or while you are using one of the tools, it asks the official tools already signed in on your PC for updated numbers.`
- 非官方聲明 → `AI Usage Meter is an independent app and is not affiliated with Anthropic, OpenAI, GitHub, Google, or xAI. Product names belong to their respective owners.`
- 功能第 3 條 → `Supports Claude Code, Codex, Antigravity CLI, GitHub Copilot, and Grok Build CLI`

### 繁體中文 (zh-TW)

- 支援工具 → `支援 Claude Code、Codex、Antigravity CLI、GitHub Copilot 和 Grok Build CLI。預設啟用 Claude Code 與 Codex；你需要先在同一台電腦安裝並登入想追蹤的工具。`
- 背景查詢 → `平常在背景只讀本機用量紀錄；打開卡片、或正在使用某個工具時，才請已登入的官方工具查詢較新的數字。`
- 非官方聲明 → `AI Usage Meter 是獨立開發的 App，與 Anthropic、OpenAI、GitHub、Google、xAI 沒有隸屬或合作關係。各產品名稱屬於其權利人。`
- 功能第 3 條 → `支援 Claude Code、Codex、Antigravity CLI、GitHub Copilot、Grok Build CLI`

### 日本語 (ja)

- 対応ツール → `対応ツールは Claude Code、Codex、Antigravity CLI、GitHub Copilot、Grok Build CLI です。Claude Code と Codex は初期状態で有効です。利用するツールは同じ PC にインストールしてサインインしてください。`
- バックグラウンド → `バックグラウンドではローカルの利用記録を参照し、カードを開いたときや、ツールを使っている間に、サインイン済みの公式ツールへ新しい情報を問い合わせます。`
- 提携の否定 → `AI Usage Meter は独立したアプリで、Anthropic、OpenAI、GitHub、Google、xAI と提携していません。`
- 機能第 3 条 → `Claude Code、Codex、Antigravity CLI、GitHub Copilot、Grok Build CLI に対応`

### Deutsch (de)

- Unterstützte Tools → `Unterstützte Tools: Claude Code, Codex, Antigravity CLI, GitHub Copilot und Grok Build CLI. Claude Code und Codex sind standardmäßig aktiviert; die anderen Tools kannst du in den Einstellungen einschalten. Die jeweiligen Tools müssen auf deinem PC installiert und angemeldet sein.`
- Abfrage → `Sie nutzt vorhandene lokale Nutzungsdaten und fragt beim Öffnen der Infokarte sowie während du ein Tool nutzt die bereits angemeldeten offiziellen Tools ab.`
- Keine Verbindung → `AI Usage Meter ist eine unabhängige App und steht in keiner Verbindung zu Anthropic, OpenAI, GitHub, Google oder xAI. Die Produktnamen gehören ihren jeweiligen Inhabern.`
- Funktion 3 → `Unterstützt Claude Code, Codex, Antigravity CLI, GitHub Copilot und Grok Build CLI`

### 简体中文 (zh-CN)

- 支持工具 → `支持 Claude Code、Codex、Antigravity CLI、GitHub Copilot 和 Grok Build CLI。Claude Code 与 Codex 默认启用，其他工具可在设置中开启。相应工具需已安装并在这台电脑上登录。`
- 后台查询 → `后台读取本地用量记录，打开用量卡片或正在使用某个工具时，才调用本机已登录工具的官方接口查询新数据。`
- 无关联声明 → `AI Usage Meter 是独立应用，与 Anthropic、OpenAI、GitHub、Google 或 xAI 没有关联。相关产品名称归各自所有者所有。`
- 功能第 4 条 → `支持 Claude Code、Codex、Antigravity CLI、GitHub Copilot 和 Grok Build CLI`

## 搜尋字詞

不用改。要加的話每語言上限 7 個，現在已滿；不建議把 `Grok` 塞進去（商標詞，且 0.1.2 的 7 個都比它重要）。
