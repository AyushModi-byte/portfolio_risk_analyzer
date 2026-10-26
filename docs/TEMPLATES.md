# README Skeleton and Resume Bullets

Claude Code writes the real README in Phase 6. This is the shape to expect; fill in only numbers you measured.

## README skeleton

```markdown
# Portfolio Risk Analyzer
Upload a broker holdings file and get risk, sector exposure and drawdown,
with AI insights that only quote computed numbers.

[Live demo](URL) | [API health](URL)

## Features
(list from the PRD)

## How it works
1. Parse the file and detect columns
2. Resolve tickers and fetch prices and FX
3. Compute metrics in code
4. AI writes insights and answers questions through fixed tools

## Validation
| Metric | Reference | Max relative error |
| --- | --- | --- |
(from docs/VALIDATION.md)

## Agent evaluation
(output of scripts/run_agent_eval.py)

## Limitations
Historical buy-and-hold model, yfinance reliability, free-tier cold starts,
Gemini quotas.

> Analytics only, not financial advice.
```

## Resume bullets

Replace each [X] or [N] with a number from your own validation and test output. Do not add user counts or traffic unless they are real.

- Built a full-stack portfolio risk analyzer (FastAPI, LangGraph, React) that turns a broker holdings file into volatility, beta, Sharpe, VaR, drawdown and sector exposure for Indian and US stocks.
- Validated every metric against quantstats and hand-calculated fixtures, with a maximum relative error of [X]% across [N] portfolios.
- Designed an LLM agent limited to [N] fixed analytics tools; an eval of [N] questions found [X] numbers outside tool outputs.
- Shipped with Docker, GitHub Actions CI/CD ([N] automated tests, [X]% coverage) and free hosting on Hugging Face Spaces and Vercel.
