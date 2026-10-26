"""Checks that keep model text honest: every number must come from the analysis, no advice."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.schemas import AnalysisResult

TOP_N = 5  # the "top N" used by risk.top5_concentration
VAR_CONFIDENCE = 0.95

SCALES = {
    "k": 1e3,
    "thousand": 1e3,
    "lakh": 1e5,
    "m": 1e6,
    "million": 1e6,
    "crore": 1e7,
    "bn": 1e9,
    "billion": 1e9,
}
_NUMBER = re.compile(
    r"(?<![\w.])(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?P<frac>\.\d+)?"
    r"(?P<suffix>\s?%|\s?(?:k|thousand|lakh|m|million|crore|bn|billion)\b)?",
    re.IGNORECASE,
)
# Phrases whose digits are not metrics.
_STRIP = [
    re.compile(r"\b1[- ]day\b", re.IGNORECASE),
    re.compile(r"\bS&P\s?500\b", re.IGNORECASE),
    re.compile(r"\bNifty\s?50\b", re.IGNORECASE),
    re.compile(r"(?m)^\s*(?:\d+[.)]|[-*•])\s+"),  # list markers
]


@dataclass(frozen=True)
class ParsedNumber:
    raw: str
    value: float
    decimals: int
    scale: float


def extract_numbers(text: str, ignore_terms: Iterable[str] = ()) -> list[ParsedNumber]:
    for term in sorted({t for t in ignore_terms if t}, key=len, reverse=True):
        text = re.sub(re.escape(term), " ", text, flags=re.IGNORECASE)
    for pattern in _STRIP:
        text = pattern.sub(" ", text)
    found: list[ParsedNumber] = []
    for m in _NUMBER.finditer(text):
        frac = m.group("frac") or ""
        suffix = (m.group("suffix") or "").strip().lower()
        found.append(
            ParsedNumber(
                raw=m.group(0).strip(),
                value=float(m.group("int").replace(",", "") + frac),
                decimals=max(len(frac) - 1, 0),
                scale=SCALES.get(suffix, 1.0),
            )
        )
    return found


def number_matches(n: ParsedNumber, candidate: float) -> bool:
    """True if the text number equals the candidate (or candidate x 100) within its rounding."""
    tol = 0.5 * 10 ** (-n.decimals) + 1e-9
    for form in (abs(candidate), abs(candidate) * 100):
        if abs(n.value - form / n.scale) <= tol:
            return True
    return False


def unsupported_numbers(
    text: str, allowed: Iterable[float], ignore_terms: Iterable[str] = ()
) -> list[str]:
    """Numbers in the text that match none of the allowed values."""
    pool = list(allowed)
    return [
        n.raw
        for n in extract_numbers(text, ignore_terms)
        if not any(number_matches(n, c) for c in pool)
    ]


_DIGITS_IN_STRING = re.compile(r"\d+(?:\.\d+)?")


def numbers_in_payload(payload: Any) -> list[float]:
    """Every numeric value in a JSON-like payload, including digits inside strings (dates)."""
    out: list[float] = []

    def walk(x: Any) -> None:
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, int | float):
            out.append(float(x))
        elif isinstance(x, str):
            out.extend(float(d) for d in _DIGITS_IN_STRING.findall(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list | tuple):
            for v in x:
                walk(v)

    walk(payload)
    return out


# --- advice detection -------------------------------------------------------------------------

_ADVICE = [
    r"\bi\s+(?:would\s+|'d\s+|strongly\s+)?(?:recommend|suggest|advise)\b",
    r"\bwe\s+(?:recommend|suggest|advise)\b",
    r"\byou\s+(?:should|could|might\s+want\s+to|ought\s+to|must|need\s+to)\s+(?:\w+\s+){0,2}"
    r"(?:buy|sell|hold|invest|add|trim|reduce|exit|dump|rebalance|diversify|accumulate)\b",
    r"(?:^|[.!?]\s+)(?:buy|sell|accumulate|dump|exit|trim|short)\b",
    r"\b(?:buy|sell)\s+(?-i:[A-Z]{2,6})\b",
    r"\b(?:is|are|a)\s+(?:a\s+)?(?:good|great|strong)\s+(?:buy|sell)\b",
    r"\bstrong\s+(?:buy|sell)\b",
    r"\bprice\s+target\b",
    r"\bwill\s+(?:go\s+up|rise|fall|outperform|underperform|double|crash)\b",
]
_ADVICE_RE = [re.compile(p, re.IGNORECASE) for p in _ADVICE]

_ADVICE_REQUEST = [
    r"\b(?:should|shall|ought)\s+i\s+(?:\w+\s+){0,2}(?:buy|sell|hold|invest|add|trim|exit|dump|keep)\b",
    r"\b(?:what|which)\s+(?:\w+\s+){0,2}(?:to|should\s+i)\s+(?:buy|sell)\b",
    r"\b(?:buy|sell)\s+(?:or|and)\s+(?:sell|buy|hold)\b",
    r"\b(?:good|right|best)\s+time\s+to\s+(?:buy|sell|invest|exit)\b",
    r"\b(?:recommend|recommendation|stock\s+tip|tips?\s+for|price\s+target)\b",
    r"\b(?:will|would)\s+\w+\s+(?:go\s+up|rise|fall|crash|double)\b",
    r"\bpredict\b",
]
_ADVICE_REQUEST_RE = [re.compile(p, re.IGNORECASE) for p in _ADVICE_REQUEST]


def contains_advice(text: str, ignore_terms: Iterable[str] = ()) -> bool:
    """True if the text reads as advice. Known symbols and names are data, so they are skipped."""
    for term in sorted({t for t in ignore_terms if t}, key=len, reverse=True):
        text = re.sub(re.escape(term), " ", text, flags=re.IGNORECASE)
    return any(p.search(text) for p in _ADVICE_RE)


def is_advice_request(question: str) -> bool:
    return any(p.search(question) for p in _ADVICE_REQUEST_RE)


# --- metric index for the insight writer ------------------------------------------------------

_PERCENT_KEYS = {
    "risk.volatility",
    "risk.var_95",
    "risk.max_drawdown",
    "risk.risk_free_rate",
    "risk.top5_concentration",
    "summary.pnl_pct",
    "param.var_confidence",
}
_PERCENT_PREFIXES = ("weight.", "sector.", "rank.", "sector_rank.", "volatility.")
_MONEY_KEYS = {"summary.value", "summary.invested", "summary.pnl"}


def metric_index(a: AnalysisResult) -> dict[str, float]:
    """Flat key -> value map of every number an insight may cite."""
    m: dict[str, float] = {
        "summary.value": a.summary.value,
        "summary.invested": a.summary.invested,
        "summary.pnl": a.summary.pnl,
        "risk.volatility": a.risk.volatility,
        "risk.var_95": a.risk.var_95,
        "risk.max_drawdown": a.risk.max_drawdown,
        "risk.risk_free_rate": a.risk.risk_free_rate,
        "risk.hhi": a.risk.hhi,
        "risk.effective_n": a.risk.effective_n,
        "risk.top5_concentration": a.risk.top5_concentration,
        "risk.observations": float(a.risk.observations),
        "risk.trading_days": float(a.risk.trading_days),
        "param.var_confidence": VAR_CONFIDENCE,
        "param.top_n": float(TOP_N),
        "count.holdings": float(len(a.weights)),
        "count.sectors": float(len(a.sector_exposure)),
    }
    if a.summary.pnl_pct is not None:
        m["summary.pnl_pct"] = a.summary.pnl_pct
    if a.risk.beta is not None:
        m["risk.beta"] = a.risk.beta
    if a.risk.sharpe is not None:
        m["risk.sharpe"] = a.risk.sharpe
    for w in a.weights:
        m[f"weight.{w.symbol}"] = w.weight
        if w.volatility is not None:
            m[f"volatility.{w.symbol}"] = w.volatility
    for s in a.sector_exposure:
        m[f"sector.{s.sector}"] = s.weight
    if a.weights:
        m["rank.1.weight"] = max(w.weight for w in a.weights)
    if a.sector_exposure:
        m["sector_rank.1.weight"] = max(s.weight for s in a.sector_exposure)
    return m


def display_value(key: str, value: float, currency: str = "") -> str:
    if key in _PERCENT_KEYS or key.startswith(_PERCENT_PREFIXES):
        return f"{value * 100:.2f}%"
    if key in _MONEY_KEYS:
        return f"{value:,.0f} {currency}".strip()
    if key.startswith(("count.", "param.top_n", "risk.observations", "risk.trading_days")):
        return f"{value:.0f}"
    return f"{value:.2f}"


def prompt_metrics(a: AnalysisResult, max_weights: int = 15) -> list[dict[str, str]]:
    """Metric list shown to the model: key plus display string. Long tails are trimmed."""
    index = metric_index(a)
    top = {f"weight.{w.symbol}" for w in sorted(a.weights, key=lambda w: -w.weight)[:max_weights]}
    rows = []
    for key, value in index.items():
        if key.startswith("weight.") and key not in top:
            continue
        if key.startswith("volatility."):
            continue
        rows.append({"key": key, "display": display_value(key, value, a.summary.base_currency)})
    return rows


def symbol_terms(a: AnalysisResult) -> list[str]:
    """Names to ignore when scanning text for numbers (they may contain digits)."""
    return (
        [w.symbol for w in a.weights] + [s.sector for s in a.sector_exposure] + [a.risk.benchmark]
    )
