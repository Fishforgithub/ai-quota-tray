"""讀 Windows 認證管理員（Credential Manager）的一般認證。只讀，絕不寫回（原則 3）。

gh CLI 與 Antigravity CLI（agy）都用 Go 的 keyring 套件把登入 token 存在這裡：
    gh：    target = "gh:github.com:"（目前使用中的帳號）、"gh:github.com:<帳號>"
    agy：   target = "gemini:antigravity"
Go keyring 在 Windows 上把字串原樣以 UTF-8 存成 blob；保險起見也接受 UTF-16 與
"go-keyring-base64:" 前綴（macOS 版的編碼方式，Windows 上理論上不會出現）。

只用 ctypes（標準函式庫），probe 不需要多裝東西。非 Windows 一律回 None。
"""
from __future__ import annotations

import base64
import ctypes
import sys

CRED_TYPE_GENERIC = 1
_B64_PREFIX = "go-keyring-base64:"

if sys.platform == "win32":
    from ctypes import wintypes

    class _CREDENTIAL(ctypes.Structure):
        _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
                    ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                    ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                    ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                    ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
                    ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
                    ("UserName", wintypes.LPWSTR)]

    _advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    _advapi.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.POINTER(ctypes.POINTER(_CREDENTIAL))]
    _advapi.CredReadW.restype = wintypes.BOOL
    _advapi.CredFree.argtypes = [ctypes.c_void_p]


def decode_blob(blob: bytes) -> str | None:
    """blob → 字串。看起來不像文字就回 None。"""
    if not blob:
        return None
    text = None
    for enc in ("utf-8", "utf-16-le"):
        try:
            candidate = blob.decode(enc)
        except UnicodeDecodeError:
            continue
        if candidate.isprintable() or candidate.strip().startswith("{"):
            text = candidate
            break
    if text is None:
        return None
    text = text.strip().strip("\x00")
    if text.startswith(_B64_PREFIX):
        try:
            text = base64.b64decode(text[len(_B64_PREFIX):]).decode("utf-8")
        except ValueError:
            return None
    return text or None


def read_generic(target: str) -> str | None:
    """讀一筆一般認證的密碼欄位。找不到、非 Windows、或讀不懂 → None。"""
    if sys.platform != "win32":
        return None
    ptr = ctypes.POINTER(_CREDENTIAL)()
    if not _advapi.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(ptr)):
        return None
    try:
        cred = ptr.contents
        blob = bytes(cred.CredentialBlob[:cred.CredentialBlobSize])
    finally:
        _advapi.CredFree(ptr)
    return decode_blob(blob)
