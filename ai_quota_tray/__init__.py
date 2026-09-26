"""AI Usage Meter：系統匣顯示各家 AI 訂閱的剩餘額度。"""
__version__ = "0.1.1"  # 與 pyproject 一致（test_msix 檢查）；MSIX／exe 版本資訊是四段式，見 display_version


def display_version() -> str:
    """畫面上顯示的版號，與 MSIX 套件版本、exe 版本資訊同樣是四段式（最後一段固定 0）。"""
    return f"{__version__}.0"
