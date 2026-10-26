"""Read broker holdings files (CSV, Excel, JSON) into Holding objects, in memory only."""

import csv
import io
import json
import re
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

from app.config import settings
from app.schemas import Holding

# Header aliases per canonical field, matched case-insensitively after normalisation.
# This is the one place to extend when a new broker layout shows up.
ALIASES: dict[str, list[str]] = {
    "symbol": ["symbol", "instrument", "stock", "scrip", "ticker", "security", "stock symbol"],
    "quantity": ["quantity", "qty", "shares", "units", "quantity available", "qty."],
    "avg_buy_price": [
        "average price",
        "avg price",
        "avg. price",
        "avg cost",
        "avg. cost",
        "average cost",
        "buy price",
        "buy avg",
        "avg buy price",
        "average buy price",
        "cost price",
    ],
    "name": ["name", "company", "company name", "security name", "stock name"],
    "exchange": ["exchange", "exch", "market"],
    "currency": ["currency", "ccy"],
}
REQUIRED = ("symbol", "quantity")
HEADER_SCAN_ROWS = 30
MAX_SYMBOL_LEN = 32
MAX_NAME_LEN = 120
ALLOWED_EXTENSIONS = (".csv", ".xlsx", ".json")


# Optional hint only: normalised header sets that identify a broker export. Extend as needed.
BROKER_SIGNATURES: dict[str, set[str]] = {
    "Zerodha": {"instrument", "qty", "avg cost"},
    "Groww": {"stock name", "quantity", "average buy price"},
    "Upstox": {"scrip", "qty", "avg price"},
}
EXTENSION_HINTS = {
    ".xlsm": "Macro-enabled workbooks (.xlsm) are not accepted. Save the file as .xlsx.",
    ".xls": "Legacy .xls files are not supported. Save the file as .xlsx or .csv.",
}


