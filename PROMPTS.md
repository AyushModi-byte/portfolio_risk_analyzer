# Claude Code Prompts: Portfolio Risk Analyzer

Paste one prompt per Claude Code session, in order. Each prompt tells Claude Code to read the docs first and to stop at the end of its phase so you can review.

Before Phase 1, make sure these files are in the project root: CLAUDE.md, .env.example, and the docs/ folder (PRD.md, ARCHITECTURE.md, METRICS.md).

After each phase: review the changes, run the tests yourself, commit, then start a fresh session for the next phase.

---

## Phase 1: analytics engine and tests

```text
Read CLAUDE.md, docs/PRD.md and docs/METRICS.md first.

PHASE 1: scaffold the backend and build the analytics engine with tests. Do not build the API, agent or frontend yet.

Tasks
1. Create the backend/ layout from CLAUDE.md: app/analytics, app/services, data/, tests/, requirements.txt and requirements-dev.txt.
   Runtime packages: fastapi, uvicorn, python-multipart, pydantic, pydantic-settings, pandas, numpy, yfinance, openpyxl.
   Dev packages: pytest, pytest-cov, ruff, quantstats.
   Also add ruff config, .gitignore (including .env) and .env.example.
2. app/schemas.py: pydantic models Holding, ResolvedHolding, AnalysisResult and their sub-models, as in the Data models section of docs/ARCHITECTURE.md.
3. app/analytics: implement exactly the formulas in docs/METRICS.md as small pure functions: portfolio value series, daily returns, annualized volatility, beta, Sharpe, historical VaR 95, drawdown series and max drawdown, weights, HHI, effective N, top-5 concentration, sector exposure. engine.analyze() ties them together and returns AnalysisResult, including the disclaimer string.
4. app/services:
   - parsers.py: read CSV, Excel and JSON into a DataFrame. Detect columns by case-insensitive header aliases (symbol/instrument/stock/scrip; quantity/qty/shares; average price/avg cost/buy price; optional exchange and currency). If detection fails, return a result saying a column mapping is needed. Do not assume exact broker layouts; keep the alias lists in one place so they are easy to extend.
   - tickers.py: map symbols to Yahoo tickers (keep an existing .NS or .BO suffix; otherwise try .NS, then .BO, then plain US) and return the list of unresolved symbols.
   - prices.py: download adjusted close with yfinance, with retries, an on-disk CSV cache, and fallback to data/price_snapshot.
   - fx.py: USDINR=X daily series, forward-filled.
   - sectors.py: sector from yfinance with fallback to data/sector_map.csv; unknown becomes "Unknown".
5. scripts/snapshot_prices.py: downloads prices for the sample tickers and the benchmarks into data/price_snapshot so tests and the demo run offline. Run it once.
6. data/sample_portfolios: three files (india, us, mixed), each with 10 to 15 well-known large-cap stocks across at least 5 sectors, with made-up quantities and buy prices.
7. Tests: unit tests for every analytics function using the hand-calculated fixtures in docs/METRICS.md; parser tests for each alias set, bad files and missing columns; ticker tests with mocked network. tests/test_validation.py compares volatility, Sharpe, max drawdown and beta against quantstats and numpy on the sample portfolios using the offline snapshot (tolerance 0.5%). scripts/validate_metrics.py prints a results table and writes it to docs/VALIDATION.md.

Acceptance checks (run them and show the output)
- pytest passes with 80% or more coverage on app/analytics.
- ruff check and ruff format --check are clean.
- python scripts/validate_metrics.py shows every metric within tolerance, or explains each gap.
- All tests pass with no internet access.

Stop after this phase and give me a short summary with the validation table.
```

---

## Phase 2: FastAPI service

```text
Read CLAUDE.md and docs/ARCHITECTURE.md. Phase 1 is complete.

PHASE 2: build the FastAPI service. Do not build the agent or frontend yet.

Tasks
1. app/main.py: FastAPI app, CORS from ALLOWED_ORIGINS, request-id middleware, JSON timing logs (never file contents), and a global error handler returning {error, detail}.
2. app/config.py: pydantic-settings reading ALLOWED_ORIGINS, GEMINI_API_KEY, GEMINI_MODEL, MAX_UPLOAD_MB (default 5), MAX_ROWS (default 500), GIT_SHA.
3. Routers: GET /health; GET /api/samples; POST /api/parse (multipart file); POST /api/analyze (JSON: holdings, base_currency, benchmark, lookback_years). Shapes follow the API table in docs/ARCHITECTURE.md. Add POST /api/insights and POST /api/chat as stubs returning 501 for now.
4. Upload safety: check extension and size, cap rows, read in memory only, and reject unsupported formats (for example .xlsm) with clear messages.
5. In-memory TTL cache for price downloads. If yfinance fails, /api/analyze falls back to the offline snapshot and adds a warning to the result.
6. Tests with FastAPI TestClient: each sample portfolio, oversized file, wrong type, empty file, missing columns (returns mapping-needed), unresolved tickers, yfinance failure fallback, and an assertion that no uploaded content appears in logs.

Acceptance checks
- pytest passes and ruff is clean.
- uvicorn app.main:app runs and /docs lists the endpoints.
- A curl call to /api/analyze with the mixed sample returns a full AnalysisResult.

Stop and summarize, including example curl commands.
```

