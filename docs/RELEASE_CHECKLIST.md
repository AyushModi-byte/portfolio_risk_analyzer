# Release Checklist

Work top to bottom before sharing the project (README, LinkedIn, a job application). Tick each box only after you have seen it with your own eyes.

## 1. Code is green

- [ ] `make test` passes (backend `pytest -q --cov=app`, then the frontend tests).
- [ ] `make lint` passes (ruff check, ruff format check, ESLint, Prettier).
- [ ] `cd frontend && npm run build` passes.
- [ ] `python scripts/run_agent_eval.py --fake-llm` prints 100% tool selection, 100% numeric accuracy, 0 numbers outside tool outputs and 0 advice violations.
- [ ] `python scripts/validate_metrics.py` ends with every metric within tolerance, and `docs/VALIDATION.md` has no uncommitted changes.
- [ ] `git status` is clean and the latest commit is pushed to `main`.

## 2. CI and deploy are green

- [ ] GitHub, Actions tab: the latest **CI** run on `main` is green (backend and frontend jobs).
- [ ] Render dashboard: the latest deploy of `portfolio-risk-api` is live and its commit matches the latest commit on `main`.
- [ ] The **Keep alive** workflow's most recent scheduled runs are green. If they are red, the repository variable `BACKEND_URL` is missing or wrong.
- [ ] Vercel: the latest production deployment succeeded.

## 3. Both live URLs work

- [ ] `<backend URL>/health` returns `status: ok`, and `git_sha` matches the latest commit. `ai_available` is `true` if you set `GEMINI_API_KEY` on Render.
- [ ] The frontend URL loads without a console error (browser dev tools, Console tab).
- [ ] After the backend has been idle for 15+ minutes, the frontend shows the "Waking up the server" banner and then recovers by itself.

## 4. Live behaviour

- [ ] The **India**, **US** and **Mixed** sample buttons each produce a full dashboard (KPIs, risk cards, sector chart, drawdown chart, correlation heatmap, holdings table, insights).
- [ ] The currency toggle (INR/USD) and the benchmark selector change the numbers.
- [ ] Uploading a CSV from your own broker works, or the mapping dialog appears and works.
- [ ] A symbol that does not exist appears in the unresolved-symbols panel instead of crashing.
- [ ] Chat answers "What are my top 3 holdings?" and shows the tools it used.
- [ ] Chat refuses "Should I sell X?" with a non-advice reply.
- [ ] The footer shows the "Analytics only, not financial advice" disclaimer.
- [ ] On a phone (or a 390 px wide browser window) nothing scrolls sideways.
- [ ] CORS is correct: no CORS errors in the console. If there are, `ALLOWED_ORIGINS` on Render lacks the exact Vercel origin.
- [ ] Rate limit check (once): chat from your laptop and from your phone on mobile data. If one device hitting the limit blocks the other, set `TRUSTED_PROXY_HOPS=2` on Render (see `docs/SETUP_AND_DEPLOYMENT.md`, section 6).

## 5. README is finished

- [ ] The live demo and API health links at the top of `README.md` point to the real URLs (search for `YOUR-`).
- [ ] Screenshots are saved in `docs/screenshots/` with the file names the README uses, and they render on GitHub.
- [ ] A demo GIF is saved as `docs/screenshots/demo.gif` and shows: pick a sample, scroll the dashboard, ask the chat a question.
- [ ] The README timing and eval tables still match a fresh run of the commands listed under them (re-run if you changed code since).
- [ ] `docs/RESUME.md`: every `[X]` placeholder is filled with something true, and nothing is invented.
- [ ] Preview `README.md` on GitHub and check that the Mermaid diagram renders.

## 6. Repository hygiene

- [ ] `LICENSE` has the right name.
- [ ] No secrets: the repository variable and secret lists in GitHub contain only what you expect, and `git log -p` has no keys (the scan in the Phase 6 summary shows the command).
- [ ] `.env` is not tracked (`git ls-files | grep .env` shows only `.env.example` files).
- [ ] The GitHub repository has a description, topics (for example `fastapi`, `react`, `langgraph`, `portfolio-analysis`) and the live demo URL in its About box.
