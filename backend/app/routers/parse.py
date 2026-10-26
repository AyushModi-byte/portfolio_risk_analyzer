import json
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import Field

from app.config import settings
from app.schemas import SampleInfo
from app.services import parsers, samples, tickers
from app.services.parsers import ParseError, ParseResult

router = APIRouter(prefix="/api")


class ParseResponse(ParseResult):
    unresolved_symbols: list[str] = Field(default_factory=list)


@router.get("/samples", response_model=list[SampleInfo])
def list_samples() -> list[SampleInfo]:
    out: list[SampleInfo] = []
    for name in samples.list_samples():
        base, benchmark = samples.SAMPLE_SETUP[name]
        path = samples.SAMPLES_DIR / f"{name}.csv"
        holdings = parsers.parse_holdings(path.name, path.read_bytes()).holdings
        out.append(
            SampleInfo(name=name, base_currency=base, benchmark=benchmark, holdings=holdings)
        )
    return out


def _read_mapping(raw: str | None) -> dict[str, str] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise ParseError("mapping must be a JSON object.") from exc
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise ParseError("mapping must be a JSON object of column names.")
    return value


@router.post("/parse", response_model=ParseResponse)
def parse(
    file: Annotated[UploadFile, File()], mapping: Annotated[str | None, Form()] = None
) -> ParseResponse:
    """Parse an uploaded holdings file in memory.

    `mapping` is an optional JSON object (canonical field -> column name) for use after a
    `needs_mapping` response.
    """
    limit = settings.max_upload_mb * 1024 * 1024
    content = file.file.read(limit + 1)  # in memory only, never written to disk
    result = parsers.parse_holdings(file.filename or "", content, _read_mapping(mapping))
    unresolved: list[str] = []
    if result.status == "ok":
        _, unresolved = tickers.resolve_symbols(
            [h.symbol for h in result.holdings],
            exchanges={h.symbol: h.exchange for h in result.holdings},
        )
    return ParseResponse(**result.model_dump(), unresolved_symbols=unresolved)
