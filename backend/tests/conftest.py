from pathlib import Path

import pytest

from app import ratelimit
from app.config import settings
from app.services import prices, sectors


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Every test runs with the network disabled and isolated caches.

    Services fall back to the bundled snapshot; the disk cache goes to a temp dir.
    """
    monkeypatch.setattr(settings, "offline", True)
    monkeypatch.setattr(settings, "gemini_api_key", "")  # tests never use a real key
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "price_cache")
    ratelimit.reset()
    prices._memory.clear()
    sectors._memory.clear()
    sectors._sector_map.cache_clear()
