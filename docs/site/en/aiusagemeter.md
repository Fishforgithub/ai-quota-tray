---
title: AI Usage Meter - See how much of your AI coding tools' usage is left, right in the system tray
head_title: AI Usage Meter for the Windows system tray
description: AI Usage Meter lives in the Windows system tray. Hover the icon to see how much of each usage limit is left for AI coding tools such as Claude Code and Codex, and when it resets. It never reads your sign-in tokens and collects no data.
meta: For Windows 10 / 11 · English and Traditional Chinese interface
changefreq: monthly
priority: "0.7"
updated: 2026-09-26
---

:::lead
**Your AI coding tools' usage, one hover away.**
Every service has its own 5-hour, weekly, or monthly limits, and the worst time to find out is when you've already hit one.
AI Usage Meter sits in the system tray and puts what's left, and when it resets, on one small card.
:::

## What it does

- **Hover the tray icon to open the card**: one section per service, one row per limit,
  showing the percentage left, a progress bar, and a countdown to the reset.
- **No assumptions about limits**: some services have a 5-hour and a weekly window, others a monthly allowance or a shared pool.
  It lists exactly the limits each service reports.
- **A heads-up before you run out**: when any limit drops below 10%, you get one Windows notification,
  and only one per reset period.
- **It tells you when numbers are old**: if a lookup fails or the data is out of date, that section turns grey and shows how many minutes old it is.
  Old numbers are never passed off as current ones.
- **Can start with Windows**, and the interface switches between English and Traditional Chinese.

## Supported tools

| Tool | Where the numbers come from |
|---|---|
| Claude Code | The usage data Claude Code gives its status line. Press "Install" in Settings to start capturing it; your existing status line keeps working |
| Codex | Codex CLI's official App Server, falling back to the records Codex keeps on your computer |
| Antigravity CLI | Antigravity CLI's official `/usage` command |
| GitHub Copilot | GitHub's official Copilot SDK |

Only Claude Code and Codex are turned on by default; turn on the others in Settings. The matching tool must be installed and signed in.

AI Usage Meter is an independent tool and is not affiliated with Anthropic, OpenAI, GitHub, or Google.

## Your sign-in stays untouched

AI Usage Meter **never reads or stores your passwords or sign-in tokens**. When it needs live numbers,
it asks the official tool that is already signed in on your computer to look them up, and shows the result.
In the background it only reads local records, without using the network. It checks online only when you open the card, and not again for a few minutes.

## Privacy

**No server of its own, no analytics, no third-party advertising, and no personal data collected.** We receive none of your data.

For the details, see the [AI Usage Meter Privacy Policy](/en/aiusagemeter-privacy).

## System requirements

- Windows 10 version 1903 (build 18362) or later, or Windows 11
- 64-bit (x64)
- The AI coding tools you want to track, installed and signed in

## Download

Coming soon to the Microsoft Store, free of charge.

## Support

For problems, bugs, or privacy questions, email
[hello@fish-zero.com](mailto:hello@fish-zero.com)
with your Windows version and a description of the issue.

Developer website: [fish-zero.com](https://fish-zero.com/)
