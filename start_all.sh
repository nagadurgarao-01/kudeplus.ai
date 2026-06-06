#!/bin/bash
echo "============================================="
echo "   🚀 Starting KubePulse AI Pipeline 🚀      "
echo "============================================="

# 1. Start Minikube & Redis
echo "[1/4] Starting Minikube Cluster & Redis..."
minikube start --cpus=4 --memory=4096 --driver=docker
docker start redis

# 2. Establish Port Forwards in background
echo "[2/4] Connecting Port Forwards (Grafana & Prometheus)..."
kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring > /dev/null 2>&1 &
kubectl port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090 -n monitoring > /dev/null 2>&1 &

# Wait for connections to establish
sleep 5

# 3. Activate Virtual Environment & Start Python Pipeline
echo "[3/4] Launching Normalizer, AI Workers, and NLP Engine..."
source venv/bin/activate
python3 collectors/normalizer.py > normalizer.log 2>&1 &
python3 -m agents.cpu_worker > cpu_worker.log 2>&1 &
python3 -m agents.memory_worker > memory_worker.log 2>&1 &
python3 -m agents.storage_worker > storage_worker.log 2>&1 &
python3 -m agents.log_worker > log_worker.log 2>&1 &
python3 -m correlation.correlation_processor > correlation.log 2>&1 &
python3 -m nlp.incident_intelligence > nlp.log 2>&1 &

echo "[4/4] Pipeline launched successfully!"
echo "---------------------------------------------"
echo "📝 Logs are being saved to: *.log files"
echo "🔍 To see active background jobs, run: ps aux | grep python3"
echo "============================================="
