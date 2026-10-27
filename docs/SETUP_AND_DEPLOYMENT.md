# Laptop Setup, Deployment and Troubleshooting

## 1. Laptop setup

Do these once, in order, before the first prompt.

1. **Install tools:** Git, Python 3.11 or newer, Node.js 20 LTS or newer, Docker Desktop (optional, only to test the container locally), and Claude Code from Anthropic's official install guide at docs.claude.com.
2. **Create free accounts:** GitHub, Hugging Face, Vercel (sign in with GitHub) and Google AI Studio for a Gemini API key.
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

1. **Hugging Face:** create a new Space with the Docker SDK and a blank template. Under Settings, add secrets GEMINI_API_KEY and ALLOWED_ORIGINS (use http://localhost:5173 for now). Create an access token with write permission.
2. **GitHub:** under Settings, Secrets and variables, Actions, add secrets HF_TOKEN and HF_SPACE (username/space-name), and a variable BACKEND_URL set to the Space's direct URL (https://username-space-name.hf.space).
3. **Push to main:** once CI passes, the deploy workflow publishes the backend (comments at the top of `.github/workflows/deploy-backend.yml` repeat the one-time setup). It force-pushes `backend/` to the Space with `SPACE_README.md` as its README, so edit files in this repo, never in the Space. You can also run it by hand from the Actions tab. Open BACKEND_URL/health and confirm it answers.
4. **Vercel:** import the GitHub repository, set Root Directory to frontend, framework Vite, and add the environment variable VITE_API_URL with the Space URL.
5. **Close the loop:** set ALLOWED_ORIGINS on the Space to your Vercel URL (keep http://localhost:5173 too, comma-separated) and restart the Space.
6. **Smoke test:** on the live site, open a sample portfolio and confirm the dashboard, insights and chat all work.

## 4. Environment variables

| Name | Where | Purpose |
| --- | --- | --- |
| GEMINI_API_KEY | Backend (.env locally, Space secret) | LLM access |
| GEMINI_MODEL | Backend | Model name; empty uses the default |
| ALLOWED_ORIGINS | Backend | Comma-separated browser origins allowed by CORS |
| MAX_UPLOAD_MB, MAX_ROWS | Backend | Upload limits |
| LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST | Backend (optional) | Agent tracing, off by default; also needs the `langfuse` package |
| GIT_SHA | Backend | Set by the deploy workflow; shown by `/health` |
| VITE_API_URL | Frontend (Vercel) | Backend base URL |
| HF_TOKEN, HF_SPACE | GitHub secrets | Deploy to the Space |
| BACKEND_URL | GitHub variable | Keep-alive pings |

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| CORS error in the browser console | ALLOWED_ORIGINS lacks the exact Vercel origin | Add it with no trailing slash, then restart the Space |
| First request slow or timing out | Backend was asleep | Wait and retry; confirm the keep-alive workflow is running |
| Empty prices or unresolved symbols | Wrong suffix or yfinance rate limit | Use .NS or .BO suffixes and retry; the app falls back to the snapshot with a warning |
| Gemini quota or 429 errors | Free-tier limits | Insights fall back to template text; wait, or change GEMINI_MODEL |
| Space build fails | Wrong port or missing front matter | Check the Dockerfile uses 7860 and the Space README has sdk: docker; read the build log |
| CI fails on formatting | Code not formatted | Run ruff format . and commit |
| Keep-alive runs late | GitHub scheduled jobs can be delayed | Acceptable; add UptimeRobot as a second pinger if needed |
