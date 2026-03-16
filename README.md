# Ultimate Typer 🎹

Type in English, Russian, Arabic (Quran), and Sanskrit (Bhagavad Gita).
Individual stats per language. Sanskrit home row trainer (12 levels).

---

## Quickstart — one command

```bash
bash scripts/deploy.sh
```

The script walks you through every step interactively.
Total time: ~15 minutes. Cost: $0.

---

## What you need (all free, no credit card)

| Account | For | Link |
|---------|-----|------|
| GitHub  | Code storage | https://github.com |
| Railway | Python backend (free $5/mo credit) | https://railway.app |
| Vercel  | Game webpage (free forever) | https://vercel.com |

---

## Manual steps (if the script doesn't work)

### 1 — Install tools
```bash
# Install Node.js first: https://nodejs.org
npm install -g @railway/cli vercel
```

### 2 — Push to GitHub
```bash
git init && git add . && git commit -m "first"
# Create repo at https://github.com/new  (name: ultimate-typer, Public)
git remote add origin https://github.com/YOURUSERNAME/ultimate-typer.git
git branch -M main && git push -u origin main
```

### 3 — Deploy backend to Railway
```bash
cd backend
railway login
railway init --name "ultimate-typer-backend"
railway variables set DATA_DIR=/data
railway up
railway domain   # ← copy this URL, e.g. https://ultimate-typer-xyz.railway.app
```

### 4 — Wire frontend to backend
Open `frontend/index.html`, find line:
```javascript
return window.__BACKEND__||'REPLACE_WITH_RAILWAY_URL';
```
Replace `REPLACE_WITH_RAILWAY_URL` with your Railway URL.

```bash
git add . && git commit -m "set backend url" && git push
```

### 5 — Deploy frontend to Vercel
```bash
cd frontend
vercel login
vercel --prod --yes --name "ultimate-typer"
# Vercel prints your URL: https://ultimate-typer.vercel.app
```

### 6 — Done
Share the Vercel URL. It works on any device, never sleeps.

---

## Updating the game

```bash
git add .
git commit -m "my changes"
git push
```

Railway and Vercel auto-redeploy in ~2 minutes.

---

## Project layout

```
ultimate-typer/
├── backend/
│   ├── api.py           Python Flask API — all game logic
│   ├── requirements.txt
│   └── railway.toml
├── frontend/
│   ├── index.html       Complete game (one HTML file)
│   └── vercel.json
└── scripts/
    └── deploy.sh        One-command deploy
```

---

## Languages & content

| Language | Content |
|----------|---------|
| English  | Pangrams · Home row · Common words |
| Russian  | Basics · Home row (ФЫВА) · Pushkin · Tolstoy |
| Arabic   | Al-Fatiha · Al-Ikhlas · An-Nas · Al-Falaq · Al-Baqarah |
| Sanskrit | Bhagavad Gita all 18 chapters (individual or range) · 12-level home row trainer |
