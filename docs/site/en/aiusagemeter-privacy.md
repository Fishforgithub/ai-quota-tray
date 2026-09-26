---
title: AI Usage Meter Privacy Policy
description: The privacy policy for AI Usage Meter, covering which local records it reads, which official tools it starts to look up your usage limits, and why it collects no personal data and has no server of its own.
meta: Effective 26 September 2026 · Applies to AI Usage Meter for Windows
changefreq: yearly
priority: "0.3"
updated: 2026-09-26
---

:::lead
**AI Usage Meter has no server of its own, collects no personal data, and contains no analytics or third-party advertising.**
It never reads or stores your passwords or sign-in tokens; every usage lookup is handed to the official tool that is already signed in on your computer.
We, the developer, receive none of your data.
:::

This policy applies to the following app:

- Microsoft Store product ID: `9PLDWKRFDGDC`
- Package name: `Fish-Zero.AIUsageMeter`

AI Usage Meter is an independent third-party tool and is not affiliated with, endorsed by, or partnered with Anthropic, OpenAI, GitHub, or Google.
Product names below belong to their respective owners and are used only to describe which tool's data the app reads.

## 1. What we don't do

- No usage analytics, and no third-party tracking or advertising SDKs.
- No collection of your name, email address, phone number, or other personal data. You don't need to create an account.
- **The app never reads or stores your passwords, API keys, or sign-in tokens**, and never signs in to any service on your behalf.
- It doesn't read your conversations, code, or prompts (with one exception, explained in the Codex row of section 2: the files contain them, but we only take the usage fields).
- Nothing is sent to the developer, and nothing is sold, traded, or shared with third parties.
- The app's interface loads no fonts, scripts, or images from external websites.

## 2. Which local records it reads

The usage numbers come from records that your AI coding tools already keep on your computer. **Only services you turn on in Settings are read** (by default, only Claude and Codex).

| Service | What it reads | What it takes |
|---|---|---|
| Claude Code | `%USERPROFILE%\.claude\usage-cache.json` (written by the status line capture in section 4) | Percentage used and reset time for each limit |
| Codex | Recent session files under `%USERPROFILE%\.codex\sessions\` | Only the usage-limit data (percentage used, reset time). ⚠️ These files are Codex's own session logs and also contain your conversations. The app reads them line by line to find the usage lines; **everything else is not kept, shown, or sent anywhere** |

This reading happens on your computer and involves no network access.

## 3. When the network is used

**The app has no server of its own and sends nothing to the developer.** When live numbers are needed, it starts an official tool you have already installed in the background. That tool asks its own service for your usage **using the sign-in you already have**, and hands the result back to the app for display.

| Service | Official tool started | When |
|---|---|---|
| Claude | None, no network access | — |
| Codex | Codex CLI's `codex app-server` | When you open the usage card or choose "Refresh now" (not repeated within 2 minutes) |
| Antigravity | Antigravity CLI's `agy -p /usage` (uses no model quota) | Same as above (not repeated within 5 minutes) |
| GitHub Copilot | GitHub's official Copilot SDK | Same as above (not repeated within 5 minutes). The first time you turn it on, the SDK downloads the runtime it needs from GitHub (about 111 MB, stored in `%LOCALAPPDATA%\github-copilot-sdk`) |

In the background, the app only re-reads the local records from section 2 every 2 minutes, without using the network.

**Update check**: the version installed from the Microsoft Store asks the Microsoft Store service built into Windows whether a new version is available, about 30 seconds after it starts and every 6 hours after that. The check only asks about updates and sends no personal data or usage numbers. If there is a new version you get one notification; whether to update is up to you, in the Microsoft Store.

These lookups are made directly between each official tool and its own service, and are covered by that service's own privacy policy. The app only receives the usage numbers (percentage used, reset time, plan name). It never receives or stores your account credentials.

**Other connections**: the bottom of the Settings window shows a banner marked "Ad" that promotes another app by the same developer. It is the only ad in the app; its image is built into the app rather than loaded from the internet, and no third-party advertising code is included. Only if you click it does your browser open its Microsoft Store page. The bottom of the Settings window also has "Privacy policy" and "Website" links, which likewise open pages on this website in your browser only when you click them.

## 4. Optional: Claude status line capture

Claude Code doesn't write its usage limits to a file by itself, so the Claude row in Settings has an "Install" button. **Only after you press it and confirm** will the app:

- place a small script in `%USERPROFILE%\.claude\ai-quota-tray\` and point the status line command in Claude Code's settings file (`%USERPROFILE%\.claude\settings.json`) to it. The settings file is backed up as `settings.json.ai-quota-tray.bak` first;
- have that script save **only the usage fields** of the data Claude Code gives the status line into `usage-cache.json`, and then show your original status line as usual;
- keep your original status line settings exactly as they were. Pressing "Remove" restores them.

This script doesn't use the network either.

## 5. What stays on your computer (never sent anywhere)

| Content | Location |
|---|---|
| Settings (enabled services, interface language, demo mode) | `%LOCALAPPDATA%\ai-quota-tray\config.json` |
| Low-usage alert history (which limit was already announced in which reset period, to avoid repeats) | Same folder, `state.json` |
| Claude status line capture (only if you install it) | See section 4 |

When installed from the Microsoft Store, the first two are stored in the folder Windows reserves for the app and **are deleted by Windows when you uninstall it**.
The files from section 4 live in Claude Code's own folder and are not removed on uninstall (so Claude Code's status line doesn't suddenly break). Please press "Remove" in Settings **before** uninstalling the app.

"Start with Windows" only registers a startup entry with Windows and can be turned off at any time from the tray menu or Windows Settings.
Low-usage alerts are local Windows notifications and don't go through any server.

## 6. Children's privacy

This app is not designed for children under 13 and does not knowingly collect personal data from children.

## 7. Your choices

- **Stop all lookups**: turn services off in Settings. A service that is off is not read, queried, or shown.
- **Delete local data**: delete the folders listed in section 5, or uninstall the app.
- We have no server and keep no data about you, so there is no server-side data to delete.

## 8. Changes and contact

If this policy changes, the effective date on this page will be updated.

For any privacy question, email
[hello@fish-zero.com](mailto:hello@fish-zero.com).

Developer website: [fish-zero.com](https://fish-zero.com/)
