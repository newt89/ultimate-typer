#!/usr/bin/env bash
# ================================================================
#  Ultimate Typer — Complete Deploy Script
#  Runs top to bottom, tells you exactly what to do at each step
# ================================================================
set -e
R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' C='\033[0;36m' B='\033[1m' N='\033[0m'
log(){ echo -e "${C}▶  $1${N}"; }
ok(){ echo -e "${G}✓  $1${N}"; }
warn(){ echo -e "${Y}!  $1${N}"; }
die(){ echo -e "${R}✗  $1${N}"; exit 1; }
hr(){ echo -e "${B}────────────────────────────────────────────────${N}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

echo -e "${B}"
echo "╔══════════════════════════════════════════════╗"
echo "║     ULTIMATE TYPER  —  DEPLOY SCRIPT         ║"
echo "║  Railway (backend) + Vercel (frontend)        ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${N}"

# ── STEP 0: Prerequisites ─────────────────────────────────────────
hr; log "Checking prerequisites..."

command -v git  &>/dev/null || die "git not installed. Download: https://git-scm.com"
command -v node &>/dev/null || die "Node.js not installed. Download: https://nodejs.org (LTS version)"
command -v npm  &>/dev/null || die "npm not found (should come with Node.js)"
ok "git $(git --version | cut -d' ' -f3)"
ok "node $(node --version)  npm $(npm --version)"

# Install CLIs if missing
if ! command -v railway &>/dev/null; then
    log "Installing Railway CLI..."; npm install -g @railway/cli; ok "Railway CLI installed"
else ok "Railway CLI $(railway --version 2>/dev/null||echo 'ready')"; fi

if ! command -v vercel &>/dev/null; then
    log "Installing Vercel CLI..."; npm install -g vercel; ok "Vercel CLI installed"
else ok "Vercel CLI ready"; fi

# ── STEP 1: GitHub ────────────────────────────────────────────────
hr
echo -e "${B}STEP 1 — GitHub${N}"
echo ""
echo "  You need a free GitHub account to store your code."
echo "  Create one at: ${C}https://github.com${N}"
echo ""
read -rp "  Enter your GitHub username: " GITHUB_USER
[[ -z "$GITHUB_USER" ]] && die "GitHub username required"
REPO="ultimate-typer"

# Init git
if [[ ! -d .git ]]; then
    log "Initialising git..."; git init; git add .; git commit -m "Initial commit — Ultimate Typer"; ok "Git initialised"
else
    git add .; git diff-index --quiet HEAD || git commit -m "Update Ultimate Typer"; ok "Git updated"
fi

echo ""
echo -e "${B}  Create the GitHub repository now:${N}"
echo "  1. Open:  ${C}https://github.com/new${N}"
echo "  2. Repository name: ${Y}${REPO}${N}"
echo "  3. Visibility: ${Y}Public${N}"
echo "  4. Do NOT tick any extra options (no README, no .gitignore)"
echo "  5. Click  ${Y}Create repository${N}"
echo ""
read -rp "  Press ENTER when the repository is created..."

log "Pushing code to GitHub..."
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/${GITHUB_USER}/${REPO}.git"
git branch -M main
if ! git push -u origin main 2>&1; then
    warn "Push failed. You may need a GitHub Personal Access Token."
    echo ""
    echo "  To fix:"
    echo "  1. Go to ${C}https://github.com/settings/tokens/new${N}"
    echo "  2. Give it a name, set expiry to 1 year"
    echo "  3. Check the 'repo' scope"
    echo "  4. Click Generate token"
    echo "  5. Run: git config --global credential.helper store"
    echo "  6. Run this script again — when prompted for password, paste the token"
    exit 1
fi
ok "Code live at: https://github.com/${GITHUB_USER}/${REPO}"

# ── STEP 2: Railway backend ───────────────────────────────────────
hr
echo -e "${B}STEP 2 — Deploy backend to Railway (free \$5/month credit)${N}"
echo ""
echo "  Railway will host your Python API 24/7."
echo "  Free \$5/month credit = ~\$0.50/month for this app = free forever."
echo ""
log "Logging into Railway (browser will open)..."
railway login

cd "$ROOT/backend"
log "Creating Railway project..."
railway init --name "ultimate-typer-backend" 2>/dev/null || true

log "Setting data directory..."
railway variables set DATA_DIR=/data 2>/dev/null || true

log "Deploying backend (takes 1-3 minutes)..."
railway up --detach

log "Generating public domain..."
RAILWAY_URL=$(railway domain 2>/dev/null | grep -oP 'https://[^\s]+' | head -1 || echo "")
if [[ -z "$RAILWAY_URL" ]]; then
    railway domain generate 2>/dev/null || true
    sleep 3
    RAILWAY_URL=$(railway domain 2>/dev/null | grep -oP 'https://[^\s]+' | head -1 || echo "")
fi
if [[ -z "$RAILWAY_URL" ]]; then
    warn "Could not auto-detect Railway URL."
    echo ""
    read -rp "  Open Railway dashboard, find your URL, paste it here: " RAILWAY_URL
fi
[[ -z "$RAILWAY_URL" ]] && die "Railway URL required"
ok "Backend deployed: ${RAILWAY_URL}"
cd "$ROOT"

# ── STEP 3: Wire frontend → backend ──────────────────────────────
hr
log "Connecting frontend to your backend..."
sed -i.bak "s|REPLACE_WITH_RAILWAY_URL|${RAILWAY_URL}|g" "$ROOT/frontend/index.html"
rm -f "$ROOT/frontend/index.html.bak"
git add frontend/index.html
git commit -m "Set Railway backend URL: ${RAILWAY_URL}" 2>/dev/null || true
git push origin main 2>/dev/null || true
ok "Frontend configured"

# ── STEP 4: Vercel frontend ───────────────────────────────────────
hr
echo -e "${B}STEP 4 — Deploy frontend to Vercel (free forever)${N}"
echo ""
echo "  Vercel hosts your game webpage on a fast global CDN."
echo "  Completely free, no credit card needed."
echo ""
log "Logging into Vercel (browser will open)..."
cd "$ROOT/frontend"
vercel login

log "Deploying frontend..."
VERCEL_OUT=$(vercel --prod --yes --name "ultimate-typer" 2>&1 | tee /dev/stderr)
VERCEL_URL=$(echo "$VERCEL_OUT" | grep -oP 'https://[^\s]+\.vercel\.app' | tail -1 || echo "")
cd "$ROOT"

# ── DONE ─────────────────────────────────────────────────────────
hr
echo ""
echo -e "${G}${B}  DEPLOYMENT COMPLETE!${N}"
echo ""
if [[ -n "$VERCEL_URL" ]]; then
  echo -e "  Your game is live at:"
  echo -e "  ${B}${C}  ${VERCEL_URL}  ${N}"
else
  echo -e "  Check your Vercel dashboard for the live URL."
fi
echo ""
echo -e "  Backend:   ${RAILWAY_URL}"
echo -e "  Frontend:  ${VERCEL_URL:-see Vercel dashboard}"
echo ""
echo -e "${B}  UPDATING IN FUTURE:${N}"
echo "  Just run these 3 commands after any change:"
echo -e "  ${C}  git add .${N}"
echo -e "  ${C}  git commit -m 'my change'${N}"
echo -e "  ${C}  git push${N}"
echo "  Both Railway and Vercel auto-redeploy from GitHub."
echo ""
