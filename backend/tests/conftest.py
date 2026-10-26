import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test runs with the network disabled; services fall back to the snapshot."""
    monkeypatch.setattr(settings, "offline", True)