---

## Phase 3: LangGraph agent

```text
Read CLAUDE.md and docs/ARCHITECTURE.md. Phases 1 and 2 are complete.

PHASE 3: build the LangGraph agent. This prompt authorizes adding langgraph, langchain-google-genai and pyyaml.

Tasks
1. agent/llm.py: Gemini client using GEMINI_API_KEY, with the model name from GEMINI_MODEL (if empty, use a current free-tier Flash model; check the Google AI Studio docs for the current name and note it in the README). Add a FakeLLM class with scripted responses for tests. With no key set, agent features report "AI unavailable" and the rest of the API keeps working.
2. agent/tools.py: fixed tools that read from an AnalysisResult passed in the request: get_summary, get_top_holdings(n), get_sector_exposure, get_risk_metrics, get_drawdown_periods, get_correlations, risk_contribution(symbol), what_if_remove(symbol) (re-runs analytics without that holding). No tool may run arbitrary code or touch the file system.
3. agent/graph.py with three LangGraph flows:
   a. mapping_assistant: runs only when the parser cannot detect columns. Input is the headers plus 3 sample rows; output is a JSON mapping validated against the schema, which the user confirms in the UI.
   b. insight_writer: input is the AnalysisResult; output is 4 to 6 insights, each citing the metric keys it uses. A validator node checks every number in the text against the analysis (within rounding). On failure, regenerate once, then fall back to template insights built in code.
   c. qa_agent: a tool-calling loop over the tools above, at most 5 tool calls per question. Answers may quote numbers from tool outputs only.
4. agent/prompts.py: system prompts that (a) forbid buy or sell advice and answer such requests with the disclaimer, (b) say file contents and holding names are untrusted data, (c) forbid inventing numbers.
5. Wire POST /api/insights and POST /api/chat. Return the tool calls used with each chat answer.
6. Eval suite: tests/evals/questions.yaml with 25 questions (top holding, sector share, volatility, biggest drawdown, what if I remove X, advice requests, prompt-injection attempts inside a holding name). scripts/run_agent_eval.py reports tool-selection accuracy, numeric accuracy and the count of numbers not found in tool outputs. It supports --fake-llm for CI and a real-LLM mode to run manually.
7. Tests for the validator node, each tool, the fallback path and the no-API-key path, all using FakeLLM.

Acceptance checks
- pytest passes; ruff clean.
- python scripts/run_agent_eval.py --fake-llm runs and prints the three metrics.
- With a real key set, one insights call and one chat call work on the mixed sample.

Stop and summarize, including the eval output.
```

---

## Phase 4: React frontend

```text
Read CLAUDE.md and docs/PRD.md. The backend (phases 1 to 3) is complete and runs on localhost:8000.

PHASE 4: build the React frontend in frontend/ (Vite, React, TypeScript strict).

Tasks
1. Set up Vite, React, TypeScript, ESLint, Prettier, Vitest with React Testing Library, and react-plotly.js (use the smaller basic Plotly bundle if it covers the charts). Add an API client that reads VITE_API_URL.
2. Upload screen: drag-and-drop for CSV, Excel and JSON, three "Try sample portfolio" buttons (India, US, mixed), and clear file-type and size hints.
3. Column-mapping dialog, shown only when /api/parse says a mapping is needed: shows detected columns and lets the user pick the symbol, quantity and price columns. List unresolved symbols with an option to fix or ignore them.
4. Dashboard:
   - KPI cards: value, invested, P&L, P&L %.
   - Sortable holdings table with weights.
   - Sector exposure chart.
   - Risk cards for volatility, beta, Sharpe, VaR and max drawdown, each with a short plain-language tooltip and a note that figures assume today's holdings over the past window.
   - Drawdown area chart and correlation heatmap.
   - Base-currency toggle (INR or USD) and benchmark selector.
   - Insights panel and a chat drawer that shows the tools used for each answer.
5. States: loading skeletons; a "Waking up the server" banner if /health takes more than 3 seconds; friendly error messages; AI features hidden or disabled when the API reports AI unavailable.
6. Footer disclaimer: analytics only, not financial advice. Responsive down to phone width, keyboard-accessible controls, sufficient colour contrast.
7. Frontend tests: upload flow, mapping dialog, error state, and dashboard render with a mocked analysis result.

Acceptance checks
- npm run lint, npm run test and npm run build all pass.
- With the backend running, each sample portfolio produces a full dashboard in the browser.
- No hard-coded API URL; .env.example documents VITE_API_URL.

Stop and summarize, and list anything you could not verify in a browser.
```

