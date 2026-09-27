"""German interface strings."""

STRINGS = {
    "menu.refresh": "Jetzt aktualisieren",
    "menu.settings": "Einstellungen…",
    "menu.startup": "Mit Windows starten",
    "menu.quit": "Beenden",
    "startup.blocked_title": "Autostart mit Windows ist deaktiviert",
    "startup.blocked_body": "Aktiviere AI Usage Meter unter Windows-Einstellungen → Apps → Autostart.",
    "welcome.title": "AI Usage Meter läuft im Infobereich",
    "welcome.body": (
        "Zeige auf das Symbol im Infobereich, um deine Nutzung zu sehen, oder klicke mit der rechten "
        "Maustaste darauf, um die Einstellungen zu öffnen. Falls du das Symbol nicht siehst, suche unter "
        "dem Pfeil ^. Du kannst auch auf diese Benachrichtigung klicken."
    ),
    "update.title": "Neue Version verfügbar",
    "update.body": (
        "Eine neue Version von AI Usage Meter ist verfügbar. Klicke auf diese Benachrichtigung oder "
        "wähle unter Einstellungen… die Option „Update verfügbar“, um sie im Microsoft Store zu aktualisieren."
    ),
    "card.loading": "Wird geladen…",
    "card.nothing_enabled": "Keine Dienste aktiviert. Rechtsklick → Einstellungen… zum Auswählen.",
    "card.api_failed": "Quelle fehlgeschlagen; lokale Daten",
    "card.auth_expired": "Token abgelaufen; bitte {cli} öffnen",
    "card.auth_antigravity": "Antigravity CLI ist nicht angemeldet; mit agy anmelden",
    "card.auth_copilot": "Copilot-Anmeldung abgelaufen; copilot login ausführen",
    "card.disabled": "Nicht aktiviert",
    "card.claude_needs_hook": (
        "Noch keine Daten: Claude-Nutzungserfassung in den Einstellungen… installieren "
        "und Claude Code einmal verwenden"
    ),
    "card.demo_banner": "Demomodus: Beispieldaten, nicht dein tatsächliches Kontingent",
    "card.preparing": "Erstmalige Nutzung: Copilot-Komponenten werden heruntergeladen (ca. 111 MB)…",
    "card.error": "Abruf fehlgeschlagen: {err}",
    "card.unknown_error": "unbekannter Fehler",
    "card.no_data": "Keine Kontingentdaten",
    "card.unlimited": "Unbegrenzt: {items}",
    "card.reset_credits": "Reset-Gutscheine: {count}",
    "card.reset_credits_expiry": "Nächster Verfall: {date}",
    "card.reset_credits_expiry_unknown": "Nächster Verfall: nicht verfügbar",
    "card.rolled_over": "Zurückgesetzt",
    "card.estimated_reset": "~{countdown}",
    "list.sep": ", ",
    "age.unknown": "Zeit unbekannt",
    "age.now": "gerade eben",
    "age.minutes": "vor {n} Min.",
    "age.hours": "vor {n} Std.",
    "age.days": "vor {n} Tagen",
    "alert.title": "{name} {label}: {pct} % Kontingent übrig",
    "alert.body": "Im Zeitfenster {label} von {name} sind noch {pct} % übrig{reset}.",
    "alert.reset": ", Zurücksetzung in {countdown}",
    "settings.title": "AI Usage Meter – Dienste",
    "settings.heading": "Anzuzeigende Dienste auswählen",
    "settings.subtitle": "Cloud: beim Öffnen",
    "settings.col.service": "Dienst",
    "settings.col.description": "Beschreibung",
    "settings.hook.not_installed": (
        "Nur Erfassung; installiert nicht Claude Code."
    ),
    "settings.hook.installed": (
        "Nur Erfassung; Claude Code bleibt installiert."
    ),
    "settings.hook.legacy": "Eine kompatible Statuszeilen-Erfassung ist bereits eingerichtet.",
    "settings.hook.no_claude": "Claude Code wurde auf diesem PC nicht gefunden.",
    "settings.hook.unreadable": "Die Einstellungsdatei von Claude Code konnte nicht gelesen werden; nichts wurde geändert.",
    "settings.hook.install": "Erfassung an",
    "settings.hook.remove": "Erfassung aus",
    "settings.reset_credits_note": (
        "Reset-Gutscheine: Zahl/Ablauf nur Codex."
    ),
    "settings.hook.confirm_install": (
        "Claude-Statuszeilen-Erfassung installieren?\n\n"
        "Dabei wird die Einstellungsdatei von Claude Code geändert:\n{path}\n\n"
        "• Der Statuszeilen-Befehl wird durch ein kleines AI Usage Meter-Skript ersetzt "
        "(im benachbarten Ordner ai-quota-tray). Es speichert die bereits in Claude Code vorhandenen "
        "Kontingentwerte auf diesem PC. Es gibt keine API-Aufrufe und deine Anmeldung bleibt unberührt.\n"
        "• Deine bisherige Statuszeile wird weiterhin angezeigt.\n"
        "• Die Einstellungsdatei wird zuerst gesichert. Mit „Erfassung aus“ kannst du sie "
        "jederzeit wiederherstellen."
    ),
    "settings.hook.confirm_remove": (
        "Claude-Statuszeilen-Erfassung entfernen?\n\n"
        "Die Statuszeilen-Einstellung von Claude Code wird wiederhergestellt:\n{path}"
    ),
    "settings.hook.failed": "Das hat nicht funktioniert; nichts wurde geändert: {err}",
    "settings.demo": "Demomodus",
    "settings.version": " (Vers. {v})",
    "settings.update": "Update verfügbar",
    "settings.link.privacy": "Datenschutzerklärung",
    "settings.link.website": "Website",
    "settings.disclaimer": "Unabhängig von Anthropic, OpenAI, GitHub und Google",
    "settings.yes": "Ja",
    "settings.no": "Nein",
    "settings.source.codex": "Offizieller App Server; sonst lokale Daten.",
    "settings.source.antigravity": "Offizielle agy CLI; vorher mit agy anmelden.",
    "settings.source.copilot": "Offizielles SDK; vorher copilot login ausführen.",
    "settings.language": "Sprache",
    "settings.cancel": "Abbrechen",
    "settings.save": "Speichern",
    "settings.promo_eyebrow": "Ad · A FISH-ZERO app",
    "settings.promo_title": "Taskbar Buddy",
    "settings.promo_body": "A tiny pet for your Windows desktop, keeping you company as you work.",
    "settings.promo_cta": "Get it from Microsoft Store",
}
