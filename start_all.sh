#!/bin/bash
echo "============================================="
echo "   🚀 Starting KubePulse AI Pipeline 🚀      "
echo "============================================="

# 1. Start Minikube & Redis
echo "[1/4] Checking Minikube Cluster & Redis..."
if ! minikube status 2>/dev/null | grep -q "Running"; then
    echo "Starting Minikube..."
    minikube start --cpus=4 --memory=3072 --driver=docker
else
    echo "Minikube is already running."
fi
docker start redis 2>/dev/null || docker run -d --name redis -p 6379:6379 redis:7-alpine

# 2. Establish Port Forwards in background
echo "[2/4] Connecting Port Forwards (Grafana, Prometheus & Loki)..."
nohup kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring > /dev/null 2>&1 &
nohup kubectl port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090 -n monitoring > /dev/null 2>&1 &
nohup kubectl port-forward svc/loki 3100:3100 -n monitoring > /dev/null 2>&1 &

# Wait for connections to establish
sleep 5

# 3. Detect Python Environment & Start Pipeline
echo "[3/4] Launching Normalizer, AI Workers, Correlation, DB Writer, NLP, and API..."
if [ -f ".venv/bin/python" ]; then
    PY=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PY="venv/bin/python"
else
    PY="python3"
fi

nohup $PY collectors/normalizer.py > normalizer.log 2>&1 &
nohup $PY -m agents.cpu_worker > cpu_worker.log 2>&1 &
nohup $PY -m agents.memory_worker > memory_worker.log 2>&1 &
nohup $PY -m agents.storage_worker > storage_worker.log 2>&1 &
nohup $PY -m agents.log_worker > log_worker.log 2>&1 &
nohup $PY -m correlation.correlation_processor > correlation.log 2>&1 &
nohup $PY -m correlation.db_writer > db_writer.log 2>&1 &
nohup $PY -m nlp.incident_intelligence > nlp.log 2>&1 &
nohup $PY -m uvicorn api.main:app --host 0.0.0.0 --port 8000 > api.log 2>&1 &

disown -a 2>/dev/null || true

echo "[4/4] Pipeline & API launched successfully!"
echo "---------------------------------------------"
echo "🌐 API Server: http://localhost:8000"
echo "📝 Logs are being saved to: *.log files"
echo "🔍 To see active background jobs, run: ps aux | grep python3"
echo "============================================="
