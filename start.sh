#!/bin/bash

cd "$(dirname "$0")"

mkdir -p logs

echo "Starting Docker containers (postgres + redis + razorpay-mcp)..."
docker compose up -d

echo "Waiting for postgres to be ready..."
sleep 3

echo "Starting Merchant Server - Python (Port 8080)..."
cd merchant-server-py
if [ ! -d "venv" ]; then
  echo "  Creating virtual environment..."
  python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt -q
python3 -m uvicorn main:app --host 0.0.0.0 --port 8080 > ../logs/merchant-server.log 2>&1 &
deactivate
cd ..

echo "Starting AI Agent (Port 8001)..."
cd ai-agent
source venv/bin/activate 2>/dev/null || true
python3 -m uvicorn main:app --port 8001 > ../logs/ai-agent.log 2>&1 &
cd ..

echo "Starting Dashboard (Port 3000)..."
cd dashboard
npm run dev > ../logs/dashboard.log 2>&1 &
cd ..

echo ""
echo "All services started."
echo "  Merchant Server : http://localhost:8080/health"
echo "  AI Agent        : http://localhost:8001"
echo "  Dashboard       : http://localhost:3000"
echo ""
echo "Logs:"
echo "  logs/merchant-server.log"
echo "  logs/ai-agent.log"
echo "  logs/dashboard.log"
echo ""
echo "Run ./stop.sh to stop everything."