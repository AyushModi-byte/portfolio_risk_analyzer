from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import BACKEND_DIR, settings
from app.schemas import AnalysisResult, AnalyzeRequest
from app.services import parsers, prices, sectors
from app.services.pipeline import run_analysis

SAMPLES = BACKEND_DIR / "data" / "sample_portfolios"


def build_request(name: str = "mixed", base: str = "INR") -> AnalyzeRequest:
    path = SAMPLES / f"{name}.csv"
    holdings = parsers.parse_holdings(path.name, path.read_bytes()).holdings
    return AnalyzeRequest(holdings=holdings, base_currency=base)  # type: ignore[arg-type]


@pytest.fixture(scope="session")
def mixed_request() -> AnalyzeRequest:
    return build_request("mixed")


@pytest.fixture(scope="session")
def analysis(
    mixed_request: AnalyzeRequest, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[AnalysisResult]:
    """The mixed sample analysed offline from the bundled snapshot."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "offline", True)
        mp.setattr(settings, "cache_dir", Path(tmp_path_factory.mktemp("cache")))
        prices._memory.clear()
        sectors._memory.clear()
        yield run_analysis(mixed_request)
