#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

touch "$SCRIPT_DIR/backend.log" "$SCRIPT_DIR/frontend.log"

echo "==> Tailing backend and frontend logs (Ctrl+C to stop)..."
echo ""

tail -f "$SCRIPT_DIR/backend.log" "$SCRIPT_DIR/frontend.log"
