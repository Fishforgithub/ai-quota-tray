# AI Usage Meter 0.1.5.0 商店清單文案

套件 `AiUsageMeter-0.1.5.0-x64.msix`。這版兩件事（細節見 CLAUDE.md「0.1.5」）：
**釘選**（桌面卡片＋工作列長條，2026-10-03 使用者回饋）與 **Antigravity 狀態列擷取**（2026-10-04，照 Claude 的做法；沒裝時 `agy -p /usage` 逾時重試一次、逾時不再顯示成紅字）。
App 仍然不讀、不存任何 token，「不讀取權杖」的句子都不用改。

要動的欄位（其他沿用 [store-listing-0.1.4.md](store-listing-0.1.4.md) 送出時的內容）：

1. **此版本的新增功能**：五語全換（下方）。
2. **說明**：五語各「加一段」（釘選）＋「換一句」（擷取按鈕現在 Claude 與 Antigravity 都有），下方「說明」逐語對照原句。
3. **產品功能**：五語各加第 13 條（釘選）。
4. **runFullTrust 說明**：已同步改在 [store-listing.md](store-listing.md) §5（第 2 條多讀 agy 擷取的快取、第 4 條多 agy 的設定檔）。更新版通常不會再問；有跳出來才貼。
5. **認證注意事項**（產品層級的「其他測試資訊」）：[store-listing.md](store-listing.md) §6 的英文最後一段多一句釘選。⚠️ Partner Center 裡要逐語更新。
6. **截圖**：五語各 4 張，`packaging/store_shots.py` 重畫（1～3 原位替換：hover 卡片多了「釘選…」、設定視窗多了 Antigravity 的「安裝擷取」；第 4 張新增：釘選）。
7. **隱私權政策**：網址不變（`https://fish-zero.com/aiusagemeter-privacy`），內容補 Antigravity 擷取與釘選（fish-zero-web，⚠️ **送審前要先上線**）。

上限：新增功能 1,500 字元、每條功能 200 字元。貼純文字、一行一項、不加項目符號。

## 此版本的新增功能

### English (en)

```text
Pin the usage card: choose "Pin…" at the bottom of the card to keep a card on your desktop, or a slim strip above the taskbar that shows each limit as a small battery with the number inside. Drag it anywhere; it steps aside while a full-screen app is running. The desktop card has a "Refresh now" link at the bottom left.
Antigravity CLI: Settings can now install a status line capture for agy, just like for Claude Code. While you use agy, its numbers are saved on your PC and shown right away, without starting agy in the background. Without the capture, a lookup that times out is retried once, and a timeout is no longer shown as an error.
```

### 繁體中文 (zh-TW)

```text
新增釘選：點卡片下方的「釘選…」，可以讓卡片常駐在桌面，或縮成工作列上方的一排長條（每個額度是一顆小電池，數字就在裡面）。可以拖到想要的位置；有全螢幕程式時會自動讓開。桌面卡片左下角有「立即刷新」。
Antigravity CLI：設定裡現在可以為 agy 安裝狀態列擷取，做法跟 Claude Code 一樣。使用 agy 時，額度會存到本機並立刻顯示，不必再在背景啟動 agy 查詢。沒有安裝時，查詢逾時會自動重試一次，逾時也不再顯示成錯誤。
```

### 日本語 (ja)

```text
カードの固定に対応しました。カード下部の「固定…」から、デスクトップに常に表示するカードか、タスクバーの上に並ぶ細いバー（各利用枠を数字入りの小さなバッテリーで表示）を選べます。好きな位置にドラッグでき、全画面アプリの使用中は自動で隠れます。デスクトップのカードには左下に「今すぐ更新」があります。
Antigravity CLI：Claude Code と同じように、設定から agy のステータスライン取得を導入できるようになりました。agy を使っている間は利用枠がこの PC に保存されてすぐに表示され、バックグラウンドで agy を起動する必要がありません。導入していない場合も、タイムアウトした照会は 1 回だけ再試行し、タイムアウトはエラーとして表示しなくなりました。
```

### Deutsch (de)

```text
Neu: Anheften. Über „Anheften…“ unten auf der Karte bleibt die Karte auf dem Desktop, oder sie wird zu einer schmalen Leiste über der Taskleiste, in der jedes Limit als kleiner Akku mit der Zahl darin erscheint. Du kannst sie frei verschieben; bei Vollbild-Apps blendet sie sich aus. Die Desktop-Karte hat links unten „Jetzt aktualisieren“.
Antigravity CLI: In den Einstellungen lässt sich jetzt wie bei Claude Code eine Statuszeilen-Erfassung für agy installieren. Während du agy nutzt, werden die Werte auf deinem PC gespeichert und sofort angezeigt, ohne agy im Hintergrund zu starten. Ohne Erfassung wird eine Abfrage mit Zeitüberschreitung einmal wiederholt, und eine Zeitüberschreitung erscheint nicht mehr als Fehler.
```

