#!/bin/bash

cd "$(dirname "$0")"

echo "Stopping Dashboard (port 3000)..."
pkill -f "next-server" 2>/dev/null || true
pkill -f "next dev"    2>/dev/null || true
echo "  Done."

echo "Stopping AI Agent (port 8001)..."
AGENT_PID=$(lsof -t -i:8001 2>/dev/null)
if [ -n "$AGENT_PID" ]; then
  kill -9 $AGENT_PID 2>/dev/null
  echo "  Stopped (PID: $AGENT_PID)."
else
  echo "  Not running."
fi

echo "Stopping Merchant Server (port 8080)..."
MERCHANT_PID=$(lsof -t -i:8080 2>/dev/null)
if [ -n "$MERCHANT_PID" ]; then
  kill -9 $MERCHANT_PID 2>/dev/null
  echo "  Stopped (PID: $MERCHANT_PID)."
else
  echo "  Not running."
fi

echo "Stopping Docker containers..."
docker compose down
echo "  Done."

echo ""
echo "All services stopped."