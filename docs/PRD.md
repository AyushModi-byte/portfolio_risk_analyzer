# Product Requirements: Portfolio Risk Analyzer

Portfolio Risk Analyzer lets an investor upload a broker holdings file and see risk, sector exposure and drawdown in one dashboard, with AI-written insights that can only quote numbers the code computed.

## Problem

Broker apps show profit and loss per stock but not portfolio-level risk: volatility, beta, drawdown and concentration. Mixed Indian and US holdings make this harder because prices and currencies differ.

## Goals

1. Upload CSV, Excel or JSON, or pick a sample portfolio, and get a full dashboard.
2. Metrics match an independent library (quantstats) and hand-calculated fixtures within a stated tolerance.
3. The AI explains results but never calculates or invents numbers.
4. Runs end to end on free hosting: Vercel (frontend) and Render (backend).
5. Portfolio-grade engineering: tests, CI/CD, an agent eval suite and structured logs.

## Non-goals

- No trading, no buy or sell advice, no tax, no options or futures.
- No user accounts, and no storage of uploaded files (processed in memory only).
- No real-time tick data; daily prices only.

## Users

- **Primary:** a retail investor holding Indian and/or US stocks.
- **Secondary:** a recruiter or interviewer who opens the demo and clicks "Try sample portfolio".

## Features

P0 = must have, P1 = should have, P2 = nice to have.

| ID | Feature | Priority |
| --- | --- | --- |
| F1 | Upload CSV, Excel or JSON, plus sample portfolios (India, US, mixed) | P0 |
| F2 | Broker format detection, with manual column mapping as fallback | P0 |
| F3 | Ticker resolution (NSE .NS, BSE .BO, US) with a list of unresolved symbols | P0 |
| F4 | Price fetch with caching and a bundled offline snapshot as fallback | P0 |
| F5 | Holdings value, P&L, weights, top-5 concentration, HHI | P0 |
| F6 | Sector exposure | P0 |
| F7 | Risk: volatility, beta, Sharpe ratio, 1-day VaR | P0 |
| F8 | Max drawdown and drawdown chart | P0 |
| F9 | Base currency choice (INR or USD) with FX conversion | P0 |
| F10 | Correlation heatmap | P1 |
| F11 | AI insights, checked against computed numbers | P1 |
| F12 | Q&A chat that calls fixed analytics tools | P1 |
| F13 | Structured request logging and optional Langfuse tracing | P2 |
| F14 | Export report as CSV or PDF | P2 |

## Requirements

### Functional

- Accept .csv, .xlsx and .json up to 5 MB and 500 rows; reject anything else with a clear message.
- Detect common broker layouts by header names; if not recognized, ask the user to map columns.
- Resolve every symbol to a Yahoo Finance ticker and list unresolved symbols instead of failing silently.
- Convert all values to the chosen base currency.
- Show "Analytics only, not financial advice" on every analysis.

### Non-functional

- Stateless backend; file contents never written to disk or logs.
- Dashboard still works if the LLM is unavailable; insights fall back to template text and chat is disabled.
- Secrets live only in environment variables.
- Analysis time for a 20-stock portfolio is measured and reported in the README (no promised number until measured).

## Success metrics

| Metric | Target |
| --- | --- |
| Accuracy vs quantstats | Max relative error 0.5% or less on the sample portfolios |
| Hand-calculated fixtures | Match within 1e-6 |
| Automated tests | 40 or more tests, 80% or more coverage on analytics code |
| Agent eval | Zero numbers in answers that are absent from tool outputs |
| Deployment | Live frontend URL and a working backend /health URL |
