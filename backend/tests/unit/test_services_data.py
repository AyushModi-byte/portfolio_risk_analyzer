from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app.config import settings
from app.services import fx, prices, samples, sectors


@pytest.fixture(autouse=True)
def fresh_sector_cache() -> None:
    sectors._sector_map.cache_clear()
    yield
    sectors._sector_map.cache_clear()


@pytest.fixture
def dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    snap, cache = tmp_path / "snap", tmp_path / "cache"
    monkeypatch.setattr(settings, "snapshot_dir", snap)
    monkeypatch.setattr(settings, "cache_dir", cache)
    return snap, cache


def series(values: list[float], start: str = "2024-01-01") -> pd.Series:
    return pd.Series(values, index=pd.date_range(start, periods=len(values)), name="Close")


def test_filename_is_filesystem_safe() -> None:
    assert prices.filename("^NSEI") == "_NSEI.csv"
    assert prices.filename("USDINR=X") == "USDINR=X.csv"


def test_series_csv_round_trip(tmp_path: Path) -> None:
    s = series([1.0, 2.5, 3.0])
    prices.write_series(tmp_path / "a.csv", s)
    back = prices.read_series(tmp_path / "a.csv")
    assert back is not None
    assert back.tolist() == s.tolist()
    assert prices.read_series(tmp_path / "missing.csv") is None


def test_offline_uses_snapshot_with_warning(dirs: tuple[Path, Path]) -> None:
    snap, _ = dirs
    prices.write_series(snap / "AAA.csv", series([1.0, 2.0, 3.0]))
    s, warning = prices.get_series("AAA")
    assert s is not None
    assert warning is not None
    assert "snapshot" in warning


def test_missing_everywhere_returns_none_and_warning(dirs: tuple[Path, Path]) -> None:
    s, warning = prices.get_series("NOPE")
    assert s is None
    assert warning is not None
    assert "NOPE" in warning


def test_online_download_is_cached_then_reused(
    dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cache = dirs
    monkeypatch.setattr(settings, "offline", False)
    calls: list[str] = []

    def fake_download(ticker: str, years: int) -> pd.Series:
        calls.append(ticker)
        return series([5.0, 6.0])

    monkeypatch.setattr(prices, "download", fake_download)
    first, warn1 = prices.get_series("AAA")
    second, warn2 = prices.get_series("AAA")
    assert warn1 is None and warn2 is None
    assert calls == ["AAA"]  # second call served from the on-disk cache
    assert (cache / "AAA.csv").exists()
    assert second is not None and second.tolist() == [5.0, 6.0]
    assert first is not None


def test_online_failure_falls_back_to_snapshot(
    dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    snap, _ = dirs
    monkeypatch.setattr(settings, "offline", False)
    monkeypatch.setattr(prices, "download", lambda t, y: None)
    prices.write_series(snap / "AAA.csv", series([1.0, 2.0]))
    s, warning = prices.get_series("AAA")
    assert s is not None and warning is not None


def test_download_retries_then_gives_up(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []

    def boom(_: str) -> None:
        attempts.append(1)
        raise RuntimeError("rate limited")

    monkeypatch.setattr(prices.yf, "Ticker", boom)
    monkeypatch.setattr(prices.time, "sleep", lambda s: None)
    assert prices.download("AAA", 2) is None
    assert len(attempts) == prices.RETRIES


def test_download_returns_naive_adjusted_close(monkeypatch: pytest.MonkeyPatch) -> None:
    idx = pd.date_range("2024-01-01", periods=3, tz="Asia/Kolkata")
    hist = pd.DataFrame({"Close": [1.0, 2.0, 3.0]}, index=idx)
    monkeypatch.setattr(prices.yf, "Ticker", lambda t: SimpleNamespace(history=lambda **kw: hist))
    out = prices.download("AAA", 1)
    assert out is not None
    assert out.index.tz is None
    assert out.tolist() == [1.0, 2.0, 3.0]


def test_get_prices_skips_missing_tickers(dirs: tuple[Path, Path]) -> None:
    snap, _ = dirs
    prices.write_series(snap / "AAA.csv", series([1.0, 2.0]))
    df, warnings = prices.get_prices(["AAA", "NOPE"])
    assert list(df.columns) == ["AAA"]
    assert len(warnings) == 2


def test_fx_is_forward_filled_to_calendar_days(dirs: tuple[Path, Path]) -> None:
    snap, _ = dirs
    s = pd.Series([80.0, 82.0], index=pd.to_datetime(["2024-01-05", "2024-01-08"]))
    prices.write_series(snap / "USDINR=X.csv", s)
    out, _ = fx.get_usdinr()
    assert out is not None
    assert out.loc["2024-01-06"] == 80.0 and out.loc["2024-01-07"] == 80.0
    assert out.loc["2024-01-08"] == 82.0


def test_fx_unavailable_returns_none(dirs: tuple[Path, Path]) -> None:
    out, warnings = fx.get_usdinr()
    assert out is None and warnings


def test_sector_from_map_and_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "map.csv"
    path.write_text("ticker,sector\nabc.ns,Energy\n")
    monkeypatch.setattr(settings, "sector_map_path", path)
    sectors._sector_map.cache_clear()
    assert sectors.get_sector("ABC.NS") == "Energy"
    assert sectors.get_sector("ZZZ") == "Unknown"
    sectors._sector_map.cache_clear()


def test_sector_missing_map_file_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "sector_map_path", tmp_path / "none.csv")
    sectors._sector_map.cache_clear()
    assert sectors.get_sector("ABC") == "Unknown"
    sectors._sector_map.cache_clear()


def test_sector_prefers_yfinance_online(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "offline", False)
    monkeypatch.setattr(settings, "sector_map_path", tmp_path / "none.csv")
    sectors._sector_map.cache_clear()
    monkeypatch.setattr(
        sectors.yf, "Ticker", lambda t: SimpleNamespace(info={"sector": "Technology"})
    )
    assert sectors.get_sector("AAA") == "Technology"
    monkeypatch.setattr(sectors.yf, "Ticker", lambda t: SimpleNamespace(info={}))
    assert sectors.get_sector("AAA") == "Unknown"

    def boom(t: str) -> None:
        raise RuntimeError("x")

    monkeypatch.setattr(sectors.yf, "Ticker", boom)
    assert sectors.get_sector("AAA") == "Unknown"
    sectors._sector_map.cache_clear()


@pytest.mark.parametrize("name", ["india", "us", "mixed"])
def test_sample_portfolios_meet_spec(name: str) -> None:
    inputs = samples.load_sample(name)
    assert 10 <= len(inputs.holdings) <= 15
    assert len({h.sector for h in inputs.holdings}) >= 5
    assert "Unknown" not in {h.sector for h in inputs.holdings}
    assert not any("Unresolved" in w for w in inputs.warnings)


def test_list_samples() -> None:
    assert samples.list_samples() == ["india", "mixed", "us"]
