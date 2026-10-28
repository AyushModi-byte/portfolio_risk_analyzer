# Resume and Interview Notes

Every number below comes from a command in this repository. The command is in the "Source" column so you can re-run it before you rely on a figure. Replace each `[X]` with something that is true for you; do not add user counts, traffic or revenue unless they are real.

## Short project description

**Portfolio Risk Analyzer** ([GitHub](https://github.com/AyushModi-byte/portfolio_risk_analyzer) | [live demo]([LIVE_DEMO_URL]))

A full-stack web app that turns a broker holdings file (CSV, Excel or JSON) into portfolio risk, sector exposure and drawdown for Indian and US stocks. A FastAPI backend computes every metric in code and validates it against quantstats, and a LangGraph agent writes insights and answers questions using eight fixed analytics tools. Each number in the AI text is checked against the computed results, and nothing is executed. The React and TypeScript frontend is deployed on Vercel, and the Dockerized backend on Render, with GitHub Actions CI. Built over [X] weeks as a solo project.

## Resume bullets

Pick four. The first four are the strongest; the fifth is optional.

1. Built a full-stack portfolio risk analyzer (FastAPI, LangGraph, React and TypeScript) that turns a broker holdings file into volatility, beta, Sharpe, 1-day VaR, maximum drawdown and sector exposure for Indian and US stocks, with INR/USD conversion.
2. Validated the metrics against quantstats and numpy on 3 sample portfolios: 0 relative error on volatility, Sharpe, maximum drawdown and beta and a largest VaR difference of 3.47e-18, against a 0.5% tolerance, backed by 338 backend tests at 98% coverage (100% on the analytics package).
3. Designed an LLM agent limited to 8 fixed analytics tools, with a validator that rejects any number not found in the tool outputs and any buy or sell advice; on a 27-question eval it scored 100% tool selection and numeric accuracy with 0 unsupported numbers and 0 advice violations (scripted-model run used in CI). On a real model (Groq `openai/gpt-oss-120b`, eval-only, 26 questions) it scored 96.2% tool selection (25/26) and 100% numeric accuracy with 0 unsupported numbers and 0 advice violations.
4. Shipped with Docker, GitHub Actions CI (lint, format, tests, an 80% coverage gate on the analytics package, an offline agent eval, and frontend lint, test and build) and free hosting on Render and Vercel, with a bundled price snapshot as fallback when Yahoo Finance fails.
5. Measured analysis time at 6.7 seconds for the India sample with empty caches (live Yahoo Finance downloads) and 0.03 seconds with warm caches, and 0.06 to 0.10 seconds from the bundled snapshot (4 portfolios, 3 cold and 5 warm runs each, on a laptop).

Optional lines, only if true:

- Worked with [X] testers who tried the live demo and gave feedback.
- Wrote the React frontend with strict TypeScript, 78 tests, and an automated colour-contrast audit of the dashboard.

## Where each number comes from

| Claim | Value | Source |
| --- | --- | --- |
| Portfolios in the validation | 3 (india, us, mixed) | `python scripts/validate_metrics.py` writes `docs/VALIDATION.md` |
| Relative error vs reference | 0.00e+00 for volatility, Sharpe, max drawdown, beta | `docs/VALIDATION.md` |
| Largest VaR difference | 3.47e-18 (absolute) | `docs/VALIDATION.md` |
| Tolerance | 0.5% relative; 1e-6 absolute for VaR | `scripts/validate_metrics.py` |
| Backend tests | 338 | `cd backend && pytest -q --cov=app` |
| Coverage | 98% overall; 100% for `app/analytics` | same command, then `coverage report --include="app/analytics/*"` |
| Frontend tests | 78 | `cd frontend && npm run test` |
| Eval questions | 27 (26 against a real model) | `python scripts/run_agent_eval.py --fake-llm` |
| Eval scores (scripted model) | 100.0% tool selection, 100.0% numeric, 0 unsupported numbers, 0 advice violations | same command |
| Eval scores (Groq `openai/gpt-oss-120b`) | 96.2% tool selection (25/26), 100.0% numeric, 0 unsupported numbers, 0 advice violations, 0 errors | `python scripts/run_agent_eval.py --provider groq --pause 3`; `docs/eval_groq_gpt-oss-120b.json` |
| Fixed agent tools | 8 | `backend/app/agent/tools.py` |
| Analysis times | see `docs/PERFORMANCE.md` and `docs/PERFORMANCE_OFFLINE.md` | `python scripts/measure_analysis_time.py` (and `--offline`) |

## Honest framing for interviews

- The validation compares the engine with quantstats and numpy on the same return series, so it proves the formulas and conventions match, not that the market data is right. The one real discrepancy found along the way was the Sharpe risk-free convention (arithmetic versus compounded daily rate, about 2% on the India sample), which is documented in `docs/VALIDATION.md`.
- The scripted-model eval proves the validators and the pipeline, not the quality of a model. The real-model score is from Groq `openai/gpt-oss-120b`, not from Gemini, which is what the deployed app uses (the Gemini free-tier quota blocked that run). Say so, and that it is 26 questions on one sample portfolio. The one miss was a tool-selection miss on `concentration`.
- Cold-start analysis time is dominated by Yahoo Finance. The US sample is slower than the India one because symbols with no exchange column are tried as `.NS` and `.BO` first; that is a known inefficiency, not something to hide.
- The model is "buy-and-hold of today's holdings over the past window". It is not a forecast and not what the user earned.
- Not measured: performance on the deployed free-tier server, and any real usage. Say so if asked.
