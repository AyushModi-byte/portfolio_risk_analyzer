# Portfolio Risk Analyzer

Upload broker holdings (CSV, Excel or JSON) and get risk, sector exposure, drawdown and AI-written insights. The code computes every number; the AI only words results and answers questions through a fixed set of tools. Analytics only, not financial advice.

Requirements are in `docs/PRD.md`, formulas in `docs/METRICS.md`, the API in `docs/ARCHITECTURE.md`, metric validation in `docs/VALIDATION.md`.

## Run the backend

```bash
cd backend
python -m venv .venv            # Python 3.11 or newer
.venv/Scripts/pip install -r requirements-dev.txt     # Windows; use .venv/bin/pip elsewhere
cp .env.example .env            # optional: add GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs. Run the tests with `pytest -q --cov=app` and lint with `ruff check . && ruff format --check .`.

## AI features

The AI features need a Google AI Studio key in `GEMINI_API_KEY`. Without one the dashboard still works: insights fall back to template text built in code, and chat and column-mapping suggestions report "AI unavailable".

**Model.** `GEMINI_MODEL` selects the model. When it is empty the backend uses `gemini-3.6-flash`, a stable Flash model that Google's pricing page lists as free of charge on the standard tier (checked against ai.google.dev). The newer `gemini-3.8-flash` is also listed as free, but it returned 504 timeouts in testing, so it is not the default. Free-tier quotas are small; when Google rate limits a call, chat returns HTTP 429 and insights fall back to templates.

**Evals.** `python scripts/run_agent_eval.py --fake-llm` runs the 27 questions in `backend/tests/evals/questions.yaml` with a scripted model (offline, used in CI) and prints tool-selection accuracy, numeric accuracy, the count of numbers not found in tool outputs and the count of advice violations. Run it without `--fake-llm` and with a key set to test the real model manually.
