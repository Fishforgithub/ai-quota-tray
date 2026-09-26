---
title: AI Usage Meter - 在系統匣看 AI 程式開發工具還剩多少用量
head_title: AI Usage Meter 系統匣 AI 用量顯示
description: AI Usage Meter 住在 Windows 系統匣，滑鼠移到圖示上就能看到 Claude Code、Codex 等 AI 程式開發工具各額度還剩多少、多久後重置。不讀取你的登入權杖，也不收集任何資料。
meta: Windows 10／11 適用 · 繁體中文／English 介面
changefreq: monthly
priority: "0.7"
updated: 2026-09-26
---

:::lead
**AI 程式開發工具的用量，滑鼠移過去就看得到。**每一家各有 5 小時、每週、每月不同的額度，用完了才發現最麻煩。AI Usage Meter 待在系統匣裡，把還剩多少、多久後重置整理在一張小卡片上。
:::

## 它會做什麼

- **滑鼠移到系統匣圖示上就彈出卡片**：每個服務一個區塊，每個額度一列，顯示剩餘百分比、進度條和重置倒數。
- **額度結構不寫死**：有的服務是 5 小時＋每週，有的是每月、有的是共用額度池，它照實際回傳的額度逐一列出來。
- **快用完時提醒你**：任何一個額度剩不到 10%，就用 Windows 通知提醒一次；同一個重置週期不會重複吵你。
- **資料舊了會說**：查詢失敗或資料過時，那一塊會變灰並標示是幾分鐘前的數字，不會把舊數字當成現在的。
- **可以開機自動啟動**，也可以切換繁體中文／English 介面。

## 支援的工具

| 工具 | 資料從哪裡來 |
|---|---|
| Claude Code | Claude Code 提供給狀態列的額度資料。設定裡按一下「安裝」即可開始擷取，原本的狀態列照常顯示 |
| Codex | Codex CLI 官方的 App Server；查不到時改讀 Codex 在本機留下的紀錄 |
| Antigravity CLI | Antigravity CLI 官方的 `/usage` 指令 |
| GitHub Copilot | GitHub 官方的 Copilot SDK |

預設只啟用 Claude Code 與 Codex，其他的到設定裡勾選。你需要先安裝並登入對應的工具。

AI Usage Meter 是獨立開發的工具，與 Anthropic、OpenAI、GitHub、Google 沒有隸屬或合作關係。

## 不碰你的登入

AI Usage Meter **不讀取、不保存你的密碼或登入權杖**。需要即時數字時，它請你電腦上已經登入的官方工具自己去查，再把結果顯示出來。平常在背景只讀本機紀錄、不連網；只有在你打開卡片時才會查詢雲端，而且幾分鐘內不重複查。

## 隱私

**沒有自己的伺服器、沒有分析追蹤、沒有廣告，也不收集個人資料。**我們收不到你的任何資料。

詳細說明請看 [AI Usage Meter 隱私權政策](/aiusagemeter-privacy)。

## 系統需求

- Windows 10 1903（build 18362）以上，或 Windows 11
- 64 位元（x64）
- 已安裝並登入要查詢的 AI 程式開發工具

## 下載

即將在 Microsoft Store 上架，免費使用。

## 支援

使用上有問題、功能異常，或對隱私權有疑問，請寄信到[hello@fish-zero.com](mailto:hello@fish-zero.com)，並附上 Windows 版本與問題說明。

開發者網站：[fish-zero.com](https://fish-zero.com/)
