#!/bin/bash
echo '=== KubePulse AI — Chaos Injection Demo ==='
echo '[1/3] Injecting CPU spike...'
kubectl run cpu-chaos --image=polinux/stress --restart=Never \
  -- stress --cpu 4 --timeout 60
sleep 20

echo '[2/3] Injecting memory leak...'
kubectl run mem-chaos --image=polinux/stress --restart=Never \
  -- stress --vm 2 --vm-bytes 256M --timeout 60
sleep 20

echo '[3/3] Injecting disk I/O stress...'
kubectl run disk-chaos --image=polinux/stress --restart=Never \
  -- stress --io 4 --timeout 60
sleep 20

echo '=== Check your dashboard: http://localhost:3001 ==='
echo '=== Check alerts: curl http://localhost:8000/api/incidents ==='
