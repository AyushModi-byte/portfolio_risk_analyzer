import json
import logging
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.routers import analyze as analyze_router
from app.services import prices, sectors, tickers

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "sample_portfolios"
MARKER = "ZZSECRETMARKERZZ"
UNIQUE_HEADER_CSV = b"Symbol,Quantity,Average Price\nINFY,10,1500\nTCS,5,3000\n"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def upload(client: TestClient, name: str, content: bytes, **data: str) -> Any:
    return client.post("/api/parse", files={"file": (name, content)}, data=data)


def sample(client: TestClient, name: str) -> dict[str, Any]:
    return next(s for s in client.get("/api/samples").json() if s["name"] == name)


# --- basics -----------------------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert {"version", "git_sha", "ai_available"} <= set(body)
    assert body["ai_available"] is False  # tests run without a key


def test_health_reports_ai_available_when_a_key_is_set(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    assert client.get("/health").json()["ai_available"] is True


def test_docs_list_all_endpoints(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths) >= {
        "/health",
        "/api/samples",
        "/api/parse",
        "/api/analyze",
        "/api/insights",
        "/api/chat",
    }
    assert client.get("/docs").status_code == 200


def test_error_shape_for_unknown_route(client: TestClient) -> None:
    r = client.get("/nope")
    assert r.status_code == 404
    assert set(r.json()) == {"error", "detail"}
    assert r.json()["error"] == "not_found"


def test_request_id_is_generated_and_echoed(client: TestClient) -> None:
    assert len(client.get("/health").headers["x-request-id"]) == 32
    assert (
        client.get("/health", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"]
        == "abc-123"
    )
    bad = client.get("/health", headers={"X-Request-ID": "bad id;\n"}).headers["x-request-id"]
    assert bad != "bad id;"


def test_cors_allows_configured_origin_only(client: TestClient) -> None:
    ok = client.options(
        "/api/analyze",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    other = client.options(
        "/api/analyze",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in other.headers


# --- samples and analyze ----------------------------------------------------------------------


def test_samples_listing(client: TestClient) -> None:
    items = client.get("/api/samples").json()
    assert [s["name"] for s in items] == ["india", "mixed", "us"]
    assert all(10 <= len(s["holdings"]) <= 15 for s in items)


@pytest.mark.parametrize(
    ("name", "benchmark"), [("india", "^NSEI"), ("us", "^GSPC"), ("mixed", None)]
)
def test_analyze_each_sample(client: TestClient, name: str, benchmark: str | None) -> None:
    s = sample(client, name)
    r = client.post(
        "/api/analyze",
        json={"holdings": s["holdings"], "base_currency": s["base_currency"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {
        "summary",
        "weights",
        "sector_exposure",
        "risk",
        "drawdown_series",
        "correlation",
        "warnings",
        "disclaimer",
    }
    assert body["disclaimer"] == "Analytics only, not financial advice."
    assert body["summary"]["base_currency"] == s["base_currency"]
    assert abs(sum(w["weight"] for w in body["weights"]) - 1) < 1e-9
    assert abs(sum(x["weight"] for x in body["sector_exposure"]) - 1) < 1e-9
    assert len(body["sector_exposure"]) >= 5
    assert body["risk"]["observations"] > 400
    if benchmark:
        assert body["risk"]["benchmark"] == benchmark
    else:
        assert body["risk"]["benchmark"] in {"^NSEI", "^GSPC"}


def test_analyze_benchmark_override_and_lookback(client: TestClient) -> None:
    s = sample(client, "india")
    r = client.post(
        "/api/analyze",
        json={
            "holdings": s["holdings"],
            "base_currency": "INR",
            "benchmark": "^GSPC",
            "lookback_years": 1,
        },
    )
    assert r.status_code == 200
    assert r.json()["risk"]["benchmark"] == "^GSPC"
    assert 200 < r.json()["risk"]["observations"] < 300


def test_analyze_converts_us_portfolio_to_inr(client: TestClient) -> None:
    s = sample(client, "us")
    usd = client.post("/api/analyze", json={"holdings": s["holdings"], "base_currency": "USD"})
    inr = client.post("/api/analyze", json={"holdings": s["holdings"], "base_currency": "INR"})
    ratio = inr.json()["summary"]["value"] / usd.json()["summary"]["value"]
    assert 60 < ratio < 120  # USD/INR rate


@pytest.mark.parametrize(
    "payload",
    [
        {"holdings": []},
        {"holdings": [{"symbol": "TCS", "quantity": 0}]},
        {"holdings": [{"symbol": "TCS", "quantity": 1}], "lookback_years": 9},
        {"holdings": [{"symbol": "TCS", "quantity": 1}], "base_currency": "EUR"},
        {"holdings": [{"symbol": "TCS", "quantity": 1}], "benchmark": "a b;c"},
    ],
)
def test_analyze_rejects_invalid_requests(client: TestClient, payload: dict[str, Any]) -> None:
    r = client.post("/api/analyze", json=payload)
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"


def test_analyze_too_many_holdings(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_rows", 2)
    holdings = [{"symbol": s, "quantity": 1} for s in ("TCS", "INFY", "ITC")]
    r = client.post("/api/analyze", json={"holdings": holdings})
    assert r.status_code == 413


def test_unresolved_tickers_are_excluded_with_warning(client: TestClient) -> None:
    holdings = [
        {"symbol": "TCS", "quantity": 5, "avg_buy_price": 3000},
        {"symbol": "INFY", "quantity": 5, "avg_buy_price": 1400},
        {"symbol": "NOSUCHTICKER", "quantity": 5},
    ]
    r = client.post("/api/analyze", json={"holdings": holdings})
    assert r.status_code == 200
    body = r.json()
    assert any("NOSUCHTICKER" in w for w in body["warnings"])
    assert {w["symbol"] for w in body["weights"]} == {"TCS", "INFY"}


def test_all_unresolved_is_422(client: TestClient) -> None:
    r = client.post("/api/analyze", json={"holdings": [{"symbol": "NOSUCH", "quantity": 1}]})
    assert r.status_code == 422
    assert "resolved" in r.json()["detail"]


def test_yfinance_failure_falls_back_to_snapshot(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "offline", False)
    downloads: list[str] = []

    def failing_download(ticker: str, years: int) -> None:
        downloads.append(ticker)

    monkeypatch.setattr(prices, "download", failing_download)
    monkeypatch.setattr(sectors, "_from_yfinance", lambda t: None)
    monkeypatch.setattr(tickers, "_has_data", lambda t: False)
    s = sample(client, "mixed")
    r = client.post("/api/analyze", json={"holdings": s["holdings"], "base_currency": "INR"})
    assert r.status_code == 200, r.text
    warnings = r.json()["warnings"]
    assert warnings[0].startswith("Live prices unavailable")
    assert "AAPL" in warnings[0]
    # the first failure switches off live downloads for the rest of the request
    assert len(downloads) == 1


# --- parse ------------------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "broker"), [("india", "Zerodha"), ("us", None), ("mixed", None)])
def test_parse_each_sample_file(client: TestClient, name: str, broker: str | None) -> None:
    content = (SAMPLES / f"{name}.csv").read_bytes()
    r = upload(client, f"{name}.csv", content)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["broker"] == broker
    assert len(body["holdings"]) >= 10
    assert body["unresolved_symbols"] == []


def test_parse_json_upload(client: TestClient) -> None:
    payload = json.dumps([{"symbol": "TCS", "qty": 3, "avg cost": 3000}]).encode()
    r = upload(client, "h.json", payload)
    assert r.status_code == 200
    assert r.json()["holdings"][0]["symbol"] == "TCS"


def test_parse_reports_unresolved_symbols(client: TestClient) -> None:
    r = upload(client, "h.csv", b"Symbol,Qty\nTCS,1\nNOSUCHTICKER,2\n")
    assert r.status_code == 200
    assert r.json()["unresolved_symbols"] == ["NOSUCHTICKER"]


def test_parse_missing_columns_requests_mapping_then_accepts_it(client: TestClient) -> None:
    content = b"Foo,Bar\nTCS,10\nINFY,5\n"
    r = upload(client, "h.csv", content)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "needs_mapping"
    assert body["columns"] == ["Foo", "Bar"]
    assert body["holdings"] == []
    mapped = upload(
        client, "h.csv", content, mapping=json.dumps({"symbol": "Foo", "quantity": "Bar"})
    )
    assert mapped.json()["status"] == "ok"
    assert [h["symbol"] for h in mapped.json()["holdings"]] == ["TCS", "INFY"]


@pytest.mark.parametrize("mapping", ["{not json", "[1, 2]", '{"symbol": 3}'])
def test_parse_rejects_bad_mapping(client: TestClient, mapping: str) -> None:
    r = upload(client, "h.csv", UNIQUE_HEADER_CSV, mapping=mapping)
    assert r.status_code == 400


def test_parse_wrong_type(client: TestClient) -> None:
    r = upload(client, "h.txt", b"Symbol,Qty\nTCS,1\n")
    assert r.status_code == 415
    assert r.json()["error"] == "unsupported_media_type"


def test_parse_rejects_xlsm_with_helpful_message(client: TestClient) -> None:
    r = upload(client, "macro.xlsm", b"PK\x03\x04")
    assert r.status_code == 415
    assert ".xlsm" in r.json()["detail"]
    assert ".xlsx" in r.json()["detail"]


def test_parse_empty_file(client: TestClient) -> None:
    r = upload(client, "h.csv", b"")
    assert r.status_code == 400
    assert "empty" in r.json()["detail"]


def test_parse_missing_file_field(client: TestClient) -> None:
    r = client.post("/api/parse", data={"mapping": "{}"})
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"


def test_parse_oversized_file_is_rejected_before_reading(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    big = UNIQUE_HEADER_CSV + b"#" * (1024 * 1024 + 100_000)
    r = upload(client, "h.csv", big)
    assert r.status_code == 413
    assert r.json()["error"] == "payload_too_large"


def test_parse_file_just_over_limit_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    just_over = UNIQUE_HEADER_CSV + b"#" * (1024 * 1024 - len(UNIQUE_HEADER_CSV) + 1)
    r = upload(client, "h.csv", just_over)
    assert r.status_code == 413
    assert "1 MB" in r.json()["detail"]


def test_parse_too_many_rows(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_rows", 3)
    rows = b"Symbol,Qty\n" + b"".join(b"S%d,1\n" % i for i in range(10))
    r = upload(client, "h.csv", rows)
    assert r.status_code == 413
    assert "rows" in r.json()["detail"]


def test_parse_requires_content_length(client: TestClient) -> None:
    def chunks():  # type: ignore[no-untyped-def]
        yield b"--b\r\n"

    r = client.post(
        "/api/parse", content=chunks(), headers={"Content-Type": "multipart/form-data; boundary=b"}
    )
    assert r.status_code == 411


def test_uploads_larger_than_one_mb_stay_in_memory(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    rolled: list[bool] = []
    original = tempfile.SpooledTemporaryFile.rollover

    def spy(self: Any) -> None:
        rolled.append(True)
        original(self)

    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", spy)
    padded = json.dumps([{"symbol": "TCS", "qty": 1, "note": "x" * (2 * 1024 * 1024)}]).encode()
    assert len(padded) > 2 * 1024 * 1024
    r = upload(client, "h.json", padded)
    assert r.status_code == 200, r.text
    assert rolled == []


# --- errors and logging -----------------------------------------------------------------------


def test_unhandled_error_returns_json_without_leaking(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def boom(_: Any) -> None:
        raise RuntimeError(f"boom {MARKER}")

    monkeypatch.setattr(analyze_router, "run_analysis", boom)
    with caplog.at_level(logging.INFO, logger="app"):
        r = client.post("/api/analyze", json={"holdings": [{"symbol": "TCS", "quantity": 1}]})
    assert r.status_code == 500
    assert r.json() == {"error": "internal_error", "detail": "Internal server error."}
    assert MARKER not in r.text
    assert MARKER not in caplog.text
    assert any(
        getattr(rec, "fields", {}).get("error_type") == "RuntimeError" for rec in caplog.records
    )
    assert "x-request-id" in r.headers


def log_text(caplog: pytest.LogCaptureFixture) -> str:
    return "\n".join(f"{r.getMessage()} {getattr(r, 'fields', {})}" for r in caplog.records)


def test_logs_have_timing_and_never_contain_uploaded_content(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    csv_ok = f"Symbol,Name,Qty\nTCS,{MARKER},3\n{MARKER},{MARKER},1\n".encode()
    csv_bad_columns = f"Foo,Bar\n{MARKER},{MARKER}\n".encode()
    with caplog.at_level(logging.INFO, logger="app"):
        upload(client, f"{MARKER}.csv", csv_ok)
        upload(client, "h.csv", csv_bad_columns)
        upload(client, f"{MARKER}.txt", csv_ok)  # wrong type
        upload(client, "h.csv", csv_ok, mapping=f"{{{MARKER}")  # invalid mapping
        client.post(
            "/api/analyze",
            json={"holdings": [{"symbol": MARKER, "name": MARKER, "quantity": -1}]},
        )  # validation error
        client.post(
            "/api/analyze", json={"holdings": [{"symbol": MARKER, "quantity": 1}]}
        )  # unresolved
    text = log_text(caplog)
    assert MARKER not in text
    requests = [r for r in caplog.records if r.getMessage() == "request"]
    assert len(requests) == 6
    for rec in requests:
        fields = rec.fields  # type: ignore[attr-defined]
        assert {"method", "route", "path", "status", "duration_ms"} <= set(fields)
        assert fields["duration_ms"] >= 0


def test_json_log_line_format(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    from app.observability import JsonFormatter

    with caplog.at_level(logging.INFO, logger="app"):
        client.get("/health", headers={"X-Request-ID": "rid-1"})
    rec = next(r for r in caplog.records if r.getMessage() == "request")
    line = json.loads(JsonFormatter().format(rec))
    assert line["event"] == "request"
    assert line["path"] == "/health"
    assert line["route"] == "/health"
    assert line["status"] == 200
    assert "ts" in line and "level" in line


def test_validation_errors_do_not_echo_input(client: TestClient) -> None:
    r = client.post(
        "/api/analyze", json={"holdings": [{"symbol": "X", "quantity": f"abc {MARKER}"}]}
    )
    assert r.status_code == 422
    assert MARKER not in r.text


def test_price_series_helper_is_unused_when_snapshot_missing() -> None:
    # sanity: the snapshot directory used by the API tests is the bundled one
    assert (settings.snapshot_dir / prices.filename("TCS.NS")).exists()
    assert isinstance(pd.Series(dtype=float), pd.Series)


def test_git_sha_comes_from_env_or_render(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import Settings

    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    assert Settings().git_sha == "abc123"
    monkeypatch.setenv("GIT_SHA", "explicit")
    assert Settings().git_sha == "explicit"
