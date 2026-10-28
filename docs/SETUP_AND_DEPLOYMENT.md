# Laptop Setup, Deployment and Troubleshooting

## 1. Laptop setup

Do these once, in order, before the first prompt.

1. **Install tools:** Git, Python 3.11 or newer, Node.js 20 LTS or newer, Docker Desktop (optional, only to test the container locally), and Claude Code from Anthropic's official install guide at docs.claude.com.
2. **Create free accounts:** GitHub, Render, Vercel (sign in with GitHub) and Google AI Studio for a Gemini API key.
3. **Put this package in place:** unzip it so the folder `portfolio-risk-analyzer` becomes your project root, then run `git init` inside it.
4. **Create .env:** copy `.env.example` to `.env` and put your real Gemini key only in `.env`. Create a `.gitignore` that contains `.env` before the first commit (Phase 1 also adds one).
5. **First commit:** create an empty GitHub repository, then commit and push the folder.
6. **Start Claude Code:** open a terminal in the project folder, run `claude`, and paste the Phase 1 prompt from PROMPTS.md.

### Working rhythm

- One phase per Claude Code session. When it finishes, review the changes, run the tests yourself, commit, then open a fresh session for the next phase.
- Read each permission request before approving a command.
- Never paste real API keys into a prompt.
- If a phase misses its acceptance checks, paste the failing output back and ask for a fix before moving on.

## 2. Run locally

```text
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# Tests
pytest -q --cov=app

# Frontend (second terminal)
cd frontend
npm install
npm run dev
```

## 3. Deploy steps

Deploy the backend first, then the frontend, then point each at the other.

1. **Render:** Dashboard, New, Blueprint, connect this GitHub repository. Render reads `render.yaml` (free Docker web service, deploys after CI passes) and asks for `GEMINI_API_KEY` and `ALLOWED_ORIGINS` (use http://localhost:5173 for now). Wait for the first build, then open `https://<service>.onrender.com/health`.
2. **GitHub:** under Settings, Secrets and variables, Actions, Variables, add BACKEND_URL set to the Render service URL (no trailing slash). No secrets are needed: Render pulls the code itself.
3. **Push to main:** once the CI workflow passes, Render deploys the new commit automatically. Check that `/health` shows the new `git_sha`.
4. **Vercel:** import the GitHub repository, set Root Directory to frontend, framework Vite, and add the environment variable VITE_API_URL with the Render service URL.
5. **Close the loop:** set ALLOWED_ORIGINS in the Render dashboard to your Vercel URL (keep http://localhost:5173 too, comma-separated); Render restarts the service.
6. **Smoke test:** on the live site, open a sample portfolio and confirm the dashboard, insights and chat all work.

## 4. Environment variables

| Name | Where | Purpose |
| --- | --- | --- |
| GEMINI_API_KEY | Backend (.env locally, Render environment) | LLM access |
| GEMINI_MODEL | Backend | Model name; empty uses the default |
| ALLOWED_ORIGINS | Backend | Comma-separated browser origins allowed by CORS |
| MAX_UPLOAD_MB, MAX_ROWS | Backend | Upload limits |
| LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST | Backend (optional) | Agent tracing, off by default; also needs the `langfuse` package |
| GIT_SHA | Backend | Optional; Render's `RENDER_GIT_COMMIT` is used when unset; shown by `/health` |
| VITE_API_URL | Frontend (Vercel) | Backend base URL |
| PORT, TRUSTED_PROXY_HOPS | Backend (set in `render.yaml`) | Listen port 7860; proxies in front of the app for rate limits |
| BACKEND_URL | GitHub variable | Keep-alive pings |

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| CORS error in the browser console | ALLOWED_ORIGINS lacks the exact Vercel origin | Add it with no trailing slash, then wait for Render to restart the service |
| First request slow or timing out | Backend was asleep | Wait and retry; confirm the keep-alive workflow is running |
| Empty prices or unresolved symbols | Wrong suffix or yfinance rate limit | Use .NS or .BO suffixes and retry; the app falls back to the snapshot with a warning |
| Gemini quota or 429 errors | Free-tier limits | Insights fall back to template text; wait, or change GEMINI_MODEL |
| Render build or deploy fails | Wrong port, or CI failed so no deploy started | Check `PORT=7860` in `render.yaml`, that the CI run for the commit is green, and the deploy log in Render |
| Everyone gets 429 `rate_limited` | `TRUSTED_PROXY_HOPS` does not match the proxies in front of the app | Render's docs do not state the hop count; see "Verify the rate limit key" below |
| Service suspended mid-month | The 750 free instance hours were used up | Keep-alive uses about 744 hours in a 31-day month; remove other free services or pause keep-alive |
| CI fails on formatting | Code not formatted | Run ruff format . and commit |
| Keep-alive runs late | GitHub scheduled jobs can be delayed | Acceptable; add UptimeRobot as a second pinger if needed |

## 6. Verify the rate limit key (once, after the first deploy)

Per-client AI limits use the client address from `X-Forwarded-For` (`TRUSTED_PROXY_HOPS=1` in `render.yaml`). Render's documentation does not say how many proxies sit in front of a service, so confirm it once: with a Gemini key set, open the live site on your phone (mobile data) and on your laptop, and use chat on both. If one device exhausts the limit (6 requests per minute) and the other is also blocked, the key is shared; try `TRUSTED_PROXY_HOPS=2` in the Render dashboard. Do not use 0 on Render.
