#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.pids"

if [ ! -f "$PID_FILE" ]; then
  echo "No .pids file found — killing by port as fallback..."
  lsof -ti:8000 | xargs kill -9 2>/dev/null && echo "  Killed backend (port 8000)" || echo "  Nothing on port 8000"
  lsof -ti:5173 | xargs kill -9 2>/dev/null && echo "  Killed frontend (port 5173)" || echo "  Nothing on port 5173"
  exit 0
fi

read -r BACKEND_PID FRONTEND_PID < "$PID_FILE"

kill "$BACKEND_PID" 2>/dev/null && echo "Stopped backend (PID $BACKEND_PID)" || echo "Backend already stopped"
kill "$FRONTEND_PID" 2>/dev/null && echo "Stopped frontend (PID $FRONTEND_PID)" || echo "Frontend already stopped"

rm -f "$PID_FILE"
echo "Done."
