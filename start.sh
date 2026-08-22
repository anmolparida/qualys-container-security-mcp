#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.pids"

if [ -f "$PID_FILE" ]; then
  echo "App may already be running (found .pids file). Run ./stop.sh first, or delete .pids manually."
  exit 1
fi

echo "==> Installing backend dependencies..."
cd "$SCRIPT_DIR/backend"
pip3 install -q -r requirements.txt

echo "==> Installing frontend dependencies..."
cd "$SCRIPT_DIR/frontend"
npm install --silent

echo "==> Starting FastAPI backend on port 8000..."
cd "$SCRIPT_DIR/backend"
python3 -m uvicorn main:app --reload --port 8000 >> "$SCRIPT_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

echo "==> Starting React frontend on port 5173..."
cd "$SCRIPT_DIR/frontend"
npm run dev >> "$SCRIPT_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

echo "$BACKEND_PID $FRONTEND_PID" > "$PID_FILE"

echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  Run ./stop.sh in another terminal to terminate."
echo ""
echo "==> Live logs (Ctrl+C stops log view, servers keep running)..."
echo ""

sleep 1
tail -f "$SCRIPT_DIR/backend.log" "$SCRIPT_DIR/frontend.log"