class ParseError(ValueError):
    """The file is unusable (bad type, too big, unreadable, too many rows)."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class ParseResult(BaseModel):
    status: Literal["ok", "needs_mapping"]
    broker: str | None = None
    holdings: list[Holding] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)  # offered to the user when mapping is needed
    detected: dict[str, str] = Field(default_factory=dict)  # canonical field -> file column
    missing: list[str] = Field(default_factory=list)
    sample_rows: list[dict[str, str]] = Field(default_factory=list)  # first rows, for mapping help
    warnings: list[str] = Field(default_factory=list)


def _norm(header: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(header).lower()).strip()


def detect_columns(headers: list[object]) -> dict[str, str]:
    """Map canonical field -> original header using the alias lists."""
    normed = {_norm(h): str(h).strip() for h in reversed(headers)}  # first occurrence wins
    found: dict[str, str] = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            hit = normed.get(_norm(alias))
            if hit is not None:
                found[field] = hit
                break
    return found


def _read_raw(filename: str, content: bytes) -> pd.DataFrame:
    name = filename.lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
        hint = EXTENSION_HINTS.get(ext, "Upload a .csv, .xlsx or .json file.")
        raise ParseError(f"Unsupported file type. {hint}", status_code=415)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise ParseError(f"File is larger than {settings.max_upload_mb} MB.", status_code=413)
    if not content.strip():
        raise ParseError("The file is empty.")
    try:
        if name.endswith(".json"):
            data = json.loads(content.decode("utf-8-sig"))
            if isinstance(data, dict):
                data = next((v for v in data.values() if isinstance(v, list)), None)
            if not isinstance(data, list) or not data:
                raise ParseError("JSON must be a list of holdings or an object containing one.")
            return pd.json_normalize(data).astype(object)
        if name.endswith(".xlsx"):
            return pd.read_excel(io.BytesIO(content), header=None, dtype=object)
        text = content.decode("utf-8-sig")
        rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
        width = max((len(r) for r in rows), default=0)
        return pd.DataFrame([r + [None] * (width - len(r)) for r in rows], dtype=object)
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(f"Could not read the file: {type(exc).__name__}.") from exc


def _with_header(raw: pd.DataFrame, is_json: bool) -> tuple[pd.DataFrame, dict[str, str]]:
    """Find the header row (brokers often add preamble lines) and return the body below it."""
    if is_json:
        return raw, detect_columns(list(raw.columns))
    limit = min(HEADER_SCAN_ROWS, len(raw))
    for i in range(limit):
        found = detect_columns(list(raw.iloc[i].dropna()))
        if all(f in found for f in REQUIRED):
            body = raw.iloc[i + 1 :].copy()
            body.columns = [
                str(c).strip() if pd.notna(c) else f"col{j}" for j, c in enumerate(raw.iloc[i])
            ]
            return body, found
    first = raw.iloc[0] if len(raw) else pd.Series(dtype=object)
    body = raw.iloc[1:].copy()
    body.columns = [str(c).strip() if pd.notna(c) else f"col{j}" for j, c in enumerate(first)]
    return body, detect_columns(list(body.columns))


def _clean_text(value: object, limit: int) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value)).strip()
    return text[:limit] or None


def _to_number(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(re.sub(r"[,\s₹$]", "", str(value)))
    except ValueError:
        return None


def build_holdings(body: pd.DataFrame, cols: dict[str, str]) -> tuple[list[Holding], list[str]]:
    warnings: list[str] = []
    merged: dict[str, dict] = {}
    skipped = 0
    for _, row in body.iterrows():
        symbol = _clean_text(row.get(cols["symbol"]), MAX_SYMBOL_LEN)
        qty = _to_number(row.get(cols["quantity"]))
        if not symbol or qty is None or qty <= 0:
            skipped += 1
            continue
        price = _to_number(row.get(cols["avg_buy_price"])) if "avg_buy_price" in cols else None
        key = symbol.upper()
        entry = merged.get(key)
        if entry is None:
            merged[key] = {
                "symbol": key,
                "name": _clean_text(row.get(cols.get("name", "")), MAX_NAME_LEN),
                "quantity": qty,
                "cost": None if price is None else price * qty,
                "exchange": _clean_text(row.get(cols.get("exchange", "")), 16),
                "currency": _clean_text(row.get(cols.get("currency", "")), 8),
            }
        else:
            entry["quantity"] += qty
            if price is not None and entry["cost"] is not None:
                entry["cost"] += price * qty
            else:
                entry["cost"] = None
            warnings.append(f"Duplicate symbol {key} merged into one holding.")
    if skipped:
        warnings.append(f"Skipped {skipped} row(s) with a missing symbol or invalid quantity.")
    if "avg_buy_price" not in cols:
        warnings.append("No average price column found; P&L will not be available.")
    holdings = [
        Holding(
            symbol=e["symbol"],
            name=e["name"],
            quantity=e["quantity"],
            avg_buy_price=None if e["cost"] is None else e["cost"] / e["quantity"],
            exchange=e["exchange"],
            currency=e["currency"],
        )
        for e in merged.values()
    ]
    return holdings, warnings


def _sample_rows(body: pd.DataFrame, n: int = 3, width: int = 60) -> list[dict[str, str]]:
    rows = []
    for _, row in body.head(n).iterrows():
        rows.append({str(c): (_clean_text(row[c], width) or "") for c in body.columns})
    return rows


def detect_broker(headers: list[str]) -> str | None:
    normed = {_norm(h) for h in headers}
    for broker, signature in BROKER_SIGNATURES.items():
        if signature <= normed:
            return broker
    return None


def parse_holdings(
    filename: str, content: bytes, mapping: dict[str, str] | None = None
) -> ParseResult:
    """Parse an uploaded file. `mapping` (canonical field -> file column) overrides detection."""
    raw = _read_raw(filename, content)
    body, detected = _with_header(raw, filename.lower().endswith(".json"))
    if mapping:
        detected = {**detected, **{k: v for k, v in mapping.items() if k in ALIASES}}
    body = body.dropna(how="all")
    if len(body) > settings.max_rows:
        raise ParseError(f"File has more than {settings.max_rows} rows.", status_code=413)

    missing = [f for f in REQUIRED if f not in detected or detected[f] not in body.columns]
    if missing:
        return ParseResult(
            status="needs_mapping",
            columns=[str(c) for c in body.columns],
            detected={k: v for k, v in detected.items() if v in body.columns},
            missing=missing,
            sample_rows=_sample_rows(body),
            warnings=["Could not detect all required columns; please map them."],
        )
    holdings, warnings = build_holdings(body, detected)
    if not holdings:
        raise ParseError("No valid holdings found in the file.")
    return ParseResult(
        status="ok",
        broker=detect_broker([str(c) for c in body.columns]),
        holdings=holdings,
        detected=detected,
        warnings=warnings,
    )
