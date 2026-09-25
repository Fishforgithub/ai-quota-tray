"""各家 provider。每個模組提供 NAME 與 fetch(use_token, now) -> ProviderState。"""
from . import claude, codex, grok

ALL = {m.NAME: m for m in (claude, codex, grok)}