### 简体中文 (zh-CN)

```text
新增固定：点击卡片下方的“固定…”，可以让卡片常驻桌面，或缩成任务栏上方的一排长条（每项额度显示为一个小电池，数字就在里面）。可拖到任意位置；有全屏程序时会自动隐藏。桌面卡片左下角有“立即刷新”。
Antigravity CLI：现在可以在设置中为 agy 安装状态栏采集，做法与 Claude Code 相同。使用 agy 时，额度会保存在本机并立即显示，无需在后台启动 agy 查询。未安装时，查询超时会自动重试一次，超时也不再显示为错误。
```

## 說明

每語兩處：①第一段（「滑鼠移過去就看得到」那段）後面**新增一段**；②擷取按鈕那句**整句替換**（原句是 0.1.2 的，0.1.4 沒動過）。

### English (en)

- 新增一段（接在第一段後）→ `You can also pin the card to your desktop, or shrink it into a strip of small batteries right above the taskbar.`
- 原句 `The Claude Code “Install capture” and “Remove capture” buttons manage usage capture; they do not install or remove Claude Code.`
  → `The “Install capture” and “Remove capture” buttons for Claude Code and Antigravity CLI manage usage capture; they do not install or remove those tools.`
- 功能第 13 條 → `Pin the card to your desktop, or show limits as tiny batteries above the taskbar`

### 繁體中文 (zh-TW)

- 新增一段 → `也可以把卡片釘在桌面上，或縮成工作列上方的一排小電池。`
- 原句 `Claude Code 的「安裝擷取」與「移除擷取」只管理用量擷取，不會安裝或移除 Claude Code。`
  → `Claude Code 與 Antigravity CLI 的「安裝擷取」與「移除擷取」只管理用量擷取，不會安裝或移除這些工具。`
- 功能第 13 條 → `可釘在桌面，或以小電池長條貼在工作列上方`

### 日本語 (ja)

- 新增一段 → `カードをデスクトップに固定したり、タスクバーの上に並ぶ小さなバッテリー表示にしたりすることもできます。`
- 原句 `設定画面の Claude Code の「取得を導入／取得を削除」は、利用情報を保存するステータスライン連携を設定・解除する操作です。Claude Code 本体をインストールまたはアンインストールする操作ではありません。`
  → `設定画面の Claude Code と Antigravity CLI の「取得を導入／取得を削除」は、利用情報を保存するステータスライン連携を設定・解除する操作です。各ツール本体をインストールまたはアンインストールする操作ではありません。`
- 機能第 13 条 → `カードをデスクトップに固定、またはタスクバーの上に小さなバッテリーで表示`

### Deutsch (de)

- 新增一段 → `Du kannst die Karte auch auf dem Desktop anheften oder als Reihe kleiner Akkus direkt über der Taskleiste anzeigen.`
- 原句 `Die Claude-Schaltflächen installieren bzw. entfernen nur die Erfassung der Nutzungsdaten, nicht Claude Code selbst.`
  → `Die Schaltflächen bei Claude und Antigravity installieren bzw. entfernen nur die Erfassung der Nutzungsdaten, nicht die Tools selbst.`
- Funktion 13 → `Karte auf dem Desktop anheften oder als kleine Akkus über der Taskleiste anzeigen`

### 简体中文 (zh-CN)

- 新增一段 → `也可以把卡片固定在桌面上，或缩成任务栏上方的一排小电池。`
- 原句 `Claude 设置中的“安装采集／移除采集”仅管理用量采集，并非安装或卸载 Claude Code。`
  → `Claude 与 Antigravity 设置中的“安装采集／移除采集”仅管理用量采集，并非安装或卸载这些工具。`
- 功能第 13 条 → `可固定在桌面，或以小电池长条贴在任务栏上方`

## 截圖

`docs/store/shots/<語言>-1～4.png`（3840×2160）。1～3 原位替換（Partner Center 的截圖本身就是「更新圖片」按鈕），第 4 張加在最後。
英文、日文、德文、簡中、繁中各傳自己語言那組（英文清單配中文截圖會被退件）。

## 搜尋字詞

不用改（每語言 7 個已滿）。