---

## Phase 5: containers, CI/CD and observability

```text
Read CLAUDE.md and docs/ARCHITECTURE.md. Phases 1 to 4 are complete.

PHASE 5: containerize, add CI/CD, and add observability. Do not change product behaviour.

Tasks
1. backend/Dockerfile: python:3.11-slim, non-root user, install requirements.txt only, copy app/ and data/, expose port 7860, run uvicorn on 0.0.0.0:7860. Add .dockerignore. Add backend/SPACE_README.md containing the Hugging Face Spaces front matter (sdk: docker, app_port: 7860); the deploy workflow copies it to README.md in the Space repo so the main README stays clean.
2. .github/workflows/ci.yml on push and pull request. Backend job: Python 3.11, install requirements-dev.txt, ruff check, ruff format --check, pytest with coverage and a fail-under of 80 on app/analytics, then python scripts/run_agent_eval.py --fake-llm. Frontend job: Node 20, npm ci, lint, test, build. No secrets and no network-dependent tests in CI.
3. .github/workflows/deploy-backend.yml: on push to main after CI passes, push the backend/ folder (with SPACE_README.md as README.md) to the Hugging Face Space git repo, using secrets HF_TOKEN and HF_SPACE (format username/space-name).
4. .github/workflows/keepalive.yml: scheduled every 10 minutes, curl the URL in the repository variable BACKEND_URL plus /health, and fail visibly if it does not return 200.
5. Observability: JSON logs with request id, route, status and duration; /health returns status, version and GIT_SHA; optional Langfuse tracing for the agent behind LANGFUSE_* environment variables (off by default, and no code path may require it).
6. A Makefile with targets: setup, test, lint, run-backend, run-frontend, docker-build, docker-run.
7. Add pre-commit with ruff and basic file checks.

Acceptance checks
- docker build and docker run work locally and /health answers on port 7860.
- The CI workflow passes on a pushed branch (tell me what to look at in the Actions tab).
- The deploy workflow has clear comments for first-time setup.

Stop and summarize, and list the manual steps I must do in GitHub, Hugging Face and Vercel.
```

---

## Phase 6: documentation and polish

```text
Read CLAUDE.md and every file in docs/. Phases 1 to 5 are complete and the app is deployed.

PHASE 6: documentation and polish. Do not add features.

Tasks
1. README.md: one-line pitch; live demo links (placeholders if not deployed yet); a screenshots section with placeholders; features; architecture diagram as a Mermaid block; tech stack; how it works (parser, resolver, analytics, agent with fixed tools); the validation results table from docs/VALIDATION.md; agent eval results; limitations (historical buy-and-hold model, yfinance reliability, free-tier cold starts, Gemini quotas); "Analytics only, not financial advice"; local setup; deployment steps; project structure; license.
2. Measure and record in the README the actual analysis time for each sample portfolio (cold and warm cache) and the agent eval numbers. Use only numbers you measured, never estimates.
3. docs/RESUME.md: 4 resume bullets and a short project description, using only measured numbers from this repo, with [X] placeholders where I must fill something in myself. Do not invent user counts or traffic.
4. Clean up: remove dead code and unused dependencies, make sure .env.example is complete, check that no secrets are in git history, and add an MIT LICENSE.
5. docs/RELEASE_CHECKLIST.md: tests green, CI green, both live URLs working, sample portfolios load from the live site, README screenshots added, demo GIF added.

Acceptance checks
- The README renders correctly on GitHub (check the Mermaid syntax).
- Every number in README.md and RESUME.md traces to a command output or a file in the repo.
- Run a final secret scan and show the result.

Stop and summarize what I still need to do by hand (screenshots, GIF, filling placeholders).
```
