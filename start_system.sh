#!/usr/bin/env bash
# ==============================================================================
# Adaptive Network Traffic Management System — Unified Launcher
# Launches both the Flask REST API Backend and the React Vite Frontend
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

echo "================================================================="
echo " Adaptive Network Traffic Management System"
echo "================================================================="
echo "[*] Project Directory: $PROJECT_ROOT"

# 1. Activate Python virtual environment
if [ -d "$PROJECT_ROOT/.venv" ]; then
    echo "[*] Activating Python virtual environment (.venv)..."
    source "$PROJECT_ROOT/.venv/bin/activate"
else
    echo "[!] Warning: .venv not found. Using system python3."
fi

# 2. Check and start Flask Backend (port 5001)
BACKEND_PORT=5001
if lsof -i :$BACKEND_PORT >/dev/null 2>&1; then
    echo "[+] Flask REST API is already running on port $BACKEND_PORT"
else
    echo "[*] Starting Flask REST API Backend on port $BACKEND_PORT..."
    PORT=$BACKEND_PORT python "$PROJECT_ROOT/backend/app.py" &
    BACKEND_PID=$!
    echo "[+] Backend launched (PID: $BACKEND_PID)"
    sleep 2
fi

# 3. Check and start React Frontend (port 3000)
FRONTEND_PORT=3000
if lsof -i :$FRONTEND_PORT >/dev/null 2>&1; then
    echo "[+] React Frontend Dashboard is already running on port $FRONTEND_PORT"
else
    echo "[*] Starting React Frontend Dashboard on port $FRONTEND_PORT..."
    cd "$PROJECT_ROOT/frontend"
    npm run dev &
    FRONTEND_PID=$!
    cd "$PROJECT_ROOT"
    echo "[+] Frontend launched (PID: $FRONTEND_PID)"
    sleep 2
fi

echo "================================================================="
echo " System Online & Ready"
echo "================================================================="
echo "  Frontend Dashboard : http://localhost:3000"
echo "  Backend REST API   : http://127.0.0.1:5001/api"
echo "  Health Endpoint    : http://127.0.0.1:5001/api/health"
echo "================================================================="
echo "Press Ctrl+C to stop servers when finished."

# Trap termination signals
trap 'echo -e "\n[*] Shutting down servers..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; exit 0' SIGINT SIGTERM

# Wait for children if we spawned them
wait
